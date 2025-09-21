import { useQuery, QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SiteCard from "@/components/SiteCard";
import { Card } from "@/components/ui/card";
import React from "react";

// Создаем клиент React Query для v5
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchInterval: 30000, // обновляем каждые 30 секунд
      retry: 2,
      refetchOnWindowFocus: false,
    },
  },
});

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

// Функция для получения данных с API
const fetchSites = async (): Promise<SiteData[]> => {
  console.log("Fetching sites from API...");
  try {
    const response = await fetch("/api/sites/monitored");
    if (!response.ok) {
      throw new Error(`API error: ${response.status}`);
    }
    const data = await response.json();
    console.log("Sites data received:", data);
    return data;
  } catch (error) {
    console.error("Error fetching sites:", error);
    throw error;
  }
};

const DashboardContent = () => {
  const { data: sites = [], isLoading, isError, error } = useQuery<SiteData[]>({
    queryKey: ["sites"],
    queryFn: fetchSites,
  });

  if (isLoading) return (
      <div className="p-8 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mr-3"></div>
        <p>Загрузка сайтов...</p>
      </div>
  );

  if (isError) {
    console.error("Error loading sites:", error);
    return (
        <div className="p-8 bg-destructive/10 rounded-lg border border-destructive">
          <h2 className="text-xl font-bold mb-2">Ошибка загрузки данных с сервера.</h2>
          <p className="mb-4">Проверьте, что API доступен по адресу /api/sites/monitored</p>
          <button
              onClick={() => window.location.reload()}
              className="px-4 py-2 bg-primary text-white rounded-md"
          >
            Попробовать снова
          </button>
        </div>
    );
  }

  const onlineSites = sites.filter(site => site.status === "online");

  // Безопасный расчет среднего пинга с учетом null значений
  const validPings = sites.filter(site => site.ping !== null).map(site => site.ping || 0);
  const avgPing = validPings.length
      ? Math.round(validPings.reduce((sum, ping) => sum + ping * 1000, 0) / validPings.length)
      : 0;

  return (
      <div className="space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-3xl font-bold text-foreground">Мониторинг сайтов</h1>
          <p className="mt-2 text-muted-foreground">
            Отслеживание производительности и доступности ключевых сайтов
          </p>
        </div>

        {/* Overview Stats */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          <Card className="p-6 bg-white border border-border">
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Всего сайтов</p>
              <p className="text-2xl font-bold text-foreground">{sites.length}</p>
            </div>
          </Card>

          <Card className="p-6 bg-white border border-border">
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Онлайн</p>
              <p className="text-2xl font-bold text-success">{onlineSites.length}</p>
            </div>
          </Card>

          <Card className="p-6 bg-white border border-border">
            <div className="space-y-2">
              <p className="text-sm font-medium text-muted-foreground">Средний пинг</p>
              <p className="text-2xl font-bold text-foreground">{avgPing} мс</p>
            </div>
          </Card>
        </div>

        {/* Sites Grid */}
        <div className="space-y-6">
          <h2 className="text-xl font-semibold text-foreground">Отслеживаемые сайты</h2>
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {sites.map(site => (
                <SiteCard key={site.id} site={site} />
            ))}
          </div>
        </div>
      </div>
  );
};

// Главный компонент с QueryClientProvider
const Dashboard = () => (
    <QueryClientProvider client={queryClient}>
      <DashboardContent />
    </QueryClientProvider>
);

export default Dashboard;