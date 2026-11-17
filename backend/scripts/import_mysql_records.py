"""Import checksummed API baseline files into the isolated, empty MySQL target.

Per-table commits/checkpoints permit resume. Existing non-imported rows are never
overwritten. Counts alone do not establish a consistent source snapshot.
"""
import hashlib
import json
import sys
from pathlib import Path

BACKEND=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(BACKEND))
from app.localdb.storage import SCHEMA,connect,encode,ident


def main():
    source=BACKEND/'migration-private'/'api-baseline'
    manifest=json.loads((source/'manifest.json').read_text())
    with connect(user='root',password='') as conn:
        with conn.cursor() as cursor:
            for table,info in manifest['tables'].items():
                cursor.execute('SELECT * FROM local_migration_imports WHERE table_name=%s',(table,))
                imported=cursor.fetchone()
                if imported:
                    if imported['sha256']!=info['sha256']: raise RuntimeError('Source export changed after import: '+table)
                    print(table+': already imported',flush=True); continue
                cursor.execute(f'SELECT COUNT(*) n FROM {ident(table)}')
                if cursor.fetchone()['n']: raise RuntimeError('Target table is not empty: '+table)
                path=source/(table+'.jsonl')
                with path.open('rb') as stream:
                    if hashlib.file_digest(stream,'sha256').hexdigest()!=info['sha256']: raise RuntimeError('Checksum mismatch: '+table)
                keys=list(SCHEMA[table]['properties'])
                sql=f'INSERT INTO {ident(table)} ('+','.join(map(ident,keys))+') VALUES ('+','.join(['%s']*len(keys))+')'
                count=0; batch=[]
                with path.open(encoding='utf-8') as stream:
                    for line in stream:
                        row=json.loads(line)
                        if set(row)!=set(keys): raise RuntimeError('Export columns changed: '+table)
                        batch.append([encode(row[k],SCHEMA[table]['properties'][k]) for k in keys])
                        if len(batch)==1000:
                            cursor.executemany(sql,batch); count+=len(batch); batch=[]
                    if batch: cursor.executemany(sql,batch); count+=len(batch)
                if count!=info['rows']: raise RuntimeError('Row count mismatch: '+table)
                cursor.execute('INSERT INTO local_migration_imports(table_name,rows_imported,sha256) VALUES (%s,%s,%s)',(table,count,info['sha256']))
                conn.commit()
                print(f'{table}: imported {count} rows',flush=True)
    print('All completed export tables imported. No source changes.',flush=True)


if __name__=='__main__': main()
