// src/lib/api.ts
export const fetchSites = async () => {
    const res = await fetch("/api/monitor/monitored");
    if (!res.ok) throw new Error("Ошибка при загрузке сайтов");
    return res.json();
};

export const fetchSiteMetrics = async (siteId: number, period = "24h") => {
    const res = await fetch(`/api/monitor/${siteId}/metrics?period=${period}`);
    if (!res.ok) throw new Error("Ошибка при загрузке метрик сайта");
    return res.json();
};
