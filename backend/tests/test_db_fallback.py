"""Database resilience + DDL portability guards.

Two ways production has silently degraded to ephemeral SQLite:
1. one-shot primary connect at boot (release-window races) → bounded retries;
2. non-portable CHECK DDL that Postgres rejects at CREATE TABLE.
"""
import app.db.session as dbmod


async def test_unreachable_primary_falls_back_after_retries(monkeypatch):
    """A dead primary exhausts its retries, then lands loudly on SQLite."""
    monkeypatch.setattr(dbmod, "_PRIMARY_CONNECT_ATTEMPTS", 2)
    monkeypatch.setattr(dbmod, "_PRIMARY_RETRY_BACKOFF_S", (0.0,))
    monkeypatch.setattr(
        dbmod.get_settings(),
        "database_url",
        "postgresql+asyncpg://probe:probe@127.0.0.1:9/probe",
    )

    saved = (dbmod._DbState.engine, dbmod._DbState.maker)
    try:
        dbmod._DbState.engine = None
        dbmod._DbState.maker = None

        ok = await dbmod.init_db()

        assert ok is False  # degraded mode signalled to the lifespan caller
        assert dbmod.get_engine().url.drivername.startswith("sqlite")
        # diagnostics captured for the /api/dbstatus ops probe
        assert "127.0.0.1:9" in dbmod._DbState.primary_endpoint
        assert dbmod._DbState.last_primary_error
    finally:
        eng = saved[0]
        cur = dbmod._DbState.engine
        if cur is not None and cur is not eng:
            await cur.dispose()
        dbmod._DbState.engine, dbmod._DbState.maker = saved


def test_trials_choice_constraint_is_ddl_portable():
    """Guard the exact bug that stranded prod on SQLite: Boolean columns must
    never be compared to integer literals inside CHECK constraints."""
    constraints = {
        c.name: str(c.sqltext).lower()
        for c in __import__("app.db.models", fromlist=["Base"]).Base.metadata.tables[
            "trials"
        ].constraints
        if c.name
    }
    sql = constraints["ck_trials_choice_semantics"]
    assert "= 0" not in sql and "= 1" not in sql
    assert "not parse_ok" in sql and "null_allowed" in sql
