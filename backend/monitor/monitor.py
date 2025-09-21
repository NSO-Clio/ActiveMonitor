import os
import json
import pandas as pd
import nest_asyncio
import uuid
from datetime import datetime, timezone
from datetime import datetime, timedelta
from urllib.parse import urlparse
from datetime import datetime

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
    resp = supabase.table(SITES_TABLE).select("*").execute()
    try:
        return resp.data or []
    except Exception:
        # В редких случаях resp может быть объектом и не иметь .data
        return []

def get_checks_dataframe(limit: int = None, since=None):
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

def _normalize_single_log(entry):
    out = {"timestamp": None, "log_level": None, "message": None}

    # If it's a dict, try to map fields
    if isinstance(entry, dict):
        # timestamp: prefer ISO-like string, else numeric (ms or s)
        ts = None
        for k in ("timestamp", "time", "ts", "date"):
            if k in entry and entry[k] is not None:
                ts = entry[k]
                break
        if ts is not None:
            # numeric epoch? (ms or s)
            if isinstance(ts, (int, float)):
                # if > 10^12 assume ms, else seconds
                try:
                    if ts > 1e12:
                        dt = datetime.fromtimestamp(ts / 1000.0, tz=timezone.utc)
                    else:
                        dt = datetime.fromtimestamp(ts, tz=timezone.utc)
                    out["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    out["timestamp"] = str(ts)
            else:
                # try parse ISO-like or common format
                s = str(ts)
                try:
                    # try ISO first
                    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
                    out["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                except Exception:
                    # try common format "YYYY-MM-DD HH:MM:SS"
                    try:
                        dt = datetime.strptime(s, "%Y-%m-%d %H:%M:%S")
                        out["timestamp"] = dt.strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        out["timestamp"] = s

        # log level
        for lvl_key in ("log_level", "level", "levelName", "severity", "levelName"):
            if lvl_key in entry and entry[lvl_key]:
                out["log_level"] = str(entry[lvl_key])
                break

        # message
        for msg_key in ("message", "msg", "text", "body"):
            if msg_key in entry and entry[msg_key]:
                out["message"] = str(entry[msg_key])
                break

        # if message still empty, try to construct from other fields
        if not out["message"]:
            # join remaining key:value but skip timestamp/level keys
            parts = []
            for k, v in entry.items():
                if k in ("timestamp", "time", "ts", "date", "log_level", "level", "levelName", "severity", "message", "msg", "text", "body"):
                    continue
                try:
                    parts.append(f"{k}={v}")
                except Exception:
                    parts.append(f"{k}={str(v)}")
            if parts:
                out["message"] = "; ".join(parts)

    else:
        # not a dict: just stringify as message and set timestamp to None
        out["message"] = str(entry)

    # final fallbacks
    if out["timestamp"] is None:
        out["timestamp"] = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
    if out["log_level"] is None:
        out["log_level"] = "INFO"
    if out["message"] is None:
        out["message"] = ""

    return out

def get_console_logs_normalized_for_site(site_id: int, limit: int = 10):
    if site_id is None:
        raise ValueError("site_id must be provided")

    q = supabase.table(CHECKS_TABLE).select("console_logs").order("check_time", desc=True).eq("site_id", site_id)
    if limit is not None:
        q = q.limit(limit)

    resp = q.execute()
    rows = resp.data or []

    out_logs = []
    for r in rows:
        logs = r.get("console_logs")
        if not logs:
            continue
        if isinstance(logs, str):
            try:
                logs = json.loads(logs)
            except Exception:
                logs = [logs]
        if isinstance(logs, dict):
            logs = [logs]

        if isinstance(logs, (list, tuple)):
            for entry in logs:
                out_logs.append(_normalize_single_log(entry))
        else:
            out_logs.append(_normalize_single_log(str(logs)))

    return out_logs

def get_response_times(limit: int = 50, site_id: int = None):
    q = supabase.table(CHECKS_TABLE).select("check_time,response_time,site_id,url").order("check_time", desc=True)
    if site_id is not None:
        q = q.eq("site_id", site_id)
    if limit is not None:
        q = q.limit(limit)

    resp = q.execute()
    rows = resp.data or []

    result = []
    for r in rows:
        ts = r.get("check_time")
        rt = r.get("response_time")
        if ts and rt is not None:
            result.append({
                "timestamp": ts,
                "response_time_ms": int(rt * 1000),  # в миллисекунды
            })
    return result


sites = get_all_sites()
df_last = get_checks_dataframe(limit=10)
since = datetime.utcnow() - timedelta(days=1)
df_recent = get_checks_dataframe(since=since)

site_logs = get_console_logs_normalized_for_site(site_id=1, limit=5)

sites = get_all_sites()
first_site_id = sites[0]["id"]
