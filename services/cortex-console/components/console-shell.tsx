"use client";

import type { Route } from "next";
import Link from "next/link";
import { usePathname } from "next/navigation";

import { cn } from "@/lib/utils";

const NAV_ITEMS: Array<{ href: Route; label: string; hint: string }> = [
  { href: "/", label: "Cockpit", hint: "Vue globale" },
  { href: "/models", label: "Modeles", hint: "Cles et liaisons" },
  { href: "/search", label: "Recherche", hint: "Moteur profond" },
  { href: "/attack-paths", label: "Attack Paths", hint: "Tier 0 et blast" },
  { href: "/graph", label: "Graph", hint: "Privileges et relations" },
  { href: "/machines", label: "Machines", hint: "Fleet temps reel" },
  { href: "/decisions", label: "Decisions", hint: "Approvals et analyses" },
  { href: "/schemas", label: "Schemas", hint: "Contrats et structures" }
];

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen xl:grid xl:grid-cols-[17rem_minmax(0,1fr)]">
      <aside className="border-b border-border/70 bg-[#06101c]/95 backdrop-blur xl:min-h-screen xl:border-b-0 xl:border-r">
        <div className="sticky top-0 flex flex-col gap-6 p-4 xl:p-6">
          <div className="panel-sheen rounded-[1.6rem] border border-border/70 bg-panel/85 p-5 shadow-panel">
            <div className="font-mono text-[11px] uppercase tracking-[0.35em] text-cyan-300">
              Cortex Control
            </div>
            <h1 className="mt-3 text-[1.85rem] font-semibold leading-tight text-ink">Decision Surface</h1>
            <p className="mt-3 text-sm leading-6 text-muted">
              Correlation, trust, approvals et signal machine dans une seule surface operateur.
            </p>
            <div className="mt-4 flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
              <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />
              posture live
            </div>
          </div>

          <nav className="grid gap-2">
            {NAV_ITEMS.map((item) => {
              const active = pathname === item.href;
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={cn(
                    "rounded-2xl border px-4 py-3 transition duration-200",
                    active
                      ? "signal-glow border-cyan-400/60 bg-cyan-400/10 shadow-panel"
                      : "border-border/70 bg-panel/60 hover:border-cyan-500/40 hover:bg-panel/90"
                  )}
                >
                  <div className="text-sm font-semibold text-ink">{item.label}</div>
                  <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
                    {item.hint}
                  </div>
                </Link>
              );
            })}
          </nav>

          <div className="panel-sheen rounded-2xl border border-border/70 bg-panel/70 p-4">
            <div className="flex items-center gap-2">
              <span className="signal-glow h-2.5 w-2.5 rounded-full bg-green-500" />
              <span className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                Real-time polling
              </span>
            </div>
            <p className="mt-2 text-sm text-muted">
              Dashboard, health, graph et approvals sont rafraichis automatiquement.
            </p>
          </div>
        </div>
      </aside>

      <div className="min-w-0">
        <div className="border-b border-border/60 bg-[#081321]/80 px-4 py-3 backdrop-blur xl:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <div className="font-mono text-[11px] uppercase tracking-[0.3em] text-muted">
                Zero Trust Command
              </div>
              <div className="mt-1 text-sm text-ink">
                Interface operateur pour corriger, comprendre et contenir sans perdre la trace.
              </div>
            </div>
            <div className="rounded-full border border-border/70 bg-panel/70 px-3 py-1 font-mono text-xs text-muted">
              {pathname === "/" ? "cockpit" : pathname.replace("/", "")}
            </div>
          </div>
        </div>
        {children}
      </div>
    </div>
  );
}
