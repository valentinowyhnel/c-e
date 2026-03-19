"use client";

import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";

import { IdentityGraph } from "@/components/identity-graph";
import { NodeComparePanel } from "@/components/node-compare-panel";
import { NodeEvolutionPanel } from "@/components/node-evolution-panel";

type DeepSearchRecord = {
  id: string;
  label: string;
  category: "machine" | "resource" | "identity" | "agent" | "node";
  privilegeScore: number;
  blastRadiusScore: number;
  tierZeroExposure: boolean;
  attackPathCount: number;
};

type SearchPayload = {
  records: DeepSearchRecord[];
  tierZeroAssets?: string[];
};

type AttackPathPayload = {
  data?: {
    paths?: Array<{
      nodes?: string[];
      edges?: string[];
      length?: number;
    }>;
  };
};

type SavedScenario = {
  name: string;
  source: string;
  target: string;
};

const ATTACK_SCENARIOS_KEY = "cortex-console.attack-paths.saved-scenarios";
const ATTACK_STATE_KEY = "cortex-console.attack-paths.state";
const ATTACK_COMPARE_KEY = "cortex-console.attack-paths.compare";
const ATTACK_SERVER_SCOPE = "attack-paths";

async function loadCandidates(): Promise<SearchPayload> {
  const response = await fetch("/api/search/deep", { cache: "no-store" });
  if (!response.ok) {
    throw new Error("deep_search_failed");
  }
  return response.json();
}

async function loadAttackPath(source: string, target: string): Promise<AttackPathPayload> {
  const response = await fetch(
    `/api/search/attack-paths?source=${encodeURIComponent(source)}&target=${encodeURIComponent(target)}`,
    { cache: "no-store" }
  );
  if (!response.ok) {
    throw new Error("attack_path_failed");
  }
  return response.json();
}

