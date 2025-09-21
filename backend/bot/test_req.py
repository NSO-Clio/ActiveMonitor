import os
import json
import pandas as pd
import nest_asyncio
import uuid
from urllib.parse import urlparse
from datetime import datetime, timedelta

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

from dotenv import load_dotenv
from supabase import create_client, Client
from apscheduler.schedulers.asyncio import AsyncIOScheduler

nest_asyncio.apply()
load_dotenv()

# ---------------- config ----------------
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
CHROMEDRIVER_PATH = os.getenv("CHROMEDRIVER_PATH")
SITES_TABLE = os.getenv("SITES_TABLE", "sites")
CHECKS_TABLE = os.getenv("CHECKS_TABLE", "site_checks")
CHECK_INTERVAL = int(os.getenv("CHECK_INTERVAL_SECONDS", 300))

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ---------------- REQUSTS ----------------
def get_all_sites():
    """
    Возвращает список всех сайтов из таблицы SITES_TABLE.
    Каждый элемент — dict (row), содержит id, name, url, site_key и т.д.
    """
    resp = supabase.table(SITES_TABLE).select("*").execute()
    try:
        return resp.data or []
    except Exception:
        # В редких случаях resp может быть объектом и не иметь .data
        return []

def get_checks_dataframe(limit: int = None, since=None):
    """
    Возвращает pandas.DataFrame с данными из CHECKS_TABLE.

    limit: максимальное число строк (None = все)
    since: фильтр по check_time (datetime или ISO string). None = без фильтра.
    """
    q = supabase.table(CHECKS_TABLE).select("*").order("check_time", desc=True)
    if limit is not None:
        q = q.limit(limit)
    if since is not None:
        # Преобразуем since в ISO, если передали datetime
        if isinstance(since, datetime):
            since_iso = since.isoformat()
        else:
            since_iso = str(since)
        q = q.gte("check_time", since_iso)

    resp = q.execute()
    rows = resp.data or []

    # Нормализуем JSON-поля (ssl_issuer, ssl_subject, console_logs) -> строки JSON
    normalized = []
    for r in rows:
        rcopy = dict(r)  # shallow copy
        for fld in ("ssl_issuer", "ssl_subject", "console_logs"):
            v = rcopy.get(fld)
            if v is None:
                rcopy[fld] = None
            else:
                try:
                    rcopy[fld] = json.dumps(v, ensure_ascii=False)
                except Exception:
                    rcopy[fld] = str(v)
        # ensure check_time is datetime for DataFrame convenience
        if "check_time" in rcopy and isinstance(rcopy["check_time"], str):
            try:
                rcopy["check_time"] = datetime.fromisoformat(rcopy["check_time"].replace("Z", "+00:00"))
            except Exception:
                pass
        normalized.append(rcopy)

    # build DataFrame
    df = pd.DataFrame(normalized)
    # if df empty, return empty df with expected columns
    if df.empty:
        cols = ["id","site_id","url","check_time","status_code","response_time","content_size",
                "ssl_valid","ssl_issuer","ssl_subject","frontend_title","html_size","console_logs","error"]
        return pd.DataFrame(columns=cols)
    return df

sites = get_all_sites()
print("=== Все сайты в системе ===")
for site in sites:
    print(f"ID={site['id']}, name={site['name']}, url={site['url']}, site_key={site['site_key']}")

# --- Пример 2: получаем последние 10 проверок ---
print("\n=== Последние 10 проверок ===")
df_last = get_checks_dataframe(limit=10)
print(df_last[["id", "url", "check_time", "status_code", "response_time", "ssl_valid"]])

# --- Пример 3: проверки за последние 24 часа ---
since = datetime.utcnow() - timedelta(days=1)
print("\n=== Проверки за последние 24 часа ===")
df_recent = get_checks_dataframe(since=since)
print(df_recent[["url", "check_time", "status_code", "frontend_title"]])
