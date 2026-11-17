"""Read-only validation of the imported target using its restricted app account."""
import json
import os
import sys
from pathlib import Path
from uuid import UUID
from dotenv import dotenv_values

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))


def main():
    for key,value in dotenv_values(BACKEND/'migration-private'/'mysql.env').items():
        os.environ[key]=value
    from app.core.config import get_settings
    get_settings.cache_clear()
    from app.core.database import get_supabase_admin
    from app.schemas.auth import CurrentUser
    from app.core.auth import AuthenticatedUser
    from app.schemas.incident import IncidentDetailResponse,IncidentTimelineResponse
    from app.services.incident_service import incident_service
    from app.services.hospital_inbox import hospital_inbox
    from app.localdb.auth import verify_password
    from app.localdb.storage import transaction,execute
    db=get_supabase_admin()
    profiles=db.table('profiles').select('*').execute().data
    admins=[p for p in profiles if p['role']=='superuser' and p['status']=='active']
    if not admins: raise RuntimeError('No active local administrator')
    admin=CurrentUser.model_validate(admins[0]|{'owner_id':None})
    incidents=db.table('incidents').select('id').execute().data
    for record in incidents:
        iid=UUID(record['id'])
        IncidentDetailResponse.model_validate(incident_service.get_incident(iid,admin))
        IncidentTimelineResponse.model_validate(incident_service.get_timeline(iid,admin))
    print(f'{len(incidents)} imported incidents and timelines validated.',flush=True)
    count=0
    for p in profiles:
        if p['role']=='hospital_staff':
            count+=len(hospital_inbox.list_hospital_alerts(AuthenticatedUser.model_validate(p)))
    print(f'Hospital-scoped inbox responses validated ({count} assignments across staff accounts).',flush=True)
    credentials=json.loads((BACKEND/'migration-private'/'temporary-logins.json').read_text())
    with transaction() as conn:
        for entry in credentials:
            rows=execute(conn,'SELECT c.password_hash,c.reset_required FROM local_credentials c JOIN profiles p ON p.id=c.profile_id WHERE p.email=%s',(entry['email'],))
            if len(rows)!=1 or not rows[0]['reset_required'] or not verify_password(entry['temporary_password'],rows[0]['password_hash']):
                raise RuntimeError('Temporary local credential verification failed')
    print(f'{len(credentials)} temporary credentials verified without signing in or changing records.',flush=True)
    overview=db.rpc('admin_get_overview',{'p_actor_id':str(admin.id)}).execute().data
    print('Restricted application account can read local overview; no cloud calls required.',flush=True)
    (BACKEND/'migration-private'/'smoke-check.json').write_text(json.dumps({'passed':True,'accounts':len(profiles),'incidents':len(incidents)}),encoding='utf-8')


if __name__=='__main__': main()
