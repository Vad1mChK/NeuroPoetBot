import asyncio
import json
import logging
from typing import Callable
from pathlib import Path

from aiogram import Router, types, Bot, F
from aiogram.filters.command import Command
from aiogram.exceptions import TelegramBadRequest
from aiogram.types import ReactionTypeEmoji, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, \
    BufferedInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder

from database.database import GenerationModel, get_default_user_settings
from .api.emotion_api import EmotionAnalyzeRequestDto
from .api.poetry_api import PoetryGenerationRequestDto
from .util.emoji import Emoji
from .util.markdown import escape_markdown
from .util.telegram.restrictions import owner_only_command, get_owner_ids
from .util.text import truncate_text
from .globals import get_global_state as gs

ABOUT_FILE = Path(__file__).parent.parent / "res" / "about.md"
additional_command_list = {
    'owners': 'Выводит список ID владельцев бота',
    'get_feedback': 'Выводит статистику по обратной связи',
    'export_feedback': 'Экспортирует отзывы о боте в JSON',
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
    description = await bot.get_my_description()

    start_text = (
        f"👋 {escape_markdown(description.description)}\n"
        "*С чего ты хотел бы начать*?"
    )

    # Define buttons explicitly corresponding to commands
    command_buttons = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🪪 О боте", callback_data="command:about")],
        [InlineKeyboardButton(text="❔ Список доступных команд", callback_data="command:help")],
        [InlineKeyboardButton(text="🎲 Случайное стихотворение", callback_data="command:random_poem")],
        [InlineKeyboardButton(text="🗨 Оставить отзыв", callback_data="command:feedback")],
        # Add other buttons if you have more commands
    ])

    await message.answer(
        start_text,
        parse_mode="MarkdownV2",
        reply_markup=command_buttons
    )


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

        reply_message = await message.reply('⌛ Выполняется анализ эмоций...')

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

            top_emotion = max(
                response.emotions.keys(),
                key=lambda x: response.emotions.get(x, 0.0)
            ) or "no_emotion"
            top_emotion_percentage = int(response.emotions.get(top_emotion, 0) * 100)
            emojis: dict[str, Emoji] = {
                "joy": Emoji.BIG_SMILE,
                "sad": Emoji.TEAR,
                "sadness": Emoji.TEAR,
                "fear": Emoji.FEAR,
                "anger": Emoji.ANGER,
                "surprise": Emoji.SURPRISE,
                "disgust": Emoji.DISGUST,
                "neutral": Emoji.NEUTRAL,
                "no_emotion": Emoji.NEUTRAL,
            }
            top_emoji = emojis.get(top_emotion, Emoji.NEUTRAL).emoji
            await reply_message.edit_text(
                (
                    f"📊 Распознанные эмоции:\n```json\n{emotions_json}\n```\n"
                    f"🥇 Топовая эмоция: {top_emoji}{top_emotion}{top_emoji} \\({top_emotion_percentage}%\\)"
                ),
                parse_mode='MarkdownV2'
            )

            try:
                await message.react(
                    reaction=[ReactionTypeEmoji(emoji=top_emoji)]
                )
            except TelegramBadRequest as e:
                print(e)
        else:
            await reply_message.edit_text("❌ Ошибка анализа эмоции")

    except Exception as e:
        logging.error(f"Emotion analysis error: {str(e)}", exc_info=True)
        await message.reply("❌ Ошибка анализа эмоций")


