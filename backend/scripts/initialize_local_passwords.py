"""Generate private temporary passwords for imported accounts, once only."""
import json
import secrets
import sys
from pathlib import Path

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app.localdb.storage import connect,execute
from app.localdb.auth import hash_password


def main():
    path=BACKEND/'migration-private'/'temporary-logins.json'
    if path.exists():
        print('Temporary login file already exists. No passwords replaced.'); return
    with connect(user='root',password='') as conn:
        profiles=execute(conn,'SELECT id,email,role FROM profiles ORDER BY email')
        rows=[]
        for profile in profiles:
            if execute(conn,'SELECT profile_id FROM local_credentials WHERE profile_id=%s',(profile['id'],)):
                continue
            password=secrets.token_urlsafe(18)
            rows.append({'email':profile['email'],'role':profile['role'],'temporary_password':password})
            execute(conn,'INSERT INTO local_credentials(profile_id,password_hash,reset_required) VALUES (%s,%s,TRUE)',
                    (profile['id'],hash_password(password)))
        # Write privately before committing: no plaintext credentials in tool output.
        with path.open('x',encoding='utf-8') as out: json.dump(rows,out,indent=2)
        conn.commit()
    print(f'{len(rows)} accounts initialized. Private file: backend/migration-private/temporary-logins.json')


if __name__=='__main__': main()
