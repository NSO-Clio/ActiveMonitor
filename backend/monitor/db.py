#!/usr/bin/env python3
import os
import json
import time
import ssl
import socket
import asyncio
import aiohttp
import pandas as pd
import nest_asyncio
import uuid
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

# ---------------- helper functions ----------------
def check_http(url, keywords=None, timeout=10):
    import requests
    result = {}
    start = time.time()
    try:
        r = requests.get(url, timeout=timeout)
        elapsed = time.time() - start
        result["status_code"] = r.status_code
        result["response_time"] = round(elapsed, 6)
        result["size_bytes"] = len(r.content)
        result["headers"] = dict(r.headers or {})
        ct = r.headers.get("Content-Type", "")

        if "application/json" in ct:
            try:
                result["json"] = r.json()
                result["json_valid"] = True
            except Exception:
                result["json_valid"] = False
        elif "xml" in ct or "text/html" in ct:
            try:
                import xml.etree.ElementTree as ET
                ET.fromstring(r.text)
                result["xml_valid"] = True
            except Exception:
                result["xml_valid"] = False

        if keywords:
            text = r.text or ""
            result["keywords_found"] = [k for k in keywords if k in text]
    except Exception as e:
        result["error"] = str(e)
    return result

def check_ssl(url):
    parsed = urlparse(url)
    hostname = parsed.hostname
    port = parsed.port or 443
    ctx = ssl.create_default_context()
    try:
        with socket.create_connection((hostname, port), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=hostname) as ssock:
                cert = ssock.getpeercert()
                subject, issuer = {}, {}
                for item in cert.get("subject", ()):
                    if item and len(item[0]) == 2:
                        subject[item[0][0]] = item[0][1]
                for item in cert.get("issuer", ()):
                    if item and len(item[0]) == 2:
                        issuer[item[0][0]] = item[0][1]
                return {
                    "valid": True,
                    "subject": subject,
                    "issuer": issuer,
                    "valid_from": cert.get("notBefore"),
                    "valid_to": cert.get("notAfter")
                }
    except Exception as e:
        return {"valid": False, "error": str(e)}

def check_frontend(url, chromedriver_path=None, page_timeout=30, wait_after_load=1.0):
    caps = webdriver.DesiredCapabilities.CHROME.copy()
    caps["goog:loggingPrefs"] = {"performance": "ALL", "browser": "ALL"}

    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--window-size=1920,1080")
    service = Service(executable_path=chromedriver_path) if chromedriver_path else Service()

    driver = webdriver.Chrome(service=service, options=options)
    try:
        driver.set_page_load_timeout(page_timeout)
        t0 = time.time()
        driver.get(url)
        time.sleep(wait_after_load)
        load_time = time.time() - t0

        console_logs = []
        try:
            raw_logs = driver.get_log("browser")
            for entry in raw_logs:
                normalized = {}
                for k, v in entry.items():
                    try:
                        json.dumps(v)
                        normalized[k] = v
                    except Exception:
                        normalized[k] = str(v)
                console_logs.append(normalized)
        except Exception:
            console_logs = []

        return {
            "title": driver.title or "",
            "html_size": len(driver.page_source or ""),
            "page_load_time": round(load_time, 3),
            "console_logs": console_logs
        }
    finally:
        driver.quit()

def full_site_check(url, chromedriver_path=None):
    report = {}
    report["http"] = check_http(url)
    report["ssl"] = check_ssl(url)
    try:
        report["frontend"] = check_frontend(url, chromedriver_path=chromedriver_path)
        report["full_load_time_ms"] = int(report["frontend"].get("page_load_time", 0) * 1000)
        printre(report["frontend"])

    except Exception as e:
        report["frontend_error"] = str(e)
    return report

def build_record(url, report, site_id):
    rec = {"url": url, "site_id": site_id, "check_time": datetime.utcnow().isoformat()}

    http = report.get("http", {})
    rec["status_code"] = http.get("status_code")
    rec["response_time"] = http.get("response_time")
    rec["content_size"] = http.get("size_bytes")

    ssl_info = report.get("ssl", {})
    rec["ssl_valid"] = ssl_info.get("valid")
    rec["ssl_issuer"] = ssl_info.get("issuer")
    rec["ssl_subject"] = ssl_info.get("subject")

    frontend = report.get("frontend", {})
    rec["frontend_title"] = frontend.get("title")
    rec["html_size"] = frontend.get("html_size")
    rec["console_logs"] = frontend.get("console_logs")
    rec["full_load_time_ms"] = report.get("full_load_time_ms")

    return {k:v for k,v in rec.items() if v is not None}

async def process_site(site):
    site_id = site["id"]
    url = site["url"]
    report = await asyncio.to_thread(full_site_check, url, CHROMEDRIVER_PATH)
    record = build_record(url, report, site_id)
    supabase.table(CHECKS_TABLE).insert(record).execute()
    print(f"[{datetime.utcnow().isoformat()}] Checked {url}")

async def poll_sites():
    resp = supabase.table(SITES_TABLE).select("*").execute()
    sites = resp.data or []
    tasks = [process_site(site) for site in sites]
    await asyncio.gather(*tasks)

def add_site(name, url):
    site_key = str(uuid.uuid4())
    payload = {"name": name, "url": url, "site_key": site_key}
    supabase.table(SITES_TABLE).upsert(payload, on_conflict="url").execute()
    print(f"Added site {name} with key {site_key}")
    return site_key

# ---------------- scheduler ----------------
async def start_scheduler():
    scheduler = AsyncIOScheduler()
    # Запускаем poll_sites без create_task напрямую
    scheduler.add_job(poll_sites, 'interval', seconds=CHECK_INTERVAL, next_run_time=datetime.utcnow())
    scheduler.start()
    print(f"Scheduler started. Checking every {CHECK_INTERVAL} seconds.")
    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        scheduler.shutdown()

# ---------------- main ----------------
if __name__ == "__main__":
    # Просто запускаем планировщик
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(start_scheduler())
    except KeyboardInterrupt:
        print("Shutting down...")
        loop.stop()