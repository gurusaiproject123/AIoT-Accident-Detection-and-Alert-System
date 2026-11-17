"""Create the isolated MySQL target and least-privilege application login.

Does not alter source records or activate MySQL in the app.
Run from backend with a local MySQL administrator account.
"""
import json
import secrets
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app.localdb.storage import SCHEMA, ident, connect


def mysql_type(name, prop):
    fmt = prop.get('format')
    if fmt == 'uuid': return 'CHAR(36)'
    if fmt == 'timestamp with time zone': return 'DATETIME(6)'
    if fmt == 'jsonb': return 'JSON'
    if fmt == 'boolean': return 'BOOLEAN'
    if fmt == 'int64': return 'BIGINT'
    if fmt == 'int32': return 'INT'
    if prop.get('type') == 'number': return 'DOUBLE'
    if name in {'message','body','detail','description','notes','reason','decline_reason','closing_note','cancel_reason','impact_summary','review_note','user_agent','rejection_reason','location_label','target_label'}: return 'TEXT'
    return 'VARCHAR(255)'


def statements():
    result = []
    for table, definition in SCHEMA.items():
        cols = []
        for name, prop in definition['properties'].items():
            pk = '<pk/>' in prop.get('description','')
            col = f'{ident(name)} {mysql_type(name,prop)}'
            if pk or name in definition.get('required',[]): col += ' NOT NULL'
            if pk and prop.get('format') == 'int64': col += ' AUTO_INCREMENT'
            if pk: col += ' PRIMARY KEY'
            cols.append(col)
        result.append(f'CREATE TABLE IF NOT EXISTS {ident(table)} ('+',\n'.join(cols)+') ENGINE=InnoDB')
    result.extend([
        'CREATE TABLE IF NOT EXISTS local_login_attempts (attempt_key CHAR(64) PRIMARY KEY, attempts INT NOT NULL, started_at DATETIME(6) NOT NULL) ENGINE=InnoDB',
        'CREATE TABLE IF NOT EXISTS local_credentials (profile_id CHAR(36) PRIMARY KEY, password_hash VARCHAR(255) NULL, reset_required BOOLEAN NOT NULL DEFAULT TRUE, FOREIGN KEY (profile_id) REFERENCES profiles(id)) ENGINE=InnoDB',
        'CREATE TABLE IF NOT EXISTS local_sessions (token_hash CHAR(64) PRIMARY KEY, profile_id CHAR(36) NOT NULL, expires_at DATETIME(6) NOT NULL, FOREIGN KEY (profile_id) REFERENCES profiles(id)) ENGINE=InnoDB',
        'CREATE TABLE IF NOT EXISTS local_account_preparations (email VARCHAR(255) PRIMARY KEY, role VARCHAR(32) NOT NULL, hospital_id CHAR(36), owner_id CHAR(36), actor_id CHAR(36) NOT NULL, created_at DATETIME(6) NOT NULL) ENGINE=InnoDB',
        'CREATE TABLE IF NOT EXISTS local_migration_imports (table_name VARCHAR(64) PRIMARY KEY, rows_imported BIGINT NOT NULL, sha256 CHAR(64) NOT NULL) ENGINE=InnoDB',
    ])
    return result


def main():
    private = BACKEND/'migration-private'
    private.mkdir(exist_ok=True)
    credential_file = private/'mysql.env'
    if credential_file.exists():
        print('MySQL preparation credentials already exist; refusing to replace them.')
        return
    password = secrets.token_urlsafe(36)
    with connect(user='root',password='') as connection:
        with connection.cursor() as cursor:
            for statement in statements(): cursor.execute(statement)
            cursor.execute("CREATE USER 'aiot_app'@'127.0.0.1' IDENTIFIED BY %s",(password,))
            cursor.execute("GRANT SELECT,INSERT,UPDATE,DELETE ON aiot_accident_detection.* TO 'aiot_app'@'127.0.0.1'")
        connection.commit()
    credential_file.write_text('DATABASE_BACKEND=mysql\nMYSQL_HOST=127.0.0.1\nMYSQL_PORT=3306\nMYSQL_DATABASE=aiot_accident_detection\nMYSQL_USER=aiot_app\nMYSQL_PASSWORD='+password+'\n',encoding='utf-8')
    (private/'target-schema.sql').write_text(';\n'.join(statements())+';\n',encoding='utf-8')
    print('Local schema and dedicated application login prepared. Private settings saved; app not switched.')


if __name__ == '__main__': main()
