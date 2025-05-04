import asyncio
import logging
import re
from typing import Callable
from pathlib import Path

from aiogram import Router, types, Bot
from aiogram.filters.command import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ReactionTypeEmoji

from util.emoji import Emoji
from util.markdown import escape_markdown
from util.telegram.restrictions import owner_only_command, get_owner_ids
from globals import emotion_api, poetry_api, database

ABOUT_FILE = Path(__file__).parent.parent / "res" / "about.md"

router = Router()
bot: Bot = None


def set_bot(new_bot: Bot):
    global bot
    bot = new_bot


async def owner_only_permission_denied(message: types.Message):
    await message.reply("Эта команда доступна только владельцам бота.")


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("Hello!")


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    command_list = await bot.get_my_commands()
    command_list_formatted = '\n'.join(
        f'/{cmd.command}: {cmd.description}' for cmd in command_list
    )
    await message.answer(command_list_formatted)


@router.message(Command("about"))
async def cmd_about(message: types.Message):
    try:
        about_text = ABOUT_FILE.read_text(encoding="utf-8")
        await message.reply(text=about_text, parse_mode='Markdown', disable_web_page_preview=True)
    except FileNotFoundError:
        await message.reply("ℹ️ Информация о боте временно недоступна")


@router.message(Command("history"))
async def cmd_history(message: types.Message):
    try:
        user_id = message.from_user.id
        args = message.text.split()[1:]  # Получаем аргументы команды

        # Парсим лимит записей
        limit = 5  # Значение по умолчанию
        if args and args[0].isdigit():
            limit = min(int(args[0]), 20)  # Максимум 20 записей

        # Получаем историю из базы данных
        history = database.get_user_history(user_id=user_id, limit=limit)

        # Форматируем сообщение
        response = []
        if not history['emotions'] and not history['generations']:
            await message.answer("📭 Ваша история пуста")
            return

        # Форматируем эмоции
        if history['emotions']:
            response.append("*📊 Последние анализы эмоций:*")
            for idx, emotion in enumerate(history['emotions'], 1):
                date = emotion.performed_at.strftime("%d.%m.%Y %H:%M")
                emotions = ", ".join(
                    escape_markdown(f"{k}: {v:.2f}") for k, v in emotion.emotions.items()
                )
                response.append(
                    f"{idx}\\. *{escape_markdown(date)}*\n"
                    f"Эмоции: {escape_markdown(emotions)}"
                )

        # Форматируем генерации
        if history['generations']:
            response.append("\n*🖋 Последние генерации:*")
            for idx, gen in enumerate(history['generations'], 1):
                date = gen.performed_at.strftime("%d.%m.%Y %H:%M")
                response.append(
                    f"{idx}\\. *{escape_markdown(date)}*\n"
                    f"Запрос: {escape_markdown(gen.request_text)}\n"
                    f"Ответ: {escape_markdown(gen.response_text)}"
                )

        # Отправляем сообщение
        await message.reply(
            text="\n\n".join(response),
            parse_mode="MarkdownV2"
        )

    except Exception as e:
        logging.error(f"History error: {str(e)}")
        await message.reply("❌ Не удалось загрузить историю")


@router.message(Command("health"))
async def cmd_health(message: types.Message):
    sent_reply = await message.reply("🩺 Проверка статуса сервисов...")
    service_order = ['emotion', 'poetry', 'database']
    status = {name: "checking" for name in service_order}  # checking/success/error

    try:
        await message.react(reaction=[ReactionTypeEmoji(emoji=Emoji.THINK.emoji)])

        async def update_message():
            """Обновляем сообщение с текущими статусами"""
            lines = []
            for name in service_order:
                if status[name] == "checking":
                    line = f"{Emoji.HOURGLASS.emoji} {name.capitalize()}: Проверяется..."
                elif status[name] == "success":
                    line = f"{Emoji.CHECK_MARK.emoji} {name.capitalize()}: Работает"
                else:
                    line = f"{Emoji.CROSSOUT.emoji} {name.capitalize()}: Ошибка"
                lines.append(line)

            await sent_reply.edit_text("\n".join(lines))

        # Первоначальное сообщение с индикаторами прогресса
        await update_message()

        async def check_service(name: str, checker: Callable):
            """Проверяем один сервис и обновляем статус"""
            try:
                # Запускаем проверку с таймаутом
                result = await asyncio.wait_for(
                    checker() if asyncio.iscoroutinefunction(checker)
                    else asyncio.to_thread(checker),
                    timeout=10
                )
                status[name] = "success" if result else "error"
            except Exception as e:
                status[name] = "error"
                logging.error(f"Health check failed for {name}: {str(e)}")
            finally:
                await update_message()  # Обновляем после каждой проверки

        # Параллельный запуск всех проверок
        await asyncio.gather(*[
            check_service(name, service.check_health)
            for name, service in {
                'emotion': emotion_api,
                'poetry': poetry_api,
                'database': database
            }.items()
        ])

        # Финальная реакция
        final_emoji = Emoji.THUMBS_UP if all(v == "success" for v in status.values()) else Emoji.THUMBS_DOWN
        await message.react(reaction=[ReactionTypeEmoji(emoji=final_emoji.emoji)])

    except Exception as e:
        await sent_reply.edit_text(f"❌ Критическая ошибка: {str(e)}")
        await message.react(reaction=[ReactionTypeEmoji(emoji=Emoji.WARNING.emoji)])


@router.message(Command("user_data"))
async def cmd_user_data(message: types.Message):
    from random import random

    emotion_dict = {
        'happy': random(),
        'sad': random(),
        'anger': random(),
        'fear': random(),
        'surprise': random(),
        'disgust': random(),
    }

    emotion_to_emoji = {
        'happy': '😁',
        'sad': '😢',
        'anger': '😡',
        'fear': '😱',
        'surprise': '🤯',
        'disgust': '🤮'
    }

    prevailing_emotion = max(emotion_dict, key=emotion_dict.get)

    try:
        await message.react(
            reaction=[ReactionTypeEmoji(emoji=emotion_to_emoji[prevailing_emotion])]
        )
    except TelegramBadRequest as e:
        pass

    await message.answer(
        f"You are {message.from_user}\n"
        f"Emotions: {emotion_dict}\n"
        f"Prevailing emotion: {emotion_to_emoji[prevailing_emotion]}{prevailing_emotion}"
    )


@router.message(Command("owners"))
@owner_only_command(default_action=owner_only_permission_denied)
async def cmd_owners(message: types.Message):
    owners_string = ("\\[" +
                     ", ".join([f"`{owner_id}`" for owner_id in get_owner_ids()]) +
                     "\\]")

    await message.reply(
        text=
            f"Владельцы бота: {owners_string}\n" +
            f"Вы `{message.from_user.id}`",
        parse_mode='MarkdownV2'
    )
