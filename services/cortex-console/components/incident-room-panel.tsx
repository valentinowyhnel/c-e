"use client";

import { useState } from "react";

type IncidentRoom = {
  name: string;
  query: string;
  selectedId: string | null;
  compareIds: string[];
  favorites: string[];
  notesByNode: Record<string, string>;
  tagsByNode: Record<string, string[]>;
};

export function IncidentRoomPanel({
  onSave,
  rooms,
  onLoad,
  onDelete
}: {
  onSave: (name: string) => void;
  rooms: IncidentRoom[];
  onLoad: (name: string) => void;
  onDelete: (name: string) => void;
}) {
  const [name, setName] = useState("");

  return (
    <div className="rounded-3xl border bg-panel/80 p-4 shadow-panel">
      <div className="flex items-center justify-between gap-3">
        <div>
          <div className="text-sm font-semibold uppercase tracking-[0.2em] text-muted">
            Incident Room
          </div>
          <p className="mt-1 text-sm text-muted">
            Workspace local regroupant requetes, noeuds, tags, notes et comparaisons.
          </p>
        </div>
        <div className="rounded-full border border-border/70 px-3 py-1 font-mono text-xs text-muted">
          {rooms.length} room(s)
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_auto]">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          placeholder="Nom du workspace local"
          className="rounded-2xl border border-border/70 bg-background/45 px-4 py-3 text-sm text-ink outline-none"
        />
        <button
          type="button"
          onClick={() => {
            if (!name.trim()) {
              return;
            }
            onSave(name.trim());
            setName("");
          }}
          className="rounded-2xl border border-cyan-400/50 bg-cyan-400/10 px-4 py-3 text-sm font-semibold text-cyan-100"
        >
          Sauvegarder
        </button>
      </div>

      {rooms.length ? (
        <div className="mt-4 flex flex-wrap gap-2">
          {rooms.map((room) => (
            <div
              key={room.name}
              className="flex items-center gap-2 rounded-full border border-border/70 bg-background/40 px-3 py-2"
            >
              <button
                type="button"
                onClick={() => onLoad(room.name)}
                className="text-xs font-mono text-muted hover:text-ink"
              >
                {room.name}
              </button>
              <button
                type="button"
                onClick={() => onDelete(room.name)}
                className="font-mono text-xs text-red-300"
              >
                x
              </button>
            </div>
          ))}
        </div>
      ) : (
        <div className="mt-4 rounded-2xl border border-dashed border-border/70 p-6 text-sm text-muted">
          Aucun workspace local sauvegarde.
        </div>
      )}
    </div>
  );
}
