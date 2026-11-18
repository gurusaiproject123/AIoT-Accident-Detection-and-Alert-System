"""Real MySQL integration tests, isolated from imported records.

Run with MYSQL_TESTS=1 while WAMP MySQL is running. Each test creates and drops
only its own aiot_test_<uuid> schema; application/source databases are untouched.
"""
import asyncio
import os
from datetime import timedelta
from uuid import uuid4

import pytest
from fastapi import HTTPException
from postgrest.exceptions import APIError
from app.core.config import get_settings
from app.localdb import auth
from app.localdb.storage import connect,execute,insert,update,now,transaction,MySQLDatabase
from app.localdb.rules import dispatch
from scripts.prepare_mysql import statements
from scripts.mysql_constraints import apply

pytestmark=pytest.mark.skipif(os.getenv('MYSQL_TESTS')!='1',reason='Requires isolated WAMP MySQL tests')


@pytest.fixture
def database(monkeypatch):
    name='aiot_test_'+uuid4().hex
    settings=get_settings()
    with connect(database='mysql',user='root',password='') as conn:
        execute(conn,'CREATE DATABASE `'+name+'` CHARACTER SET utf8mb4')
    monkeypatch.setattr(settings,'mysql_database',name)
    monkeypatch.setattr(settings,'mysql_user','root')
    from pydantic import SecretStr
    monkeypatch.setattr(settings,'mysql_password',SecretStr(''))
    monkeypatch.setattr(settings,'database_backend','mysql')
    try:
        with connect() as conn:
            for sql in statements(): execute(conn,sql)
            apply(conn)
        yield MySQLDatabase()
    finally:
        assert name.startswith('aiot_test_') and len(name)==42
        with connect(database='mysql',user='root',password='') as conn:
            execute(conn,'DROP DATABASE `'+name+'`')


def seed():
    with transaction() as conn:
        hospital=insert(conn,'hospitals',{'name':'Test hospital','city':'Test','latitude':-17.29,'longitude':31.34})
        admin=insert(conn,'profiles',{'id':str(uuid4()),'full_name':'Admin','email':'admin@example.com','role':'superuser'})
        staff=insert(conn,'profiles',{'id':str(uuid4()),'full_name':'Staff','email':'staff@example.com','role':'hospital_staff','hospital_id':hospital['id']})
        owner=insert(conn,'vehicle_owners',{'full_name':'Owner'})
        car=insert(conn,'vehicles',{'registration':'TEST-1','owner_id':owner['id']})
        device=insert(conn,'devices',{'device_code':'TEST-DEVICE','vehicle_id':car['id'],'secret_hash':'a'*64})
        return hospital,admin,staff,car,device


def packet(car):
    start=now()
    samples=[{'recorded_at':(start+timedelta(milliseconds=10*i)).isoformat(),'accel_x':0,'accel_y':0,'accel_z':9.8,'gyro_x':0,'gyro_y':0,'gyro_z':0} for i in range(2)]
    return {'schema_version':1,'vehicle_id':car['id'],'boot_id':str(uuid4()),'sequence_number':1,
        'sample_count':2,'sampling_hz':100,'acceleration_unit':'m/s^2','rotation_unit':'deg/s',
        'recorded_start':samples[0]['recorded_at'],'recorded_end':samples[-1]['recorded_at'],
        'samples':samples,'gps':{'latitude':-17.29,'longitude':31.34,'recorded_at':start.isoformat()}}


def incident(device,car):
    with transaction() as conn:
        return insert(conn,'incidents',{'device_id':device['id'],'vehicle_id':car['id'],'latitude':-17.29,
            'longitude':31.34,'cancellation_deadline':now()-timedelta(seconds=1)})


def test_packet_retry_and_changed_payload(database):
    h,a,s,c,d=seed()
    params={'p_device_id':d['id'],'p_secret_hash':'a'*64,'p_payload':packet(c),'p_payload_sha256':'b'*64}
    first=database.rpc('device_ingest_telemetry',params).execute().data
    second=database.rpc('device_ingest_telemetry',params).execute().data
    assert first['packet_id']==second['packet_id'] and second['duplicate']
    assert database.table('sensor_readings').select('*',count='exact').execute().count==2
    with pytest.raises(APIError) as exc:
        database.rpc('device_ingest_telemetry',params|{'p_payload_sha256':'c'*64}).execute()
    assert exc.value.code=='23505'


def test_deadline_acknowledgment_acceptance(database):
    h,a,s,c,d=seed(); i=incident(d,c)
    assert database.rpc('process_incident_deadlines',{}).execute().data['windows_expired']==1
    assert database.rpc('process_incident_deadlines',{}).execute().data['windows_expired']==0
    notification=database.table('incident_notifications').select('*').execute().data[0]
    args={'p_actor_id':s['id'],'p_notification_id':notification['id']}
    database.rpc('hospital_acknowledge_notification',args).execute()
    database.rpc('hospital_acknowledge_notification',args).execute()
    result=database.rpc('hospital_accept_notification',args).execute().data
    assert result['status']=='accepted'
    assert database.table('incidents').select('*').eq('id',i['id']).execute().data[0]['status']=='accepted'


