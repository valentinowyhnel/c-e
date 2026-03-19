"use client";

import { DeepSearchWorkbench } from "@/components/deep-search-workbench";

export default function SearchPage() {
  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
            Deep Search
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-ink">Recherche profonde</h1>
          <p className="mt-2 text-sm text-muted">
            Moteur de recherche operateur pour privileges, ressources, noeuds, machines et graphes
            de risque.
          </p>
        </div>

        <DeepSearchWorkbench />
      </div>
    </main>
  );
}
