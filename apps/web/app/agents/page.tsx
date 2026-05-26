"use client";

import { useEffect, useState } from "react";
import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

const SOURCE_META: Record<string, { label: string; icon: string }> = {
  prices:    { label: "Prices Agent",    icon: "💹" },
  gdelt:     { label: "GDELT Agent",     icon: "🌍" },
  logistics: { label: "Logistics Agent", icon: "🚢" },
  press:     { label: "Press Agent",     icon: "📰" },
  demand:    { label: "Demand Agent",    icon: "📈" },
  sec:       { label: "SEC Agent",       icon: "📄" },
};

const INTERVAL_OPTIONS = [1, 2, 4, 6, 12, 24];

// ── Live "running" badge ──────────────────────────────────────────────────────

function RunningBadge({ since }: { since: string | null }) {
  // Tick every second so the elapsed counter updates smoothly
  const [, setTick] = useState(0);
  useEffect(() => {
    const id = setInterval(() => setTick((t) => t + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const elapsedSec = since
    ? Math.max(0, Math.floor((Date.now() - new Date(since).getTime()) / 1000))
    : 0;

  return (
    <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[10px] font-semibold
      bg-blue-50 text-blue-700 border border-blue-200">
      <span className="relative flex h-2 w-2">
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-blue-400 opacity-75" />
        <span className="relative inline-flex rounded-full h-2 w-2 bg-blue-500" />
      </span>
      Running · {elapsedSec}s
    </span>
  );
}

// ── Toggle ────────────────────────────────────────────────────────────────────

function Toggle({ checked, onChange, disabled }: {
  checked: boolean;
  onChange: (v: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <button
      onClick={() => !disabled && onChange(!checked)}
      disabled={disabled}
      aria-label={checked ? "Disable agent" : "Enable agent"}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors
        ${checked ? "bg-green-400" : "bg-slate-200"}
        ${disabled ? "opacity-50 cursor-not-allowed" : "cursor-pointer"}`}
    >
      <span
        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white shadow transition-transform
          ${checked ? "translate-x-5" : "translate-x-1"}`}
      />
    </button>
  );
}

// ── Schedule display helper ───────────────────────────────────────────────────

function formatSchedule(cfg: AgentConfig | undefined): string {
  if (!cfg) return "—";
  if (cfg.schedule_mode === "daily") {
    return `Daily ${String(cfg.daily_hour ?? 0).padStart(2, "0")}:00 UTC`;
  }
  return `Every ${cfg.interval_hours}h`;
}

// ── Types ─────────────────────────────────────────────────────────────────────

interface AgentConfig {
  enabled: boolean;
  schedule_mode: "interval" | "daily";
  interval_hours: number;
  daily_hour: number;
  lookback_hours: number;
}

interface AgentStatus {
  source: string;
  total: number;
  escalated: number;
  discarded: number;
  last_seen: string | null;
  // Live run state (from in-process runtime registry)
  is_running: boolean;
  running_since: string | null;
  // Run telemetry (populated from agent_runs)
  last_run_at: string | null;
  last_run_status: string | null;     // "ok" | "error" | "budget_exceeded"
  last_pulled: number | null;
  last_passed_rules: number | null;
  last_passed_llm: number | null;
  last_classified: number | null;
  last_notes: string | null;
}

// ── Agent Card ────────────────────────────────────────────────────────────────

function AgentCard({ agent, config, onConfigChange }: {
  agent: AgentStatus;
  config: AgentConfig | undefined;
  onConfigChange: () => void;
}) {
  const meta = SOURCE_META[agent.source] ?? { label: agent.source, icon: "⚙️" };

  // Schedule editing state
  const [editSched, setEditSched] = useState(false);
  const [schedMode, setSchedMode] = useState<"interval" | "daily">(config?.schedule_mode ?? "interval");
  const [intervalH, setIntervalH] = useState(config?.interval_hours ?? 1);
  const [dailyH, setDailyH] = useState(config?.daily_hour ?? 6);
  const [saving, setSaving] = useState(false);

  // Run-now state
  const [runOpen, setRunOpen] = useState(false);
  const [runLookback, setRunLookback] = useState(config?.lookback_hours ?? 6);
  const [running, setRunning] = useState(false);
  const [runMsg, setRunMsg] = useState<string | null>(null);
  const [togglingEnabled, setTogglingEnabled] = useState(false);

  const enabled = config?.enabled ?? true;

  async function patchConfig(patch: Record<string, unknown>) {
    const res = await fetch(`${API}/api/agents/config/${agent.source}`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(patch),
    });
    if (!res.ok) throw new Error(await res.text());
    onConfigChange();
  }

  async function handleToggle(val: boolean) {
    setTogglingEnabled(true);
    try { await patchConfig({ enabled: val }); }
    finally { setTogglingEnabled(false); }
  }

  async function handleSaveSchedule() {
    setSaving(true);
    const patch: Record<string, unknown> = { schedule_mode: schedMode };
    if (schedMode === "interval") patch.interval_hours = intervalH;
    else patch.daily_hour = dailyH;
    try {
      await patchConfig(patch);
      setEditSched(false);
    } finally {
      setSaving(false);
    }
  }

  async function handleRunNow() {
    setRunning(true);
    setRunMsg(null);
    try {
      await fetch(`${API}/api/agents/run/${agent.source}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ lookback_hours: runLookback }),
      });
      setRunOpen(false);
      setRunMsg(`Started — collecting last ${runLookback}h`);
      setTimeout(() => setRunMsg(null), 5000);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className={`bg-white rounded-xl border border-slate-200 p-5 flex flex-col gap-0 transition-opacity
      ${enabled ? "" : "opacity-60"}`}>

      {/* ── Header ── */}
      <div className="flex items-start justify-between mb-4 gap-2">
        <div className="flex items-center gap-3 min-w-0">
          <div className="text-2xl shrink-0">{meta.icon}</div>
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <span className="font-semibold text-slate-800 truncate">{meta.label}</span>
              {agent.is_running && <RunningBadge since={agent.running_since} />}
            </div>
            <div className="text-xs text-slate-400 flex items-center gap-1.5">
              {formatSchedule(config)}
              {!enabled && (
                <span className="text-slate-400 italic">· paused</span>
              )}
            </div>
          </div>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <div
            className={`w-2 h-2 rounded-full ${
              agent.is_running ? "bg-blue-500 animate-pulse"
              : agent.last_run_status === "error" ? "bg-red-500"
              : agent.last_run_at ? "bg-green-400"
              : "bg-slate-200"
            }`}
            title={
              agent.is_running ? "Currently running"
              : agent.last_run_status === "error" ? "Last run errored"
              : agent.last_run_at ? "Recently ran"
              : "Has not run yet"
            }
          />
          <Toggle checked={enabled} onChange={handleToggle} disabled={togglingEnabled} />
        </div>
      </div>

      {/* ── Last-run telemetry (from agent_runs) ── */}
      {/* This is the honest "did the agent actually run" indicator —
          unlike signal counts, which only reflect items above the persist
          threshold and are 0 when the scorer rejects everything as noise. */}
      <div className="mb-4 bg-slate-50 rounded-lg px-3 py-2.5 border border-slate-100">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">
            Last run
          </span>
          <span className="text-xs text-slate-500">
            {agent.last_run_at
              ? formatDistanceToNow(new Date(agent.last_run_at), { addSuffix: true })
              : <span className="italic text-slate-400">never</span>}
            {agent.last_run_status === "error" && (
              <span className="ml-1.5 text-red-500 font-medium">· error</span>
            )}
          </span>
        </div>
        {agent.last_run_at ? (
          <div className="flex items-center justify-between gap-1 text-xs">
            <FunnelStep label="pulled"    value={agent.last_pulled} />
            <FunnelArrow />
            <FunnelStep label="filtered"  value={agent.last_passed_rules} />
            <FunnelArrow />
            <FunnelStep label="scored"    value={agent.last_passed_llm} />
            <FunnelArrow />
            <FunnelStep label="kept"      value={agent.last_classified} highlight />
          </div>
        ) : (
          <div className="text-xs text-slate-400 italic">
            Use "Run now" below to trigger first run
          </div>
        )}
        {agent.last_notes && (
          <div className="text-[10px] text-red-500 mt-1.5 truncate" title={agent.last_notes}>
            {agent.last_notes}
          </div>
        )}
      </div>

      {/* ── Cumulative DB stats (last 24h) ── */}
      <div className="grid grid-cols-3 gap-3 mb-4">
        <Metric label="Stored 24h" value={agent.total} />
        <Metric label="Escalated"  value={agent.escalated} highlight />
        <Metric label="Discarded"  value={agent.discarded} />
      </div>

      {/* ── Controls ── */}
      <div className="border-t border-slate-100 pt-3 space-y-2.5">

        {/* Schedule editor */}
        {editSched ? (
          <div className="space-y-2">
            <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Schedule</div>
            <div className="flex items-center gap-2 flex-wrap">
              <select
                value={schedMode}
                onChange={(e) => setSchedMode(e.target.value as "interval" | "daily")}
                className="text-xs border border-slate-200 rounded-md px-2 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-300"
              >
                <option value="interval">Every N hours</option>
                <option value="daily">Daily at hour</option>
              </select>

              {schedMode === "interval" ? (
                <select
                  value={intervalH}
                  onChange={(e) => setIntervalH(Number(e.target.value))}
                  className="text-xs border border-slate-200 rounded-md px-2 py-1.5 bg-white text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-300"
                >
                  {INTERVAL_OPTIONS.map((h) => (
                    <option key={h} value={h}>{h}h</option>
                  ))}
                </select>
              ) : (
                <div className="flex items-center gap-1">
                  <input
                    type="number"
                    min={0}
                    max={23}
                    value={dailyH}
                    onChange={(e) => setDailyH(Number(e.target.value))}
                    className="text-xs border border-slate-200 rounded-md px-2 py-1.5 w-14 text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-300"
                  />
                  <span className="text-xs text-slate-400">:00 UTC</span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleSaveSchedule}
                disabled={saving}
                className="text-xs px-2.5 py-1.5 bg-slate-800 text-white rounded-md hover:bg-slate-700 disabled:opacity-50 transition-colors"
              >
                {saving ? "Saving…" : "Save"}
              </button>
              <button
                onClick={() => setEditSched(false)}
                className="text-xs px-2 py-1.5 text-slate-400 hover:text-slate-600 transition-colors"
              >
                Cancel
              </button>
            </div>
            <p className="text-xs text-slate-400 italic">
              Schedule takes effect at next API restart
            </p>
          </div>
        ) : (
          <button
            onClick={() => setEditSched(true)}
            className="text-xs text-slate-400 hover:text-slate-600 underline underline-offset-2 transition-colors"
          >
            Edit schedule
          </button>
        )}

        {/* Run now */}
        {runMsg ? (
          <div className="text-xs text-green-600 font-medium">{runMsg}</div>
        ) : runOpen ? (
          <div className="space-y-2">
            <div className="text-xs font-semibold text-slate-600 uppercase tracking-wide">Single run</div>
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-xs text-slate-500">Collect last</span>
              <input
                type="number"
                min={1}
                max={168}
                value={runLookback}
                onChange={(e) => setRunLookback(Number(e.target.value))}
                className="text-xs border border-slate-200 rounded-md px-2 py-1.5 w-14 text-slate-700 focus:outline-none focus:ring-1 focus:ring-slate-300"
              />
              <span className="text-xs text-slate-500">hours of data</span>
            </div>
            <div className="flex items-center gap-2">
              <button
                onClick={handleRunNow}
                disabled={running}
                className="text-xs px-2.5 py-1.5 bg-blue-600 text-white rounded-md hover:bg-blue-700 disabled:opacity-50 transition-colors"
              >
                {running ? "Starting…" : "▶ Run"}
              </button>
              <button
                onClick={() => setRunOpen(false)}
                className="text-xs px-2 py-1.5 text-slate-400 hover:text-slate-600 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <button
            onClick={() => setRunOpen(true)}
            disabled={agent.is_running}
            className="text-xs px-2.5 py-1.5 border border-slate-200 rounded-md text-slate-600 hover:bg-slate-50 hover:border-slate-300 transition-colors disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-white disabled:hover:border-slate-200"
            title={agent.is_running ? "Already running — wait for it to finish" : ""}
          >
            ▶ Run now
          </button>
        )}
      </div>
    </div>
  );
}

// ── Metric ────────────────────────────────────────────────────────────────────

function Metric({ label, value, highlight }: {
  label: string;
  value: number;
  highlight?: boolean;
}) {
  return (
    <div className="text-center">
      <div className={`text-xl font-bold ${highlight ? "text-red-600" : "text-slate-800"}`}>
        {value}
      </div>
      <div className="text-xs text-slate-400">{label}</div>
    </div>
  );
}

// ── Funnel step (used in Last-run block) ──────────────────────────────────────

function FunnelStep({ label, value, highlight }: {
  label: string;
  value: number | null;
  highlight?: boolean;
}) {
  return (
    <div className="text-center flex-1 min-w-0">
      <div className={`text-sm font-bold ${highlight ? "text-red-600" : "text-slate-700"}`}>
        {value ?? "—"}
      </div>
      <div className="text-[10px] text-slate-400">{label}</div>
    </div>
  );
}

function FunnelArrow() {
  return <span className="text-slate-300 text-xs shrink-0">→</span>;
}

// ── Pipeline summary banner ───────────────────────────────────────────────────

function PipelineSummary({ data, configs }: { data: AgentStatus[]; configs: Record<string, AgentConfig> | undefined }) {
  const total     = data.reduce((s, a) => s + a.total, 0);
  const escalated = data.reduce((s, a) => s + a.escalated, 0);
  const active    = configs ? Object.values(configs).filter((c) => c.enabled).length : "—";

  return (
    <div className="bg-slate-900 rounded-xl p-5 text-white mb-6">
      <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
        Pipeline Summary — last 24h
      </div>
      <div className="flex items-center gap-6 text-sm flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold">{total}</span>
          <span className="text-slate-400">signals ingested</span>
        </div>
        <div className="text-slate-600">→</div>
        <div className="flex items-center gap-2">
          <span className="text-2xl font-bold text-red-400">{escalated}</span>
          <span className="text-slate-400">escalated</span>
        </div>
        <div className="text-slate-600">→</div>
        <span className="text-slate-400">7-node assessment pipeline</span>
        <div className="ml-auto flex items-center gap-1.5 text-slate-400 text-xs">
          <span className="w-2 h-2 rounded-full bg-green-400 inline-block" />
          {active} / 6 agents active
        </div>
      </div>
    </div>
  );
}

// ── Page ──────────────────────────────────────────────────────────────────────

export default function AgentsPage() {
  // Poll fast (3s) while any agent is running so the elapsed counter and
  // funnel results refresh promptly; slow to 60s when idle.
  const [pollMs, setPollMs] = useState(60_000);

  const { data: agents, isLoading } = useSWR<AgentStatus[]>(
    `${API}/api/agents/status?hours=24`,
    fetcher,
    { refreshInterval: pollMs }
  );

  // Adjust poll cadence whenever the running-set changes
  useEffect(() => {
    const anyRunning = (agents ?? []).some((a) => a.is_running);
    setPollMs(anyRunning ? 3_000 : 60_000);
  }, [agents]);

  const { data: configs, mutate: mutateConfigs } = useSWR<Record<string, AgentConfig>>(
    `${API}/api/agents/config`,
    fetcher
  );

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Agents</h1>
        <p className="text-slate-500 text-sm mt-1">
          Toggle agents on/off, edit their schedule, or trigger a one-off run with a custom lookback window
        </p>
      </div>

      {isLoading && (
        <div className="text-slate-400 text-sm animate-pulse">Loading agent status…</div>
      )}

      {agents && agents.length > 0 && (
        <PipelineSummary data={agents} configs={configs} />
      )}

      <div className="grid grid-cols-3 gap-4">
        {(agents ?? []).map((agent) => (
          <AgentCard
            key={agent.source}
            agent={agent}
            config={configs?.[agent.source]}
            onConfigChange={() => mutateConfigs()}
          />
        ))}
      </div>

      {/* System architecture reference */}
      <div className="mt-6 bg-white rounded-xl border border-slate-200 p-5">
        <div className="text-sm font-semibold text-slate-700 mb-3">System Architecture</div>
        <div className="grid grid-cols-2 gap-4 text-xs text-slate-600">
          <div>
            <div className="font-medium text-slate-800 mb-1">Ingestion Pipeline</div>
            <ul className="space-y-0.5 text-slate-500">
              <li>→ Rule filter (keyword matching)</li>
              <li>→ Claude Haiku batch scoring</li>
              <li>→ Escalate / Classify / Discard</li>
            </ul>
          </div>
          <div>
            <div className="font-medium text-slate-800 mb-1">Assessment Pipeline (7 nodes)</div>
            <ul className="space-y-0.5 text-slate-500">
              <li>1. Triage (Haiku — event classification)</li>
              <li>2. Graph retriever (Neo4j expansion)</li>
              <li>3. Vector retriever (Voyage AI + pgvector)</li>
              <li>4. Contract scanner (clause matching)</li>
              <li>5. Synthesizer (Opus via DSPy)</li>
              <li>6. Critic (Haiku — quality gate)</li>
              <li>7. Finalizer (Neon persistence)</li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  );
}
