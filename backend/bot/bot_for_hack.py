import asyncio
import logging
import os
import nest_asyncio
import pandas as pd
import matplotlib.pyplot as plt
import httpx
from aiogram import Bot, Dispatcher, types, F, html
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, FSInputFile, InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta
import json

from .test_req import get_checks_dataframe, get_all_sites
# Применяем nest_asyncio для корректной работы Supabase в асинхронной среде
nest_asyncio.apply()
load_dotenv()

# --- Конфигурация и подключение к Supabase/LLM ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SITES_TABLE = os.getenv("SITES_TABLE", "sites")
CHECKS_TABLE = os.getenv("CHECKS_TABLE", "site_checks")
TOKEN = os.getenv("TOKEN_REAL")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
ORCHESTRATOR_URL = os.getenv("ORCHESTRATOR_URL")


if not all([SUPABASE_URL, SUPABASE_KEY, TOKEN, GOOGLE_API_KEY]):
    raise ValueError("One or more required environment variables (SUPABASE_URL, SUPABASE_KEY, TOKEN, GOOGLE_API_KEY) not found in .env file")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Настройки бота и планировщика ---
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(storage=MemoryStorage())
scheduler = AsyncIOScheduler()

user_data = {}
monitored_sites = {}

# --- Функции для работы с Supabase ---
def get_all_sites():
    """Возвращает список всех сайтов из таблицы SITES_TABLE."""
    try:
        resp = supabase.table(SITES_TABLE).select("*").execute()
        return resp.data or []
    except Exception as e:
        logging.error(f"Error fetching all sites: {e}")
        return []

def get_site_by_url(url: str):
    """Возвращает данные о сайте по его URL."""
    try:
        resp = supabase.table(SITES_TABLE).select("*").eq("url", url).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logging.error(f"Error fetching site by URL: {e}")
        return None

def get_site_by_id(site_id: str):
    """Возвращает данные о сайте по его ID."""
    try:
        resp = supabase.table(SITES_TABLE).select("*").eq("id", site_id).execute()
        return resp.data[0] if resp.data else None
    except Exception as e:
        logging.error(f"Error fetching site by ID: {e}")
        return None

# ИСПРАВЛЕНО: добавил url в параметры
async def add_check_to_db(site_id: str, status_code: int, response_time: float, url: str, error_message: str = None):
    """Добавляет результат проверки в базу данных."""
    try:
        data = {
            "site_id": site_id,
            "url": url,  # ИСПРАВЛЕНО: теперь URL сохраняется
            "status_code": status_code,
            "response_time": response_time,
            "check_time": datetime.now().isoformat(),
            "console_logs": {"error": error_message} if error_message else None
        }
        # НОВОЕ: Возвращаем результат вставленной строки
        resp = supabase.table(CHECKS_TABLE).insert(data).execute()
        return resp.data[0]['id'] if resp.data else None
    except Exception as e:
        logging.error(f"Error adding check to DB: {e}")
        return None

