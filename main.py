"""Application entry point."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "portfolio-service"))
from backend.db import portfolio_engine


async def main() -> None:
    await portfolio_engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
