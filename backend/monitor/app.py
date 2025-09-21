from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, HttpUrl
from typing import List, Optional
from datetime import datetime, timedelta
from monitor import *
from bot.bot_for_hack import *
import uuid
import math
import numpy as np
import re

router = APIRouter()

# ---------------- Helpers ----------------
def safe_value(v):
    """Преобразуем NaN/inf в None для безопасного JSON."""
    if isinstance(v, (float, int)):
        if math.isnan(v) or math.isinf(v):
            return None
    return v

def clean_for_json(obj):
    """Рекурсивно очищаем данные от NaN и Inf перед JSON-сериализацией."""
    if isinstance(obj, dict):
        return {k: clean_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_for_json(v) for v in obj]
    elif isinstance(obj, (float, int)):
        return safe_value(obj)
    else:
        return obj

def normalize_url(url: str) -> str:
    """Нормализация URL для поиска."""
    url = url.lower()
    url = re.sub(r'^https?://', '', url)
    url = re.sub(r'^www\.', '', url)
    url = re.sub(r'/$', '', url)
    return url

# ---------------- Models ----------------
class SiteCreateRequest(BaseModel):
    name: str
    url: HttpUrl  # проверка корректности URL

# ---------------- GET: Все мониторимые сайты ----------------
@router.get("/monitored")
def get_monitored_sites():
    sites = get_all_sites()
    result = []

    df_all = get_checks_dataframe(limit=1000)  # последние проверки
    df_all = df_all.replace([np.inf, -np.inf], np.nan)  # безопасно для JSON

    for s in sites:
        last_check = df_all[df_all["site_id"] == s["id"]].sort_values("check_time", ascending=False)
        if not last_check.empty:
            last = last_check.iloc[0]
            status = "online" if last.get("status_code") and last["status_code"] < 400 else "offline"
            result.append({
                "id": s["id"],
                "name": s["name"],
                "url": s["url"],
                "status": status,
                "ping": safe_value(last.get("response_time")),
                "loadTime": safe_value(last.get("full_load_time_ms")),
                "uptime": None,
                "lastChecked": last["check_time"].isoformat() if last["check_time"] else None,
                "status_code": last.get("status_code"),
                "content_size": safe_value(last.get("content_size")),
                "ssl_valid": last.get("ssl_valid"),
                "ssl_issuer": last.get("ssl_issuer"),
                "ssl_subject": last.get("ssl_subject"),
                "frontend_title": last.get("frontend_title"),
                "html_size": safe_value(last.get("html_size")),
                "console_logs": last.get("console_logs")
            })
        else:
            result.append({
                "id": s["id"],
                "name": s["name"],
                "url": s["url"],
                "status": "offline",
                "ping": None,
                "loadTime": None,
                "uptime": None,
                "lastChecked": None,
                "status_code": None,
                "content_size": None,
                "ssl_valid": None,
                "ssl_issuer": None,
                "ssl_subject": None,
                "frontend_title": None,
                "html_size": None,
                "console_logs": None
            })
    return clean_for_json(result)

