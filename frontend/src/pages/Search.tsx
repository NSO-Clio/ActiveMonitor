import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card } from "@/components/ui/card";
import { Search as SearchIcon, Globe, AlertCircle, BarChart2, PlusCircle, Loader } from "lucide-react";
import SiteCard from "@/components/SiteCard";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";

// Интерфейс сайта, соответствующий API
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

// Интерфейс отчета с аналитикой
interface AnalyticsReport {
  report: {
    performance_analysis?: string;
    security_analysis?: string;
    anomalies?: string;
    recommendations?: string[];
    [key: string]: any;
  };
}

const Search = () => {
  const [searchUrl, setSearchUrl] = useState("");
  const [searchResult, setSearchResult] = useState<SiteData | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [hasSearched, setHasSearched] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [analyticsResult, setAnalyticsResult] = useState<AnalyticsReport | null>(null);
  const [activeTab, setActiveTab] = useState("overview");
  const [isAddingSite, setIsAddingSite] = useState(false);
  const [addSiteResult, setAddSiteResult] = useState<{success: boolean; message: string} | null>(null);

  // Функция нормализации URL для поиска
  const normalizeUrl = (url: string) => {
    return url.replace(/^https?:\/\//i, '')
        .replace(/^www\./i, '')
        .replace(/\/$/, '')
        .toLowerCase();
  };

  const handleSearch = async () => {
    if (!searchUrl.trim()) return;

    setIsLoading(true);
    setHasSearched(true);
    setError(null);
    setAnalyticsResult(null);
    setAddSiteResult(null);
    setActiveTab("overview");

    try {
      // Используем относительный путь к API, соответствующий настройкам FastAPI
      const normalizedUrl = normalizeUrl(searchUrl);
      const response = await fetch(`/api/sites/search?url=${encodeURIComponent(normalizedUrl)}`);

      if (response.ok) {
        const data = await response.json();
        console.log("Search result:", data);
        setSearchResult(data);
      } else if (response.status === 404) {
        // Сайт не найден в системе мониторинга
        setSearchResult(null);
      } else {
        // Другие ошибки API
        const errorData = await response.json();
        setError(`Ошибка API: ${response.status} - ${errorData.detail || response.statusText}`);
        setSearchResult(null);
      }
    } catch (err) {
      console.error("Search error:", err);
      setError(`Ошибка запроса: ${err instanceof Error ? err.message : String(err)}`);
      setSearchResult(null);
    } finally {
      setIsLoading(false);
    }
  };

  const handleAnalyzeClick = async () => {
    if (!searchResult) return;

    setIsAnalyzing(true);
    setAnalyticsResult(null);
    setError(null);
    setActiveTab("analytics");

    try {
      const response = await fetch(`/api/sites/analyze-logs/${searchResult.id}`, {
        method: 'POST',
      });

      // Проверяем, содержит ли ответ валидный JSON
      const contentType = response.headers.get('content-type');

      if (response.ok) {
        if (contentType && contentType.includes('application/json')) {
          const data = await response.json();
          console.log("Analytics result:", data);
          setAnalyticsResult(data);
        } else {
          // Если сервер вернул не JSON, обрабатываем как текстовую ошибку
          const textResponse = await response.text();
          setError(`Ошибка анализа: Сервер вернул некорректный формат данных. ${textResponse.substring(0, 100)}...`);
        }
      } else {
        // Для ошибок сервера
        try {
          // Сначала пробуем получить JSON с деталями ошибки
          const errorData = await response.json();
          setError(`Ошибка анализа: ${response.status} - ${errorData.detail || response.statusText}`);
        } catch (jsonError) {
          // Если JSON не получается распарсить, получаем ошибку как текст
          const textError = await response.text();
          setError(`Ошибка анализа: ${response.status} - ${textError.substring(0, 100) || response.statusText}`);
        }
      }
    } catch (err) {
      console.error("Analytics error:", err);
      setError(`Ошибка анализа: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsAnalyzing(false);
    }
  };

  const handleAddSite = async () => {
    if (!searchUrl.trim()) return;

    setIsAddingSite(true);
    setAddSiteResult(null);
    setError(null);

    try {
      // Формируем имя из URL, если не указано иное
      const siteName = searchUrl.replace(/^https?:\/\//i, '').replace(/^www\./i, '');

      // Используем POST-запрос вместо GET
      const response = await fetch(`/api/sites/add`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: siteName,
          url: searchUrl
        })
      });

      if (response.ok) {
        const data = await response.json();
        setAddSiteResult({
          success: true,
          message: `Сайт успешно добавлен: ${siteName}`
        });

        // После успешного добавления, выполняем поиск снова
        await handleSearch();
      } else {
        const errorData = await response.json();
        setAddSiteResult({
          success: false,
          message: `Ошибка: ${errorData.detail || "Не удалось добавить сайт"}`
        });
      }
    } catch (err) {
      console.error("Add site error:", err);
      setAddSiteResult({
        success: false,
        message: `Ошибка: ${err instanceof Error ? err.message : String(err)}`
      });
    } finally {
      setIsAddingSite(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === "Enter") {
      handleSearch();
    }
  };

  const getStatusBadgeColor = (status: string) => {
    switch(status) {
      case "online": return "bg-green-500 hover:bg-green-600";
      case "offline": return "bg-red-500 hover:bg-red-600";
      case "warning": return "bg-yellow-500 hover:bg-yellow-600";
      default: return "bg-gray-500 hover:bg-gray-600";
    }
  };

  return (
      <div className="space-y-8">
        {/* Header */}
        <div className="text-center space-y-4">
          <div className="flex justify-center">
            <div className="p-3 bg-muted rounded-full">
              <Globe className="h-8 w-8 text-muted-foreground" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-foreground">Поиск и анализ сайта</h1>
          <p className="text-muted-foreground max-w-2xl mx-auto">
            Введите URL сайта для просмотра статистики мониторинга и аналитики производительности.
            Система позволяет получить детальный анализ работы отслеживаемых сайтов.
          </p>
        </div>

        {/* Search Form */}
        <Card className="p-6 bg-white border border-border max-w-2xl mx-auto">
          <div className="space-y-4">
            <div className="flex space-x-2">
              <Input
                  type="url"
                  placeholder="Введите URL сайта (например: google.com)"
                  value={searchUrl}
                  onChange={(e) => setSearchUrl(e.target.value)}
                  onKeyPress={handleKeyPress}
                  className="flex-1"
              />
              <Button
                  onClick={handleSearch}
                  disabled={isLoading || !searchUrl.trim()}
                  className="px-6"
              >
                {isLoading ? (
                    <>
                      <Loader className="h-4 w-4 mr-2 animate-spin" />
                      Поиск...
                    </>
                ) : (
                    <>
                      <SearchIcon className="h-4 w-4 mr-2" />
                      Найти
                    </>
                )}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Поддерживаемые форматы: google.com, https://google.com, www.google.com
            </p>
          </div>
        </Card>

        {/* Add Site Result Message */}
        {addSiteResult && (
            <div className={`max-w-2xl mx-auto p-4 rounded-md ${addSiteResult.success ? 'bg-green-50 border border-green-200 text-green-700' : 'bg-red-50 border border-red-200 text-red-700'}`}>
              <div className="flex items-center">
                {addSiteResult.success ? (
                    <PlusCircle className="h-5 w-5 mr-2 text-green-500" />
                ) : (
                    <AlertCircle className="h-5 w-5 mr-2 text-red-500" />
                )}
                <p>{addSiteResult.message}</p>
              </div>
            </div>
        )}

        {/* Search Results */}
        {hasSearched && !error && (
            <div className="max-w-4xl mx-auto">
              {searchResult ? (
                  <div className="space-y-6">
                    {/* Заголовок и статус с кнопкой анализа */}
                    <div className="flex flex-col sm:flex-row justify-between items-start sm:items-center gap-4">
                      <div className="flex items-center gap-2">
                        <h2 className="text-xl font-semibold text-foreground">Результаты поиска</h2>
                        <Badge className={getStatusBadgeColor(searchResult.status)}>
                          {searchResult.status === "online" ? "Онлайн" :
                              searchResult.status === "offline" ? "Офлайн" : "Внимание"}
                        </Badge>
                      </div>
                      <Button
                          onClick={handleAnalyzeClick}
                          disabled={isAnalyzing}
                          variant="outline"
                          className="shrink-0"
                      >
                        {isAnalyzing ? (
                            <>
                              <Loader className="h-4 w-4 mr-2 animate-spin" />
                              Анализ...
                            </>
                        ) : (
                            <>
                              <BarChart2 className="h-4 w-4 mr-2" />
                              Анализировать сайт
                            </>
                        )}
                      </Button>
                    </div>

                    {/* Tabs для переключения между обзором и аналитикой */}
                    <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
                      <TabsList className="grid w-full grid-cols-2">
                        <TabsTrigger value="overview">Обзор</TabsTrigger>
                        <TabsTrigger value="analytics">Аналитика</TabsTrigger>
                      </TabsList>

                      <TabsContent value="overview" className="mt-4">
                        <div className="grid grid-cols-1 gap-6">
                          <SiteCard site={searchResult} />
                        </div>
                      </TabsContent>

                      <TabsContent value="analytics" className="mt-4">
                        {analyticsResult ? (
                            <Card className="p-6 bg-white border border-border">
                              <div className="space-y-6">
                                <h3 className="text-lg font-semibold text-foreground">Аналитический отчет</h3>

                                {analyticsResult.report.performance_analysis && (
                                    <div className="space-y-2">
                                      <h4 className="font-medium text-foreground">Анализ производительности</h4>
                                      <p className="text-muted-foreground">{analyticsResult.report.performance_analysis}</p>
                                    </div>
                                )}

                                {analyticsResult.report.security_analysis && (
                                    <div className="space-y-2">
                                      <h4 className="font-medium text-foreground">Анализ безопасности</h4>
                                      <p className="text-muted-foreground">{analyticsResult.report.security_analysis}</p>
                                    </div>
                                )}

                                {analyticsResult.report.anomalies && (
                                    <div className="space-y-2">
                                      <h4 className="font-medium text-foreground">Обнаруженные аномалии</h4>
                                      <p className="text-muted-foreground">{analyticsResult.report.anomalies}</p>
                                    </div>
                                )}

                                {analyticsResult.report.recommendations && analyticsResult.report.recommendations.length > 0 && (
                                    <div className="space-y-2">
                                      <h4 className="font-medium text-foreground">Рекомендации</h4>
                                      <ul className="list-disc list-inside text-muted-foreground">
                                        {analyticsResult.report.recommendations.map((rec, index) => (
                                            <li key={index}>{rec}</li>
                                        ))}
                                      </ul>
                                    </div>
                                )}
                              </div>
                            </Card>
                        ) : isAnalyzing ? (
                            <div className="flex flex-col items-center justify-center p-12 text-center">
                              <Loader className="h-8 w-8 animate-spin text-primary mb-4" />
                              <p className="text-muted-foreground">Выполняется анализ сайта...</p>
                              <p className="text-sm text-muted-foreground mt-2">Это может занять несколько секунд</p>
                            </div>
                        ) : (
                            <div className="flex flex-col items-center justify-center p-12 text-center">
                              <BarChart2 className="h-8 w-8 text-muted-foreground mb-4" />
                              <p className="text-muted-foreground">Нажмите кнопку "Анализировать сайт" в верхней части страницы для получения аналитического отчета</p>
                            </div>
                        )}
                      </TabsContent>
                    </Tabs>
                  </div>
              ) : (
                  <Card className="p-8 text-center bg-white border border-border">
                    <div className="space-y-4">
                      <div className="p-3 bg-muted rounded-full w-fit mx-auto">
                        <SearchIcon className="h-6 w-6 text-muted-foreground" />
                      </div>
                      <h3 className="text-lg font-semibold text-foreground">Сайт не найден</h3>
                      <p className="text-muted-foreground">
                        К сожалению, сайт <span className="font-medium">{searchUrl}</span> не отслеживается в нашей системе мониторинга.
                      </p>
                      <div className="mt-4">
                        <Button
                            onClick={handleAddSite}
                            disabled={isAddingSite}
                            className="bg-primary hover:bg-primary/90"
                        >
                          {isAddingSite ? (
                              <>
                                <Loader className="h-4 w-4 mr-2 animate-spin" />
                                Добавление...
                              </>
                          ) : (
                              <>
                                <PlusCircle className="h-4 w-4 mr-2" />
                                Добавить сайт в мониторинг
                              </>
                          )}
                        </Button>
                      </div>
                    </div>
                  </Card>
              )}
            </div>
        )}

        {/* Error Display */}
        {error && (
            <Card className="p-6 bg-destructive/10 border border-destructive max-w-4xl mx-auto">
              <div className="flex items-start space-x-4">
                <AlertCircle className="h-6 w-6 text-destructive shrink-0 mt-1" />
                <div>
                  <h3 className="text-lg font-semibold text-foreground">Ошибка при поиске</h3>
                  <p className="text-muted-foreground mt-1">{error}</p>
                  <Button
                      variant="outline"
                      className="mt-4"
                      onClick={() => setError(null)}
                  >
                    Попробовать снова
                  </Button>
                </div>
              </div>
            </Card>
        )}

        {/* Tips Section */}
        <Card className="p-6 bg-muted border border-border max-w-4xl mx-auto">
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-foreground">💡 Советы по поиску и аналитике</h3>
            <div className="space-y-2 text-sm text-muted-foreground">
              <p>• При поиске не обязательно указывать <code>http://</code> или <code>https://</code></p>
              <p>• Поиск игнорирует префикс <code>www.</code> и другие субдомены</p>
              <p>• Аналитика использует данные за последние 24 часа для выявления трендов и аномалий</p>
              <p>• Для получения точных результатов анализа необходимо минимум 10 проверок сайта</p>
              <p>• Если сайт не найден, вы можете добавить его в систему мониторинга одним кликом</p>
            </div>
          </div>
        </Card>
      </div>
  );
};

export default Search;