def test_hospital_alert_includes_registered_details_only_for_assigned_hospital(database):
    from app.core.auth import AuthenticatedUser
    from app.services.hospital_inbox import HospitalInbox
    h,a,s,c,d=seed(); i=incident(d,c)
    database.rpc('process_incident_deadlines',{}).execute()
    notification=database.table('incident_notifications').select('*').execute().data[0]
    caller=AuthenticatedUser(id=s['id'],full_name='Staff',role='hospital_staff',status='active',hospital_id=h['id'])
    inbox=HospitalInbox()
    alert=inbox.get_authorized_alert(notification['id'],caller)
    assert alert.incident.device_code=='TEST-DEVICE'
    assert alert.incident.vehicle.registration=='TEST-1'
    assert alert.incident.owner.full_name=='Owner'
    assert inbox.list_hospital_alerts(caller)[0].incident.owner.full_name=='Owner'
    assert 'secret_hash' not in alert.model_dump_json()
    assert 'user_id' not in alert.incident.owner.model_dump()
    outsider=AuthenticatedUser(id=uuid4(),full_name='Other',role='hospital_staff',status='active',hospital_id=uuid4())
    assert inbox.list_hospital_alerts(outsider)==[]
    with pytest.raises(HTTPException) as error:
        inbox.get_authorized_alert(notification['id'],outsider)
    assert error.value.status_code==404
    with transaction() as conn:
        update(conn,'incidents',{'vehicle_id':None},'id',i['id'])
    unlinked=inbox.get_authorized_alert(notification['id'],caller)
    assert unlinked.incident.vehicle is None and unlinked.incident.owner is None


def test_cancel_before_deadline_and_no_routing(database):
    h,a,s,c,d=seed(); i=incident(d,c)
    with transaction() as conn: update(conn,'incidents',{'cancellation_deadline':now()+timedelta(seconds=30)},'id',i['id'])
    result=database.rpc('device_cancel_incident',{'p_device_id':d['id'],'p_secret_hash':'a'*64,'p_incident_id':i['id']}).execute().data
    assert result['status']=='cancelled'
    database.rpc('process_incident_deadlines',{}).execute()
    assert not database.table('incident_notifications').select('*').execute().data


def test_local_password_sessions_and_assignment(database):
    h,a,s,c,d=seed()
    with transaction() as conn:
        execute(conn,'INSERT INTO local_credentials(profile_id,password_hash,reset_required) VALUES (%s,%s,TRUE)',(a['id'],auth.hash_password('Original-pass-123')))
    session=auth.sign_in(a['email'],'Original-pass-123')
    with pytest.raises(HTTPException) as exc: auth.LocalAuth().get_user(session['access_token'])
    assert exc.value.status_code==403
    auth.change_password(session['access_token'],'Original-pass-123','Replacement-pass-456')
    assert auth.LocalAuth().get_user(session['access_token']).user.id==a['id']
    auth.logout(session['access_token'])
    with pytest.raises(HTTPException): auth.verify_token(session['access_token'])
    with pytest.raises(HTTPException): auth.sign_in(a['email'],'Original-pass-123')


def test_hospital_isolation_and_manual_routing(database):
    h,a,s,c,d=seed(); i=incident(d,c)
    database.rpc('process_incident_deadlines',{}).execute()
    with transaction() as conn:
        other=insert(conn,'hospitals',{'name':'Other','city':'Test','latitude':-17.3,'longitude':31.4})
        outsider=insert(conn,'profiles',{'id':str(uuid4()),'full_name':'Other Staff','email':'other@example.com','role':'hospital_staff','hospital_id':other['id']})
    n=database.table('incident_notifications').select('*').execute().data[0]
    with pytest.raises(APIError) as exc:
        database.rpc('hospital_acknowledge_notification',{'p_actor_id':outsider['id'],'p_notification_id':n['id']}).execute()
    assert exc.value.code=='42501'
    new=database.rpc('route_incident_manually',{'p_actor_id':a['id'],'p_incident_id':i['id'],'p_hospital_id':other['id']}).execute().data
    assert new['hospital_id']==other['id']
    assert database.table('incident_notifications').select('*').eq('id',n['id']).execute().data[0]['status']=='withdrawn'


