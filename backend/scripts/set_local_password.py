"""Interactive recovery for an existing local account. Never pass passwords in argv."""
import sys
from getpass import getpass
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.core.config import get_settings
from app.localdb.auth import hash_password
from app.localdb.storage import execute,transaction


def main():
    if get_settings().database_backend!='mysql':
        raise SystemExit('Local MySQL must be enabled before resetting a local password.')
    email=input('Existing account email: ').strip().lower()
    password=getpass('New password (12-128 characters): ')
    if password!=getpass('Confirm password: '):
        raise SystemExit('Passwords did not match. No changes made.')
    encoded=hash_password(password)
    with transaction() as conn:
        rows=execute(conn,'SELECT id FROM profiles WHERE email=%s',(email,))
        if len(rows)!=1: raise SystemExit('Account not found. No changes made.')
        uid=rows[0]['id']
        execute(conn,'INSERT INTO local_credentials(profile_id,password_hash,reset_required) VALUES (%s,%s,FALSE) ON DUPLICATE KEY UPDATE password_hash=%s,reset_required=FALSE',(uid,encoded,encoded))
        execute(conn,'DELETE FROM local_sessions WHERE profile_id=%s',(uid,))
    print('Local password changed. Previous sessions revoked.')


if __name__=='__main__': main()
