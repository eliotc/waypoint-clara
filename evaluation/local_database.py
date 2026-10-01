"""Provision a new localhost-only evaluation DB; never seed an existing DB."""
from __future__ import annotations

import argparse
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
from uuid import uuid4
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_ADMIN = 'postgresql://waypoint_eval:waypoint_eval_local@127.0.0.1:55432/postgres'
NAME = re.compile(r'^waypoint_eval_[0-9a-f]{32}$')


def local_dsn(dsn: str, *, database: bool = False):
    from psycopg2.extensions import parse_dsn
    if any(os.environ.get(k) for k in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        raise ValueError("Unset PostgreSQL connection override environment variables for evaluation")
    parts = parse_dsn(dsn)
    if parts.get('host') not in ('127.0.0.1', 'localhost', '::1'):
        raise ValueError('Evaluation databases must use an explicit loopback host')
    if any(k in parts for k in ('hostaddr', 'service', 'options')):
        raise ValueError('Connection overrides are not allowed for evaluation databases')
    if database and not NAME.fullmatch(parts.get('dbname', '')):
        raise ValueError('Expected a uniquely named waypoint_eval database')
    return parts


def database_uri(dsn: str) -> str:
    """Use a URI accepted by both psycopg2 and asyncpg."""
    parts = local_dsn(dsn, database=True)
    database = parts.pop('dbname')
    return 'postgresql:///' + database + '?' + urlencode(parts)


def state_file(path: Path) -> dict:
    state = json.loads(path.read_text())
    local_dsn(state['readonly_dsn'], database=True)
    local_dsn(state['admin_dsn'], database=True)
    if not NAME.fullmatch(state['database']):
        raise ValueError('Invalid evaluation database identity')
    return state


def connect_verified(state: dict, readonly=True):
    import psycopg2
    dsn = state['readonly_dsn' if readonly else 'admin_dsn']
    parts = local_dsn(dsn, database=True)
    if parts['dbname'] != state['database']:
        raise ValueError('Database state does not match connection identity')
    conn = psycopg2.connect(dsn, connect_timeout=5)
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT token, dataset_id FROM evaluation_identity')
            row = cur.fetchone()
            if row != (state['identity'], state['dataset_id']):
                raise ValueError('Database ownership marker mismatch')
            if readonly:
                cur.execute('SHOW transaction_read_only')
                if cur.fetchone()[0] != 'on':
                    raise ValueError('Evaluation role must default to read-only transactions')
                for table in ('courses', 'events', 'tour_bookings', 'event_registrations', 'knowledge_docs', 'scholarships'):
                    cur.execute("SELECT has_table_privilege(current_user, %s, 'INSERT,UPDATE,DELETE,TRUNCATE')", (table,))
                    if cur.fetchone()[0]:
                        raise ValueError('Evaluation role has write privileges')
        return conn
    except Exception:
        conn.close()
        raise


def snapshot(state: dict) -> dict:
    """Actual DB authority, including all returned content but not embedding arrays."""
    conn = connect_verified(state)
    try:
        with conn.cursor() as cur:
            result = {}
            for table in ('courses', 'events', 'tour_bookings', 'event_registrations', 'knowledge_docs', 'scholarships'):
                cur.execute(f"SELECT to_jsonb(t) - 'embedding' FROM {table} t ORDER BY id")
                result[table] = [row[0] for row in cur.fetchall()]
            cur.execute('SELECT CURRENT_TIMESTAMP')
            result['observed_at'] = cur.fetchone()[0].isoformat()
            return result
    finally:
        conn.close()


def provision(output: Path, with_embeddings=False) -> dict:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import make_dsn
    if output.exists():
        raise ValueError('State output already exists; each database needs a new state file')
    admin = os.environ.get('EVAL_ADMIN_DATABASE_URL', DEFAULT_ADMIN)
    parts = local_dsn(admin)
    name = 'waypoint_eval_' + uuid4().hex
    role = name + '_reader'
    password, identity, token = secrets.token_hex(24), secrets.token_hex(24), secrets.token_hex(24)
    db_dsn = make_dsn(admin, dbname=name)
    readonly_dsn = make_dsn(admin, dbname=name, user=role, password=password)
    state = {'version': 1, 'database': name, 'reader_role': role, 'admin_dsn': db_dsn,
             'readonly_dsn': readonly_dsn, 'identity': identity, 'http_token': token,
             'dataset_id': 'clara-local-seed-v2', 'embeddings_ready': False,
             'created_at': datetime.now(timezone.utc).isoformat(), 'status': 'initializing'}
    output.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as f:
        json.dump(state, f, indent=2)
    control = psycopg2.connect(admin, connect_timeout=5)
    control.autocommit = True
    try:
        with control.cursor() as cur:
            cur.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
        with closing(psycopg2.connect(db_dsn)) as conn, conn, conn.cursor() as cur:
            cur.execute((ROOT / 'data/schema.sql').read_text())
            cur.execute((ROOT / 'data/seed.sql').read_text())
            cur.execute('CREATE TABLE evaluation_identity (token text NOT NULL, dataset_id text NOT NULL)')
            cur.execute('INSERT INTO evaluation_identity VALUES (%s, %s)', (identity, state['dataset_id']))
        # Optional explicit API-backed preparation, only inside the newly created DB.
        if with_embeddings:
            # asyncpg accepts PostgreSQL URIs, not libpq keyword DSNs.
            seed_uri = database_uri(db_dsn)
            env = {**os.environ, 'DATABASE_URL': seed_uri}
            subprocess.run([sys.executable, str(ROOT / 'backend/seed.py')], env=env, cwd=ROOT, check=True)
            state['embeddings_ready'] = True
        with closing(psycopg2.connect(db_dsn)) as conn, conn, conn.cursor() as cur:
            from evaluation.event_fixture import rebase_events
            state['clock_anchor'] = rebase_events(cur)
        with control.cursor() as cur:
            cur.execute(sql.SQL('CREATE ROLE {} LOGIN PASSWORD %s').format(sql.Identifier(role)), (password,))
            cur.execute(sql.SQL('ALTER ROLE {} SET default_transaction_read_only = on').format(sql.Identifier(role)))
        with closing(psycopg2.connect(db_dsn)) as conn, conn, conn.cursor() as cur:
            cur.execute(sql.SQL('GRANT CONNECT ON DATABASE {} TO {}').format(sql.Identifier(name), sql.Identifier(role)))
            cur.execute(sql.SQL('GRANT USAGE ON SCHEMA public TO {}').format(sql.Identifier(role)))
            cur.execute(sql.SQL('GRANT SELECT ON ALL TABLES IN SCHEMA public TO {}').format(sql.Identifier(role)))
        state['status'] = 'ready'
        state['seed_hashes'] = {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest() for f in ('data/schema.sql','data/seed.sql','evaluation/event_fixture.py')}
        output.write_text(json.dumps(state, indent=2) + '\n')
        connect_verified(state).close()
        return state
    finally:
        control.close()


def destroy(path: Path) -> None:
    import psycopg2
    from psycopg2 import sql
    from psycopg2.extensions import make_dsn
    state = state_file(path)
    # Refuse to delete an unmarked DB, including incomplete provisioning.
    connect_verified(state, readonly=False).close()
    control = psycopg2.connect(make_dsn(state['admin_dsn'], dbname='postgres'), connect_timeout=5)
    control.autocommit = True
    try:
        with control.cursor() as cur:
            # No FORCE: a running server/client must be stopped first.
            cur.execute(sql.SQL('DROP DATABASE {}').format(sql.Identifier(state['database'])))
            cur.execute(sql.SQL('DROP ROLE {}').format(sql.Identifier(state['database'] + '_reader')))
        state['status'] = 'destroyed'
        path.write_text(json.dumps(state, indent=2) + '\n')
    finally:
        control.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('create','destroy'))
    parser.add_argument('--state', type=Path, required=True)
    parser.add_argument('--with-embeddings', action='store_true', help='Generate real embeddings using the configured Gemini API')
    args = parser.parse_args()
    try:
        if args.command == 'create':
            state = provision(args.state, args.with_embeddings)
            print(f"Created {state['database']}; private state: {args.state}; embeddings={state['embeddings_ready']}")
        else:
            destroy(args.state)
            print('Destroyed the marked evaluation database and reader role')
    except Exception as exc:
        # Driver exceptions can contain DSNs. Never print credentials.
        print(f'Database setup failed ({type(exc).__name__}). Check the local PostgreSQL service and private state file.', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    sys.exit(main())
