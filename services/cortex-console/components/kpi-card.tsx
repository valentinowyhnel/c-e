import { cn } from "@/lib/utils";

export function KpiCard({
  title,
  value,
  tone = "default",
  subtitle,
  eyebrow
}: {
  title: string;
  value: string;
  tone?: "default" | "danger" | "warning" | "success";
  subtitle?: string;
  eyebrow?: string;
}) {
  return (
    <div
      className={cn(
        "panel-sheen rounded-[1.7rem] border bg-panel/80 p-5 shadow-panel backdrop-blur-sm",
        tone === "default" && "border-border/80",
        tone === "danger" && "danger-glow border-danger/50 bg-danger/10",
        tone === "warning" && "border-warning/50 bg-warning/10",
        tone === "success" && "border-success/50 bg-success/10"
      )}
    >
      {eyebrow ? (
        <div className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted">{eyebrow}</div>
      ) : null}
      <div className="mt-2 text-xs uppercase tracking-[0.2em] text-muted">{title}</div>
      <div className="mt-4 flex items-end justify-between gap-3">
        <div className="font-mono text-4xl font-semibold leading-none text-ink">{value}</div>
        <span
          className={cn(
            "rounded-full px-2 py-1 font-mono text-[10px] uppercase tracking-[0.18em]",
            tone === "danger" && "bg-danger/20 text-red-100",
            tone === "warning" && "bg-warning/20 text-amber-100",
            tone === "success" && "bg-success/20 text-emerald-100",
            tone === "default" && "bg-signal/10 text-cyan-100"
          )}
        >
          {tone}
        </span>
      </div>
      {subtitle ? <div className="mt-3 text-sm leading-6 text-muted">{subtitle}</div> : null}
    </div>
  );
}
