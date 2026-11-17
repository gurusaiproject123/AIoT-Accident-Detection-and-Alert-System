import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import pymysql
from fastapi import HTTPException
from postgrest.exceptions import APIError

from app.core.config import get_settings

SCHEMA = json.loads(Path(__file__).with_name('schema.json').read_text(encoding='utf-8-sig'))


def ident(value):
    if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]*', value):
        raise ValueError('Invalid SQL identifier')
    return '`' + value + '`'


def now():
    return datetime.now(timezone.utc)


def encode(value, prop=None):
    fmt = (prop or {}).get('format', '')
    if value is None:
        return None
    if fmt == 'jsonb' or isinstance(value, (dict, list)):
        return json.dumps(value)
    if fmt == 'timestamp with time zone' and isinstance(value, str):
        value = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, UUID):
        return str(value)
    return value


def decode(table, row):
    result = dict(row)
    for key, value in row.items():
        fmt = SCHEMA.get(table, {}).get('properties', {}).get(key, {}).get('format')
        if isinstance(value, datetime):
            result[key] = value.replace(tzinfo=timezone.utc).isoformat()
        elif fmt == 'boolean' and value is not None:
            result[key] = bool(value)
        elif fmt == 'jsonb' and isinstance(value, str):
            result[key] = json.loads(value)
    return result


def connect(database=None, user=None, password=None, read_timeout=30):
    s = get_settings()
    return pymysql.connect(host=s.mysql_host, port=s.mysql_port,
        user=user or s.mysql_user, password=s.mysql_password.get_secret_value() if password is None else password,
        database=database or s.mysql_database, charset='utf8mb4', autocommit=False,
        cursorclass=pymysql.cursors.DictCursor, connect_timeout=5, read_timeout=read_timeout, write_timeout=30,
        init_command="SET time_zone = '+00:00'")


def error(code, message):
    raise APIError({'code': code, 'message': message, 'details': None, 'hint': None})


@contextmanager
def transaction():
    connection = None
    try:
        connection = connect()
        yield connection
        connection.commit()
    except pymysql.IntegrityError as exc:
        if connection:
            connection.rollback()
        error('23505' if exc.args[0] == 1062 else '23514', 'Local database constraint rejected this change.')
    except pymysql.OperationalError as exc:
        if connection:
            connection.rollback()
        if exc.args[0] in (1205, 1213):
            error('40001', 'Concurrent update; retry the request.')
        raise HTTPException(503, 'Local MySQL is unavailable. Check the WAMP MySQL service.') from None
    except Exception:
        if connection:
            connection.rollback()
        raise
    finally:
        if connection:
            connection.close()


def execute(conn, sql, args=()):
    with conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall()


def get(conn, table, key, value, lock=False):
    rows = execute(conn, f'SELECT * FROM {ident(table)} WHERE {ident(key)}=%s' + (' FOR UPDATE' if lock else ''), (value,))
    return decode(table, rows[0]) if rows else None


def insert(conn, table, record):
    record = dict(record)
    props = SCHEMA[table]['properties']
    for name, prop in props.items():
        if name in record:
            continue
        default = prop.get('default')
        if default == 'gen_random_uuid()':
            record[name] = str(uuid4())
        elif default == 'now()':
            record[name] = now()
        elif isinstance(default, str) and 'nextval(' in default:
            prefix = {'incidents': 'INC', 'hospitals': 'HSP', 'audit_logs': 'AUD'}[table]
            record[name] = prefix + '-' + uuid4().hex[:12].upper()
        elif default is not None:
            record[name] = default
    keys = list(record)
    if any(k not in props for k in keys):
        raise ValueError('Unknown database column')
    with conn.cursor() as cur:
        cur.execute(f'INSERT INTO {ident(table)} ({",".join(map(ident,keys))}) VALUES ({",".join(["%s"]*len(keys))})',
                    [encode(record[k], props[k]) for k in keys])
        pk = 'key' if table == 'system_settings' else 'id'
        value = record.get(pk, cur.lastrowid)
    return get(conn, table, pk, value)


def update(conn, table, record, key, value):
    props = SCHEMA[table]['properties']
    record = dict(record)
    if 'updated_at' in props:
        record['updated_at'] = now()
    if any(k not in props for k in record):
        raise ValueError('Unknown database column')
    execute(conn, f'UPDATE {ident(table)} SET '+','.join(ident(k)+'=%s' for k in record)+f' WHERE {ident(key)}=%s',
            [encode(v,props[k]) for k,v in record.items()]+[value])
    return get(conn, table, key, value)


