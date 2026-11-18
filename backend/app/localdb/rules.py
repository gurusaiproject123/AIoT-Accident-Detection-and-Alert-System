"""Transactional replacements for the application's PostgreSQL RPCs/triggers.

Database records, not browser state, decide permissions and transitions.
All helpers here operate on the caller's single MySQL transaction.
"""
import hashlib
import hmac
import json
import math
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from app.localdb.storage import SCHEMA, decode, encode, error, execute, get, insert, now, update


def timestamp(value):
    if isinstance(value,datetime):
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value
    return datetime.fromisoformat(value.replace('Z','+00:00')) if value else None


def required(conn, table, value, lock=True):
    row = get(conn,table,'id',str(value),lock)
    if not row: error('P0002',f'{table} record not found.')
    return row


def actor(conn, value, role='superuser'):
    row = required(conn,'profiles',value)
    if row['status']!='active' or row['role']!=role:
        error('42501','Operation not permitted.')
    if role=='hospital_staff' and not row['hospital_id']:
        error('42501','Hospital assignment required.')
    return row


def setting(conn, key, fallback):
    row=get(conn,'system_settings','key',key)
    value=row['value'] if row else fallback
    return int(value) if isinstance(value,(float,int,str)) else fallback


def event(conn, incident, kind, message, hospital=None, user=None):
    insert(conn,'incident_events',{'incident_id':incident['id'],'event_type':kind,'message':message,
        'hospital_id':hospital,'actor_id':user['id'] if user else None,
        'actor_label':user['full_name'] if user else 'System','metadata':{}})


def audit(conn, user, category, action, target, detail=''):
    insert(conn,'audit_logs',{'actor_id':user['id'] if user else None,
        'actor_label':user['full_name'] if user else 'System','actor_role':user['role'] if user else 'system',
        'category':category if category in ('incident','hospital','user','device','system') else 'system','action':action,'target_type':category,'target_id':str(target),
        'target_label':str(target),'detail':detail,'metadata':{}})


def device(conn, params):
    row=required(conn,'devices',params['p_device_id'])
    if not hmac.compare_digest(row.get('secret_hash') or '',params.get('p_secret_hash') or ''):
        error('28000','Invalid device credential.')
    if not row['is_active']: error('42501','Device inactive.')
    return row


def heartbeat(conn,p):
    row=device(conn,p)
    if row['vehicle_id']!=p.get('p_vehicle_id'): error('23514','Vehicle binding changed.')
    row=update(conn,'devices',{'last_seen_at':now(),'status':'online',
        'firmware_version':p.get('p_firmware_version') or row['firmware_version']},'id',row['id'])
    return {k:row[k] for k in ('id','device_code','vehicle_id','status','last_seen_at','firmware_version')} | {'device_id':row['id']}


def telemetry(conn,p):
    row=device(conn,p)
    from app.schemas.telemetry import TelemetryPacket
    payload=TelemetryPacket.model_validate(p['p_payload']).model_dump(mode='json')
    if row['vehicle_id']!=payload['vehicle_id']: error('23514','Vehicle binding changed.')
    old=execute(conn,'SELECT * FROM telemetry_packets WHERE device_id=%s AND boot_id=%s AND sequence_number=%s FOR UPDATE',
        (row['id'],payload['boot_id'],payload['sequence_number']))
    if old:
        packet=decode('telemetry_packets',old[0])
        if packet['payload_sha256']!=p['p_payload_sha256']: error('23505','Packet content changed on retry.')
        return dict(packet_id=packet['id'],duplicate=True,sample_count=packet['sample_count'],samples_saved=0,received_at=packet['received_at'])
    fields={k:payload[k] for k in ('boot_id','sequence_number','sample_count','sampling_hz','acceleration_unit','rotation_unit','recorded_start','recorded_end')}
    packet=insert(conn,'telemetry_packets',fields | {'device_id':row['id'],'payload_sha256':p['p_payload_sha256']})
    gps=payload.get('gps')
    cols=['device_id','packet_id','sample_index','recorded_at','received_at','accel_x','accel_y','accel_z','gyro_x','gyro_y','gyro_z','latitude','longitude','gps_fix','speed_kmh']
    values=[]
    for index,sample in enumerate(payload['samples']):
        values.append([row['id'],packet['id'],index,encode(sample['recorded_at'],{'format':'timestamp with time zone'}),
            encode(now()),*[sample[k] for k in ('accel_x','accel_y','accel_z','gyro_x','gyro_y','gyro_z')],
            gps['latitude'] if gps else None,gps['longitude'] if gps else None,bool(gps),gps.get('speed_kmh') if gps else None])
    with conn.cursor() as cursor:
        cursor.executemany('INSERT INTO sensor_readings ('+','.join(cols)+') VALUES ('+','.join(['%s']*len(cols))+')',values)
    changes={'last_seen_at':now(),'status':'online'}
    if gps and (not row['last_location_at'] or timestamp(gps['recorded_at'])>=timestamp(row['last_location_at'])):
        changes.update(last_latitude=gps['latitude'],last_longitude=gps['longitude'],last_location_at=gps['recorded_at'],gps_status='fix')
    update(conn,'devices',changes,'id',row['id'])
    return dict(packet_id=packet['id'],duplicate=False,sample_count=payload['sample_count'],samples_saved=payload['sample_count'],received_at=packet['received_at'])


