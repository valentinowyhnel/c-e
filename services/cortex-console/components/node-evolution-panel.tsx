"use client";

import { useMemo } from "react";
import {
  Area,
  AreaChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis
} from "recharts";

type NodeSignal = {
  id: string;
  label: string;
  privilegeScore: number;
  blastRadiusScore: number;
  driftScore: number;
  kerberosDelegationRisk: number;
  alerts: number;
};

export function NodeEvolutionPanel({ node }: { node: NodeSignal | null }) {
  const series = useMemo(() => {
    if (!node) {
      return [];
    }

    const privilegeBase = Math.max(10, node.privilegeScore - 18);
    const blastBase = Math.max(6, node.blastRadiusScore - 14);
    const driftBase = Math.max(4, node.driftScore - 12);

    return [
      { step: "J-6", privilege: privilegeBase, blast: blastBase, drift: driftBase },
      { step: "J-4", privilege: privilegeBase + 6, blast: blastBase + 5, drift: driftBase + 4 },
      { step: "J-2", privilege: privilegeBase + 12, blast: blastBase + 8, drift: driftBase + 7 },
      {
        step: "Now",
        privilege: node.privilegeScore,
        blast: node.blastRadiusScore,
        drift: node.driftScore
      }
    ];
  }, [node]);

  return (
    <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
            Evolution
          </div>
          <p className="mt-1 text-sm text-muted">
            Trajectoire recentre de privilege, blast radius et derive.
          </p>
        </div>
        {node ? (
          <div className="rounded-full border border-border/70 px-3 py-1 font-mono text-xs text-muted">
            {node.label}
          </div>
        ) : null}
      </div>

      {node ? (
        <div className="mt-4 h-64">
          <ResponsiveContainer width="100%" height="100%">
            <AreaChart data={series}>
              <CartesianGrid stroke="#17304f" strokeDasharray="3 3" />
              <XAxis dataKey="step" stroke="#8ba3c0" />
              <YAxis stroke="#8ba3c0" />
              <Tooltip />
              <Area type="monotone" dataKey="privilege" stroke="#f97316" fill="#f97316" fillOpacity={0.16} />
              <Area type="monotone" dataKey="blast" stroke="#ef4444" fill="#ef4444" fillOpacity={0.12} />
              <Area type="monotone" dataKey="drift" stroke="#22c55e" fill="#22c55e" fillOpacity={0.1} />
            </AreaChart>
          </ResponsiveContainer>
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted">
          Selectionnez un noeud pour afficher son evolution.
        </div>
      )}
    </div>
  );
}
