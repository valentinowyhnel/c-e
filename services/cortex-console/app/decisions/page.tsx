"use client";

import { DecisionTheater } from "@/components/decision-theater";
import { ModelConnectivityPanel } from "@/components/model-connectivity-panel";

export default function DecisionsPage() {
  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
            Decision Surface
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-ink">Decisions et approvals</h1>
          <p className="mt-2 text-sm text-muted">
            Vue operateur des arbitrages vLLM, Claude, GPT et interventions humaines, avec verification
            explicite de la connectivite des modeles et de la chaine API pour Claude et ChatGPT.
          </p>
        </div>
        <ModelConnectivityPanel />
        <DecisionTheater />
      </div>
    </main>
  );
}