@router.message(Command("generate"))
async def cmd_generate(message: types.Message):
    try:
        # Extract command text
        command, *args = message.text.split(maxsplit=1)
        text = args[0] if args else ""

        if not text:
            await message.reply("❌ Напишите текст после команды: /generate <текст>")
            return

        reply_message = await message.reply('⌛ Выполняется анализ эмоций...')

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
            await reply_message.edit_text("❌ Ошибка при анализе эмоции")
            return

        emotions = emotion_response.emotions
        database.log_emotion_analysis(user_id=message.from_user.id, emotions=emotions)
        top_emotion = max(emotions.keys(), key=lambda x: emotions.get(x, 0.0))
        top_emotion_percentage = int(emotions.get(top_emotion, 0) * 100)

        await reply_message.edit_text(
            "📈 Анализ эмоций выполнен\n"
            f"*Преобладает эмоция*: {top_emotion} \\({top_emotion_percentage}%\\)\n"
            "⌛ Выполняется генерация стихотворения",
            parse_mode="MarkdownV2"
        )
        user_settings = database.get_user_data(message.from_user.id).user_settings

        poetry_request = PoetryGenerationRequestDto(
            user_id=message.from_user.id,
            emotions=emotions,
            gen_strategy=user_settings.get("preferred_model", "deepseek")
        )
        poetry_response = await poetry_api.generate_poem(poetry_request)

        if not poetry_response:
            await reply_message.edit_text("❌ Ошибка при генерации стихотворения")
            return

        poem = poetry_response.poem

        generation_record = database.log_generation(
            user_id=message.from_user.id,
            request_text=text,
            emotions=emotions,
            response_text=poem,
            model=poetry_response.gen_strategy,
            rhyme_scheme=poetry_response.rhyme_scheme,
            genre=poetry_response.genre,
        )
        # Explicitly define rating buttons
        rating_buttons = InlineKeyboardMarkup(
            inline_keyboard=[[
                InlineKeyboardButton(text=f"⭐{i}", callback_data=f"rating:{generation_record.id}:{i}")
                for i in range(1, 6)
            ]]
        )


        await reply_message.edit_text(
            (
                f"📃 *Сгенерированное стихотворение*:\n{escape_markdown(poem)}\n\n"
                f"📈 *Преобладает эмоция*: {top_emotion} \\({top_emotion_percentage}%\\)\n"
                f"✒ *Схема рифмовки*: {escape_markdown(poetry_response.rhyme_scheme)}\n"
                f"💡 *Жанр*: {escape_markdown(poetry_response.genre)}\n"
                f"🧠 *Модель*: `{poetry_response.gen_strategy}`\n\n"
                "_Оцените генерацию!_"
            ),
            parse_mode='MarkdownV2',
            reply_markup=rating_buttons
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
                    f"*Ответ*: {escape_markdown(
                        truncate_text(gen.response_text)
                    )}"
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


@router.message(Command("random_poem"))
async def cmd_random_poem(message: types.Message):
    try:
        database = await gs().get_database()
        poem = database.get_random_poem_fast()

        if poem is None:
            await message.reply("❌ Не найдено ни одного стихотворения")
            return

        generation_id = poem.id  # Assume get_random_poem_fast returns the Generation object directly
        user_id = message.from_user.id

        # Check explicitly if user has rated the poem
        user_already_rated = database.has_user_rated(user_id, generation_id)

        # Get explicit average rating
        avg_rating = poem.average_rating()
        avg_rating_text = f"\n⭐ Средняя оценка: {avg_rating:.1f}/5" if avg_rating else ""

        reply_markup = None
        if not user_already_rated:
            # Define explicit rating buttons
            reply_markup = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text=f"⭐{i}", callback_data=f"rating:{generation_id}:{i}")
                for i in range(1, 6)
            ]])

        await message.reply(
            f"*Случайное стихотворение*:\n"
            f"{escape_markdown(poem.response_text)}"
            f"{escape_markdown(avg_rating_text)}",
            parse_mode="MarkdownV2",
            reply_markup=reply_markup
        )

    except Exception as e:
        logging.error(f"Random poem error: {str(e)}", exc_info=True)
        await message.reply("❌ Не удалось загрузить стихотворение")

@router.message(Command("feedback"))
async def cmd_feedback(message: types.Message):
    star_buttons = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=f"⭐{i}",
            callback_data=f"feedback:{i}"
        ) for i in range(1, 6)
    ]])

    sent_msg = await message.reply(
        "Пожалуйста, оцените бота:",
        reply_markup=star_buttons
    )


