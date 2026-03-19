"use client";

type CompareNode = {
  id: string;
  label: string;
  type: string;
  category: string;
  privilegeScore: number;
  blastRadiusScore: number;
  driftScore: number;
  kerberosDelegationRisk: number;
  alerts: number;
  riskBand: string;
};

export function NodeComparePanel({ nodes }: { nodes: CompareNode[] }) {
  return (
    <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
            Comparaison locale
          </div>
          <p className="mt-1 text-sm text-muted">
            Vue cote a cote des noeuds critiques selectionnes.
          </p>
        </div>
        <div className="rounded-full border border-border/70 px-3 py-1 font-mono text-xs text-muted">
          {nodes.length} noeud(s)
        </div>
      </div>

      {nodes.length ? (
        <div className="mt-4 grid gap-4 xl:grid-cols-3">
          {nodes.map((node) => (
            <div key={node.id} className="rounded-2xl border border-border/70 bg-background/35 p-4">
              <div className="text-sm font-semibold text-ink">{node.label}</div>
              <div className="mt-1 font-mono text-[11px] uppercase tracking-[0.2em] text-muted">
                {node.type} | {node.category}
              </div>
              <div className="mt-4 grid grid-cols-2 gap-3 font-mono text-xs text-muted">
                <span>priv={node.privilegeScore}</span>
                <span>blast={node.blastRadiusScore}</span>
                <span>drift={node.driftScore}</span>
                <span>kerb={node.kerberosDelegationRisk}</span>
                <span>alerts={node.alerts}</span>
                <span>{node.riskBand}</span>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted">
          Ajoutez des favoris ou des noeuds de comparaison pour afficher une vue cote a cote.
        </div>
      )}
    </div>
  );
}
