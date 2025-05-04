import asyncio
import json
import logging
import re
from typing import Callable
from pathlib import Path

from aiogram import Router, types, Bot
from aiogram.filters.command import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ReactionTypeEmoji

from api.emotion_api import EmotionAnalyzeRequestDto
from api.poetry_api import PoetryGenerationRequestDto
from util.emoji import Emoji
from util.markdown import escape_markdown
from util.telegram.restrictions import owner_only_command, get_owner_ids
from globals import get_global_state as gs

ABOUT_FILE = Path(__file__).parent.parent / "res" / "about.md"
additional_command_list = {
    'owners': 'Выводит список ID владельцев бота'
}

router = Router()
bot: Bot = None


def set_bot(new_bot: Bot):
    global bot
    bot = new_bot


async def owner_only_permission_denied(message: types.Message):
    await message.reply("Эта команда доступна только владельцам бота.")


@router.message(Command("start"))
async def cmd_start(message: types.Message):
    database = await gs().get_database()
    database.add_user(user_id=message.from_user.id)
    await message.answer("Hello!")


@router.message(Command("help"))
async def cmd_help(message: types.Message):
    command_list = await bot.get_my_commands()
    command_list_formatted = '\n'.join(
        f'/{cmd.command}: {cmd.description}' for cmd in command_list
    )
    if message.from_user.id in get_owner_ids():
        command_list_formatted += '\nДополнительные команды для владельцев:\n'
    command_list_formatted += '\n'.join(
        f'/{cmd[0]}: {cmd[1]}' for cmd in additional_command_list.items()
    )

    await message.answer(command_list_formatted)


@router.message(Command("about"))
async def cmd_about(message: types.Message):
    try:
        about_text = ABOUT_FILE.read_text(encoding="utf-8")
        await message.reply(text=about_text, parse_mode='Markdown', disable_web_page_preview=True)
    except FileNotFoundError:
        await message.reply("ℹ️ Информация о боте временно недоступна")


@router.message(Command("emotions"))
async def cmd_emotions(message: types.Message):
    try:
        # Extract command text
        command, *args = message.text.split(maxsplit=1)
        text = args[0] if args else ""

        if not text:
            await message.reply("❌ Напишите текст после команды: /emotions <текст>")
            return

        # Get API instance from global state
        api = await gs().get_emotion_api()

        # Process request
        request = EmotionAnalyzeRequestDto(
            user_id=message.from_user.id,
            message=text
        )

        response = await api.analyze_emotions(request)

        print(response)

        if response:
            # Safe JSON formatting with markdown escaping
            emotions_json = escape_markdown(json.dumps(response.emotions, indent=2, ensure_ascii=False))

            database = await gs().get_database()
            database.log_emotion_analysis(user_id=message.from_user.id, emotions=response.emotions)

            await message.reply(
                f"📊 Распознанные эмоции:\n```json\n{emotions_json}\n```",
                parse_mode='MarkdownV2'
            )
        else:
            await message.reply("❌ Сервис анализа эмоций недоступен")

    except Exception as e:
        logging.error(f"Emotion analysis error: {str(e)}", exc_info=True)
        await message.reply("❌ Ошибка анализа эмоций")


