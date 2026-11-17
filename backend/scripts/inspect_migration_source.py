"""Read-only PostgreSQL inventory for the MySQL port. Does not export passwords.

Run from backend: python scripts/inspect_migration_source.py
DATABASE_URL must be set privately in backend/.env.
"""
import json
import sys
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
from app.core.config import get_settings


QUERIES = {
    "columns": """
        SELECT table_name, column_name, ordinal_position, data_type, udt_name,
               is_nullable, column_default, character_maximum_length,
               numeric_precision, numeric_scale, is_identity, identity_generation
        FROM information_schema.columns WHERE table_schema = 'public'
        ORDER BY table_name, ordinal_position
    """,
    "constraints": """
        SELECT c.relname AS table_name, con.conname AS name, con.contype AS type,
               pg_get_constraintdef(con.oid) AS definition
        FROM pg_constraint con JOIN pg_class c ON c.oid = con.conrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' ORDER BY c.relname, con.conname
    """,
    "indexes": "SELECT tablename, indexname, indexdef FROM pg_indexes WHERE schemaname = 'public' ORDER BY tablename, indexname",
    "functions": """
        SELECT p.proname AS name, pg_get_function_identity_arguments(p.oid) AS arguments,
               pg_get_functiondef(p.oid) AS definition
        FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname = 'public' AND p.prokind = 'f'
          AND NOT EXISTS (
            SELECT 1 FROM pg_depend d
            WHERE d.classid = 'pg_proc'::regclass AND d.objid = p.oid AND d.deptype = 'e'
          )
        ORDER BY p.proname, p.oid
    """,
    "triggers": """
        SELECT c.relname AS table_name, t.tgname AS name, pg_get_triggerdef(t.oid) AS definition
        FROM pg_trigger t JOIN pg_class c ON c.oid = t.tgrelid
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('public', 'auth') AND NOT t.tgisinternal
        ORDER BY c.relname, t.tgname
    """,
    "enums": """
        SELECT t.typname AS name, e.enumlabel AS value, e.enumsortorder AS sort_order
        FROM pg_type t JOIN pg_enum e ON e.enumtypid = t.oid
        JOIN pg_namespace n ON n.oid = t.typnamespace
        WHERE n.nspname = 'public' ORDER BY t.typname, e.enumsortorder
    """,
    "views": "SELECT viewname, definition FROM pg_views WHERE schemaname = 'public' ORDER BY viewname",
    "policies": "SELECT * FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename, policyname",
    "tables": "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = 'BASE TABLE' ORDER BY table_name",
}


def inspect_source(connection):
    result = {}
    with connection.transaction():
        connection.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")
        for name, sql in QUERIES.items():
            result[name] = connection.execute(sql).fetchall()
        # Count availability only; never print or store password hashes here.
        result["auth_summary"] = connection.execute("""
            SELECT count(*) AS users,
                   count(*) FILTER (WHERE encrypted_password IS NOT NULL AND encrypted_password <> '') AS password_accounts
            FROM auth.users
        """).fetchone()
    return result


def main():
    source = get_settings().database_url
    if not source:
        print("Add the source PostgreSQL URI as DATABASE_URL in backend/.env. No changes made.")
        return 2
    try:
        with psycopg.connect(source, connect_timeout=15, sslmode="require", row_factory=dict_row) as connection:
            report = inspect_source(connection)
    except psycopg.Error:
        # Connection errors can contain credentials/host details. Do not echo them.
        print("Source inspection failed. Check DATABASE_URL, its password, network access, and schema-reading permissions. No changes made.")
        return 1
    directory = BACKEND / "migration-private"
    directory.mkdir(exist_ok=True)
    output = directory / "source-schema.json"
    temporary = output.with_suffix(".tmp")
    temporary.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    temporary.replace(output)
    print(f"Inspected {len(report['tables'])} tables and {len(report['functions'])} functions.")
    print("Private schema report: backend/migration-private/source-schema.json")
    print("No records changed; no password hashes exported.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
