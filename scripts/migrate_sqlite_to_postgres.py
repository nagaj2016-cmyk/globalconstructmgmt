#!/usr/bin/env python3
"""Copy NagaForge data from SQLite into PostgreSQL.

The target PostgreSQL database should be empty. The script creates the schema
from SQLAlchemy models, copies rows in model dependency order, and resets
PostgreSQL sequences.
"""
import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import MetaData, Table, create_engine, func, inspect, select, text


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", default="/opt/nagaforge-gpt")
    parser.add_argument("--sqlite", required=True)
    parser.add_argument("--postgres-url", required=True)
    return parser.parse_args()


VALUE_NORMALIZERS = {
    ("nc_reports", "severity"): {
        "minor": "low",
        "major": "high",
        "severe": "critical",
    },
    ("safety_incidents", "severity"): {
        "minor": "low",
        "major": "high",
        "severe": "critical",
    },
}


def chunked(items, size=500):
    for index in range(0, len(items), size):
        yield items[index:index + size]


def normalize_value(table_name, column_name, value):
    if value is None:
        return value
    mapping = VALUE_NORMALIZERS.get((table_name, column_name))
    if not mapping:
        return value
    return mapping.get(str(value).lower(), value)


def normalize_row(table_name, row, target_columns):
    return {
        key: normalize_value(table_name, key, value)
        for key, value in dict(row).items()
        if key in target_columns
    }


def reset_sequence(conn, table_name):
    sequence = conn.execute(
        text("SELECT pg_get_serial_sequence(:table_name, 'id')"),
        {"table_name": table_name},
    ).scalar()
    if not sequence:
        return
    max_id = conn.execute(text(f'SELECT COALESCE(MAX(id), 0) FROM "{table_name}"')).scalar()
    if not max_id:
        conn.execute(text("SELECT setval(:sequence, 1, false)"), {"sequence": sequence})
        return
    conn.execute(text("SELECT setval(:sequence, :max_id, :called)"), {
        "sequence": sequence,
        "max_id": max_id,
        "called": True,
    })


def main():
    args = parse_args()
    app_dir = Path(args.app_dir).resolve()
    backend_dir = app_dir / "backend"
    sqlite_path = Path(args.sqlite).resolve()

    if not sqlite_path.exists():
        raise SystemExit(f"SQLite database not found: {sqlite_path}")

    os.environ["DATABASE_URL"] = args.postgres_url
    sys.path.insert(0, str(backend_dir))

    from database import Base  # noqa: WPS433
    import models  # noqa: F401,WPS433  (registers tenant tables + mixin columns)
    import platform_models  # noqa: F401,WPS433  (registers roles/i18n/country tables)

    sqlite_engine = create_engine(f"sqlite:///{sqlite_path}", connect_args={"check_same_thread": False})
    postgres_engine = create_engine(args.postgres_url)

    Base.metadata.create_all(bind=postgres_engine)

    source_inspector = inspect(sqlite_engine)
    source_tables = set(source_inspector.get_table_names())
    target_meta = MetaData()
    target_meta.reflect(bind=postgres_engine)

    copied = {}
    with sqlite_engine.connect() as source_conn, postgres_engine.begin() as target_conn:
        for model_table in Base.metadata.sorted_tables:
            table_name = model_table.name
            if table_name not in source_tables or table_name not in target_meta.tables:
                continue

            source_table = Table(table_name, MetaData(), autoload_with=sqlite_engine)
            target_table = target_meta.tables[table_name]
            target_columns = {column.name for column in target_table.columns}
            existing_count = target_conn.execute(select(func.count()).select_from(target_table)).scalar() or 0
            if existing_count:
                print(f"skip {table_name}: target already has {existing_count} rows")
                continue

            rows = source_conn.execute(select(source_table)).mappings().all()
            if not rows:
                copied[table_name] = 0
                continue

            payload = [normalize_row(table_name, row, target_columns) for row in rows]
            for batch in chunked(payload):
                target_conn.execute(target_table.insert(), batch)
            copied[table_name] = len(payload)
            print(f"copied {table_name}: {len(payload)} rows")

        for table_name in copied:
            if table_name in target_meta.tables and "id" in target_meta.tables[table_name].columns:
                reset_sequence(target_conn, table_name)

    # Seed platform tables (roles, languages, country code packs, proofs) and
    # ensure tenant columns / demo account exist on the PostgreSQL target. This
    # is the same idempotent routine the app runs on boot, so the migrated DB is
    # immediately consistent even before the first request.
    try:
        import migrate_platform  # noqa: WPS433 (backend_dir already on sys.path)
        result = migrate_platform.run()
        print("Platform seed:", {k: result[k] for k in ("roles_added", "i18n", "demo")})
    except Exception as exc:  # pragma: no cover
        print(f"WARNING: platform seed step failed ({exc}). "
              "It will run automatically on the next app start.")

    print("Migration complete.")


if __name__ == "__main__":
    main()
