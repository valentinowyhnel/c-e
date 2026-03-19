"use client";

import { ModelKeyControl } from "@/components/model-key-control";

export default function ModelsPage() {
  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">Model Governance</div>
          <h1 className="mt-2 text-3xl font-semibold text-ink">Cles API, verification et liaison agents</h1>
          <p className="mt-2 max-w-3xl text-sm text-muted">
            Cette page centralise les cles Anthropic et OpenAI, les modeles vLLM relies au MCP, puis
            verifie que chaque agent utilise un modele compatible avec ses taches reelles.
          </p>
        </div>
        <ModelKeyControl />
      </div>
    </main>
  );
}
