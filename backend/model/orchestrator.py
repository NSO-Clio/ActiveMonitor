import argparse
from datetime import datetime
import os
from .predict_failures import DetectorAnomaly
from .notification_manager import NotificationManager
from .analyze_logs import LogAnalyzer
from .report_generator import ReportGenerator


class Orchestr:
    def __init__(self, api_key: str, model_name: str):
        self.detector = DetectorAnomaly(
            anomalies_model_path=os.path.abspath('model/weights/anomaly_detector.pkl'),
            potential_failures_model_path=os.path.abspath('model/weights/failure_predictor.pkl')
        )
        self.notification_manager = NotificationManager(api_key=api_key, model_name=model_name)
        self.report_generator = ReportGenerator(api_key=api_key, model_name=model_name)
        self.log_analyzer = LogAnalyzer(
            vectorizer_path=os.path.abspath('model/weights/tfidf_vectorizer.pkl'),
            kmeans_path=os.path.abspath('model/weights/kmeans_model.pkl')
        )

    def get_predict(self, old_logs: list, logs_anomaly: list, choice_role: bool):
        predicted_failure = self.detector.predict_potential_failures(old_logs)
        if predicted_failure:
            print(f"!!! ПРОГНОЗ: Агент предсказывает будущий сбой: {predicted_failure}")
            final_report = self.report_generator.generate_incident_report(predicted_failure, None)
        else:
            print("--- Агент сообщает: Прогноз стабилен. Анализирую прошлое. ---")

            anomaly_details = self.detector.check_for_anomalies(old_logs)
            if not anomaly_details:
                print("--- Агент сообщает: Цикл завершен. Проблем не обнаружено. ---")
                return

            print(f"!!! ДЕТЕКЦИЯ: Агент обнаружил прошлую аномалию: {anomaly_details}")

            log_analysis_results = self.log_analyzer.analyze(logs_anomaly)
            final_report = self.report_generator.generate_incident_report(anomaly_details, log_analysis_results)
        if choice_role:
            return (final_report, self.notification_manager.determine_responsible_engineer(anomaly_details, log_analysis_results))
        return final_report


# test = Orchestr(
#     api_key=API_KEY,
#     model_name=MODEL_NAME
# )

# print(
#     test.get_predict(
#         old_logs=[
#             { "timestamp": "2025-09-21T10:00:00", "response_time_ms": 210 },
#             { "timestamp": "2025-09-21T10:01:00", "response_time_ms": 225 },
#             { "timestamp": "2025-09-21T10:02:00", "response_time_ms": 198 },
#             { "timestamp": "2025-09-21T10:03:00", "response_time_ms": 10000 }
#         ],
#         logs_anomaly=[
#             {"timestamp": "2025-09-21 10:03:10", "log_level": "ERROR", "message": "Database connection refused by host 127.0.0.1"},
#             {"timestamp": "2025-09-21 10:03:12", "log_level": "INFO", "message": "Request processed"},
#             {"timestamp": "2025-09-21 10:03:15", "log_level": "ERROR", "message": "Database connection refused by host 127.0.0.1"},
#             {"timestamp": "2025-09-21 10:03:20", "log_level": "ERROR", "message": "Failed to authenticate user 'guest'"},
#             {"timestamp": "2025-09-21 10:03:25", "log_level": "ERROR", "message": "Database connection refused by host 127.0.0.1"}
#         ],
#         choice_role=True
#     )
# )