# --- ФУНКЦИЯ ПРОГНОЗА ---
async def analyze_and_predict(site_id: str):
    """
    Запрашивает прогноз у локального AI Incident Orchestrator API.
    """
    try:
        # Достаём последние проверки (например, за 24 часа)
        since = datetime.utcnow() - timedelta(days=1)
        resp = (
            supabase.table(CHECKS_TABLE)
            .select("response_time, status_code, check_time, console_logs")
            .eq("site_id", site_id)
            .gte("check_time", since.isoformat())
            .order("check_time", desc=False)
            .execute()
        )
        data = resp.data or []

        # Логи времени ответа
        old_logs = [
            {
                "timestamp": row["check_time"],
                "response_time_ms": int(row["response_time"] * 1000),
            }
            for row in data
            if row.get("response_time") is not None
        ]

        # Логи с ошибками
        logs_anomaly = []
        for row in data:
            if row.get("console_logs") and isinstance(row["console_logs"], dict):
                error_msg = row["console_logs"].get("error")
                if error_msg:
                    logs_anomaly.append(
                        {
                            "timestamp": row["check_time"],
                            "log_level": "ERROR",
                            "message": error_msg,
                        }
                    )

        payload = {
            "old_logs": old_logs,
            "logs_anomaly": logs_anomaly,
            "choice_role": False,  # укажи True, если нужно получить и роль инженера
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/run-orchestrator", json=payload)
            response.raise_for_status()
            result = response.json()

        return f"🛠 Рекомендации от Orchestrator:\n\n{json.dumps(result, indent=2, ensure_ascii=False)}"

    except Exception as e:
        logging.error(f"Error calling orchestrator API: {e}")
        return "⚠️ Не удалось получить прогноз. Проверьте API."


# --- ФУНКЦИЯ ДЛЯ РАСШИФРОВКИ ОШИБКИ ---
async def decipher_error_and_suggest_specialist(error_message: str):
    """
    Отправляет ошибку в Orchestrator API для анализа и определения специалиста.
    """
    try:
        payload = {
            "old_logs": [],  # тут можно передать историю, если нужно
            "logs_anomaly": [
                {
                    "timestamp": datetime.utcnow().isoformat(),
                    "log_level": "ERROR",
                    "message": error_message,
                }
            ],
            "choice_role": True  # включаем, чтобы API вернул инженера
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(f"{ORCHESTRATOR_URL}/run-orchestrator", json=payload)
            response.raise_for_status()
            result = response.json()

        return f"📌 Результат анализа ошибки:\n\n{json.dumps(result, indent=2, ensure_ascii=False)}"

    except Exception as e:
        logging.error(f"Error deciphering error with Orchestrator API: {e}")
        return "⚠️ Не удалось расшифровать ошибку. Проверьте API."


# --- Мониторинг сайта ---
async def monitor_site(site_id: str, chat_id: int):
    if site_id not in monitored_sites:
        return

    site_data = get_site_by_id(site_id)
    if not site_data:
        logging.warning(f"Site with ID {site_id} not found in DB. Stopping monitor.")
        return

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(site_data['url'])
            status_code = resp.status_code
            response_time = resp.elapsed.total_seconds()
            error_message = None

            if 200 <= status_code < 400:
                logging.info(f"Сайт {site_data['url']} работает. Статус: {status_code}")
                # ИСПРАВЛЕНО: Передаём URL
                check_id = await add_check_to_db(site_id, status_code, response_time, site_data['url'])
            else:
                error_message = f"Сайт вернул ошибку: {status_code}"
                logging.error(error_message)

                # ИСПРАВЛЕНО: Передаём URL
                check_id = await add_check_to_db(site_id, status_code, response_time, site_data['url'], error_message)

                if site_id in monitored_sites and check_id:
                    # НОВОЕ: Передаем ID проверки напрямую в callback_data
                    inline_kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="Расшифровать ошибку", callback_data=f"decipher_{check_id}")]
                    ])
                    await bot.send_message(
                        chat_id,
                        f"⚠️ **ВНИМАНИЕ!** Сайт <b>{site_data.get('name', 'без имени')}</b> сломался!\n"
                        f"URL: <b>{site_data['url']}</b>\n"
                        f"Ошибка: {error_message}",
                        reply_markup=inline_kb
                    )

    except httpx.RequestError as e:
        error_message = f"Ошибка подключения: {e}"
        logging.error(error_message)

        # ИСПРАВЛЕНО: Передаём URL
        check_id = await add_check_to_db(site_id, 0, 0, site_data['url'], error_message)

        if site_id in monitored_sites and check_id:
            # НОВОЕ: Передаем ID проверки напрямую в callback_data
            inline_kb = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="Расшифровать ошибку", callback_data=f"decipher_{check_id}")]
            ])
            await bot.send_message(
                chat_id,
                f"❌ **ВНИМАНИЕ!** Сайт <b>{site_data.get('name', 'без имени')}</b> недоступен!\n"
                f"URL: <b>{site_data['url']}</b>\n"
                f"Ошибка: {error_message}",
                reply_markup=inline_kb
            )

# --- Тексты сообщений и клавиатуры ---
WELCOME_MESSAGE = (
    "👋 **Добро пожаловать в систему мониторинга веб-сервисов!**\n\n"
    "Я — ваш автоматизированный помощник для непрерывного отслеживания доступности и производительности цифровых ресурсов 24/7."
)

