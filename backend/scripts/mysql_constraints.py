"""Keys and constraints restored after all tables have been imported."""
import re
import json
import sys
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app.localdb.storage import SCHEMA,ident,connect

INDEXES = {
    'telemetry_packets': [('uq_packet_retry',True,['device_id','boot_id','sequence_number'])],
    'sensor_readings': [('uq_packet_sample',True,['packet_id','sample_index']),('ix_motion_latest',False,['device_id','recorded_at'])],
    'model_predictions': [('uq_prediction_packet',True,['packet_id'])],
    'incidents': [('uq_incident_prediction',True,['prediction_id']),('uq_incident_code',True,['code']),('ix_incident_deadline',False,['status','cancellation_deadline']),('ix_device_incident',False,['device_id','detected_at'])],
    'incident_notifications': [('uq_incident_hospital',True,['incident_id','hospital_id']),('ix_hospital_inbox',False,['hospital_id','notified_at']),('ix_notification_deadline',False,['status','response_deadline'])],
    'profiles': [('uq_profile_email',True,['email'])],
    'vehicle_owners': [('uq_owner_login',True,['user_id'])],
    'devices': [('uq_device_code',True,['device_code'])],
    'vehicles': [('uq_registration',True,['registration'])],
    'hospitals': [('uq_hospital_code',True,['code'])],
}


def apply(conn):
    with conn.cursor() as cursor:
        cursor.execute('ALTER TABLE incidents MODIFY location_label TEXT NULL')
        cursor.execute('ALTER TABLE audit_logs MODIFY target_label TEXT NULL')
        cursor.execute('SELECT TABLE_NAME,CONSTRAINT_NAME FROM information_schema.TABLE_CONSTRAINTS WHERE CONSTRAINT_SCHEMA=DATABASE()')
        existing={(r['TABLE_NAME'],r['CONSTRAINT_NAME']) for r in cursor.fetchall()}
        cursor.execute('SELECT TABLE_NAME,INDEX_NAME FROM information_schema.STATISTICS WHERE TABLE_SCHEMA=DATABASE()')
        indexes={(r['TABLE_NAME'],r['INDEX_NAME']) for r in cursor.fetchall()}
        for table, entries in INDEXES.items():
            for name,unique,cols in entries:
                if (table,name) not in indexes:
                    cursor.execute(f'CREATE {"UNIQUE " if unique else ""}INDEX {ident(name)} ON {ident(table)} ('+','.join(map(ident,cols))+')')
        for table,definition in SCHEMA.items():
            for column,prop in definition['properties'].items():
                match=re.search(r"<fk table='(\w+)' column='(\w+)'/>",prop.get('description',''))
                name='fk_'+table+'_'+column
                if match and (table,name) not in existing:
                    cursor.execute(f'ALTER TABLE {ident(table)} ADD CONSTRAINT {ident(name)} FOREIGN KEY ({ident(column)}) REFERENCES {ident(match[1])} ({ident(match[2])})')
                values=prop.get('enum')
                name='ck_'+table+'_'+column
                if values and (table,name) not in existing:
                    literals=','.join("'"+v.replace("'","''")+"'" for v in values)
                    cursor.execute(f'ALTER TABLE {ident(table)} ADD CONSTRAINT {ident(name)} CHECK ({ident(column)} IN ({literals}))')
        extra=[
            ('profiles','ck_profile_hospital',"(role='hospital_staff' AND hospital_id IS NOT NULL) OR (role IN ('superuser','car_owner') AND hospital_id IS NULL)"),
            ('telemetry_packets','ck_packet_count','sample_count BETWEEN 1 AND 1600 AND sampling_hz=100 AND sequence_number>=0'),
            ('incidents','ck_incident_score','model_score IS NULL OR model_score BETWEEN 0 AND 1'),
            ('model_predictions','ck_prediction_scores','score BETWEEN 0 AND 1 AND threshold BETWEEN 0 AND 1'),
        ]
        for table,name,expression in extra:
            if (table,name) not in existing:
                cursor.execute(f'ALTER TABLE {ident(table)} ADD CONSTRAINT {ident(name)} CHECK ({expression})')
        if ('devices','uq_active_vehicle_device') not in indexes:
            cursor.execute('CREATE UNIQUE INDEX uq_active_vehicle_device ON devices ((CASE WHEN is_active THEN vehicle_id ELSE NULL END))')
    conn.commit()


if __name__=='__main__':
    with connect(user='root',password='',read_timeout=600) as connection: apply(connection)
    private=Path(__file__).resolve().parents[1]/'migration-private'
    private.mkdir(exist_ok=True)
    (private/'constraints.json').write_text(json.dumps({'installed':True}),encoding='utf-8')
    print('Local uniqueness, reference, and state constraints installed.')
