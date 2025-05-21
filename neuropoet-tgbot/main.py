import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher

import src.commands as commands

logging.basicConfig(level=logging.INFO)
load_dotenv()


async def main():
    API_TOKEN = os.getenv("NPB_API_TOKEN")
    if not API_TOKEN:
        raise ValueError('NPB_API_TOKEN is not set')

    bot = Bot(token=API_TOKEN)
    dp = Dispatcher()
    commands.set_bot(bot)

    dp.include_router(commands.router)
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())