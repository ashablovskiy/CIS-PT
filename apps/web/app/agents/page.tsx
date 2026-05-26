"use client";

import useSWR from "swr";
import { formatDistanceToNow } from "date-fns";

const fetcher = (url: string) => fetch(url).then((r) => r.json());

const SOURCE_META: Record<string, { label: string; icon: string; cadence: string }> = {
  prices: { label: "Prices Agent", icon: "💹", cadence: "Every hour" },
  gdelt:  { label: "GDELT Agent",  icon: "🌍", cadence: "Every hour" },
  logistics: { label: "Logistics Agent", icon: "🚢", cadence: "Every hour" },
  press: { label: "Press Agent", icon: "📰", cadence: "Every 2 hours" },
  demand: { label: "Demand Agent", icon: "📈", cadence: "Every 4 hours" },
  sec:   { label: "SEC Agent", icon: "📄", cadence: "Daily 06:00 UTC" },
};

function AgentCard({ agent }: { agent: any }) {
  const meta = SOURCE_META[agent.source] || { label: agent.source, icon: "⚙️", cadence: "—" };
  const escalateRate = agent.total > 0 ? ((agent.escalated / agent.total) * 100).toFixed(1) : "0";

  return (
    <div className="bg-white rounded-xl border border-slate-200 p-5">
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="text-2xl">{meta.icon}</div>
          <div>
            <div className="font-semibold text-slate-800">{meta.label}</div>
            <div className="text-xs text-slate-400">{meta.cadence}</div>
          </div>
        </div>
        <div className={`w-2 h-2 rounded-full mt-1 ${agent.last_seen ? "bg-green-400" : "bg-slate-200"}`}
          title={agent.last_seen ? "Recently active" : "No activity"} />
      </div>

      <div className="grid grid-cols-3 gap-3 mb-4">
        <Metric label="Total" value={agent.total} />
        <Metric label="Escalated" value={agent.escalated} highlight />
        <Metric label="Discarded" value={agent.discarded} />
      </div>

      <div className="flex items-center justify-between">
        <div>
          <div className="text-xs text-slate-400 mb-1">Escalation rate</div>
          <div className="flex items-center gap-1">
            <div className="w-24 h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className="h-full bg-red-400 rounded-full"
                style={{ width: `${escalateRate}%` }}
              />
            </div>
            <span className="text-xs text-slate-500">{escalateRate}%</span>
          </div>
        </div>
        <div className="text-right">
          <div className="text-xs text-slate-400">Last seen</div>
          <div className="text-xs text-slate-600">
            {agent.last_seen
              ? formatDistanceToNow(new Date(agent.last_seen), { addSuffix: true })
              : "Never"}
          </div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, highlight }: { label: string; value: number; highlight?: boolean }) {
  return (
    <div className="text-center">
      <div className={`text-xl font-bold ${highlight ? "text-red-600" : "text-slate-800"}`}>
        {value}
      </div>
      <div className="text-xs text-slate-400">{label}</div>
    </div>
  );
}

function PipelineSummary({ data }: { data: any[] }) {
  const total = data.reduce((s, a) => s + a.total, 0);
  const escalated = data.reduce((s, a) => s + a.escalated, 0);

  return (
    <div className="bg-slate-900 rounded-xl p-5 text-white mb-6">
      <div className="text-xs font-semibold text-slate-400 uppercase tracking-wide mb-3">
        Pipeline Summary (last 24h)
      </div>
      <div className="flex items-center gap-4 text-sm">
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
        <div className="flex items-center gap-2">
          <span className="text-slate-400">7-node assessment pipeline</span>
        </div>
      </div>
    </div>
  );
}

export default function AgentsPage() {
  const { data: agents, isLoading } = useSWR(
    "/api/agents/status?hours=24",
    fetcher,
    { refreshInterval: 60_000 }
  );

  return (
    <div className="p-8 max-w-5xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Agent Observability</h1>
        <p className="text-slate-500 text-sm mt-1">
          6 ingestion agents + assessment pipeline + daily scout
        </p>
      </div>

      {isLoading && (
        <div className="text-slate-400 text-sm animate-pulse">Loading agent status…</div>
      )}

      {agents && agents.length > 0 && <PipelineSummary data={agents} />}

      <div className="grid grid-cols-3 gap-4">
        {(agents ?? []).map((agent: any) => (
          <AgentCard key={agent.source} agent={agent} />
        ))}
      </div>

      {/* System info */}
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