@router.message(Command("settings"))
async def cmd_settings(message: types.Message):
    database = await gs().get_database()
    user = database.get_user_data(message.from_user.id)

    current_settings = get_default_user_settings()
    current_settings.update(user.user_settings or {})

    await message.answer(
        "⚙️ *Настройки пользователя*",
        parse_mode="MarkdownV2",
        reply_markup=get_settings_keyboard(current_settings)
    )


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


@router.message(Command("get_feedback"))
@owner_only_command(default_action=owner_only_permission_denied)
async def cmd_get_feedback(message: types.Message):
    database = await gs().get_database()
    summary = database.get_feedback_summary()

    def format_feedback(title, feedback):
        if feedback:
            msg = feedback['message'] or "(нет комментария)"
            return (
                f"🔹 *{title}*\n"
                f"Рейтинг: ⭐{feedback['rating']}\n"
                f"Комментарий: _{escape_markdown(msg)}_\n"
                f"Дата: {escape_markdown(feedback['created_at'])}\n"
            )
        else:
            return f"🔹 *{title}*: Нет данных\n"

    reply_text = (
        f"📊 *Статистика отзывов:*\n"
        f"Средний рейтинг: ⭐ {escape_markdown(str(summary['average_rating'])) or 'нет данных'}\n\n"
        f"Средний рейтинг \\(генерации\\): ⭐ {escape_markdown(str(summary['avg_gen_rating']))}\n"
        "• по моделям:\n"
        + "\n".join(
            f"  • `{entry[0]}`: ⭐ {escape_markdown(str(entry[1]))}"
            for entry in summary['avg_gen_rating_by_model'].items()
        )
        + "\n\n"
        f"{format_feedback('Лучший отзыв', summary['best_feedback'])}\n"
        f"{format_feedback('Худший отзыв', summary['worst_feedback'])}\n"
        f"{format_feedback('Самый свежий отзыв', summary['newest_feedback'])}\n"
        f"{format_feedback('Самый подробный отзыв', summary['longest_feedback'])}"
    )

    await message.reply(reply_text, parse_mode="MarkdownV2")


@router.message(Command("export_feedback"))
@owner_only_command(default_action=owner_only_permission_denied)
async def cmd_export_feedback(message: types.Message):
    database = await gs().get_database()

    feedback_json = database.export_bot_feedback_json()
    feedback_bytes = feedback_json.encode("utf-8")
    MAX_DISPLAY_LEN = 1024

    file = BufferedInputFile(
        file=feedback_bytes,
        filename="bot_feedback.json"
    )

    summary = (
        "📃 *Содержимое отзывов: *" + f"```json\n{feedback_json}\n```"
        if len(feedback_bytes) <= MAX_DISPLAY_LEN
        else (
            f"📃 *Содержимое отзывов превышает размер для отображения*: {MAX_DISPLAY_LEN} Б, "
            + escape_markdown("поэтому я отправил его файлом.")
        )
    )

    await message.reply_document(
        file,
        caption=(
            escape_markdown("📄 Экспорт отзывов успешно создан.\n")
            + summary
        ),
        parse_mode="MarkdownV2"
    )


# Explicitly ignore clicks on non-clickable button
@router.callback_query(F.data == "ignore")
async def ignore_callback(callback: types.CallbackQuery):
    await callback.answer()  # Silently ignore the click


def get_settings_keyboard(settings: dict):
    builder = InlineKeyboardBuilder()

    # First setting: Generation model
    builder.button(
        text="🔧 Модель генерации: 🔧",
        callback_data="ignore"
    )

    for model in GenerationModel:
        selected_icon = '🔘' if settings.get('preferred_model') == model.value else '⚫'
        builder.button(
            text=f"{selected_icon} {model.value}",
            callback_data=f"settings:preferred_model={model.value}"
        )

    # Additional settings can be added here in future following the same pattern:
    # builder.button("Setting Title", callback_data="ignore")
    # builder.button("(x) option", callback_data="settings:setting_name=value")

    builder.adjust(1, len(list(GenerationModel)))

    return builder.as_markup()

