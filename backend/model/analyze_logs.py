import re
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
import pickle

MAX_LOG_EXAMPLE_LENGTH = 500  # Макс. длина примера лога для отправки в LLM

class LogAnalyzer:
    """Класс для анализа логов и нахождения доминирующих причин ошибок."""

    def __init__(self, vectorizer_path: str, kmeans_path: str):
        """
        Инициализация: загружает vectorizer из pickle-файла.

        Args:
            pickle_path (str): путь к pickle-файлу с vectorizer
        """
        self.vectorizer = pickle.load(open(vectorizer_path, 'rb'))
        print(f"INFO: vectorizer успешно загружен из {vectorizer_path}")
        
        self.kmeans = pickle.load(open(kmeans_path, 'rb'))
        print(f"INFO: kmeans успешно загружен из {kmeans_path}")

    @staticmethod
    def _preprocess_log(message: str) -> str:
        """Очистка и нормализация сообщения лога."""
        message = str(message)
        message = re.sub(r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}', 'IP_ADDRESS', message)
        message = re.sub(r'[0-9]+', 'NUMBER', message)
        return message.lower()

    def analyze(self, logs_anomaly: list, n_clusters: int = 3) -> dict | None:
        """
        Анализирует логи, находит самый крупный кластер ошибок и возвращает сводку.

        Args:
            n_clusters (int): количество кластеров для поиска

        Returns:
            dict | None: результаты анализа
        """

        logs_df = pd.DataFrame(logs_anomaly)
        if logs_df.empty:
            print("INFO: DataFrame пустой, нечего анализировать.")
            return None

        error_logs = logs_df[logs_df['log_level'] == 'ERROR'].copy()
        if len(error_logs) < n_clusters:
            print("INFO: Недостаточно ошибок для кластерного анализа.")
            return None

        # Предобработка текста
        error_logs['clean_message'] = error_logs['message'].apply(self._preprocess_log)

        # TF-IDF и KMeans
        X = self.vectorizer.transform(error_logs['clean_message'])
        error_logs['cluster'] = self.kmeans.predict(X)

        # Выбираем топ-кластер
        top_cluster_id = error_logs['cluster'].value_counts().idxmax()
        top_cluster_logs = error_logs[error_logs['cluster'] == top_cluster_id]

        total_errors = len(error_logs)
        top_cluster_percentage = round((len(top_cluster_logs) / total_errors) * 100)

        sample_messages = top_cluster_logs['message'].head(2).tolist()

        example1 = (
            (sample_messages[0][:MAX_LOG_EXAMPLE_LENGTH] + '...')
            if len(sample_messages) > 0 and len(sample_messages[0]) > MAX_LOG_EXAMPLE_LENGTH
            else (sample_messages[0] if len(sample_messages) > 0 else "N/A")
        )
        example2 = (
            (sample_messages[1][:MAX_LOG_EXAMPLE_LENGTH] + '...')
            if len(sample_messages) > 1 and len(sample_messages[1]) > MAX_LOG_EXAMPLE_LENGTH
            else (sample_messages[1] if len(sample_messages) > 1 else "N/A")
        )

        return {
            "top_error_type": f"Схожие ошибки, сгруппированные в кластер №{top_cluster_id}",
            "percentage": top_cluster_percentage,
            "example1": example1,
            "example2": example2,
        }
