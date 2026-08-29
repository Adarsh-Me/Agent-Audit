"""cache_put must compile against BOTH dialects (2026-08-29 live-fire fix).

The old sqlite-only upsert raised AttributeError at execute time on Postgres,
which the runner's engine-error hatch converted into parse_ok=false for every
single successful LLM call — the root cause of all 0/N usable-answer runs.
"""
from sqlalchemy.dialects import postgresql, sqlite

from app.engine.cache import _on_conflict_insert


def test_upsert_compiles_on_sqlite():
    stmt = _on_conflict_insert("h", "m", {"product_id": "sku_001", "reason": "r"},
                               dialect_name="sqlite")
    sql = str(stmt.compile(dialect=sqlite.dialect()))
    assert "INSERT INTO response_cache" in sql
    assert "ON CONFLICT" in sql


def test_upsert_compiles_on_postgres():
    stmt = _on_conflict_insert("h", "m", {"product_id": "sku_001", "reason": "r"},
                               dialect_name="postgresql")
    sql = str(stmt.compile(dialect=postgresql.dialect()))
    assert "INSERT INTO response_cache" in sql
    assert "ON CONFLICT" in sql


def test_sqlite_only_upsert_fails_on_pg_documents_the_bug():
    """Documents the original defect: the sqlite-dialect insert cannot compile
    under the postgresql dialect — exactly what broke deployed runs."""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert

    from app.db.models import ResponseCache

    stmt = sqlite_insert(ResponseCache).values(
        prompt_hash="h", model_version="m", response={"a": 1})
    stmt = stmt.on_conflict_do_nothing()
    try:
        str(stmt.compile(dialect=postgresql.dialect()))
        raised = False
    except AttributeError:
        raised = True
    assert raised, "sqlite upsert unexpectedly compiled on PG — bug no longer reproducible"
