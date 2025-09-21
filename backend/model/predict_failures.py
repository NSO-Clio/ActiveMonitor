import warnings
from datetime import datetime
import pandas as pd
import pickle
from prophet import Prophet

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Конфигурация динамического порога ---
RELATIVE_THRESHOLD_MULTIPLIER = 3.0
ABSOLUTE_THRESHOLD_ADDITION_MS = 500


class DetectorAnomaly:
    """Класс для детекции аномалий и прогнозирования потенциальных сбоев с pickle."""

    def __init__(self, anomalies_model_path: str, potential_failures_model_path: str) -> None:
        """
        Инициализация: загружает модели Prophet из pickle-файлов.

        Args:
            anomalies_model_path (str): путь к pickle модели для детекции аномалий
            potential_failures_model_path (str): путь к pickle модели для прогнозирования
        """
        self.model_anomalies: Prophet = pickle.load(open(anomalies_model_path, "rb"))
        print(f"INFO: Модель детекции аномалий загружена из {anomalies_model_path}")

        self.model_potential_failures: Prophet = pickle.load(open(potential_failures_model_path, "rb"))
        print(f"INFO: Модель прогнозирования загружена из {potential_failures_model_path}")

    def check_for_anomalies(self, old_logs: list) -> dict | None:
        """Анализ прошлых данных для детекции внезапных аномалий."""
        print(f"INFO (Детектор): Анализ прошлого из {old_logs}...")
        old_logs = pd.DataFrame(old_logs)
        if old_logs.empty:
            return None
        old_logs["timestamp"] = pd.to_datetime(old_logs["timestamp"])
        
        print(old_logs)

        prophet_df = old_logs[["timestamp", "response_time_ms"]].rename(
            columns={"timestamp": "ds", "response_time_ms": "y"}
        )

        forecast = self.model_anomalies.predict(prophet_df)

        results = pd.merge(
            prophet_df,
            forecast[["ds", "yhat", "yhat_lower", "yhat_upper"]],
            on="ds",
        )
        results["anomaly"] = results["y"] > results["yhat_upper"]

        latest_anomaly = results[results["anomaly"]].tail(1)

        if not latest_anomaly.empty:
            return {
                "type": "Обнаружена прошлая аномалия",
                "timestamp": latest_anomaly["ds"].iloc[0].strftime("%Y-%m-%d %H:%M:%S"),
                "value": f"{latest_anomaly['y'].iloc[0]:.0f} ms",
                "expected": f"не более {latest_anomaly['yhat_upper'].iloc[0]:.0f} ms",
            }

        return None

    def predict_potential_failures(self, metrics_filepath: str, prediction_minutes: int = 60) -> dict | None:
        """Прогноз будущих сбоев с динамическим порогом."""
        print(f"INFO (Предсказатель): Прогнозирование будущего из {metrics_filepath}...")
        try:
            metrics_df = pd.read_json(metrics_filepath)
            if metrics_df.empty:
                return None
            metrics_df["timestamp"] = pd.to_datetime(metrics_df["timestamp"])
        except Exception:
            return None

        future = self.model_potential_failures.make_future_dataframe(
            periods=prediction_minutes, freq="T"
        )
        forecast = self.model_potential_failures.predict(future)

        now = datetime.now()
        future_forecast = forecast[forecast["ds"] > now].copy()
        if future_forecast.empty:
            return None

        future_forecast["dynamic_threshold"] = future_forecast.apply(
            lambda row: max(
                row["yhat"] * RELATIVE_THRESHOLD_MULTIPLIER,
                row["yhat"] + ABSOLUTE_THRESHOLD_ADDITION_MS,
            ),
            axis=1,
        )

        potential_failures = future_forecast[
            future_forecast["yhat_upper"] > future_forecast["dynamic_threshold"]
        ]

        if not potential_failures.empty:
            predicted_event = potential_failures.iloc[0]
            return {
                "type": "Прогноз будущего сбоя (динамический порог)",
                "predicted_time": predicted_event["ds"].strftime("%Y-%m-%d %H:%M:%S"),
                "predicted_max_value": f"до {predicted_event['yhat_upper']:.0f} ms",
                "expected_norm_for_this_time": f"~{predicted_event['yhat']:.0f} ms",
                "triggered_threshold": f"{predicted_event['dynamic_threshold']:.0f} ms",
            }

        return None