# ---------------- GET: Поиск сайта по URL ----------------
@router.get("/search")
def search_site_by_url(url: str = Query(..., description="URL для поиска")):
    """
    Поиск сайта по URL в системе мониторинга.
    Нормализует URL и ищет частичное соответствие.
    """
    # Нормализуем URL для поиска
    normalized_search_url = normalize_url(url)
    if not normalized_search_url:
        raise HTTPException(status_code=400, detail="Invalid URL format")

    # Получаем все сайты
    sites = get_all_sites()

    # Ищем соответствие
    matched_site = None
    for site in sites:
        site_url = normalize_url(site["url"])
        # Проверяем точное совпадение или содержание
        if site_url == normalized_search_url or normalized_search_url in site_url:
            matched_site = site
            break

    if not matched_site:
        raise HTTPException(status_code=404, detail="Site not found")

    # Получаем последние метрики для сайта
    df_all = get_checks_dataframe(limit=1000)
    df_all = df_all.replace([np.inf, -np.inf], np.nan)

    site_id = matched_site["id"]
    last_check = df_all[df_all["site_id"] == site_id].sort_values("check_time", ascending=False)

    if not last_check.empty:
        last = last_check.iloc[0]
        status = "online" if last.get("status_code") and last["status_code"] < 400 else "offline"
        result = {
            "id": site_id,
            "name": matched_site["name"],
            "url": matched_site["url"],
            "status": status,
            "ping": safe_value(last.get("response_time")),
            "loadTime": safe_value(last.get("full_load_time_ms")),
            "uptime": None,
            "lastChecked": last["check_time"].isoformat() if last["check_time"] else None,
            "status_code": last.get("status_code"),
            "content_size": safe_value(last.get("content_size")),
            "ssl_valid": last.get("ssl_valid"),
            "ssl_issuer": last.get("ssl_issuer"),
            "ssl_subject": last.get("ssl_subject"),
            "frontend_title": last.get("frontend_title"),
            "html_size": safe_value(last.get("html_size")),
            "console_logs": last.get("console_logs")
        }
    else:
        result = {
            "id": site_id,
            "name": matched_site["name"],
            "url": matched_site["url"],
            "status": "offline",
            "ping": None,
            "loadTime": None,
            "uptime": None,
            "lastChecked": None,
            "status_code": None,
            "content_size": None,
            "ssl_valid": None,
            "ssl_issuer": None,
            "ssl_subject": None,
            "frontend_title": None,
            "html_size": None,
            "console_logs": None
        }

    return clean_for_json(result)

# ---------------- GET: Метрики конкретного сайта ----------------
@router.get("/{site_id}/metrics")
def get_site_metrics(site_id: int, period: str = "24h"):
    if period.endswith("h"):
        try:
            hours = int(period.rstrip("h"))
            since = datetime.utcnow() - timedelta(hours=hours)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period format")
    elif period.endswith("d"):
        try:
            days = int(period.rstrip("d"))
            since = datetime.utcnow() - timedelta(days=days)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid period format")
    else:
        raise HTTPException(status_code=400, detail="Period must end with 'h' (hours) or 'd' (days)")

    df = get_checks_dataframe(since=since)
    df = df[df["site_id"] == site_id].sort_values("check_time")
    df = df.replace([np.inf, -np.inf], np.nan)

    metrics = []
    for _, row in df.iterrows():
        metrics.append({
            "timestamp": row["check_time"].isoformat() if row["check_time"] else None,
            "ping": safe_value(row.get("response_time")),
            "loadTime": safe_value(row.get("full_load_time_ms")),
            "status_code": row.get("status_code"),
            "content_size": safe_value(row.get("content_size")),
            "ssl_valid": row.get("ssl_valid"),
            "frontend_title": row.get("frontend_title"),
            "html_size": safe_value(row.get("html_size"))
        })
    return clean_for_json(metrics)

# ---------------- GET: Консольные логи для сайта ----------------
@router.get("/{site_id}/logs")
def get_site_logs(site_id: int, limit: int = 10):
    """Получение нормализованных логов консоли для сайта."""
    try:
        logs = get_console_logs_normalized_for_site(site_id=site_id, limit=limit)
        return clean_for_json(logs)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching logs: {str(e)}")

# ---------------- GET: Времена отклика для сайта ----------------
@router.get("/{site_id}/response-times")
def get_site_response_times(site_id: int, limit: int = 50):
    """Получение времен отклика для сайта."""
    try:
        times = get_response_times(site_id=site_id, limit=limit)
        return clean_for_json(times)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error fetching response times: {str(e)}")

# ---------------- POST: Добавление нового сайта ----------------
@router.post("/add")
def add_new_site(request: SiteCreateRequest):
    sites = get_all_sites()
    if any(normalize_url(s["url"]) == normalize_url(str(request.url)) for s in sites):
        raise HTTPException(status_code=400, detail="Site already exists")

    site_key = str(uuid.uuid4())
    payload = {
        "name": request.name,
        "url": str(request.url),
        "site_key": site_key
    }

    response = supabase.table("sites").insert(payload).execute()
    new_id = response.data[0]["id"] if response.data else None

    return {
        "id": new_id,
        "name": request.name,
        "url": str(request.url),
        "site_key": site_key,
        "status": "pending"
    }

