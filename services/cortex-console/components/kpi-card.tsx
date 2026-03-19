import { cn } from "@/lib/utils";

export function KpiCard({
  title,
  value,
  tone = "default",
  subtitle
}: {
  title: string;
  value: string;
  tone?: "default" | "danger" | "warning" | "success";
  subtitle?: string;
}) {
  return (
    <div
      className={cn(
        "rounded-2xl border bg-panel/80 p-4 shadow-panel backdrop-blur-sm",
        tone === "danger" && "border-danger/50",
        tone === "warning" && "border-warning/50",
        tone === "success" && "border-success/50"
      )}
    >
      <div className="text-xs uppercase tracking-[0.2em] text-muted">{title}</div>
      <div className="mt-3 font-mono text-3xl font-semibold text-ink">{value}</div>
      {subtitle ? <div className="mt-2 text-sm text-muted">{subtitle}</div> : null}
    </div>
  );
}
