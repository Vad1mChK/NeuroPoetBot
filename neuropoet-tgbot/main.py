import asyncio
import logging
import os
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.filters.command import Command

logging.basicConfig(level=logging.INFO)

load_dotenv()
API_TOKEN = os.getenv("NPB_API_TOKEN")
if API_TOKEN is None:
    raise EnvironmentError('NPB_API_TOKEN is not set')

bot = Bot(token=API_TOKEN)
dp = Dispatcher()


@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Hello!")


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    command_list = await bot.get_my_commands()
    command_list_formatted = '\n'.join(
        (f'/{command.command}: {command.description}' for command in command_list)
    )
    await message.answer(command_list_formatted)


async def main():
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
