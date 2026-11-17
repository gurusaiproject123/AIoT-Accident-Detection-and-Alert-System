"""Switch backend/.env only after verified import and constraint installation.

Keep backend and ESP32 stopped. Existing Supabase settings are retained for
rollback; no source database changes are performed.
"""
import json
import re
import sys
from pathlib import Path
from dotenv import dotenv_values

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app.localdb.storage import connect,execute


def main():
    private=BACKEND/'migration-private'
    manifest=json.loads((private/'api-baseline'/'manifest.json').read_text())
    verified=json.loads((private/'verification.json').read_text())
    source_check=json.loads((private/'source-check.json').read_text())
    constraints=json.loads((private/'constraints.json').read_text())
    smoke=json.loads((private/'smoke-check.json').read_text())
    if not smoke.get('passed'):
        raise SystemExit('Target smoke check has not passed.')
    if len(manifest['tables'])!=17 or not constraints.get('installed'):
        raise SystemExit('Incomplete migration; configuration was not changed.')
    for table,meta in manifest['tables'].items():
        if verified.get(table)!=meta['rows'] or source_check.get(table,{}).get('rows')!=meta['rows']:
            raise SystemExit('Unverified table: '+table)
    values=dotenv_values(private/'mysql.env')
    if values.get('MYSQL_DATABASE')!='aiot_accident_detection' or values.get('MYSQL_USER')!='aiot_app':
        raise SystemExit('Unexpected target configuration. No changes made.')
    with connect(user=values['MYSQL_USER'],password=values['MYSQL_PASSWORD']) as conn:
        imported=execute(conn,'SELECT table_name,rows_imported,sha256 FROM local_migration_imports')
        if len(imported)!=len(verified): raise SystemExit('Import checkpoint count mismatch.')
        for row in imported:
            meta=manifest['tables'][row['table_name']]
            if row['rows_imported']!=meta['rows'] or row['sha256']!=meta['sha256']:
                raise SystemExit('Import checkpoint mismatch.')
        missing=execute(conn,'SELECT COUNT(*) n FROM profiles p LEFT JOIN local_credentials c ON p.id=c.profile_id WHERE c.password_hash IS NULL')[0]['n']
        if missing: raise SystemExit('Some local accounts do not have credentials yet.')
    env=BACKEND/'.env'
    text=env.read_text(encoding='utf-8-sig')
    backup=private/'backend.env.before-mysql'
    if not backup.exists():
        backup.write_bytes(env.read_bytes())
    for key,value in values.items():
        if value is None: raise SystemExit('Missing private setting: '+key)
        pattern=re.compile(r'^'+re.escape(key)+r'=.*$',re.MULTILINE)
        line=key+'='+value
        text=pattern.sub(lambda _:line,text) if pattern.search(text) else text.rstrip()+'\n'+line+'\n'
    temporary=private/'backend.env.pending'
    temporary.write_text(text,encoding='utf-8')
    temporary.replace(env)
    print('Backend configuration switched to local MySQL. Previous configuration backed up privately.')
    print('Restart FastAPI and the frontend. Existing source records were not modified.')


if __name__=='__main__': main()
