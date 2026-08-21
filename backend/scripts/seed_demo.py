"""Seed the demo catalog into the DB (make seed-demo step 2)."""
import asyncio

from app.db.session import get_sessionmaker, init_db
from app.ingest.demo import load_demo_catalog


async def main() -> None:
    await init_db()
    async with get_sessionmaker()() as session:
        catalog_id = await load_demo_catalog(session)
    print(f"demo catalog ready: {catalog_id}")


if __name__ == "__main__":
    asyncio.run(main())
