"use client";

import { useEffect, useState } from "react";

interface ActiveSOT {
  token_id: string;
  entity_id: string;
  observation_level: "standard" | "deep" | "forensic_lite";
  restrictions: string[];
  expires_at: number;
}

const LEVEL = {
  standard: { label: "STANDARD", cls: "text-amber-600 bg-amber-50 dark:bg-amber-950" },
  deep: { label: "PROFOND", cls: "text-orange-600 bg-orange-50 dark:bg-orange-950" },
  forensic_lite: {
    label: "FORENSIQUE",
    cls: "text-red-600 bg-red-50 dark:bg-red-950 animate-pulse"
  }
} as const;

export function SOTPanel() {
  const [tokens, setTokens] = useState<ActiveSOT[]>([]);

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_WS_URL ?? "ws://localhost:3000";
    const ws = new WebSocket(`${base}/obs/sot-stream`);
    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      if (msg.type === "sot.issued") {
        setTokens((prev) => [msg.payload, ...prev].slice(0, 10));
      }
      if (msg.type === "sot.expired") {
        setTokens((prev) => prev.filter((token) => token.token_id !== msg.token_id));
      }
    };
    return () => ws.close();
  }, []);

  if (!tokens.length) {
    return null;
  }

  return (
    <div className="rounded-lg border p-4 space-y-2">
      <div className="flex items-center gap-2">
        <div className="w-2 h-2 rounded-full bg-amber-500 animate-pulse" />
        <span className="text-xs font-mono font-medium">
          Observation coercitive {tokens.length} entité(s)
        </span>
      </div>
      {tokens.map((token) => {
        const cfg = LEVEL[token.observation_level];
        const secs = Math.max(0, token.expires_at - Date.now() / 1000);
        const mins = Math.floor(secs / 60);
        return (
          <div key={token.token_id} className={`rounded p-3 text-xs ${cfg.cls}`}>
            <div className="flex justify-between font-mono">
              <span className="font-bold">{cfg.label}</span>
              <span>{mins}min restantes</span>
            </div>
            <p className="font-mono mt-1">{token.entity_id}</p>
            <div className="flex flex-wrap gap-1 mt-1">
              {token.restrictions.map((restriction) => (
                <span key={restriction} className="bg-black/10 rounded px-1">
                  {restriction}
                </span>
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}
