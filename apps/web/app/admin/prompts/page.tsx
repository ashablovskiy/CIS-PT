"use client";

import { useState, useEffect, useCallback } from "react";

interface PromptSummary {
  name: string;
  version: number;
  description: string | null;
  model_hint: string | null;
  is_active: boolean;
  created_by: string;
  created_at: string;
}

interface PromptDetail extends PromptSummary {
  system_text: string;
  metrics: Record<string, unknown> | null;
}

const MODEL_BADGE: Record<string, string> = {
  haiku: "bg-sky-900 text-sky-300",
  opus: "bg-violet-900 text-violet-300",
};

const PROMPT_LABELS: Record<string, string> = {
  relevance_scorer: "Relevance Scorer",
  triage_classifier: "Triage Classifier",
  critic: "Critic",
  daily_brief: "Daily Brief",
};

export default function PromptsAdminPage() {
  const [prompts, setPrompts] = useState<PromptSummary[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [history, setHistory] = useState<PromptDetail[]>([]);
  const [editText, setEditText] = useState("");
  const [saving, setSaving] = useState(false);
  const [rolling, setRolling] = useState(false);
  const [toast, setToast] = useState<{ msg: string; ok: boolean } | null>(null);
  const [loading, setLoading] = useState(true);

  const showToast = (msg: string, ok = true) => {
    setToast({ msg, ok });
    setTimeout(() => setToast(null), 3500);
  };

  const fetchPrompts = useCallback(async () => {
    try {
      const r = await fetch("/api/prompts");
      if (r.ok) setPrompts(await r.json());
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { fetchPrompts(); }, [fetchPrompts]);

  const selectPrompt = async (name: string) => {
    setSelected(name);
    setRolling(false);
    const r = await fetch(`/api/prompts/${name}`);
    if (r.ok) {
      const data: PromptDetail[] = await r.json();
      setHistory(data);
      const active = data.find((d) => d.is_active);
      setEditText(active?.system_text ?? "");
    }
  };

  const handleSave = async () => {
    if (!selected || !editText.trim()) return;
    setSaving(true);
    try {
      const r = await fetch(`/api/prompts/${selected}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ system_text: editText, created_by: "admin" }),
      });
      if (r.ok) {
        showToast("New version saved and activated ✓");
        await selectPrompt(selected);
        await fetchPrompts();
      } else {
        showToast("Save failed", false);
      }
    } finally {
      setSaving(false);
    }
  };

  const handleRollback = async (version: number) => {
    if (!selected) return;
    setRolling(true);
    try {
      const r = await fetch(`/api/prompts/${selected}/rollback/${version}`, { method: "POST" });
      if (r.ok) {
        showToast(`Rolled back to v${version} ✓`);
        await selectPrompt(selected);
        await fetchPrompts();
      } else {
        showToast("Rollback failed", false);
      }
    } finally {
      setRolling(false);
    }
  };

  const activeVersion = history.find((h) => h.is_active);
  const isDirty = activeVersion ? editText !== activeVersion.system_text : false;

  return (
    <div className="flex h-full min-h-screen bg-slate-950 text-slate-200">
      {/* Toast */}
      {toast && (
        <div
          className={`fixed top-4 right-4 z-50 px-4 py-3 rounded-lg text-sm font-medium shadow-lg
            ${toast.ok ? "bg-emerald-800 text-emerald-100" : "bg-red-800 text-red-100"}`}
        >
          {toast.msg}
        </div>
      )}

      {/* Left panel — prompt list */}
      <div className="w-64 shrink-0 border-r border-slate-800 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-800">
          <h1 className="text-base font-semibold text-white">Prompt Registry</h1>
          <p className="text-xs text-slate-500 mt-1">Edit LLM system prompts without a deploy</p>
        </div>

        <div className="flex-1 overflow-y-auto p-3 space-y-1">
          {loading ? (
            <p className="text-xs text-slate-500 px-3 py-2">Loading…</p>
          ) : prompts.length === 0 ? (
            <p className="text-xs text-slate-500 px-3 py-2">No prompts seeded yet.</p>
          ) : (
            prompts.map((p) => (
              <button
                key={p.name}
                onClick={() => selectPrompt(p.name)}
                className={`w-full text-left px-3 py-2.5 rounded-lg transition-colors
                  ${selected === p.name
                    ? "bg-slate-700 text-white"
                    : "text-slate-400 hover:bg-slate-800 hover:text-white"}`}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-medium truncate">
                    {PROMPT_LABELS[p.name] ?? p.name}
                  </span>
                  {p.model_hint && (
                    <span
                      className={`text-[10px] font-semibold px-1.5 py-0.5 rounded uppercase tracking-wide
                        ${MODEL_BADGE[p.model_hint] ?? "bg-slate-700 text-slate-400"}`}
                    >
                      {p.model_hint}
                    </span>
                  )}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">v{p.version} · {p.created_by}</div>
              </button>
            ))
          )}
        </div>
      </div>

      {/* Right panel — editor */}
      <div className="flex-1 flex flex-col min-w-0">
        {!selected ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center text-slate-600">
              <div className="text-4xl mb-3">✏️</div>
              <p className="text-sm">Select a prompt to edit</p>
            </div>
          </div>
        ) : (
          <>
            {/* Header */}
            <div className="px-6 py-4 border-b border-slate-800 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-white">
                  {PROMPT_LABELS[selected] ?? selected}
                </h2>
                {activeVersion?.description && (
                  <p className="text-sm text-slate-400 mt-0.5 max-w-xl">
                    {activeVersion.description}
                  </p>
                )}
              </div>
              <button
                onClick={handleSave}
                disabled={saving || !isDirty}
                className={`shrink-0 px-4 py-2 rounded-lg text-sm font-medium transition-colors
                  ${isDirty && !saving
                    ? "bg-emerald-600 hover:bg-emerald-500 text-white"
                    : "bg-slate-700 text-slate-500 cursor-not-allowed"}`}
              >
                {saving ? "Saving…" : isDirty ? "Publish new version" : "No changes"}
              </button>
            </div>

            {/* Editor */}
            <div className="flex-1 flex flex-col p-6 gap-4 min-h-0">
              <div className="flex items-center gap-3 text-xs text-slate-500">
                <span>Active: <strong className="text-slate-300">v{activeVersion?.version}</strong></span>
                <span>·</span>
                <span>Model: <strong className="text-slate-300">{activeVersion?.model_hint ?? "—"}</strong></span>
                <span>·</span>
                <span>Saved by: <strong className="text-slate-300">{activeVersion?.created_by}</strong></span>
                {isDirty && (
                  <>
                    <span>·</span>
                    <span className="text-amber-400">● Unsaved changes</span>
                  </>
                )}
              </div>

              <textarea
                value={editText}
                onChange={(e) => setEditText(e.target.value)}
                spellCheck={false}
                className="flex-1 bg-slate-900 border border-slate-700 rounded-xl p-4 text-sm
                  font-mono text-slate-200 resize-none focus:outline-none focus:border-slate-500
                  leading-relaxed min-h-[300px]"
                placeholder="System prompt text…"
              />
            </div>

            {/* Version history */}
            {history.length > 1 && (
              <div className="border-t border-slate-800 px-6 py-4">
                <h3 className="text-xs font-semibold text-slate-500 uppercase tracking-widest mb-3">
                  Version History
                </h3>
                <div className="space-y-2 max-h-48 overflow-y-auto">
                  {history.map((h) => (
                    <div
                      key={h.version}
                      className="flex items-center justify-between gap-4 py-1.5 text-sm"
                    >
                      <div className="flex items-center gap-3">
                        <span className={`font-mono text-xs px-2 py-0.5 rounded
                          ${h.is_active
                            ? "bg-emerald-900 text-emerald-300"
                            : "bg-slate-800 text-slate-500"}`}>
                          v{h.version}
                        </span>
                        <span className="text-slate-400 text-xs">
                          {h.created_by} · {new Date(h.created_at).toLocaleString()}
                        </span>
                        {h.is_active && (
                          <span className="text-[10px] text-emerald-400 font-medium">ACTIVE</span>
                        )}
                      </div>
                      {!h.is_active && (
                        <button
                          onClick={() => handleRollback(h.version)}
                          disabled={rolling}
                          className="text-xs text-slate-400 hover:text-white underline underline-offset-2
                            transition-colors disabled:opacity-50"
                        >
                          {rolling ? "Rolling back…" : "Roll back"}
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
