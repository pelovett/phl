import asyncio
import logging
import sys

from phl.agent import get_model
from phl.cron import loop as cron_loop
from phl.db import Database
from phl.telegram import build_app, register_handlers

logging.basicConfig(
    format="%(asctime)s | %(name)s | %(levelname)s : %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
    level=logging.INFO,
)

logging.getLogger("httpx").setLevel(logging.WARNING)


async def run():
    async with Database() as db:
        await db.migrate()
        telegram_app, telegram_user_id = build_app()
        agent = get_model(db, telegram_app.bot, telegram_user_id)
        register_handlers(telegram_app, agent, telegram_user_id)

        async with telegram_app:
            await telegram_app.start()
            if not telegram_app.updater:
                raise ValueError("Couldn't find telegram_app.updater !")
            await telegram_app.updater.start_polling()
            await cron_loop(db, agent.run_prompt)
            await telegram_app.updater.stop()
            await telegram_app.stop()


def main():
    asyncio.run(run())


if __name__ == "__main__":
    main()
