import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import MetricCard from "./MetricCard";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import React from "react";

// Обновленный интерфейс, соответствующий реальному API
interface SiteData {
  id: number;
  name: string;
  url: string;
  status: "online" | "offline" | "warning";
  ping: number | null;
  loadTime: number | null;
  uptime: number | null;
  lastChecked: string | null;
  status_code: number | null;
  content_size: number | null;
  ssl_valid: boolean | null;
  ssl_issuer: string | null;
  ssl_subject: string | null;
  frontend_title: string | null;
  html_size: number | null;
  console_logs: string | null;
}

interface Metric {
  timestamp: string;
  ping: number | null;
  loadTime: number | null;
}

interface SiteCardProps {
  site: SiteData;
}

// Функция для получения метрик с API
const fetchSiteMetrics = async (siteId: number, period: string): Promise<Metric[]> => {
  console.log(`Fetching metrics for site ${siteId}, period ${period}`);
  try {
    const response = await fetch(`/api/sites/${siteId}/metrics?period=${period}`);
    if (!response.ok) {
      // Для тестирования, возвращаем пустой массив вместо ошибки
      console.warn(`API returned status ${response.status} for metrics`);
      return [];
    }
    const data = await response.json();
    return data;
  } catch (error) {
    console.error(`Error fetching metrics for site ${siteId}:`, error);
    return []; // Возвращаем пустой массив вместо ошибки
  }
};

const SiteCard = ({ site }: SiteCardProps) => {
  const [period, setPeriod] = useState<"24h" | "7d" | "30d">("24h");

  const { data: metrics = [], isLoading, isError } = useQuery<Metric[]>({
    queryKey: ["siteMetrics", site.id, period],
    queryFn: () => fetchSiteMetrics(site.id, period),
    refetchInterval: 30000,
    enabled: Boolean(site.id), // запускаем запрос только если есть id
  });

  // Преобразуем данные для графика, учитывая null значения
  const chartData = metrics.map(m => ({
    time: m.timestamp ? new Date(m.timestamp).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "",
    ping: m.ping !== null ? m.ping * 1000 : 0, // переводим секунды в миллисекунды
    loadTime: m.loadTime !== null ? m.loadTime / 1000 : 0, // переводим миллисекунды в секунды
  }));

  const getStatusColor = () => {
    switch (site.status) {
      case "online": return "bg-success text-success-foreground";
      case "warning": return "bg-warning text-warning-foreground";
      case "offline": return "bg-destructive text-destructive-foreground";
      default: return "bg-muted text-muted-foreground";
    }
  };

  const getStatusText = () => {
    switch (site.status) {
      case "online": return "Онлайн";
      case "warning": return "Проблемы";
      case "offline": return "Офлайн";
      default: return "Неизвестно";
    }
  };

  // Безопасное получение значений с учетом null
  const pingValue = site.ping !== null ? site.ping * 1000 : 0; // переводим секунды в миллисекунды
  const loadTimeValue = site.loadTime !== null ? site.loadTime / 1000 : 0; // переводим миллисекунды в секунды
  const uptimeValue = site.uptime !== null ? site.uptime : 0;

  return (
      <Card className="p-6 bg-white border border-border">
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between">
            <div>
              <h3 className="text-lg font-semibold text-foreground">{site.name}</h3>
              <p className="text-sm text-muted-foreground">{site.url}</p>
            </div>
            <Badge className={getStatusColor()}>{getStatusText()}</Badge>
          </div>

          {/* Metrics */}
          <div className="grid grid-cols-3 gap-4">
            <MetricCard
                title="Пинг"
                value={pingValue.toFixed(0)}
                unit="мс"
                status={pingValue < 100 ? "success" : pingValue < 300 ? "warning" : "error"}
            />
            <MetricCard
                title="Время загрузки"
                value={loadTimeValue.toFixed(2)}
                unit="сек"
                status={loadTimeValue < 2 ? "success" : loadTimeValue < 5 ? "warning" : "error"}
            />
            <MetricCard
                title="Статус-код"
                value={site.status_code?.toString() || "—"}
                status={site.status_code === 200 ? "success" : site.status_code && site.status_code < 400 ? "warning" : "error"}
            />
          </div>

          {/* Additional Info */}
          <div className="text-sm grid grid-cols-2 gap-4">
            <div>
              <span className="text-muted-foreground">Размер контента:</span>{" "}
              {site.content_size ? `${(site.content_size / 1024).toFixed(1)} KB` : "—"}
            </div>
            <div>
              <span className="text-muted-foreground">SSL:</span>{" "}
              {site.ssl_valid === true ? "Действителен" : site.ssl_valid === false ? "Недействителен" : "—"}
            </div>
            {site.frontend_title && (
                <div className="col-span-2 truncate">
                  <span className="text-muted-foreground">Заголовок:</span>{" "}
                  {site.frontend_title}
                </div>
            )}
            {site.lastChecked && (
                <div className="col-span-2">
                  <span className="text-muted-foreground">Последняя проверка:</span>{" "}
                  {new Date(site.lastChecked).toLocaleString()}
                </div>
            )}
          </div>

          {/* Chart */}
          <div className="space-y-2">
            <h4 className="text-sm font-medium text-foreground">Метрики за {period}</h4>
            {isLoading ? (
                <div className="h-40 flex items-center justify-center">
                  <div className="animate-spin rounded-full h-5 w-5 border-b-2 border-primary mr-2"></div>
                  <span>Загрузка графика...</span>
                </div>
            ) : isError ? (
                <div className="h-40 flex items-center justify-center bg-muted/20 rounded-md">
                  <p className="text-sm text-muted-foreground">Ошибка загрузки метрик</p>
                </div>
            ) : metrics.length === 0 ? (
                <div className="h-40 flex items-center justify-center bg-muted/20 rounded-md">
                  <p className="text-sm text-muted-foreground">Нет данных за выбранный период</p>
                </div>
            ) : (
                <div className="h-40">
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={chartData}>
                      <XAxis
                          dataKey="time"
                          axisLine={false}
                          tickLine={false}
                          tick={{ fontSize: 12, fill: 'hsl(var(--muted-foreground))' }}
                      />
                      <YAxis hide />
                      <Tooltip
                          contentStyle={{
                            backgroundColor: 'white',
                            border: '1px solid hsl(var(--border))',
                            borderRadius: '6px',
                            fontSize: '12px'
                          }}
                          formatter={(value: any, name: string) => {
                            if (name === "ping") return [`${value.toFixed(0)} мс`, "Пинг"];
                            if (name === "loadTime") return [`${value.toFixed(2)} с`, "Время загрузки"];
                            return [value, name];
                          }}
                      />
                      <Line
                          type="monotone"
                          dataKey="ping"
                          stroke="hsl(var(--primary))"
                          strokeWidth={2}
                          dot={false}
                          name="Пинг"
                      />
                      <Line
                          type="monotone"
                          dataKey="loadTime"
                          stroke="hsl(var(--accent))"
                          strokeWidth={2}
                          dot={false}
                          name="Время загрузки"
                      />
                    </LineChart>
                  </ResponsiveContainer>
                </div>
            )}

            {/* Period selection */}
            <div className="flex gap-2 mt-2">
              {(["24h", "7d", "30d"] as const).map(p => (
                  <button
                      key={p}
                      onClick={() => setPeriod(p)}
                      className={`px-2 py-1 border rounded text-sm ${
                          period === p ? "bg-primary text-white" : "bg-background"
                      }`}
                  >
                    {p}
                  </button>
              ))}
            </div>
          </div>
        </div>
      </Card>
  );
};

export default SiteCard;