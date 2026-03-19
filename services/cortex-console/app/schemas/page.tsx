"use client";

import { SchemaExplorer } from "@/components/schema-explorer";

export default function SchemasPage() {
  return (
    <main className="min-h-screen p-4 md:p-8">
      <div className="mx-auto max-w-7xl space-y-6">
        <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
            Schema Lens
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-ink">Schemas et contrats</h1>
          <p className="mt-2 text-sm text-muted">
            Lecture des structures Sentinel, trust, AD drift et decisions.
          </p>
        </div>
        <SchemaExplorer />
      </div>
    </main>
  );
}
