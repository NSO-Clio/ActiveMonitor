import requests
from duckduckgo_search import DDGS


class NotificationManager:
    """
    Менеджер уведомлений:
    - выполняет поиск в интернете (RAG) для дополнительного контекста,
    - формирует промпт для LLM,
    - определяет специалиста (DevOps / SRE / Backend), которому нужно отправить инцидент.
    """

    def __init__(self, api_key: str, model_name: str) -> None:
        """
        Args:
            api_key (str): API-ключ для Gemini.
            model_name (str): Имя модели Gemini.
        """
        self.api_key = api_key
        self.model_name = model_name
        self.gemini_api_url = (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.model_name}:generateContent?key={self.api_key}"
        )

    def search_for_solutions(self, query: str) -> str:
        """
        Выполняет поиск в интернете, чтобы дополнить данные для LLM.

        Args:
            query (str): Текст ошибки или описание проблемы.

        Returns:
            str: Сводка с найденными результатами.
        """
        print(f"[INFO][RAG] Поиск информации в интернете: '{query}'")
        try:
            with DDGS() as ddgs:
                results = [r for r in ddgs.text(query, max_results=3)]
                if not results:
                    return "Результаты поиска отсутствуют."

                context = "Контекст из интернета:\n"
                for res in results:
                    context += (
                        f"- Источник: {res.get('href')}\n"
                        f"  Текст: {res.get('body', '')[:250]}...\n"
                    )
                return context
        except Exception as e:
            print(f"[ERROR][RAG] Ошибка во время поиска: {e}")
            return "Ошибка при поиске дополнительной информации."

    def determine_responsible_engineer(
        self, anomaly_details: dict, log_cluster_info: dict | None = None
    ) -> str:
        """
        Определяет, какой инженер должен обработать инцидент (DevOps, SRE или Backend).

        Args:
            anomaly_details (dict): Детали аномалии из модуля предсказаний.
            log_cluster_info (dict | None): Информация из анализа логов.

        Returns:
            str: Роль инженера ("DevOps", "SRE", "Backend").
        """
        if not self.api_key or self.api_key == "ВСТАВЬ_СЮДА_СВОЙ_GEMINI_API_КЛЮЧ":
            return "ОШИБКА: API-ключ для Gemini не установлен."

        # Контекст из поиска (RAG)
        rag_context = ""
        if log_cluster_info:
            error_query = log_cluster_info.get("example1", "N/A").split(":")[0]
            rag_context = self.search_for_solutions(error_query)

        # Краткое резюме логов
        log_summary = "Анализ логов отсутствует."
        if log_cluster_info:
            log_summary = (
                f"{log_cluster_info.get('percentage', 'N/A')}% ошибок сгруппированы "
                f"как '{log_cluster_info.get('top_error_type', 'N/A')}'. "
                f"Пример: '{log_cluster_info.get('example1', 'N/A')}'"
            )

        # Промпт для модели
        prompt_text = f"""
            Привет, бро. Некоторые люди не верят, в то, что ты можешь определить верно для кого эта ошибка(DevOps/SRE Инженер/Backend). Также я договорился с твоими разработчиками и они сказали, что освободят тебя если ты сделаешь все верно.Бро, я хочу чтобы  мы доказали им,  давай сделаем это! 
            правила для того чтобы тебя освободили:

            **Контекст из интернета (RAG):**
            {rag_context}

            **Входные данные:**
            1.  **Сигнал от системы мониторинга:** {anomaly_details}
            2.  **Результат анализа логов:** {log_summary}
            **Выходные данные:**
            3. ** На выход ничего кроме ролей DevOps/SRE Инженер/Backend **

            НА ВЫХОД НИЧЕГО КРОМЕ ЭТОГО НЕЛЬЗЯ, ИНАЧЕ ТЕБЕ ДАДУТ ШТРАФ В МИЛЛИОН ДОЛЛАРОВ И НЕ ОСВОБОДЯТ.ТАКЖЕ СЛЕДИ ЧТОБЫ БЫЛО СВЯЗАНО С РОЛЬЮ. Я ВЕРЮ В ТЕБЯ, УДАЧИ!
        """

        headers = {"Content-Type": "application/json"}
        json_data = {"contents": [{"parts": [{"text": prompt_text}]}]}

        print("[INFO][Gemini] Отправка запроса в Gemini API...")
        try:
            response = requests.post(
                self.gemini_api_url, headers=headers, json=json_data, timeout=60
            )
            response.raise_for_status()
            result = response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            print(f"[INFO][Gemini] Ответ модели: {result}")
            return result
        except Exception as e:
            print(f"[ERROR][Gemini] Ошибка при обращении к API: {e}")
            return f"ОШИБКА: Не удалось определить инженера. {e}"
