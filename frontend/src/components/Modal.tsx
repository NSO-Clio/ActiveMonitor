import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import MetricCard from "./MetricCard";
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from "recharts";
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import React from "react";
import Modal from "./Modal"; // <- импортируем модалку

interface SiteData { /* как раньше */ }
interface Metric { /* как раньше */ }
interface SiteCardProps { site: SiteData }

const fetchSiteMetrics = async (siteId: number, period: string): Promise<Metric[]> => { /* как раньше */ };

const SiteCard = ({ site }: SiteCardProps) => {
    const [period, setPeriod] = useState<"24h" | "7d" | "30d">("24h");
    const [isAnalyzing, setIsAnalyzing] = useState(false);
    const [anomalyReport, setAnomalyReport] = useState<string | null>(null);
    const [isModalOpen, setIsModalOpen] = useState(false);

    const { data: metrics = [], isLoading, isError } = useQuery<Metric[]>({
        queryKey: ["siteMetrics", site.id, period],
        queryFn: () => fetchSiteMetrics(site.id, period),
        refetchInterval: 30000,
        enabled: Boolean(site.id),
    });

    const handleAnalyzeLogs = async () => {
        setIsAnalyzing(true);
        try {
            const resp = await fetch(`/api/sites/analyze/${site.id}`, { method: "POST" });
            if (!resp.ok) throw new Error(`Ошибка анализа: ${resp.status}`);
            const data = await resp.json();
            setAnomalyReport(JSON.stringify(data.report, null, 2));
            setIsModalOpen(true);
        } catch (err: any) {
            setAnomalyReport(`Ошибка: ${err.message}`);
            setIsModalOpen(true);
        } finally {
            setIsAnalyzing(false);
        }
    };

    // остальной код карточки — как раньше, без отображения anomalyReport внутри
    return (
        <>
            <Card className="p-6 bg-white border border-border space-y-6">
                {/* Header, metrics, chart... */}
                <div>
                    <button
                        className="px-4 py-2 bg-primary text-white rounded-md"
                        onClick={handleAnalyzeLogs}
                        disabled={isAnalyzing}
                    >
                        {isAnalyzing ? "Анализ..." : "Анализ логов"}
                    </button>
                </div>
                {/* Остальные метрики, график и period selection */}
            </Card>

            {/* Модалка с результатом */}
            <Modal
                isOpen={isModalOpen}
                onClose={() => setIsModalOpen(false)}
                title={`Результат анализа логов для ${site.name}`}
            >
                <pre className="whitespace-pre-wrap">{anomalyReport}</pre>
            </Modal>
        </>
    );
};

export default SiteCard;
