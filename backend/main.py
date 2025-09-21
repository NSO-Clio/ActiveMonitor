import asyncio
import logging
from fastapi import FastAPI

from monitor.app import router as monitor_router
from anomaly_report_api.app import router as anomaly_router
from bot.bot_for_hack import main as bot_main
from monitor.db import start_scheduler

logger = logging.getLogger(__name__)

app = FastAPI(title="Backend")

app.include_router(monitor_router, prefix="/sites", tags=["Monitoring sites"])
app.include_router(anomaly_router, prefix="/anomaly", tags=["Anomaly Report API"])


@app.on_event("startup")
async def startup_event():
    # Запуск бота в фоне вместе с бэкендом
    loop = asyncio.get_event_loop()

    # Запуск телеграм-бота
    loop.create_task(bot_main())
    logger.info("Bot started in background")

    # Запуск планировщика мониторинга сайтов
    loop.create_task(start_scheduler())
    logger.info("Site monitoring scheduler started in background")