class Query:
    def __init__(self, table):
        if table not in SCHEMA:
            raise ValueError('Unknown table')
        self.table = table
        self.columns = '*'
        self.filters, self.args, self.orders = [], [], []
        self.offset, self.size, self.count, self.one = 0, None, False, False
        self.operation, self.payload, self.ignore = 'select', None, False

    def column(self, name):
        if name not in SCHEMA[self.table]['properties']:
            raise ValueError('Unknown column')
        return ident(name)

    def select(self, columns='*', count=None):
        self.columns, self.count = columns, count == 'exact'
        return self

    def eq(self, key, value):
        self.filters.append(self.column(key) + (' IS NULL' if value is None else '=%s'))
        if value is not None:
            self.args.append(encode(value, SCHEMA[self.table]['properties'][key]))
        return self

    def in_(self, key, values):
        self.filters.append(self.column(key) + ' IN ('+','.join(['%s']*len(values))+')' if values else 'FALSE')
        self.args.extend(values)
        return self

    def order(self, key, desc=False):
        self.orders.append(self.column(key) + (' DESC' if desc else ' ASC'))
        return self

    def range(self, start, end):
        self.offset, self.size = start, end-start+1
        return self

    def limit(self, value):
        self.size = value
        return self

    def maybe_single(self):
        self.one = True
        return self

    def insert(self, payload):
        self.operation, self.payload = 'insert', payload
        return self

    def update(self, payload):
        self.operation, self.payload = 'update', payload
        return self

    def upsert(self, payload, on_conflict=None, ignore_duplicates=False):
        if not ignore_duplicates or on_conflict != 'packet_id' or self.table != 'model_predictions':
            raise ValueError('Unsupported upsert')
        self.operation, self.payload, self.ignore = 'insert', payload, True
        return self

    def execute(self):
        with transaction() as conn:
            where = ' WHERE '+' AND '.join(self.filters) if self.filters else ''
            base = f' FROM {ident(self.table)}'+where
            total = execute(conn, 'SELECT COUNT(*) AS n'+base, self.args)[0]['n'] if self.count else None
            if self.operation == 'insert':
                try:
                    rows = [insert(conn, self.table, self.payload)]
                    from app.localdb.rules import after_insert
                    after_insert(conn,self.table,rows[0])
                except pymysql.IntegrityError as exc:
                    if not self.ignore or exc.args[0] != 1062:
                        raise
                    rows = []
            else:
                sql = 'SELECT *'+base
                if self.orders:
                    sql += ' ORDER BY '+','.join(self.orders)
                if self.size is not None:
                    sql += f' LIMIT {int(self.size)} OFFSET {int(self.offset)}'
                if self.operation == 'update':
                    sql += ' FOR UPDATE'
                rows = [decode(self.table,r) for r in execute(conn,sql,self.args)]
                if self.operation == 'update':
                    from app.localdb.rules import after_update
                    changed = []
                    for old in rows:
                        new = update(conn,self.table,self.payload,'id',old['id'])
                        after_update(conn,self.table,old,new)
                        changed.append(new)
                    rows = changed
            if self.columns == '*,hospital:hospitals(*),incident:incidents(*)':
                for row in rows:
                    row['hospital'] = get(conn,'hospitals','id',row['hospital_id'])
                    row['incident'] = get(conn,'incidents','id',row['incident_id'])
            elif self.columns != '*':
                keys = [s.strip() for s in self.columns.split(',')]
                for key in keys:
                    self.column(key)
                rows = [{k:r.get(k) for k in keys} for r in rows]
            if self.one and len(rows)>1:
                error('PGRST116','More than one row found.')
            return SimpleNamespace(data=(rows[0] if rows else None) if self.one else rows,count=total)


class MySQLDatabase:
    def table(self, name):
        return Query(name)

    def rpc(self, name, params):
        def run():
            from app.localdb.rules import dispatch
            with transaction() as conn:
                return SimpleNamespace(data=dispatch(conn,name,params))
        return SimpleNamespace(execute=run)

    @property
    def auth(self):
        from app.localdb.auth import LocalAuth
        return LocalAuth()
