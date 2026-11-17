from uuid import uuid4

from app.localdb.storage import error,execute,get,insert,update,now
from app.localdb.rules import actor,audit,required


def owner_valid(conn,owner_id):
    if owner_id: required(conn,'vehicle_owners',owner_id)


def protect_owner_vehicle(conn,vehicle,new_owner):
    old_owner=vehicle.get('owner_id') if vehicle else None
    if old_owner and old_owner!=new_owner:
        owner=required(conn,'vehicle_owners',old_owner)
        if owner['user_id'] and not execute(conn,'SELECT id FROM vehicles WHERE owner_id=%s AND id<>%s',(old_owner,vehicle['id'])):
            error('23514','A registered owner login must retain at least one vehicle.')


def dispatch_registry(conn,name,p):
    user=actor(conn,p.get('p_actor_id'))
    data=p.get('p_data',{})
    if name=='admin_get_overview':
        queries={
            'total_incidents':'SELECT COUNT(*) n FROM incidents',
            'open_incidents':"SELECT COUNT(*) n FROM incidents WHERE status NOT IN ('cancelled','closed')",
            'pending_alerts':"SELECT COUNT(*) n FROM incident_notifications WHERE status='notified'",
            'online_devices':"SELECT COUNT(*) n FROM devices WHERE is_active=TRUE AND last_seen_at>=UTC_TIMESTAMP(6)-INTERVAL 60 SECOND",
            'total_devices':'SELECT COUNT(*) n FROM devices',
            'total_hospitals':'SELECT COUNT(*) n FROM hospitals',
            'active_hospitals':'SELECT COUNT(*) n FROM hospitals WHERE is_active=TRUE',
        }
        return {key:execute(conn,sql)[0]['n'] for key,sql in queries.items()}
    if name in ('admin_register_hospital','admin_update_hospital'):
        # The route's validated payload already defines the writable fields.
        allowed={'name','city','address','phone','email','latitude','longitude','is_active','notes'}
        if not set(data)<=allowed: error('22023','Unknown hospital field.')
        hid=p.get('p_hospital_id')
        if hid: required(conn,'hospitals',hid)
        row=update(conn,'hospitals',data,'id',hid) if hid else insert(conn,'hospitals',data|{'created_by':user['id']})
        category='hospital'
    elif name in ('admin_register_owner','admin_update_owner'):
        oid=p.get('p_owner_id')
        if oid: required(conn,'vehicle_owners',oid)
        else: data={'full_name':p['p_full_name'],'phone':p.get('p_phone'),'email':p.get('p_email')}
        if not set(data)<={'full_name','phone','email','relationship'}: error('22023','Unknown owner field.')
        row=update(conn,'vehicle_owners',data,'id',oid) if oid else insert(conn,'vehicle_owners',data)
        category='owner'
    elif name=='admin_save_vehicle':
        vid=p.get('p_vehicle_id')
        old=required(conn,'vehicles',vid) if vid else None
        if not set(data)<={'registration','make','model','colour','owner_id'}: error('22023','Unknown vehicle field.')
        owner=data.get('owner_id',old['owner_id'] if old else None)
        owner_valid(conn,owner)
        protect_owner_vehicle(conn,old,owner)
        if old and old['owner_id']!=owner and execute(conn,'SELECT id FROM vehicle_control_sessions WHERE vehicle_id=%s AND ended_at IS NULL AND expires_at>UTC_TIMESTAMP(6)',(vid,)):
            error('23514','End active controller sessions before transfer.')
        row=update(conn,'vehicles',data,'id',vid) if vid else insert(conn,'vehicles',data)
        category='vehicle'
    elif name=='admin_save_device':
        did=p.get('p_device_id')
        old=required(conn,'devices',did) if did else None
        if not set(data)<={'device_code','vehicle_id','label','is_active','firmware_version'}: error('22023','Unknown device field.')
        vid=data.get('vehicle_id',old['vehicle_id'] if old else None)
        if vid:
            required(conn,'vehicles',vid)
            assigned=execute(conn,'SELECT id FROM devices WHERE vehicle_id=%s AND is_active=TRUE',(vid,))
            if data.get('is_active',old['is_active'] if old else True) and any(r['id']!=did for r in assigned): error('23514','Vehicle already has an active device.')
        if p.get('p_secret_hash'): data=data|{'secret_hash':p['p_secret_hash']}
        if not did and not data.get('secret_hash'): error('22023','Device credential required.')
        row=update(conn,'devices',data,'id',did) if did else insert(conn,'devices',data|{'registered_by':user['id']})
        row.pop('secret_hash',None)
        category='device'
    elif name in ('admin_set_user_status','admin_update_user_access'):
        uid=p['p_user_id']; old=required(conn,'profiles',uid)
        if name=='admin_set_user_status': data={'status':p['p_status']}
        if not set(data)<={'status','hospital_id'}: error('22023','Unknown account field.')
        merged=old|data
        if merged['status'] not in ('active','suspended'): error('22023','Invalid account status.')
        if old['role']=='superuser' and (uid==user['id'] and merged['status']!='active'): error('23514','Cannot suspend your own administrator account.')
        if old['role']=='superuser' and merged['status']!='active':
            others=execute(conn,"SELECT id FROM profiles WHERE role='superuser' AND status='active' AND id<>%s FOR UPDATE",(uid,))
            if not others: error('23514','At least one active administrator is required.')
        if old['role']=='hospital_staff':
            if not merged['hospital_id']: error('23514','Hospital assignment required.')
            required(conn,'hospitals',merged['hospital_id'])
        elif merged['hospital_id']: error('23514','Only hospital staff can have hospital assignments.')
        row=update(conn,'profiles',data,'id',uid)
        execute(conn,'DELETE FROM local_sessions WHERE profile_id=%s',(uid,))
        category='user'
    else:
        error('0A000',f'Unimplemented local operation: {name}')
    audit(conn,user,category,name,row['id'])
    return row


def create_account(conn,caller,payload):
    from app.localdb.auth import hash_password
    user=actor(conn,str(caller.id))
    if payload.role=='hospital_staff':
        hospital=required(conn,'hospitals',str(payload.hospital_id))
        if not hospital['is_active']: error('23514','Hospital inactive.')
    else:
        owner=required(conn,'vehicle_owners',str(payload.owner_id))
        if owner['user_id'] or not execute(conn,'SELECT id FROM vehicles WHERE owner_id=%s',(owner['id'],)):
            error('23514','Owner must have a vehicle and no existing login.')
    uid=str(uuid4())
    profile=insert(conn,'profiles',{'id':uid,'full_name':payload.full_name,'email':str(payload.email).lower(),
        'role':payload.role,'hospital_id':str(payload.hospital_id) if payload.hospital_id else None})
    execute(conn,'INSERT INTO local_credentials(profile_id,password_hash,reset_required) VALUES (%s,%s,FALSE)',
        (uid,hash_password(payload.password.get_secret_value())))
    if payload.role=='car_owner': update(conn,'vehicle_owners',{'user_id':uid},'id',str(payload.owner_id))
    audit(conn,user,'user','Created local account',uid)
    return profile|{'owner_id':str(payload.owner_id) if payload.owner_id else None}