def test_http_login_admin_inbox_response_and_closure(database):
    import httpx
    from app.main import app
    h,a,s,c,d=seed(); i=incident(d,c)
    with transaction() as conn:
        for user in (a,s):
            execute(conn,'INSERT INTO local_credentials(profile_id,password_hash,reset_required) VALUES (%s,%s,FALSE)',(user['id'],auth.hash_password('Test-password-123')))
    database.rpc('process_incident_deadlines',{}).execute()
    async def run():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://test') as client:
            async def login(user):
                response=await client.post('/api/auth/login',json={'email':user['email'],'password':'Test-password-123'})
                assert response.status_code==200,response.text
                return {'Authorization':'Bearer '+response.json()['session']['access_token']}
            admin=await login(a); staff=await login(s)
            assert (await client.get('/api/auth/me',headers=admin)).status_code==200
            for path in ('/api/admin/overview','/api/admin/devices','/api/admin/vehicles','/api/admin/owners','/api/admin/hospitals','/api/admin/users',f"/api/admin/incidents/{i['id']}",f"/api/incidents/{i['id']}/timeline"):
                response=await client.get(path,headers=admin)
                assert response.status_code==200,(path,response.text)
            response=await client.get('/api/hospital/alerts',headers=staff)
            assert response.status_code==200,response.text
            nid=response.json()[0]['id']
            for action in ('acknowledge','accept'):
                response=await client.post(f'/api/alerts/{nid}/{action}',headers=staff)
                assert response.status_code==200,response.text
            response=await client.post(f"/api/admin/incidents/{i['id']}/close",headers=admin,json={'closing_note':'Integration test'})
            assert response.status_code==200,response.text
            assert response.json()['status']=='closed'
            created=await client.post('/api/admin/users',headers=admin,json={'email':'newstaff@example.com','full_name':'New Staff','password':'Staff-password-123','role':'hospital_staff','hospital_id':h['id']})
            assert created.status_code==201,created.text
            assert created.json()['hospital_id']==h['id']
    asyncio.run(run())


def test_prediction_creates_one_incident_and_decline_escalates(database):
    h,a,s,c,d=seed()
    params={'p_device_id':d['id'],'p_secret_hash':'a'*64,'p_payload':packet(c),'p_payload_sha256':'b'*64}
    uploaded=database.rpc('device_ingest_telemetry',params).execute().data
    database.table('model_predictions').insert({'packet_id':uploaded['packet_id'],'device_id':d['id'],
        'window_start':params['p_payload']['recorded_start'],'window_end':params['p_payload']['recorded_end'],
        'model_version':'test','score':0.8,'threshold':0.55,'is_suspected_accident':True}).execute()
    args={'p_packet_id':uploaded['packet_id']}
    iid=database.rpc('create_incident_from_prediction',args).execute().data
    assert database.rpc('create_incident_from_prediction',args).execute().data==iid
    with transaction() as conn:
        update(conn,'incidents',{'cancellation_deadline':now()-timedelta(seconds=1)},'id',iid)
        other=insert(conn,'hospitals',{'name':'Backup','city':'Test','latitude':-17.5,'longitude':31.5})
    database.rpc('process_incident_deadlines',{}).execute()
    notification=database.table('incident_notifications').select('*').execute().data[0]
    database.rpc('hospital_decline_notification',{'p_actor_id':s['id'],'p_notification_id':notification['id'],'p_reason':'No capacity'}).execute()
    alerts=database.table('incident_notifications').select('*').order('escalation_level').execute().data
    assert [n['status'] for n in alerts]==['declined','notified']
    assert alerts[-1]['hospital_id']==other['id']


def test_registry_constraints_and_owner_login(database):
    from types import SimpleNamespace
    from app.schemas.user import UserCreate
    from app.localdb.registry import create_account
    h,a,s,c,d=seed()
    owner=database.rpc('admin_register_owner',{'p_actor_id':a['id'],'p_full_name':'Second owner','p_phone':None,'p_email':None}).execute().data
    vehicle=database.rpc('admin_save_vehicle',{'p_actor_id':a['id'],'p_data':{'registration':'SECOND','owner_id':owner['id']}}).execute().data
    with transaction() as conn:
        profile=create_account(conn,SimpleNamespace(id=a['id']),UserCreate(full_name='Second owner',email='owner@example.com',password='Owner-password-123',role='car_owner',owner_id=owner['id']))
    assert profile['owner_id']==owner['id']
    assert auth.sign_in('owner@example.com','Owner-password-123')['user']['id']==profile['id']
    with pytest.raises(APIError) as exc:
        database.rpc('admin_save_vehicle',{'p_actor_id':a['id'],'p_vehicle_id':vehicle['id'],'p_data':{'owner_id':c['owner_id']}}).execute()
    assert exc.value.code=='23514'
    with pytest.raises(APIError):
        database.rpc('admin_save_device',{'p_actor_id':a['id'],'p_data':{'device_code':'DUPLICATE','vehicle_id':c['id']},'p_secret_hash':'d'*64}).execute()
    with pytest.raises(APIError):
        database.rpc('admin_register_hospital',{'p_actor_id':s['id'],'p_data':{'name':'Unauthorized','city':'Test'}}).execute()


def test_concurrent_packet_retries_save_once(database):
    from concurrent.futures import ThreadPoolExecutor
    h,a,s,c,d=seed()
    params={'p_device_id':d['id'],'p_secret_hash':'a'*64,'p_payload':packet(c),'p_payload_sha256':'b'*64}
    with ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(lambda _:database.rpc('device_ingest_telemetry',params).execute().data,range(2)))
    assert len({r['packet_id'] for r in results})==1
    assert sorted(r['duplicate'] for r in results)==[False,True]
    assert database.table('sensor_readings').select('*',count='exact').execute().count==2
