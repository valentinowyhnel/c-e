"use client";

import { useEffect, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { IdentityGraph } from "@/components/identity-graph";

type SearchResult = {
  id: string;
  type: string;
  displayName?: string;
};

async function loadEntity(entityId: string) {
  const response = await fetch(`/api/graph/entities/${encodeURIComponent(entityId)}`, {
    cache: "no-store"
  });
  if (!response.ok) {
    throw new Error("graph_entity_failed");
  }
  return response.json();
}

export default function GraphPage() {
  const [query, setQuery] = useState("");
  const [results, setResults] = useState<SearchResult[]>([]);
  const [error, setError] = useState("");
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);

  useEffect(() => {
    if (!selectedEntity && results[0]) {
      setSelectedEntity(results[0].id);
    }
  }, [results, selectedEntity]);

  const { data: entityData } = useQuery({
    queryKey: ["graph-entity", selectedEntity],
    queryFn: () => loadEntity(selectedEntity as string),
    enabled: Boolean(selectedEntity),
    refetchInterval: 10_000
  });

  async function searchGraph() {
    setError("");
    const response = await fetch(`/api/graph/search?q=${encodeURIComponent(query)}`, {
      cache: "no-store"
    });
    const payload = await response.json();
    if (!response.ok) {
      setResults([]);
      setError(String(payload.error ?? "graph_search_failed"));
      return;
    }
    setResults(Array.isArray(payload.results) ? payload.results : []);
    setSelectedEntity(Array.isArray(payload.results) && payload.results[0] ? payload.results[0].id : null);
  }

  return (
    <main className="min-h-screen p-6">
      <div className="mx-auto max-w-7xl space-y-4">
        <div className="rounded-3xl border bg-panel/80 p-5 shadow-panel">
          <div className="font-mono text-xs uppercase tracking-[0.3em] text-cyan-300">
            Privilege Topology
          </div>
          <h1 className="mt-2 text-3xl font-semibold text-ink">Identity Graph</h1>
          <p className="mt-2 text-sm text-muted">
            Recherche, inspection et lecture des chemins de privilege en temps quasi reel.
          </p>
        </div>
        <div className="flex flex-col gap-3 rounded-2xl border bg-panel/80 p-4 shadow-panel md:flex-row">
          <input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search entity id or display name"
            className="flex-1 rounded-md border border-border/70 bg-background/50 px-3 py-2 text-sm text-ink outline-none"
          />
          <button
            onClick={() => void searchGraph()}
            className="rounded-md bg-success px-4 py-2 text-sm font-semibold text-white"
          >
            Search
          </button>
        </div>
        {error ? <div className="font-mono text-sm text-red-300">{error}</div> : null}
        {results.length > 0 ? (
          <div className="rounded-2xl border bg-panel/80 p-4 shadow-panel">
            <div className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Search Results
            </div>
            <div className="space-y-2">
              {results.map((result) => (
                <button
                  key={result.id}
                  type="button"
                  onClick={() => setSelectedEntity(result.id)}
                  className={`w-full rounded-xl border px-3 py-2 text-left ${
                    selectedEntity === result.id
                      ? "border-cyan-400/60 bg-cyan-400/10"
                      : "border-border/70 bg-background/40"
                  }`}
                >
                  <div className="font-mono text-xs text-muted">{result.type}</div>
                  <div className="text-sm text-ink">{result.displayName || result.id}</div>
                  <div className="font-mono text-xs text-muted">{result.id}</div>
                </button>
              ))}
            </div>
          </div>
        ) : null}
        <section className="grid gap-6 xl:grid-cols-[1.05fr_0.95fr]">
          <IdentityGraph highlightId={selectedEntity} onNodeSelect={setSelectedEntity} />

          <div className="rounded-2xl border bg-panel/80 p-4 shadow-panel">
            <div className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Entity Inspector
            </div>
            {selectedEntity ? (
              <div className="mt-4 space-y-3">
                <div className="rounded-xl border border-border/70 bg-background/35 p-3">
                  <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                    Selected entity
                  </div>
                  <div className="mt-2 text-sm text-ink">{selectedEntity}</div>
                </div>
                <pre className="max-h-[24rem] overflow-auto rounded-xl border border-border/70 bg-background/35 p-3 font-mono text-xs text-muted">
                  {JSON.stringify(entityData ?? { state: "loading" }, null, 2)}
                </pre>
              </div>
            ) : (
              <div className="mt-4 rounded-xl border border-dashed border-border/70 p-6 text-sm text-muted">
                Selectionnez une entite dans les resultats ou directement dans le graphe.
              </div>
            )}
          </div>
        </section>
      </div>
    </main>
  );
}