@router.callback_query(F.data.startswith("settings:"))
async def handle_setting(callback: types.CallbackQuery):
    _, pair = callback.data.split(":", 1)
    setting_name, setting_value = pair.split("=", 1)

    user_id = callback.from_user.id
    database = await gs().get_database()

    # Update the user's setting explicitly
    database.update_user_settings(
        user_id,
        {setting_name: setting_value}
    )

    # Get updated user settings to reflect correctly in the keyboard
    user = database.get_user_data(user_id)
    current_settings = get_default_user_settings()
    current_settings.update(user.user_settings or {})

    try:
        await callback.message.edit_reply_markup(
            reply_markup=get_settings_keyboard(current_settings)
        )
    except TelegramBadRequest as e:
        if "message is not modified" in str(e):
            pass  # Silently ignore, as it's expected
        else:
            raise  # Re-raise unexpected errors

    await callback.answer(f"✅ Настройка изменена: {setting_name} → {setting_value}")


# Explicitly handle rating callback
@router.callback_query(lambda c: c.data.startswith('rating:'))
async def rating_handler(callback: CallbackQuery):
    database = await gs().get_database()

    # Parse callback data explicitly
    _, generation_id, rating_value = callback.data.split(":")
    generation_id = int(generation_id)
    rating_value = int(rating_value)
    user_id = callback.from_user.id

    # Check explicitly if user already rated
    if database.has_user_rated(user_id, generation_id):
        await callback.answer("❌ Вы уже оценили это стихотворение.", show_alert=True)
        return

    # Explicitly log the rating
    database.rate_generation(user_id, generation_id, rating_value)

    # Remove inline keyboard explicitly after rating
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer(f"Спасибо! Ваша оценка: ⭐{rating_value}", show_alert=False)


@router.callback_query(lambda c: c.data.startswith('command:'))
async def handle_command_buttons_for_start(callback: CallbackQuery):
    command = callback.data.split(":", 1)[1]

    if len(command) > 0:
        new_message = callback.message.model_copy(update={
            "text": command,
            "from_user": callback.from_user
        })

        match command:
            case "about":
                await cmd_about(new_message)
            case "help":
                await cmd_help(new_message)
            case "random_poem":
                await cmd_random_poem(new_message)
            case "feedback":
                await cmd_feedback(new_message)
            case _:
                pass

    await callback.answer()


@router.callback_query(lambda c: c.data.startswith("feedback:"))
async def handle_feedback_rating(callback: CallbackQuery):
    rating = int(callback.data.split(":")[1])
    bot_msg_id = callback.message.message_id

    # Log feedback explicitly now, with empty message:
    database = await gs().get_database()
    database.log_bot_feedback(
        user_id=callback.from_user.id,
        rating=rating,
        telegram_message_id=bot_msg_id,
        message=None
    )

    # Explicitly instruct user to reply if they want to comment:
    await callback.message.edit_text(
        "✅ Спасибо за оценку! Если хотите добавить комментарий, просто ответьте на это сообщение."
    )
    await callback.answer("✅ Оценка сохранена!")


@router.message(lambda m: m.reply_to_message and m.reply_to_message.from_user.is_bot)
async def handle_feedback_reply(message: types.Message):
    bot_msg_id = message.reply_to_message.message_id

    database = await gs().get_database()
    updated = database.update_feedback_message(
        telegram_message_id=bot_msg_id,
        new_message=message.text
    )

    if updated:
        await message.reply("✅ Ваш комментарий успешно добавлен к отзыву. Спасибо!")

        # Optionally explicitly edit bot's message to signify success:
        await message.reply_to_message.edit_text("✅ Оценка и комментарий успешно сохранены. Спасибо!")
    else:
        await message.reply("⚠️ Не удалось найти отзыв, связанный с этим сообщением.")