def create_incident(conn,p):
    packet=required(conn,'telemetry_packets',p['p_packet_id'])
    dev=required(conn,'devices',packet['device_id'])
    predictions=execute(conn,'SELECT * FROM model_predictions WHERE packet_id=%s FOR UPDATE',(packet['id'],))
    if not predictions: error('P0002','Prediction not found.')
    prediction=decode('model_predictions',predictions[0])
    if not prediction['is_suspected_accident']: return None
    existing=execute(conn,'SELECT id FROM incidents WHERE prediction_id=%s OR (device_id=%s AND status=%s AND cancellation_deadline>UTC_TIMESTAMP(6)) ORDER BY detected_at DESC LIMIT 1 FOR UPDATE',
        (prediction['id'],dev['id'],'cancellation_window'))
    if existing: return existing[0]['id']
    location=execute(conn,'SELECT latitude,longitude,recorded_at FROM sensor_readings WHERE packet_id=%s AND gps_fix=TRUE ORDER BY sample_index DESC LIMIT 1',(packet['id'],))
    seconds=setting(conn,'cancellation_window_seconds',30)
    values={'device_id':dev['id'],'vehicle_id':dev['vehicle_id'],'prediction_id':prediction['id'],
        'detected_at':now(),'occurred_at':packet['recorded_end'],'occurred_at_estimated':True,
        'model_score':prediction['score'],'impact_summary':'accident detected from uploaded IMU window',
        'cancellation_window_seconds':seconds,'cancellation_deadline':now()+timedelta(seconds=seconds)}
    if location:
        values.update(latitude=location[0]['latitude'],longitude=location[0]['longitude'],location_recorded_at=location[0]['recorded_at'])
    incident=insert(conn,'incidents',values)
    event(conn,incident,'detected','Suspected accident detected from uploaded sensor window.')
    event(conn,incident,'window_started',f'{seconds} second cancellation window started.')
    return incident['id']


def cancel(conn,p):
    dev=device(conn,p)
    inc=required(conn,'incidents',p['p_incident_id'])
    if inc['device_id']!=dev['id']: error('P0002','Incident not assigned to this device.')
    if inc['status']=='cancelled': return inc
    if inc['status']!='cancellation_window' or now()>=timestamp(inc['cancellation_deadline']):
        error('23514','Cancellation window closed.')
    new=update(conn,'incidents',{'status':'cancelled','cancellation_outcome':'cancelled','cancellation_resolved_at':now(),
        'cancelled_by_label':'Device push button','cancel_reason':'Physical cancellation requested'},'id',inc['id'])
    after_update(conn,'incidents',inc,new)
    return new


def distance(a,b):
    lat1,lat2=math.radians(a['latitude']),math.radians(b['latitude'])
    dlat=lat2-lat1; dlon=math.radians(b['longitude']-a['longitude'])
    value=math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
    return 6371*2*math.asin(math.sqrt(min(1,max(0,value))))


