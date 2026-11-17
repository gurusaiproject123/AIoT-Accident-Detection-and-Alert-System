"""Read-only final source checks after the user stops all writers.

Mutable tables are compared byte-for-byte with the baseline. Immutable sensor
history is checked by count and high-water ID; MySQL values are separately
compared against every exported sensor row by verify_mysql_records.py.
"""
import hashlib
import json
import sys
from pathlib import Path
from datetime import datetime,timezone
import httpx

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app.core.config import get_settings
from scripts.export_supabase_records import request


def main():
    source=BACKEND/'migration-private'/'api-baseline'
    manifest=json.loads((source/'manifest.json').read_text())
    settings=get_settings(); secret=settings.supabase_service_role_key.get_secret_value()
    report={}
    with httpx.Client(base_url=settings.supabase_url.rstrip('/')+'/rest/v1/',headers={'apikey':secret,'Authorization':'Bearer '+secret},timeout=120) as client:
        for table,meta in manifest['tables'].items():
            keys=meta['primary_key']
            if table=='sensor_readings':
                response=request(client,table,params={'select':'id','order':'id.desc','limit':'1'},headers={'Prefer':'count=exact'})
                total=int(response.headers['content-range'].split('/')[-1])
                # The API history is append-only in this application; writers are stopped.
                with (source/(table+'.jsonl')).open('rb') as stream:
                    stream.seek(max(0,stream.seek(0,2)-8192))
                    tail=stream.read().splitlines()[-1]
                last=json.loads(tail)['id']
                if total!=meta['rows'] or response.json()[0]['id']!=last:
                    raise RuntimeError('Sensor history changed; fresh export required.')
                report[table]={'rows':total,'high_water_id':last}
            else:
                digest=hashlib.sha256(); count=0
                while True:
                    rows=request(client,table,params={'select':'*','order':','.join(k+'.asc' for k in keys),'limit':'1000','offset':str(count)}).json()
                    if not rows: break
                    for row in rows:
                        digest.update((json.dumps(row,separators=(',',':'),ensure_ascii=False)+'\n').encode())
                    count+=len(rows)
                if count!=meta['rows'] or digest.hexdigest()!=meta['sha256']:
                    raise RuntimeError('Source changed after export: '+table)
                report[table]={'rows':count,'sha256':digest.hexdigest()}
            print(table+': source check passed',flush=True)
    report['checked_at']=datetime.now(timezone.utc).isoformat()
    (BACKEND/'migration-private'/'source-check.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('Final source checks passed. Keep writers stopped until cutover.',flush=True)


if __name__=='__main__': main()
