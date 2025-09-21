import { Card } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface MetricCardProps {
  title: string;
  value: string | number;
  unit?: string;
  trend?: "up" | "down" | "stable";
  status?: "success" | "warning" | "error";
  className?: string;
}

const MetricCard = ({ title, value, unit, trend, status, className }: MetricCardProps) => {
  const getStatusColor = () => {
    switch (status) {
      case "success":
        return "text-success";
      case "warning":
        return "text-warning";
      case "error":
        return "text-destructive";
      default:
        return "text-foreground";
    }
  };

  const getTrendIcon = () => {
    switch (trend) {
      case "up":
        return "↗";
      case "down":
        return "↘";
      case "stable":
        return "→";
      default:
        return null;
    }
  };

  return (
    <Card className={cn("p-6 bg-white border border-border", className)}>
      <div className="space-y-2">
        <p className="text-sm font-medium text-muted-foreground">{title}</p>
        <div className="flex items-baseline space-x-1">
          <span className={cn("text-2xl font-bold", getStatusColor())}>
            {value}
          </span>
          {unit && (
            <span className="text-sm text-muted-foreground">{unit}</span>
          )}
          {trend && (
            <span className={cn("text-sm ml-2", getStatusColor())}>
              {getTrendIcon()}
            </span>
          )}
        </div>
      </div>
    </Card>
  );
};

export default MetricCard;