def route(conn,inc,reason='nearest',hospital_id=None,user=None):
    if inc['status'] in ('cancelled','closed','accepted'): error('23514','Incident cannot be routed.')
    if inc['status']=='cancellation_window' and now()<timestamp(inc['cancellation_deadline']): error('23514','Cancellation window has not ended.')
    previous=execute(conn,'SELECT * FROM incident_notifications WHERE incident_id=%s ORDER BY escalation_level FOR UPDATE',(inc['id'],))
    if any(n['status']=='accepted' for n in previous): error('23514','A hospital has accepted this incident.')
    active=next((n for n in previous if n['status'] in ('notified','acknowledged')),None)
    if active and hospital_id is None: return decode('incident_notifications',active)
    if hospital_id:
        hospital=required(conn,'hospitals',hospital_id)
        if not hospital['is_active'] or any(n['hospital_id']==hospital['id'] for n in previous): error('23514','Hospital inactive or already notified.')
    else:
        tried={n['hospital_id'] for n in previous}
        eligible=[h for h in execute(conn,'SELECT * FROM hospitals WHERE is_active=TRUE') if h['id'] not in tried and h['latitude'] is not None and h['longitude'] is not None]
        if inc['latitude'] is None or inc['longitude'] is None: eligible=[]
        if len(previous)>=setting(conn,'max_escalation_level',3): eligible=[]
        hospital=min(eligible,key=lambda h:distance(inc,h)) if eligible else None
    if inc['status']=='cancellation_window':
        inc=update(conn,'incidents',{'cancellation_outcome':'expired','cancellation_resolved_at':now()},'id',inc['id'])
        event(conn,inc,'window_expired','Cancellation window expired without cancellation.')
    if not hospital:
        update(conn,'incidents',{'status':'escalated'},'id',inc['id'])
        event(conn,inc,'escalated','No eligible untried hospital; administrator action required.')
        return None
    if active:
        update(conn,'incident_notifications',{'status':'withdrawn'},'id',active['id'])
    notification=insert(conn,'incident_notifications',{'incident_id':inc['id'],'hospital_id':hospital['id'],
        'escalation_level':max([n['escalation_level'] for n in previous],default=0)+1,
        'routing_reason':reason,'routed_by':user['id'] if user else None,
        'distance_km':distance(inc,hospital) if all(x is not None for x in (inc['latitude'],inc['longitude'],hospital['latitude'],hospital['longitude'])) else None,
        'response_deadline':now()+timedelta(seconds=setting(conn,'hospital_ack_timeout_seconds',180))})
    update(conn,'incidents',{'status':'escalated' if previous else 'notified'},'id',inc['id'])
    event(conn,inc,'notified',f"Notification assigned to {hospital['name']}.",hospital['id'],user)
    audit(conn,user,'incident','Hospital notified',inc['id'],hospital['name'])
    return notification


def deadlines(conn):
    counts={'windows_expired':0,'notifications_timed_out':0,'escalations':0,'needs_superuser':0}
    for raw in execute(conn,"SELECT * FROM incidents WHERE status='cancellation_window' AND cancellation_deadline<=UTC_TIMESTAMP(6) ORDER BY id FOR UPDATE"):
        result=route(conn,decode('incidents',raw))
        counts['windows_expired']+=1
        if not result: counts['needs_superuser']+=1
    due=execute(conn,"SELECT incident_id,id FROM incident_notifications WHERE status='notified' AND response_deadline<=UTC_TIMESTAMP(6) ORDER BY incident_id")
    for row in due:
        inc=required(conn,'incidents',row['incident_id'])
        notification=required(conn,'incident_notifications',row['id'])
        if notification['status']!='notified': continue
        if inc['status'] in ('cancelled','closed','accepted'):
            update(conn,'incident_notifications',{'status':'withdrawn'},'id',row['id']); continue
        update(conn,'incident_notifications',{'status':'timed_out'},'id',row['id'])
        event(conn,inc,'timed_out','Hospital acknowledgment deadline expired.',notification['hospital_id'])
        counts['notifications_timed_out']+=1
        result=route(conn,inc,'timeout')
        counts['escalations']+=1
        if not result: counts['needs_superuser']+=1
    return counts


