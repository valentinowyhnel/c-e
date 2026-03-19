"use client";

const STATES = [
  "free",
  "monitored",
  "suspected",
  "observation",
  "restricted",
  "quarantined",
  "forensic_preserved",
  "identity_revoked",
  "isolated",
  "recovery_pending",
  "restored"
];

export function StateMachinePanel() {
  return (
    <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
      <h3 className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
        Isolation State Machine
      </h3>
      <p className="mt-2 text-sm text-muted">
        Le systeme suit une progression reversible avant toute action irreversible. Les etats
        critiques sont visibles et expliquent le niveau de contention autorise.
      </p>
      <div className="mt-4 flex flex-wrap gap-2">
        {STATES.map((state, index) => (
          <div key={state} className="flex items-center gap-2">
            <span className="rounded-full border border-border/70 bg-background/40 px-3 py-1 font-mono text-xs text-ink">
              {state}
            </span>
            {index < STATES.length - 1 ? <span className="text-muted">→</span> : null}
          </div>
        ))}
      </div>
    </div>
  );
}
