"""Local password verification and revocable, memory-only browser sessions."""
import hashlib
import hmac
import secrets
from datetime import timedelta
from types import SimpleNamespace

from fastapi import HTTPException

from app.localdb.storage import transaction, execute, get, update, now


def hash_password(password):
    if not 12 <= len(password) <= 128:
        raise HTTPException(422, 'Password must contain between 12 and 128 characters.')
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=16384, r=8, p=1)
    return 'scrypt$16384$8$1$'+salt.hex()+'$'+digest.hex()


def verify_password(password, encoded):
    try:
        kind,n,r,p,salt,expected = encoded.split('$')
        if kind != 'scrypt' or (n,r,p) != ('16384','8','1'):
            return False
        actual = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=int(n), r=int(r), p=int(p))
        return hmac.compare_digest(actual, bytes.fromhex(expected))
    except (ValueError, AttributeError):
        return False


def token_hash(token):
    return hashlib.sha256(token.encode()).hexdigest()


def sign_in(email, password):
    key=hashlib.sha256(email.strip().lower().encode()).hexdigest()
    with transaction() as conn:
        execute(conn,'INSERT IGNORE INTO local_login_attempts(attempt_key,attempts,started_at) VALUES (%s,0,UTC_TIMESTAMP(6))',(key,))
        entry=execute(conn,'SELECT * FROM local_login_attempts WHERE attempt_key=%s FOR UPDATE',(key,))[0]
        if (now().replace(tzinfo=None)-entry['started_at']).total_seconds()>=600:
            execute(conn,'UPDATE local_login_attempts SET attempts=1,started_at=UTC_TIMESTAMP(6) WHERE attempt_key=%s',(key,))
        elif entry['attempts']>=10:
            raise HTTPException(429,'Too many sign-in attempts. Try again in ten minutes.')
        else:
            execute(conn,'UPDATE local_login_attempts SET attempts=attempts+1 WHERE attempt_key=%s',(key,))
    with transaction() as conn:
        rows = execute(conn, 'SELECT p.*,c.password_hash,c.reset_required FROM profiles p JOIN local_credentials c ON c.profile_id=p.id WHERE p.email=%s', (email.strip().lower(),))
        row = rows[0] if rows else None
        # Spend the same scrypt work for unknown users.
        encoded = row['password_hash'] if row and row['password_hash'] else 'scrypt$16384$8$1$'+'00'*16+'$'+'00'*64
        valid = verify_password(password, encoded)
        if not valid or not row or row['status'] != 'active':
            raise HTTPException(401, 'Incorrect email or password, or inactive account.')
        token = secrets.token_urlsafe(48)
        expiry = now()+timedelta(hours=8)
        execute(conn, 'DELETE FROM local_sessions WHERE expires_at<=UTC_TIMESTAMP(6)')
        execute(conn, 'INSERT INTO local_sessions(token_hash,profile_id,expires_at) VALUES (%s,%s,%s)',
                (token_hash(token),row['id'],expiry.replace(tzinfo=None)))
        update(conn,'profiles',{'last_sign_in_at':now()},'id',row['id'])
        execute(conn,'DELETE FROM local_login_attempts WHERE attempt_key=%s',(key,))
        return {'access_token':token,'token_type':'bearer','expires_at':int(expiry.timestamp()),
                'user':{'id':row['id'],'email':row['email']},'password_change_required':bool(row['reset_required'])}


def verify_token(token):
    with transaction() as conn:
        rows = execute(conn, 'SELECT p.id,p.email,p.status FROM local_sessions s JOIN profiles p ON p.id=s.profile_id WHERE s.token_hash=%s AND s.expires_at>UTC_TIMESTAMP(6)', (token_hash(token),))
        if not rows:
            raise HTTPException(401,'Missing, invalid or expired access token.')
        if rows[0]['status'] != 'active':
            raise HTTPException(403,'Account is not active.')
        return SimpleNamespace(user=SimpleNamespace(id=rows[0]['id'],email=rows[0]['email']))


def logout(token):
    with transaction() as conn:
        execute(conn,'DELETE FROM local_sessions WHERE token_hash=%s',(token_hash(token),))


def change_password(token, old_password, new_password):
    user = verify_token(token).user
    encoded = hash_password(new_password)
    with transaction() as conn:
        row = get(conn,'local_credentials','profile_id',user.id,lock=True)
        if not row or not verify_password(old_password,row['password_hash']):
            raise HTTPException(401,'Current password is incorrect.')
        execute(conn,'UPDATE local_credentials SET password_hash=%s,reset_required=FALSE WHERE profile_id=%s',(encoded,user.id))
        execute(conn,'DELETE FROM local_sessions WHERE profile_id=%s AND token_hash<>%s',(user.id,token_hash(token)))


class LocalAuth:
    def get_user(self, token):
        result=verify_token(token)
        with transaction() as conn:
            rows=execute(conn,'SELECT reset_required FROM local_credentials WHERE profile_id=%s',(result.user.id,))
            if not rows or rows[0]['reset_required']:
                raise HTTPException(403,'Set your local password before accessing the dashboard.')
        return result