def hospital_response(conn,p,action):
    user=actor(conn,p['p_actor_id'],'hospital_staff')
    initial=required(conn,'incident_notifications',p['p_notification_id'],lock=False)
    inc=required(conn,'incidents',initial['incident_id'])
    notification=required(conn,'incident_notifications',initial['id'])
    if notification['hospital_id']!=user['hospital_id']: error('42501','Notification belongs to another hospital.')
    if inc['status'] in ('closed','cancelled'): error('23514','Incident resolved.')
    target={'acknowledge':'acknowledged','accept':'accepted','decline':'declined'}[action]
    if notification['status']==target: return notification
    allowed=('notified',) if action=='acknowledge' else ('acknowledged',) if action=='accept' else ('notified','acknowledged')
    if notification['status'] not in allowed: error('23514','Notification state does not permit this response.')
    if notification['status']=='notified' and notification['response_deadline'] and now()>=timestamp(notification['response_deadline']): error('23514','Notification timed out.')
    changes={'status':target}
    if action=='acknowledge': changes.update(acknowledged_at=now(),acknowledged_by=user['id'],response_deadline=None)
    else: changes.update(responded_at=now(),responded_by=user['id'])
    if action=='decline':
        reason=(p.get('p_reason') or '').strip()
        if not reason: error('22023','Decline reason is required.')
        changes['decline_reason']=reason
    if action=='accept':
        others=execute(conn,"SELECT id FROM incident_notifications WHERE incident_id=%s AND status='accepted' FOR UPDATE",(inc['id'],))
        if others: error('23514','Another hospital already accepted.')
        execute(conn,"UPDATE incident_notifications SET status='withdrawn',updated_at=UTC_TIMESTAMP(6) WHERE incident_id=%s AND id<>%s AND status IN ('notified','acknowledged')",(inc['id'],notification['id']))
    notification=update(conn,'incident_notifications',changes,'id',notification['id'])
    event(conn,inc,target,f'Hospital response: {target}.',notification['hospital_id'],user)
    audit(conn,user,'incident','Hospital '+target,inc['id'])
    if action=='decline': route(conn,inc,'declined')
    else: update(conn,'incidents',{'status':target},'id',inc['id'])
    return notification


def after_update(conn,table,old,new):
    if table!='incidents' or old['status']==new['status']: return
    state=new['status']
    if state=='cancelled':
        if old['status']!='cancellation_window' or now()>=timestamp(old['cancellation_deadline']): error('23514','Cancellation window expired.')
    if state=='closed' and old['status'] in ('cancelled','closed','cancellation_window'): error('23514','Incident cannot be closed from its current state.')
    if state in ('cancelled','closed'):
        execute(conn,"UPDATE incident_notifications SET status='withdrawn',updated_at=UTC_TIMESTAMP(6) WHERE incident_id=%s AND status IN ('notified','acknowledged')",(new['id'],))
        user=get(conn,'profiles','id',new.get('closed_by') or new.get('cancelled_by')) if (new.get('closed_by') or new.get('cancelled_by')) else None
        event(conn,new,state,f'Incident {state}.',user=user)
        audit(conn,user,'incident','Incident '+state,new['id'])


def after_insert(conn,table,row):
    if table in ('incident_notes','false_alarm_reports'):
        inc=required(conn,'incidents',row['incident_id'])
        uid=row.get('author_id') or row.get('reported_by')
        user=get(conn,'profiles','id',uid) if uid else None
        kind='note' if table=='incident_notes' else 'false_alarm_reported'
        event(conn,inc,kind,row.get('body') or row.get('reason'),row.get('hospital_id'),user)
        audit(conn,user,'incident','Added '+kind,inc['id'])
    elif table=='incidents':
        event(conn,row,'detected','Suspected incident recorded.')
        event(conn,row,'window_started','Cancellation window started.')


def dispatch(conn,name,p):
    if name=='device_record_heartbeat': return heartbeat(conn,p)
    if name=='device_ingest_telemetry': return telemetry(conn,p)
    if name=='device_cancel_incident': return cancel(conn,p)
    if name=='create_incident_from_prediction': return create_incident(conn,p)
    if name=='process_incident_deadlines': return deadlines(conn)
    if name=='hospital_acknowledge_notification': return hospital_response(conn,p,'acknowledge')
    if name=='hospital_accept_notification': return hospital_response(conn,p,'accept')
    if name=='hospital_decline_notification': return hospital_response(conn,p,'decline')
    if name=='route_incident_manually':
        user=actor(conn,p['p_actor_id'])
        inc=required(conn,'incidents',p['p_incident_id'])
        return route(conn,inc,'manual',p['p_hospital_id'],user)
    from app.localdb.registry import dispatch_registry
    return dispatch_registry(conn,name,p)
