"""Compare every imported value against the checksummed export; print no records."""
import json
import sys
from datetime import datetime,timezone
from pathlib import Path
import pymysql

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app.localdb.storage import SCHEMA,connect,ident,decode


def normalize(row,props):
    result={}
    for name,prop in props.items():
        value=row.get(name)
        if value is not None:
            fmt=prop.get('format')
            if fmt=='timestamp with time zone':
                value=datetime.fromisoformat(value.replace('Z','+00:00')).astimezone(timezone.utc).isoformat(timespec='microseconds')
            elif prop.get('type')=='number': value=float(value)
        result[name]=value
    return result


def main():
    source=BACKEND/'migration-private'/'api-baseline'
    manifest=json.loads((source/'manifest.json').read_text())
    report={}
    with connect(user='root',password='') as conn:
        for table,meta in manifest['tables'].items():
            with conn.cursor(pymysql.cursors.SSDictCursor) as cursor, (source/(table+'.jsonl')).open(encoding='utf-8') as stream:
                cursor.execute('SELECT * FROM '+ident(table)+' ORDER BY '+','.join(map(ident,meta['primary_key'])))
                count=0
                for line in stream:
                    row=cursor.fetchone()
                    if row is None: raise RuntimeError('Missing target row in '+table)
                    expected=normalize(json.loads(line),SCHEMA[table]['properties'])
                    actual=normalize(decode(table,row),SCHEMA[table]['properties'])
                    if expected!=actual: raise RuntimeError('Value mismatch in '+table+' at row '+str(count))
                    count+=1
                if cursor.fetchone() is not None or count!=meta['rows']: raise RuntimeError('Count mismatch in '+table)
                report[table]=count
                print(f'{table}: {count} rows verified, all fields match',flush=True)
    (BACKEND/'migration-private'/'verification.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print('All exported records verified against MySQL.',flush=True)


if __name__=='__main__': main()