@router.message(Command("generate"))
async def cmd_format(message: types.Message):
    try:
        # Extract command text
        command, *args = message.text.split(maxsplit=1)
        text = args[0] if args else ""

        if not text:
            await message.reply("❌ Напишите текст после команды: /generate <текст>")
            return

        # Get API instance from global state
        emotion_api = await gs().get_emotion_api()
        poetry_api = await gs().get_poetry_api()
        database = await gs().get_database()

        # Process request
        emotion_request = EmotionAnalyzeRequestDto(
            user_id=message.from_user.id,
            message=text
        )
        emotion_response = await emotion_api.analyze_emotions(emotion_request)

        if not emotion_response:
            await message.reply("❌ Сервис анализа эмоций недоступен")
            return

        emotions = emotion_response.emotions
        database.log_emotion_analysis(user_id=message.from_user.id, emotions=emotions)

        poetry_request = PoetryGenerationRequestDto(
            user_id=message.from_user.id,
            emotions=emotions
        )
        poetry_response = await poetry_api.generate_poem(poetry_request)

        if not poetry_response:
            await message.reply("❌ Сервис генерации стихотворений недоступен")
            return

        poem = poetry_response.poem
        database.log_generation(
            user_id=message.from_user.id,
            request_text=text,
            response_text=poem
        )

        await message.reply(
            f"📃 *Сгенерированное стихотворение*:\n{escape_markdown(poem)}",
            parse_mode='MarkdownV2'
        )

    except Exception as e:
        logging.error(f"Poem generation error: {str(e)}", exc_info=True)
        await message.reply("❌ Ошибка генерации стихотворения")


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
        history = (await gs().get_database()).get_user_history(user_id=user_id, limit=limit)

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
                print(emotion.emotions.items())
                top_emotion = max(emotion.emotions.items(), key=lambda x: x[1])
                top_emotion_str = f"{top_emotion[0]} ({top_emotion[1]})"
                response.append(
                    f"{idx}\\. *{escape_markdown(date)}*\n"
                    f"*Преобладает эмоция*: {escape_markdown(top_emotion_str)}"
                    # f"*Эмоции*: ```json\n{json.dumps(emotion.emotions)}\n```"
                )

        # Форматируем генерации
        if history['generations']:
            response.append("\n*🖋 Последние генерации:*")
            for idx, gen in enumerate(history['generations'], 1):
                date = gen.performed_at.strftime("%d.%m.%Y %H:%M")
                response.append(
                    f"{idx}\\. *{escape_markdown(date)}*\n"
                    f"*Запрос*: {escape_markdown(gen.request_text)}\n"
                    f"*Ответ*: {escape_markdown(gen.response_text)}"
                )

        # Отправляем сообщение
        await message.reply(
            text="\n".join(response),
            parse_mode="MarkdownV2"
        )

    except Exception as e:
        logging.error(f"History error: {str(e)}")
        await message.reply("❌ Не удалось загрузить историю")

@router.message(Command("stats"))
async def cmd_stats(message: types.Message):
    try:
        # Получаем данные
        db = await gs().get_database()
        user_data = db.get_user_data(message.from_user.id)

        # Форматируем дату регистрации
        join_date = user_data.registered_at.strftime("%d.%m.%Y %H:%M") if user_data else "неизвестно"

        # Получаем и агрегируем эмоции
        emotions = {}
        history = db.get_user_history(message.from_user.id)

        if history['emotions']:
            # Собираем средние значения
            counter = {}
            for record in history['emotions']:
                for emotion, score in record.emotions.items():
                    emotions[emotion] = emotions.get(emotion, 0) + score
                    counter[emotion] = counter.get(emotion, 0) + 1

            # Вычисляем среднее и форматируем
            emotions_avg = {
                emo: total / counter[emo]
                for emo, total in emotions.items()
            }
            emotions_text = "\n".join(
                f"{emo}: {val:.2f}"
                for emo, val in sorted(emotions_avg.items(), key=lambda x: -x[1])
            )
        else:
            emotions_text = "Нет данных об эмоциях"

        # Формируем ответ
        response = (
            f"👤 *{escape_markdown(message.from_user.full_name)}* "
            f"\\(aka @{escape_markdown(message.from_user.username)}, `{message.from_user.id}`\\)\n"
            f"📊 *Ваша статистика*\n\n"
            f"🕐 Дата регистрации: {escape_markdown(join_date)}\n"
            f"📈 Средние эмоции:\n{escape_markdown(emotions_text)}"
        )

        await message.reply(
            text=response,
            parse_mode="MarkdownV2",
            disable_web_page_preview=True
        )

    except Exception as e:
        logging.error(f"Stats error: {str(e)}", exc_info=True)
        await message.reply("❌ Не удалось загрузить статистику")

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
                'emotion': await gs().get_emotion_api(),
                'poetry': await gs().get_poetry_api(),
                'database': await gs().get_database()
            }.items()
        ])

        # Финальная реакция
        final_emoji = Emoji.THUMBS_UP if all(v == "success" for v in status.values()) else Emoji.THUMBS_DOWN
        await message.react(reaction=[ReactionTypeEmoji(emoji=final_emoji.emoji)])

    except Exception as e:
        await sent_reply.edit_text(f"❌ Критическая ошибка: {str(e)}")
        await message.react(reaction=[ReactionTypeEmoji(emoji=Emoji.WARNING.emoji)])


@router.message(Command("random_poem"))
async def cmd_random_poem(message: types.Message):
    try:
        database = await gs().get_database()
        poem = database.get_random_poem_fast()
        if poem is not None:
            await message.reply(f"*Случайное стихотворение*:\n{escape_markdown(poem)}", parse_mode="MarkdownV2")
        else:
            await message.reply("❌ Не найдено ни одного стихотворения")


    except Exception as e:
        logging.error(f"Stats error: {str(e)}", exc_info=True)
        await message.reply("❌ Не удалось загрузить стихотворение")


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
