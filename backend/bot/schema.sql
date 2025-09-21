-- Создание таблицы для мониторинга
CREATE TABLE website_monitoring (
    timestamp DateTime64(3),
    response_time_ms Float64,
    full_load_time_ms Float64,
    cpu_usage_percent Float32,
    memory_usage_percent Float32,
    active_users UInt32,
    error_rate_percent Float32
) ENGINE = MergeTree()
ORDER BY timestamp;

-- Вставка тестовых данных
INSERT INTO website_monitoring VALUES
('2025-09-21 15:30:00', 55.4, 250.7, 45.2, 67.8, 1500, 1.2),
('2025-09-21 15:31:00', 62.1, 280.5, 48.1, 69.1, 1550, 1.5),
('2025-09-21 15:32:00', 59.8, 275.2, 46.5, 68.9, 1520, 1.3);