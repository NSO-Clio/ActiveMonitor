# API_KEY = API_KEY = "AIzaSyABJ1jK42mi9ovXsnzJBt2bobl-WvAX5q8"
# MODEL_NAME = "gemini-1.5-flash-latest"
# GEMINI_API_URL = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL_NAME}:generateContent?key={API_KEY}"
# ======================================================================================
# REPORT_GENERATOR.PY
#
# РОЛЬ: "RAG-Исследователь и Синтезатор"
#
# ОПИСАНИЕ:
# Финальный и самый важный модуль конвейера. Выполняет две задачи:
#   1. ИССЛЕДОВАНИЕ (RAG): поиск релевантных решений в интернете.
#   2. СИНТЕЗ (LLM): сбор всех данных и генерация финального отчета.
# ======================================================================================
import requests
from duckduckgo_search import DDGS


class ReportGenerator:
    """Класс для формирования инцидент-отчетов с использованием RAG и LLM (Gemini API)."""

    def __init__(self, api_key: str, model_name: str) -> None:
        """
        Инициализация генератора отчетов.

        Args:
            api_key (str): API-ключ для Gemini.
            model_name (str): Название модели Gemini.
        """
        self.api_key = api_key
        self.model_name = model_name
        self.gemini_api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

    def search_for_solutions(self, query: str) -> str:
        """
        Выполняет поиск в интернете для получения дополнительного контекста (RAG).

        Args:
            query (str): Поисковый запрос (обычно, тип ошибки).

        Returns:
            str: Строка с результатами поиска, отформатированная для промпта.
        """
        print(f"INFO (Исследователь): Поиск по запросу: '{query}'")
        try:
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=3)]
                if not results:
                    return "Поиск не дал результатов."

                context = "Вот краткая сводка из интернета по этой проблеме:\n"
                for res in results:
                    context += (
                        f"- Источник: {res.get('href')}\n"
                        f"  Цитата: {res.get('body', '')[:250]}...\n"
                    )
                return context
        except Exception as e:
            print(f"ERROR (Исследователь): Ошибка во время поиска: {e}")
            return "Ошибка при поиске дополнительной информации."

    def generate_incident_report(
        self, anomaly_details: dict, log_cluster_info: dict | None = None
    ) -> str:
        """
        Формирует и отправляет запрос к Gemini API, обогащая его данными из поиска (RAG).

        Args:
            anomaly_details (dict): Словарь с деталями от predict_failures.
            log_cluster_info (dict | None): Словарь с результатами анализа логов.

        Returns:
            str: Готовый отчет в формате Markdown.
        """
        if not self.api_key or self.api_key == "ВСТАВЬ_СЮДА_СВОЙ_GEMINI_API_КЛЮЧ":
            return "ОШИБКА: API-ключ для Gemini не установлен."

        rag_context = ""
        if log_cluster_info:
            error_query = log_cluster_info.get("example1", "N/A").split(":")[0]
            rag_context = self.search_for_solutions(error_query)

        log_summary = "Анализ логов не проводился (это прогноз)"
        if log_cluster_info:
            log_summary = (
                f"{log_cluster_info.get('percentage', 'N/A')}% ошибок относятся к одному типу: "
                f"'{log_cluster_info.get('top_error_type', 'N/A')}'. "
                f"Примеры: '{log_cluster_info.get('example1', 'N/A')}'"
            )

        prompt_text = f"""
        Ты — SRE-эксперт мирового класса. Проанализируй данные и внешнюю информацию, чтобы составить исчерпывающий отчет.

        **Входные данные:**
        1.  **Сигнал от системы мониторинга:** {anomaly_details}
        2.  **Результат анализа логов:** {log_summary}

        **Контекст из интернета (RAG):**
        {rag_context}

        **Твоя задача — сгенерировать отчет в Markdown:**
        ### 🚨 Отчет об инциденте
        **1. Что произошло (или произойдет)?** (Опиши проблему простым языком)
        **2. Вероятная причина (Root Cause)** (Сделай вывод, объединив данные логов и поиска)
        **3. Рекомендуемые шаги для устранения (Action Plan)** (Предложи конкретные шаги, основываясь на ВСЕЙ информации. Будь максимально конкретен)
        """

        headers = {"Content-Type": "application/json"}
        json_data = {"contents": [{"parts": [{"text": prompt_text}]}]}

        print("INFO (Синтезатор): Отправка запроса в Gemini API...")
        try:
            response = requests.post(
                self.gemini_api_url, headers=headers, json=json_data, timeout=60
            )
            response.raise_for_status()
            return response.json()["candidates"][0]["content"]["parts"][0]["text"]
        except Exception as e:
            return f"ОШИБКА (Синтезатор): Не удалось сгенерировать отчет. {e}"
