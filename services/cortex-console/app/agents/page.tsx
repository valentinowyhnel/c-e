"use client";

import { AgentsOperationsPanel } from "@/components/agents-operations-panel";
import { ModelConnectivityPanel } from "@/components/model-connectivity-panel";
import { ModelKeyControl } from "@/components/model-key-control";

export default function AgentsPage() {
  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="agents-hero rounded-[2rem] p-6 md:p-8">
          <div className="grid gap-6 xl:grid-cols-[1.2fr_0.8fr]">
            <div>
              <div className="font-mono text-[11px] uppercase tracking-[0.35em] text-cyan-300">
                Agents Control
              </div>
              <h1 className="mt-4 text-4xl font-semibold leading-tight text-ink md:text-5xl">
                Connexion, sante et onboarding des agents Cortex.
              </h1>
              <p className="mt-4 max-w-3xl text-base leading-7 text-muted">
                Surface dediee a la verification de la chaine de connexion des agents, a la sante des modeles
                relies a Cortex, puis a la saisie propre des cles API Claude et GPT avec validation avant
                enregistrement.
              </p>
              <div className="mt-6 flex flex-wrap gap-3">
                <div className="rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1 text-xs text-cyan-100">
                  Gate runtime lisible
                </div>
                <div className="rounded-full border border-amber-500/30 bg-amber-500/10 px-3 py-1 text-xs text-amber-100">
                  Curation defensive tracee
                </div>
                <div className="rounded-full border border-white/10 bg-white/5 px-3 py-1 text-xs text-slate-200">
                  Claude / GPT onboarding
                </div>
              </div>
            </div>
            <div className="agents-rail rounded-[1.8rem] border border-white/10 p-5">
              <div className="flex items-center justify-between gap-3">
                <div className="font-mono text-[10px] uppercase tracking-[0.28em] text-muted">Scope</div>
                <div className="rounded-full border border-cyan-500/20 bg-cyan-500/10 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.22em] text-cyan-200">
                  phase 4-5
                </div>
              </div>
              <div className="mt-4 grid gap-3">
                <div className="metric-tile rounded-2xl border border-border/60 px-4 py-3 text-sm text-ink">
                  Installation logique des agents et bindings de taches
                </div>
                <div className="metric-tile rounded-2xl border border-border/60 px-4 py-3 text-sm text-ink">
                  Sante runtime des providers utilises par Cortex
                </div>
                <div className="metric-tile rounded-2xl border border-border/60 px-4 py-3 text-sm text-ink">
                  Espace dedie pour configurer Claude et GPT
                </div>
                <div className="metric-tile rounded-2xl border border-border/60 px-4 py-3 text-sm text-ink">
                  Curation defensive et routage des sources internes
                </div>
              </div>
            </div>
          </div>
        </div>

        <AgentsOperationsPanel />
        <ModelConnectivityPanel />
        <ModelKeyControl />
      </div>
    </main>
  );
}
