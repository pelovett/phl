import asyncio
import logging
import sys

from phl.agent import get_model
from phl.cron import loop as cron_loop
from phl.db import Database
from phl.telegram import get_app

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s : %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO,
)


async def run():
    async with Database() as db:
        await db.migrate()
        agent = get_model(db)
        telegram_app = get_app(agent)

        async with telegram_app:
            await telegram_app.start()
            if not telegram_app.updater:
                raise ValueError("Couldn't find telegram_app.updater !")
            await telegram_app.updater.start_polling()
            await cron_loop(db)
            await telegram_app.updater.stop()
            await telegram_app.stop()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