# ---------------- GET: Добавление нового сайта (альтернативный метод через GET) ----------------
@router.get("/add")
def add_site_get(url: str = Query(...), name: Optional[str] = None):
    """
    Альтернативный метод добавления сайта через GET запрос.
    Полезно для быстрого добавления из интерфейса.
    """
    # Используем URL в качестве имени, если имя не указано
    if not name:
        name = url

    # Проверка, существует ли уже сайт
    sites = get_all_sites()
    normalized_url = normalize_url(url)

    if any(normalize_url(s["url"]) == normalized_url for s in sites):
        raise HTTPException(status_code=400, detail="Site already exists")

    # Добавляем сайт
    try:
        site_key = add_site(name=name, url=url)
        return {"success": True, "message": f"Site {url} added successfully", "site_key": site_key}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error adding site: {str(e)}")

# ---------------- GET: Запуск проверки сайта вручную ----------------
@router.get("/{site_id}/check-now")
async def check_site_now(site_id: int):
    """Запуск проверки сайта вручную."""
    try:
        # Находим сайт по ID
        sites = get_all_sites()
        site = next((s for s in sites if s["id"] == site_id), None)

        if not site:
            raise HTTPException(status_code=404, detail="Site not found")

        # Запускаем проверку
        await process_site(site)

        return {"success": True, "message": f"Site check initiated for {site['url']}"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error checking site: {str(e)}")


@router.post("/analyze-logs/{site_id}")
async def analyze_logs(site_id: int):
    try:
        # Определяем функцию get_console_logs_normalized_for_site если она отсутствует
        def get_console_logs_normalized_for_site(site_id, limit=50):
            """Получение нормализованных логов консоли для сайта."""
            try:
                # Получаем данные из таблицы проверок
                df = get_checks_dataframe(limit=limit)
                site_checks = df[df["site_id"] == site_id].sort_values("check_time", ascending=False)

                logs = []
                for _, row in site_checks.iterrows():
                    if row.get("check_time"):
                        timestamp = row["check_time"].isoformat() if hasattr(row["check_time"], "isoformat") else str(row["check_time"])

                        # Определяем уровень лога на основе статус-кода
                        status_code = row.get("status_code")
                        level = "error" if status_code and status_code >= 400 else "info"

                        # Извлекаем консольные логи если они есть
                        console_message = "No message"
                        if row.get("console_logs"):
                            try:
                                # Если это JSON строка, парсим ее
                                import json
                                console_data = json.loads(row.get("console_logs"))
                                if isinstance(console_data, list) and len(console_data) > 0:
                                    console_message = console_data[0].get("message", "No message")
                            except:
                                console_message = str(row.get("console_logs"))[:100]

                        logs.append({
                            "timestamp": timestamp,
                            "ping": row.get("response_time", 0) * 1000 if row.get("response_time") is not None else 0,
                            "level": level,
                            "message": f"Status: {status_code}, {console_message}"
                        })

                return logs
            except Exception as e:
                logger.error(f"Error getting logs: {str(e)}")
                # Возвращаем хотя бы один элемент для предотвращения ошибок
                return [{"timestamp": datetime.utcnow().isoformat(), "ping": 0, "level": "error", "message": f"Error getting logs: {str(e)}"}]

        # Получаем логи с использованием определенной выше функции
        logs = get_console_logs_normalized_for_site(site_id=site_id, limit=50)

        payload = {
            "old_logs": [{"timestamp": l["timestamp"], "response_time_ms": l.get("ping", 0)} for l in logs],
            "logs_anomaly": [{"timestamp": l["timestamp"], "log_level": l.get("level", "info"), "message": l.get("message", "")} for l in logs],
            "choice_role": True,
        }

        # Отправка на anomaly_report_api
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post("http://localhost:8000/anomaly/run-orchestrator", json=payload, timeout=10.0)
                resp.raise_for_status()
                result = resp.json()
                return {"report": result["report"]}
            except Exception as e:
                logger.error(f"Error calling orchestrator: {str(e)}")
                # Возвращаем простой отчет в случае ошибки
                return {
                    "report": {
                        "performance_analysis": "Автоматический анализ производительности временно недоступен.",
                        "security_analysis": "Анализ безопасности временно недоступен.",
                        "anomalies": "Не удалось выполнить анализ аномалий: сервис недоступен.",
                        "recommendations": ["Убедитесь, что сервис аналитики запущен и доступен."]
                    }
                }
    except Exception as e:
        logger.error(f"Error in analyze_logs: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error analyzing logs: {str(e)}")
