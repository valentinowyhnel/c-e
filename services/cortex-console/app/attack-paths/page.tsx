"use client";

import { AttackPathExplorer } from "@/components/attack-path-explorer";

export default function AttackPathsPage() {
  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
            Attack Paths
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-ink">Chemins d&apos;attaque</h1>
          <p className="mt-2 text-sm text-muted">
            Vue dediee aux chemins BloodHound, au blast radius et aux zones Tier 0.
          </p>
        </div>
        <AttackPathExplorer />
      </div>
    </main>
  );
}
