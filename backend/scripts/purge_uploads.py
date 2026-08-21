"""Purge uploaded catalogs older than 7 days (cron/management command)."""
import argparse
import asyncio

from app.db.session import get_sessionmaker, init_db
from app.ingest.upload import purge_expired_uploads


async def main(dry_run: bool) -> None:
    await init_db()
    async with get_sessionmaker()() as session:
        expired = await purge_expired_uploads(session, dry_run=dry_run)
    label = "would purge" if dry_run else "purged"
    print(f"{label} {len(expired)} upload catalog(s): {expired or 'none'}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Purge uploads older than 7 days")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    asyncio.run(main(args.dry_run))
