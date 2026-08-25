"""init_db resilience — bounded primary retries before the SQLite fallback."""
import app.db.session as dbmod


async def test_unreachable_primary_falls_back_after_retries(monkeypatch):
    """A dead primary exhausts its retries, then lands loudly on SQLite."""
    # shrink the wait so the suite stays fast; the loop logic is what matters
    monkeypatch.setattr(dbmod, "_PRIMARY_CONNECT_ATTEMPTS", 2)
    monkeypatch.setattr(dbmod, "_PRIMARY_RETRY_BACKOFF_S", (0.0,))

    saved = (dbmod._DbState.engine, dbmod._DbState.maker)
    try:
        # point the "primary" at a closed local port → instant refusal
        dbmod._DbState.engine = None
        dbmod._DbState.maker = None
        dbmod._use("postgresql+asyncpg://probe:probe@127.0.0.1:9/probe")

        ok = await dbmod.init_db()

        assert ok is False  # degraded mode signalled to the lifespan caller
        assert dbmod.get_engine().url.drivername.startswith("sqlite")
    finally:
        if dbmod._DbState.engine is not saved[0] and dbmod._DbState.engine is not None:
            await dbmod._DbState.engine.dispose()
        dbmod._DbState.engine, dbmod._DbState.maker = saved