def get_main_keyboard():
    buttons = [
        [InlineKeyboardButton(text="Отслеживать новый сайт", callback_data="track_site")],
        [InlineKeyboardButton(text="Мои отслеживаемые сайты", callback_data="list_sites")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def get_site_actions_keyboard(site_id: str):
    buttons = [
        [InlineKeyboardButton(text="Показать информацию", callback_data=f"show_info_{site_id}")],
        [InlineKeyboardButton(text="Прогноз", callback_data=f"predict_{site_id}")],
        [InlineKeyboardButton(text="Остановить мониторинг", callback_data=f"stop_{site_id}")],
        [InlineKeyboardButton(text="<< Назад", callback_data="start_over")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

# --- Обработчики aiogram ---
@dp.message(CommandStart())
async def command_start_handler(message: types.Message) -> None:
    await message.answer(
        WELCOME_MESSAGE,
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "start_over")
async def back_to_start_handler(callback_query: types.CallbackQuery):
    await callback_query.message.edit_text(
        WELCOME_MESSAGE,
        reply_markup=get_main_keyboard()
    )
    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data == "track_site")
async def track_site_callback_handler(callback_query: types.CallbackQuery):
    await callback_query.message.answer(
        "🔗 Отправьте мне ссылку на сайт, который вы хотите отслеживать."
    )
    await bot.answer_callback_query(callback_query.id)

@dp.message(F.text.startswith("http"))
async def check_url_handler(message: types.Message) -> None:
    url = message.text.strip()
    site_data = get_site_by_url(url)

    if site_data:
        site_id = site_data['id']
        chat_id = message.chat.id
        user_id = message.from_user.id
        user_data[user_id] = site_data # Сохраняем для контекста

        if site_id not in monitored_sites:
            job_id = f"monitor_{site_id}_{chat_id}"
            scheduler.add_job(
                monitor_site,
                'interval',
                minutes=1,
                id=job_id,
                args=(site_id, chat_id),
                replace_existing=True
            )
            monitored_sites[site_id] = job_id
            await message.answer(
                f"✅ Начинаю следить за сайтом <b>{site_data.get('name', 'без имени')}</b>! "
                "Я буду проверять его каждую минуту и сообщу, если он сломается.",
                reply_markup=get_site_actions_keyboard(site_id)
            )
        else:
            await message.answer(
                f"🔍 Я уже слежу за сайтом <b>{site_data.get('name', 'без имени')}</b>.",
                reply_markup=get_site_actions_keyboard(site_id)
            )
    else:
        await message.answer(
            "❌ Сайт отсутствует в базе. Прежде чем начать мониторинг, добавьте его.",
        )

@dp.callback_query(F.data.startswith("show_info_"))
async def show_site_info_handler(callback_query: types.CallbackQuery):
    site_id = callback_query.data.split('_')[2]
    site_data = get_site_by_id(site_id)

    if not site_data:
        await callback_query.answer("Сайт не найден.", show_alert=True)
        return

    try:
        df_resp = supabase.table(CHECKS_TABLE).select("*").eq("site_id", site_id).order("check_time", desc=True).limit(10).execute()
        df = pd.DataFrame(df_resp.data)
    except Exception:
        df = pd.DataFrame()

    if not df.empty:
        df['check_time'] = pd.to_datetime(df['check_time']).dt.tz_convert(None)
        df = df.sort_values(by='check_time')

        temp_file_path = f"plot_{site_id}.png"

        plt.style.use('seaborn-v0_8-darkgrid')
        plt.figure(figsize=(10, 6))

        if not df['response_time'].empty:
            plt.plot(df['check_time'], df['response_time'], marker='o', linestyle='-', color='#4287f5')

        plt.title(f"Время ответа для {site_data.get('name', 'сайта')}", fontsize=16)
        plt.xlabel("Время", fontsize=12)
        plt.ylabel("Время ответа (с)", fontsize=12)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()

        plt.savefig(temp_file_path)
        plt.close()

        photo_file = FSInputFile(temp_file_path)
        try:
            await bot.send_photo(
                chat_id=callback_query.from_user.id,
                photo=photo_file,
                caption=f"📊 **График времени ответа** для сайта <b>{site_data.get('name', 'без имени')}</b>"
            )
        except Exception as e:
            logging.error(f"Failed to send photo: {e}")
            await callback_query.message.answer("⚠️ Не удалось отправить график. Пожалуйста, проверьте логи.")

        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)

        await callback_query.message.answer(
            f"Выберите действие для сайта {site_data.get('name', 'без имени')}",
            reply_markup=get_site_actions_keyboard(site_id)
        )

    else:
        await callback_query.message.answer(
            "⚠️ Не удалось найти данные о проверках для этого сайта. "
            "Возможно, ещё не было проведено ни одной проверки."
        )
    await bot.answer_callback_query(callback_query.id)


@dp.callback_query(F.data.startswith("stop_"))
async def stop_monitoring_handler(callback_query: types.CallbackQuery):
    site_id = callback_query.data.split('_')[1]
    site_data = get_site_by_id(site_id)
    job_id = monitored_sites.get(site_id)

    if job_id:
        try:
            scheduler.remove_job(job_id)
            del monitored_sites[site_id]
            # Также удаляем из user_data, если он там есть
            user_id_to_del = None
            for uid, s_data in user_data.items():
                if s_data.get('id') == site_id:
                    user_id_to_del = uid
                    break
            if user_id_to_del:
                del user_data[user_id_to_del]


            await callback_query.message.edit_text(
                f"✅ Мониторинг сайта <b>{site_data.get('name', 'без имени')}</b> остановлен.",
                reply_markup=get_main_keyboard()
            )
        except Exception as e:
            logging.error(f"Failed to remove job: {e}")
            await callback_query.answer("❌ Ошибка при остановке мониторинга.", show_alert=True)
    else:
        await callback_query.answer("⚠️ Мониторинг для этого сайта не был активен.", show_alert=True)

    await bot.answer_callback_query(callback_query.id)

@dp.callback_query(F.data.startswith("predict_"))
async def predict_handler(callback_query: types.CallbackQuery):
    site_id = callback_query.data.split('_')[1]
    site_data = get_site_by_id(site_id)

    if not site_data:
        await callback_query.answer("Сайт не найден.", show_alert=True)
        return

    await bot.answer_callback_query(callback_query.id, text="🔮 Запрашиваю прогноз у нейросети...")

    forecast = await analyze_and_predict(site_id)
    await callback_query.message.answer(
        f"**Прогноз для сайта {site_data.get('name', 'без имени')}:**\n\n{forecast}",
    )


@dp.callback_query(F.data.startswith("decipher_"))
async def decipher_callback_handler(callback_query: types.CallbackQuery) -> None:
    try:
        check_id = callback_query.data.split('_')[1]
        resp = supabase.table(CHECKS_TABLE).select("console_logs, site_id").eq("id", check_id).single().execute()

        site_id = resp.data.get('site_id') if resp.data else None
        error_logs = resp.data.get('console_logs', {}).get('error') if resp.data else None

        if error_logs:
            await bot.answer_callback_query(callback_query.id, text="Расшифровываю ошибку...")
            deciphered_text = await decipher_error_and_suggest_specialist(error_logs)
            await bot.send_message(
                callback_query.from_user.id,
                f"**Анализ ошибки:**\n\n{deciphered_text}",
            )
        else:
            await bot.answer_callback_query(callback_query.id, text="Не удалось найти ошибку для расшифровки.")

    except Exception as e:
        logging.error(f"Error handling decipher callback: {e}")
        await bot.answer_callback_query(callback_query.id, text="Произошла ошибка при обработке запроса.")

# --- НОВАЯ КОМАНДА ---
@dp.message(Command("tracked_sites"))
@dp.callback_query(F.data == "list_sites")
async def list_tracked_sites_handler(update: types.Update):
    message_text = "📈 **Отслеживаемые сайты:**\n\n"
    buttons = []
    if not monitored_sites:
        message_text += "Пока нет отслеживаемых сайтов."
    else:
        for site_id, job_id in monitored_sites.items():
            site_data = get_site_by_id(site_id)
            if site_data:
                buttons.append([InlineKeyboardButton(text=site_data.get('name', site_data.get('url')), callback_data=f"manage_site_{site_id}")])

    if not buttons:
        message_text += "Пока нет отслеживаемых сайтов."


    buttons.append([InlineKeyboardButton(text="<< Назад", callback_data="start_over")])
    keyboard = InlineKeyboardMarkup(inline_keyboard=buttons)

    if isinstance(update, types.Message):
        await update.answer(message_text, reply_markup=keyboard)
    elif isinstance(update, types.CallbackQuery):
        await update.message.edit_text(message_text, reply_markup=keyboard)
        await bot.answer_callback_query(update.id)


@dp.callback_query(F.data.startswith("manage_site_"))
async def manage_site_handler(callback_query: types.CallbackQuery):
    site_id = callback_query.data.split('_')[2]
    site_data = get_site_by_id(site_id)
    if site_data:
        await callback_query.message.edit_text(
            f"Выберите действие для сайта **{site_data.get('name', site_data.get('url'))}**:",
            reply_markup=get_site_actions_keyboard(site_id)
        )
    else:
        await callback_query.answer("Сайт не найден.", show_alert=True)
    await bot.answer_callback_query(callback_query.id)


async def main() -> None:
    scheduler.start()
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())