export function AttackPathExplorer() {
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("tier0");
  const [selectedNode, setSelectedNode] = useState<string | null>(null);
  const [scenarioName, setScenarioName] = useState("");
  const [savedScenarios, setSavedScenarios] = useState<SavedScenario[]>([]);
  const [compareIds, setCompareIds] = useState<string[]>([]);
  const { data } = useQuery({
    queryKey: ["attack-candidates"],
    queryFn: loadCandidates,
    refetchInterval: 8_000
  });

  const highRisk = useMemo(
    () =>
      (data?.records ?? [])
        .filter((record) => record.privilegeScore >= 60 || record.tierZeroExposure)
        .sort((left, right) => right.privilegeScore - left.privilegeScore)
        .slice(0, 12),
    [data]
  );

  useEffect(() => {
    let cancelled = false;

    async function loadServerState() {
      try {
        const response = await fetch(`/api/operator-state?scope=${ATTACK_SERVER_SCOPE}`, {
          cache: "no-store"
        });
        if (!response.ok) {
          return;
        }
        const payload = (await response.json()) as Partial<{
          source: string;
          target: string;
          selectedNode: string | null;
          savedScenarios: SavedScenario[];
          compareIds: string[];
        }>;
        if (cancelled) {
          return;
        }
        if (payload.source) setSource(payload.source);
        if (payload.target) setTarget(payload.target);
        if (payload.selectedNode !== undefined) setSelectedNode(payload.selectedNode);
        if (Array.isArray(payload.savedScenarios)) setSavedScenarios(payload.savedScenarios);
        if (Array.isArray(payload.compareIds)) setCompareIds(payload.compareIds);
      } catch {
        // Ignore server state failures and keep local-first behavior.
      }
    }

    void loadServerState();

    try {
      const rawState = window.localStorage.getItem(ATTACK_STATE_KEY);
      if (rawState) {
        const parsed = JSON.parse(rawState) as Partial<{
          source: string;
          target: string;
          selectedNode: string | null;
        }>;
        if (parsed.source) setSource(parsed.source);
        if (parsed.target) setTarget(parsed.target);
        if (parsed.selectedNode !== undefined) setSelectedNode(parsed.selectedNode);
      }
    } catch {
      // Ignore invalid local state.
    }

    try {
      const rawScenarios = window.localStorage.getItem(ATTACK_SCENARIOS_KEY);
      if (!rawScenarios) {
        return;
      }
      const parsed = JSON.parse(rawScenarios) as SavedScenario[];
      if (Array.isArray(parsed)) {
        setSavedScenarios(parsed);
      }
    } catch {
      // Ignore invalid local scenarios.
    }

    try {
      const rawCompare = window.localStorage.getItem(ATTACK_COMPARE_KEY);
      if (!rawCompare) {
        return;
      }
      const parsed = JSON.parse(rawCompare) as string[];
      if (Array.isArray(parsed)) {
        setCompareIds(parsed);
      }
    } catch {
      // Ignore invalid local compare list.
    }

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!source && highRisk[0]) {
      setSource(highRisk[0].id);
      setSelectedNode(highRisk[0].id);
    }
  }, [highRisk, source]);

  useEffect(() => {
    window.localStorage.setItem(
      ATTACK_STATE_KEY,
      JSON.stringify({ source, target, selectedNode })
    );
  }, [source, target, selectedNode]);

  useEffect(() => {
    const controller = new AbortController();
    void fetch(`/api/operator-state?scope=${ATTACK_SERVER_SCOPE}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        source,
        target,
        selectedNode,
        savedScenarios,
        compareIds
      }),
      signal: controller.signal
    }).catch(() => undefined);
    return () => controller.abort();
  }, [source, target, selectedNode, savedScenarios, compareIds]);

  const { data: attackData } = useQuery({
    queryKey: ["attack-path", source, target],
    queryFn: () => loadAttackPath(source, target),
    enabled: Boolean(source && target),
    refetchInterval: 10_000
  });

  const paths = attackData?.data?.paths ?? [];
  const selectedRecord =
    highRisk.find((record) => record.id === selectedNode) ??
    highRisk.find((record) => record.id === source) ??
    null;
  const beforeAfter = useMemo(() => {
    if (!selectedRecord) {
      return null;
    }

    const privilegeAfter = Math.max(4, selectedRecord.privilegeScore - 28);
    const blastAfter = Math.max(2, selectedRecord.blastRadiusScore - 34);
    const pathAfter = Math.max(0, selectedRecord.attackPathCount - 1);

    return {
      privilegeBefore: selectedRecord.privilegeScore,
      privilegeAfter,
      blastBefore: selectedRecord.blastRadiusScore,
      blastAfter,
      pathBefore: selectedRecord.attackPathCount,
      pathAfter
    };
  }, [selectedRecord]);
  const compareNodes = highRisk.filter((record) => compareIds.includes(record.id));

  const saveScenario = () => {
    const name = scenarioName.trim();
    if (!name || !source || !target) {
      return;
    }
    const next = [{ name, source, target }, ...savedScenarios.filter((item) => item.name !== name)].slice(0, 10);
    setSavedScenarios(next);
    setScenarioName("");
    window.localStorage.setItem(ATTACK_SCENARIOS_KEY, JSON.stringify(next));
  };

  const removeScenario = (name: string) => {
    const next = savedScenarios.filter((item) => item.name !== name);
    setSavedScenarios(next);
    window.localStorage.setItem(ATTACK_SCENARIOS_KEY, JSON.stringify(next));
  };

  const toggleCompare = (id: string) => {
    const next = compareIds.includes(id)
      ? compareIds.filter((item) => item !== id)
      : [...compareIds, id].slice(0, 3);
    setCompareIds(next);
    window.localStorage.setItem(ATTACK_COMPARE_KEY, JSON.stringify(next));
  };

  return (
    <div className="space-y-6">
      <section className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Attack Path Explorer
            </h2>
            <p className="mt-1 text-sm text-muted">
              Lecture des chemins de privilege et estimation du blast radius vers Tier 0.
            </p>
          </div>
          <div className="rounded-full border border-border/70 px-3 py-1 font-mono text-xs text-muted">
            {paths.length} path(s)
          </div>
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-[1fr_0.8fr]">
          <input
            value={source}
            onChange={(event) => {
              setSource(event.target.value);
              setSelectedNode(event.target.value);
            }}
            placeholder="Source object id"
            className="rounded-2xl border border-border/70 bg-background/45 px-4 py-3 text-sm text-ink outline-none"
          />
          <input
            value={target}
            onChange={(event) => setTarget(event.target.value)}
            placeholder="Target object id"
            className="rounded-2xl border border-border/70 bg-background/45 px-4 py-3 text-sm text-ink outline-none"
          />
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {highRisk.map((record) => (
            <button
              key={record.id}
              type="button"
              onClick={() => {
                setSource(record.id);
                setSelectedNode(record.id);
              }}
              className="rounded-full border border-border/70 bg-background/40 px-3 py-2 text-xs font-mono text-muted hover:border-cyan-500/40 hover:text-ink"
            >
              {record.label}
            </button>
          ))}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {highRisk.slice(0, 6).map((record) => (
            <button
              key={`${record.id}-compare`}
              type="button"
              onClick={() => toggleCompare(record.id)}
              className="rounded-full border border-border/70 bg-background/40 px-3 py-2 text-xs font-mono text-muted hover:text-ink"
            >
              {compareIds.includes(record.id) ? `Retirer ${record.label}` : `Comparer ${record.label}`}
            </button>
          ))}
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
          <input
            value={scenarioName}
            onChange={(event) => setScenarioName(event.target.value)}
            placeholder="Nom du scenario local"
            className="rounded-2xl border border-border/70 bg-background/45 px-4 py-3 text-sm text-ink outline-none"
          />
          <button
            type="button"
            onClick={saveScenario}
            className="rounded-2xl border border-cyan-400/50 bg-cyan-400/10 px-4 py-3 text-sm font-semibold text-cyan-100"
          >
            Sauvegarder
          </button>
        </div>

        {savedScenarios.length ? (
          <div className="mt-4 flex flex-wrap gap-2">
            {savedScenarios.map((scenario) => (
              <div
                key={scenario.name}
                className="flex items-center gap-2 rounded-full border border-border/70 bg-background/40 px-3 py-2"
              >
                <button
                  type="button"
                  onClick={() => {
                    setSource(scenario.source);
                    setTarget(scenario.target);
                    setSelectedNode(scenario.source);
                  }}
                  className="text-xs font-mono text-muted hover:text-ink"
                >
                  {scenario.name}
                </button>
                <button
                  type="button"
                  onClick={() => removeScenario(scenario.name)}
                  className="font-mono text-xs text-red-300"
                >
                  x
                </button>
              </div>
            ))}
          </div>
        ) : null}
      </section>

      <section className="grid gap-6 xl:grid-cols-[1.02fr_0.98fr]">
        <IdentityGraph highlightId={selectedNode} onNodeSelect={setSelectedNode} />

        <div className="space-y-6">
          <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
            <div className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Paths
            </div>
            <div className="mt-4 max-h-[20rem] space-y-3 overflow-auto pr-1">
              {paths.map((path, index) => (
                <div key={`${source}-${target}-${index}`} className="rounded-2xl border border-border/70 bg-background/35 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-mono text-xs uppercase tracking-[0.2em] text-cyan-300">
                      Path {index + 1}
                    </div>
                    <span className="rounded-full border border-border/70 px-2 py-1 font-mono text-xs text-muted">
                      len {path.length ?? 0}
                    </span>
                  </div>
                  <div className="mt-3 flex flex-wrap gap-2">
                    {(path.nodes ?? []).map((node) => (
                      <button
                        key={`${index}-${node}`}
                        type="button"
                        onClick={() => setSelectedNode(node)}
                        className="rounded-full border border-border/70 px-2 py-1 font-mono text-xs text-muted"
                      >
                        {node}
                      </button>
                    ))}
                  </div>
                  <div className="mt-3 font-mono text-xs text-muted">
                    {(path.edges ?? []).join(" -> ")}
                  </div>
                </div>
              ))}
              {!paths.length ? (
                <div className="rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted">
                  Aucun chemin renvoye pour cette paire source/cible.
                </div>
              ) : null}
            </div>
          </div>

          <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
            <div className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Blast radius shortlist
            </div>
            <div className="mt-4 space-y-3">
              {highRisk.slice(0, 6).map((record) => (
                <div key={record.id} className="rounded-2xl border border-border/70 bg-background/35 p-4">
                  <div className="flex items-center justify-between gap-3">
                    <div className="text-sm font-semibold text-ink">{record.label}</div>
                    <span className="rounded-full border border-border/70 px-2 py-1 font-mono text-xs text-muted">
                      blast {record.blastRadiusScore}
                    </span>
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 font-mono text-xs text-muted">
                    <span>priv={record.privilegeScore}</span>
                    <span>paths={record.attackPathCount}</span>
                    <span>{record.category}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
            <div className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
              Avant / apres remediation
            </div>
            {beforeAfter ? (
              <div className="mt-4 space-y-4">
                <div className="grid gap-4 md:grid-cols-3">
                  <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
                    <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                      Privilege
                    </div>
                    <div className="mt-3 text-sm text-ink">
                      {beforeAfter.privilegeBefore} -&gt; {beforeAfter.privilegeAfter}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
                    <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                      Blast radius
                    </div>
                    <div className="mt-3 text-sm text-ink">
                      {beforeAfter.blastBefore} -&gt; {beforeAfter.blastAfter}
                    </div>
                  </div>
                  <div className="rounded-2xl border border-border/70 bg-background/35 p-4">
                    <div className="font-mono text-xs uppercase tracking-[0.2em] text-muted">
                      Paths
                    </div>
                    <div className="mt-3 text-sm text-ink">
                      {beforeAfter.pathBefore} -&gt; {beforeAfter.pathAfter}
                    </div>
                  </div>
                </div>
                <p className="text-sm text-muted">
                  Projection operateur d&apos;une remediaton type: retrait du groupe privilegie,
                  delegation nettoyee ou isolement du noeud source.
                </p>
              </div>
            ) : (
              <div className="mt-4 rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted">
                Selectionnez une source critique pour comparer l&apos;impact d&apos;une remediation.
              </div>
            )}
          </div>

          <NodeEvolutionPanel
            node={
              selectedRecord
                ? {
                    id: selectedRecord.id,
                    label: selectedRecord.label,
                    privilegeScore: selectedRecord.privilegeScore,
                    blastRadiusScore: selectedRecord.blastRadiusScore,
                    driftScore: 0,
                    kerberosDelegationRisk: 0,
                    alerts: selectedRecord.attackPathCount
                  }
                : null
            }
          />

          <NodeComparePanel
            nodes={compareNodes.map((node) => ({
              id: node.id,
              label: node.label,
              type: "Attack source",
              category: node.category,
              privilegeScore: node.privilegeScore,
              blastRadiusScore: node.blastRadiusScore,
              driftScore: 0,
              kerberosDelegationRisk: 0,
              alerts: node.attackPathCount,
              riskBand: node.tierZeroExposure ? "critical" : "high"
            }))}
          />
        </div>
      </section>
    </div>
  );
}
