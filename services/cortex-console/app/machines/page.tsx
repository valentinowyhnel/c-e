"use client";

import { MachineFleetPanel } from "@/components/machine-fleet-panel";

export default function MachinesPage() {
  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
            Fleet View
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-ink">Machines et agents</h1>
          <p className="mt-2 text-sm text-muted">
            Lecture claire de la flotte Cortex, de la sante et des pressions de risque.
          </p>
        </div>
        <MachineFleetPanel />
      </div>
    </main>
  );
}
