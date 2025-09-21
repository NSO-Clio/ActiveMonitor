# 🚀 AI Incident Orchestrator API

## 📌 Описание
**AI Incident Orchestrator API** — сервис для анализа логов, детекции аномалий и генерации отчетов о возможных инцидентах.  
Сервис построен на **FastAPI** и использует ML-модели для прогнозирования потенциальных сбоев и анализа ошибок в логах.  

---

## ⚙️ Установка и запуск

### 1. Установка зависимостей
```bash
pip install -r requirements.txt
```

### 2. Запуск сервиса

```bash
uvicorn app:app --reload
```

### Пример обращения к пост запросу через python
```python
import requests

url = "http://127.0.0.1:8000/run-orchestrator"
data = {
    "old_logs": [
        {"timestamp": "2025-09-21T10:00:00", "response_time_ms": 210},
        {"timestamp": "2025-09-21T10:01:00", "response_time_ms": 225},
        {"timestamp": "2025-09-21T10:02:00", "response_time_ms": 198},
        {"timestamp": "2025-09-21T10:03:00", "response_time_ms": 10000}
    ],
    "logs_anomaly": [
        {"timestamp": "2025-09-21 10:03:10", "log_level": "ERROR", "message": "Database connection refused by host 127.0.0.1"},
        {"timestamp": "2025-09-21 10:03:12", "log_level": "INFO", "message": "Request processed"},
        {"timestamp": "2025-09-21 10:03:15", "log_level": "ERROR", "message": "Database connection refused by host 127.0.0.1"}
    ],
    "choice_role": True
}

response = requests.post(url, json=data)
print(response.json())
```