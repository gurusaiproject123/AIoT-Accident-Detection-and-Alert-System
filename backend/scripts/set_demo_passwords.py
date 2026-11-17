"""Explicit development-only reset requested by the local system owner.

Updates local hashes and the private handover file; revokes existing sessions.
Every account must replace its temporary password on first login.
"""
import json
import sys
from collections import Counter
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings
from app.localdb.auth import hash_password, verify_password
from app.localdb.storage import execute, transaction


def main():
    if get_settings().database_backend != 'mysql':
        raise SystemExit('This reset is only for local MySQL accounts.')
    private = BACKEND / 'migration-private'
    target = private / 'temporary-logins.json'
    pending = private / 'temporary-logins.pending.json'
    counters = Counter()
    entries = []
    with transaction() as conn:
        users = execute(conn, 'SELECT id,email,role FROM profiles ORDER BY role,email FOR UPDATE')
        for user in users:
            role = user['role']
            counters[role] += 1
            number = counters[role]
            if role == 'superuser':
                password = 'superuser@2026' if number == 1 else f'superuser{number}@2026'
            elif role == 'hospital_staff':
                password = f'hospital{number}@2026'
            elif role == 'car_owner':
                password = f'carowner{number}@2026'
            else:
                raise RuntimeError('Unexpected account role; no passwords changed.')
            encoded = hash_password(password)
            execute(conn, 'UPDATE local_credentials SET password_hash=%s,reset_required=TRUE WHERE profile_id=%s',
                    (encoded, user['id']))
            saved = execute(conn, 'SELECT password_hash,reset_required FROM local_credentials WHERE profile_id=%s', (user['id'],))
            if len(saved) != 1 or not verify_password(password, saved[0]['password_hash']) or not saved[0]['reset_required']:
                raise RuntimeError('Password update could not be verified; transaction rolled back.')
            execute(conn, 'DELETE FROM local_sessions WHERE profile_id=%s', (user['id'],))
            entries.append({'email': user['email'], 'role': role, 'temporary_password': password})
        pending.write_text(json.dumps(entries, indent=2), encoding='utf-8')
    pending.replace(target)
    print(f'Updated and verified {len(entries)} local passwords. Existing sessions revoked.')
    print('Private credentials file updated; password changes are required at next login.')


if __name__ == '__main__':
    main()
