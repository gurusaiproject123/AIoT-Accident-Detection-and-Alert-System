"""Read-only, resumable API export. Private files contain device credentials.

This is a baseline copy, not a cross-table transactional snapshot. Stop writers
and take a fresh export before final cutover. Never commit migration-private.
"""
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings


def request(client, path, **kwargs):
    for attempt in range(5):
        try:
            response = client.get(path, **kwargs)
            response.raise_for_status()
            return response
        except (httpx.TransportError, httpx.HTTPStatusError) as exc:
            if isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code < 500 and exc.response.status_code != 429:
                raise
            if attempt == 4:
                raise
            time.sleep(min(2 ** attempt, 8))


def main():
    settings = get_settings()
    directory = BACKEND / "migration-private" / "api-baseline"
    directory.mkdir(parents=True, exist_ok=True)
    secret = settings.supabase_service_role_key.get_secret_value()
    with httpx.Client(base_url=settings.supabase_url.rstrip('/') + '/rest/v1/',
                      headers={'apikey': secret, 'Authorization': 'Bearer ' + secret}, timeout=60) as client:
        spec = request(client, '').json()
        (directory / 'schema.json').write_text(json.dumps(spec, indent=2), encoding='utf-8')
        manifest_path = directory / 'manifest.json'
        manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {
            'started_at': datetime.now(timezone.utc).isoformat(), 'consistent_snapshot': False, 'tables': {}}
        for table, definition in spec['definitions'].items():
            if '/' + table not in spec['paths']:
                continue
            columns = definition.get('properties', {})
            keys = [name for name, prop in columns.items() if '<pk/>' in prop.get('description', '')]
            if not keys:
                raise RuntimeError(f'No primary key advertised for {table}; cannot export reliably.')
            destination = directory / (table + '.jsonl')
            if table in manifest['tables'] and destination.exists():
                digest = hashlib.file_digest(destination.open('rb'), 'sha256').hexdigest()
                if digest != manifest['tables'][table]['sha256']:
                    raise RuntimeError(f'Export checksum mismatch: {table}')
                print(f'{table}: already exported', flush=True)
                continue
            count = 0
            digest = hashlib.sha256()
            temporary = destination.with_suffix('.partial')
            params = {'select': '*', 'order': ','.join(key + '.asc' for key in keys), 'limit': '1000'}
            # Single-column keyset pagination avoids progressively slower offsets.
            with temporary.open('wb') as output:
                while True:
                    if len(keys) > 1:
                        params['offset'] = str(count)
                    rows = request(client, table, params=params).json()
                    if not rows:
                        break
                    for row in rows:
                        line = (json.dumps(row, separators=(',', ':'), ensure_ascii=False) + '\n').encode('utf-8')
                        output.write(line)
                        digest.update(line)
                    count += len(rows)
                    if len(keys) == 1:
                        params[keys[0]] = 'gt.' + str(rows[-1][keys[0]])
                    if count % 100000 == 0:
                        print(f'{table}: {count} rows copied', flush=True)
            temporary.replace(destination)
            manifest['tables'][table] = {'rows': count, 'sha256': digest.hexdigest(), 'primary_key': keys}
            pending = manifest_path.with_suffix('.tmp')
            pending.write_text(json.dumps(manifest, indent=2), encoding='utf-8')
            pending.replace(manifest_path)
            print(f'{table}: {count} rows exported', flush=True)
        print('Baseline export complete; source records unchanged.', flush=True)


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        # Do not expose URLs, credentials, or source rows through errors.
        print(f'Export stopped ({type(exc).__name__}). Completed tables remain available for resume.', flush=True)
        raise SystemExit(1)
