"""Run in a SEPARATE terminal: python -m app.workers.database_deadlines.
Do not also schedule the same function unless your SQL implementation supports it.
"""
import logging
import time
from app.core.database import get_supabase_admin


def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    db = get_supabase_admin()
    logging.info('Processing stored cancellation and hospital deadlines every second.')
    try:
        while True:
            try:
                result = db.rpc('process_incident_deadlines', {}).execute()
                data = result.data or {}
                if any(data.get(k, 0) for k in ['windows_expired', 'notifications_timed_out', 'escalations', 'needs_superuser']):
                    logging.info('Deadline result: %s', data)
            except Exception:
                logging.exception('Deadline processing failed; check database function and connection.')
            time.sleep(1)
    except KeyboardInterrupt:
        logging.info('Deadline worker stopped.')


if __name__ == '__main__':
    main()
