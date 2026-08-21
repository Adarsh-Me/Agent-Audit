"""Mark a stuck run terminal: python -m scripts.fail_run <run_id> [reason]"""
import asyncio
import sys
from datetime import datetime, timezone


async def main() -> None:
    from sqlalchemy import func, select

    from app.db.models import Run, Trial
    from app.db.session import get_sessionmaker

    run_id = sys.argv[1]
    reason = sys.argv[2] if len(sys.argv) > 2 else "manual abort"
    maker = get_sessionmaker()
    async with maker() as s:
        run = await s.get(Run, run_id)
        if run is None:
            raise SystemExit(f"run {run_id} not found")
        n = (await s.execute(
            select(func.count()).select_from(Trial).where(Trial.run_id == run_id)
        )).scalar()
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        await s.commit()
        print(f"run {run_id} -> failed ({n} trial rows kept); reason: {reason}")


asyncio.run(main())
