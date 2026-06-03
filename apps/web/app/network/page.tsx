"use client";

import { useState } from "react";
import useSWR from "swr";

const API = process.env.NEXT_PUBLIC_API_URL ?? "";
const fetcher = (url: string) => fetch(url).then((r) => r.json());

// ── Health gauge ────────────────────────────────────────────────────────────

const HEALTH_META: Record<string, { color: string; bg: string; ring: string; label: string }> = {
  resilient:   { color: "text-emerald-700", bg: "bg-emerald-50", ring: "stroke-emerald-500", label: "Resilient" },
  constrained: { color: "text-amber-700",   bg: "bg-amber-50",   ring: "stroke-amber-500",   label: "Constrained" },
  fragile:     { color: "text-red-700",     bg: "bg-red-50",     ring: "stroke-red-500",     label: "Fragile" },
};

function HealthGauge({ index, label }: { index: number; label: string }) {
  const m = HEALTH_META[label] ?? HEALTH_META.constrained;
  const pct = Math.round(index * 100);
  const circumference = 2 * Math.PI * 52;
  const offset = circumference * (1 - index);
  return (
    <div className={`rounded-xl border border-slate-200 ${m.bg} p-6 flex items-center gap-6`}>
      <div className="relative w-32 h-32 shrink-0">
        <svg className="w-32 h-32 -rotate-90" viewBox="0 0 120 120">
          <circle cx="60" cy="60" r="52" fill="none" stroke="#e2e8f0" strokeWidth="10" />
          <circle
            cx="60" cy="60" r="52" fill="none" strokeWidth="10" strokeLinecap="round"
            className={m.ring}
            strokeDasharray={circumference}
            strokeDashoffset={offset}
          />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-3xl font-bold ${m.color}`}>{pct}</span>
          <span className="text-[10px] uppercase tracking-wide text-slate-400">fragility</span>
        </div>
      </div>
      <div>
        <div className="text-xs uppercase tracking-wide text-slate-400 mb-1">Ecosystem Health</div>
        <div className={`text-2xl font-bold ${m.color}`}>{m.label}</div>
        <p className="text-sm text-slate-500 mt-2 max-w-md">
          {label === "fragile" && "Pressure is concentrated on highly-influential actors. Multiple paths are converging — elevated systemic risk."}
          {label === "constrained" && "Pressure is accumulating across several actors. The network is absorbing it, but watch the hotspots."}
          {label === "resilient" && "Pressure is low or well-distributed. No significant concentration on critical actors."}
        </p>
      </div>
    </div>
  );
}

// ── Sparkline ───────────────────────────────────────────────────────────────

function Sparkline({ points }: { points: { health_index: number | null }[] }) {
  const vals = points.map((p) => p.health_index ?? 0);
  if (vals.length < 2) return <span className="text-xs text-slate-400">Not enough history yet</span>;
  const w = 220, h = 44, pad = 4;
  const max = Math.max(...vals, 0.001), min = Math.min(...vals, 0);
  const range = max - min || 1;
  const pts = vals.map((v, i) => {
    const x = pad + (i / (vals.length - 1)) * (w - 2 * pad);
    const y = h - pad - ((v - min) / range) * (h - 2 * pad);
    return `${x},${y}`;
  }).join(" ");
  return (
    <svg width={w} height={h} className="overflow-visible">
      <polyline points={pts} fill="none" stroke="#64748b" strokeWidth="1.5" />
    </svg>
  );
}

// ── Pressure bar ────────────────────────────────────────────────────────────

function Bar({ value, color = "bg-slate-400" }: { value: number; color?: string }) {
  return (
    <div className="w-full h-1.5 bg-slate-100 rounded-full overflow-hidden">
      <div className={`h-full ${color} rounded-full`} style={{ width: `${Math.round(value * 100)}%` }} />
    </div>
  );
}

const LABEL_COLOR: Record<string, string> = {
  Commodity:    "bg-red-50 text-red-700 border-red-200",
  Supplier:     "bg-violet-50 text-violet-700 border-violet-200",
  Material:     "bg-orange-50 text-orange-700 border-orange-200",
  Plant:        "bg-blue-50 text-blue-700 border-blue-200",
  Port:         "bg-cyan-50 text-cyan-700 border-cyan-200",
  Category:     "bg-pink-50 text-pink-700 border-pink-200",
  DemandSource: "bg-emerald-50 text-emerald-700 border-emerald-200",
  Country:      "bg-slate-50 text-slate-600 border-slate-200",
  Lane:         "bg-indigo-50 text-indigo-700 border-indigo-200",
};

function LabelChip({ label }: { label: string | null }) {
  if (!label) return null;
  return (
    <span className={`text-[10px] px-1.5 py-0.5 rounded border ${LABEL_COLOR[label] ?? "bg-slate-50 text-slate-500 border-slate-200"}`}>
      {label}
    </span>
  );
}

// ── Actor detail drawer ─────────────────────────────────────────────────────

function ActorDrawer({ name, onClose }: { name: string; onClose: () => void }) {
  const { data } = useSWR(`${API}/api/network/actor/${encodeURIComponent(name)}?hours=720`, fetcher);
  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/20" onClick={onClose}>
      <div className="w-[480px] bg-white h-full shadow-xl overflow-y-auto p-6" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-start justify-between mb-4">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-xl font-bold text-slate-900">{name}</h2>
              <LabelChip label={data?.label} />
            </div>
            {data?.criticality && <span className="text-xs text-slate-400">{data.criticality} criticality</span>}
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-700 text-xl">×</button>
        </div>

        {!data ? (
          <div className="text-slate-400 text-sm animate-pulse">Loading…</div>
        ) : (
          <>
            <div className="grid grid-cols-3 gap-3 mb-6">
              <Metric label="Influence" value={data.influence} />
              <Metric label="Propagated" value={data.propagated_pressure} />
              <Metric label="Direct" value={data.direct_pressure} />
            </div>

            {data.propagation?.length > 0 && (
              <div className="mb-6">
                <h3 className="text-xs font-semibold uppercase text-slate-400 mb-2">Propagation paths</h3>
                <div className="space-y-1.5">
                  {data.propagation.map((p: any, i: number) => (
                    <div key={i} className="text-xs text-slate-600 bg-slate-50 rounded px-2 py-1.5">
                      <span className="font-medium">{p.strength}</span>{" → "}
                      <span className="text-slate-500">{p.path.join("  ›  ")}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <h3 className="text-xs font-semibold uppercase text-slate-400 mb-2">
              Contributing signals ({data.signals?.length ?? 0})
            </h3>
            <div className="space-y-2">
              {(data.signals ?? []).map((s: any) => (
                <div key={s.id} className="border border-slate-100 rounded-lg p-2.5">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="text-[10px] uppercase text-slate-400">{s.source}</span>
                    {s.impact_tier && <span className="text-[10px] px-1 rounded bg-slate-100 text-slate-500">T{s.impact_tier}</span>}
                    <span className="ml-auto text-xs font-mono text-slate-600">+{s.pressure?.toFixed?.(2)}</span>
                  </div>
                  <div className="text-xs text-slate-700 leading-snug line-clamp-2">{s.title}</div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="bg-slate-50 rounded-lg p-2.5 text-center">
      <div className="text-lg font-bold text-slate-800">{value != null ? value.toFixed(2) : "—"}</div>
      <div className="text-[10px] uppercase text-slate-400">{label}</div>
    </div>
  );
}

// ── Page ────────────────────────────────────────────────────────────────────

export default function NetworkPage() {
  const [actor, setActor] = useState<string | null>(null);
  const { data: state, isLoading } = useSWR(`${API}/api/network/state?hours=720`, fetcher, {
    refreshInterval: 60_000,
  });
  const { data: health } = useSWR(`${API}/api/network/health?limit=60`, fetcher);

  if (isLoading || !state) {
    return <div className="p-8 text-slate-400 animate-pulse">Computing network state…</div>;
  }

  return (
    <div className="p-8 max-w-7xl mx-auto">
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-slate-900">Network State</h1>
        <p className="text-slate-500 text-sm mt-0.5">
          Industrial-ecosystem condition from {state.pressured_actor_count} pressured actors ·
          {" "}{state.node_count} nodes / {state.edge_count} edges · last 30 days
        </p>
      </div>

      {/* Health + trend */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
        <div className="lg:col-span-2">
          <HealthGauge index={state.health_index} label={state.health_label} />
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-5">
          <div className="text-xs uppercase tracking-wide text-slate-400 mb-2">Health trend</div>
          <Sparkline points={health ?? []} />
          <div className="text-xs text-slate-400 mt-2">{(health ?? []).length} snapshots</div>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Systemic influence */}
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-3">
            Systemic Influence <span className="text-slate-400 font-normal">· most depended-upon</span>
          </h2>
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {state.top_actors.map((a: any) => (
              <button
                key={a.actor}
                onClick={() => setActor(a.actor)}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors text-left"
              >
                <span className="text-sm font-medium text-slate-800 w-44 truncate">{a.actor}</span>
                <LabelChip label={a.label} />
                <div className="flex-1"><Bar value={a.influence} color="bg-violet-400" /></div>
                <span className="text-xs font-mono text-slate-500 w-9 text-right">{a.influence.toFixed(2)}</span>
              </button>
            ))}
          </div>
        </section>

        {/* Pressure hotspots */}
        <section>
          <h2 className="text-sm font-semibold text-slate-700 mb-3">
            Pressure Hotspots <span className="text-slate-400 font-normal">· converging signals</span>
          </h2>
          <div className="bg-white rounded-xl border border-slate-200 divide-y divide-slate-100">
            {state.hotspots.length === 0 && (
              <div className="px-4 py-6 text-center text-sm text-slate-400">No convergence hotspots in this window.</div>
            )}
            {state.hotspots.map((h: any) => (
              <button
                key={h.actor}
                onClick={() => setActor(h.actor)}
                className="w-full flex items-center gap-3 px-4 py-2.5 hover:bg-slate-50 transition-colors text-left"
              >
                <span className="text-sm font-medium text-slate-800 w-40 truncate">{h.actor}</span>
                <LabelChip label={h.label} />
                <div className="flex-1"><Bar value={h.propagated_pressure} color="bg-orange-400" /></div>
                {h.convergence_ratio && (
                  <span className="text-[10px] px-1.5 py-0.5 rounded bg-orange-50 text-orange-600 border border-orange-200">
                    {h.convergence_ratio}×
                  </span>
                )}
              </button>
            ))}
          </div>
        </section>
      </div>

      {/* Emerging bottlenecks */}
      <section className="mt-6">
        <h2 className="text-sm font-semibold text-slate-700 mb-3">
          Emerging Bottlenecks <span className="text-slate-400 font-normal">· influence × pressure × criticality</span>
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {state.bottlenecks.length === 0 && (
            <div className="col-span-full text-sm text-slate-400 px-1">No emerging bottlenecks — influence and pressure are not yet coinciding.</div>
          )}
          {state.bottlenecks.map((b: any) => (
            <button
              key={b.actor}
              onClick={() => setActor(b.actor)}
              className="bg-white rounded-xl border border-slate-200 p-4 text-left hover:border-slate-300 transition-colors"
            >
              <div className="flex items-center gap-2 mb-2">
                <span className="text-sm font-semibold text-slate-800 truncate">{b.actor}</span>
                <LabelChip label={b.label} />
              </div>
              <div className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-slate-500">
                <span>Influence</span><span className="text-right font-mono text-slate-700">{b.influence.toFixed(2)}</span>
                <span>Pressure</span><span className="text-right font-mono text-slate-700">{b.pressure.toFixed(2)}</span>
                <span>Criticality</span><span className="text-right text-slate-700">{b.criticality ?? "—"}</span>
              </div>
            </button>
          ))}
        </div>
      </section>

      {actor && <ActorDrawer name={actor} onClose={() => setActor(null)} />}

      {/* ── Layer 2: ANT Actor State ────────────────────────────────── */}
      <AntActorSection />
    </div>
  );
}

// ── Layer 2 ANT Actor section ─────────────────────────────────────────────

const BAND_ORDER = ["components", "production", "logistics", "trade_geo", "demand"];
const BAND_LABEL: Record<string, string> = {
  components: "Components",
  production: "Production",
  logistics: "Logistics",
  trade_geo: "Trade & Geopolitics",
  demand: "Demand",
};
const CRIT_COLOR: Record<string, string> = {
  critical: "bg-red-50 text-red-700 border-red-200",
  high:     "bg-amber-50 text-amber-700 border-amber-200",
  medium:   "bg-blue-50 text-blue-700 border-blue-200",
};

function AntActorSection() {
  const [expanded, setExpanded] = useState<string | null>(null);
  const { data: antState, isLoading } = useSWR(
    `${API}/api/network/ant/state?hours=720`, fetcher, { refreshInterval: 120_000 }
  );

  if (isLoading || !antState) {
    return (
      <div className="mt-10">
        <div className="text-xs text-slate-400 animate-pulse">Computing ANT actor state…</div>
      </div>
    );
  }

  const actors: any[] = antState.actors ?? [];
  const byBand: Record<string, any[]> = {};
  for (const a of actors) {
    if (!byBand[a.band]) byBand[a.band] = [];
    byBand[a.band].push(a);
  }
  const hotspotSet = new Set<string>(antState.hotspots ?? []);

  return (
    <div className="mt-10">
      {/* Divider */}
      <div className="flex items-center gap-3 mb-5">
        <div className="flex-1 h-px bg-slate-200" />
        <span className="text-xs font-semibold uppercase tracking-widest text-slate-400">
          Layer 2 — ANT Actor State · Systemic Forces
        </span>
        <div className="flex-1 h-px bg-slate-200" />
      </div>

      {/* L2 health */}
      <div className="flex items-center gap-4 mb-5 px-1">
        <span className="text-sm text-slate-500">Systemic health:</span>
        <span className={`text-sm font-bold ${
          antState.health_label === "fragile" ? "text-red-700" :
          antState.health_label === "constrained" ? "text-amber-700" :
          "text-emerald-700"
        }`}>
          {antState.health_label?.toUpperCase()} ({Math.round(antState.health_index * 100)})
        </span>
        <span className="text-xs text-slate-400">
          {antState.pressured_actor_count} of {antState.actor_count} actors under pressure
        </span>
      </div>

      {/* Actor cards by band */}
      <div className="space-y-4">
        {BAND_ORDER.map((band) => {
          const bandActors = byBand[band];
          if (!bandActors?.length) return null;
          return (
            <div key={band}>
              <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-400 mb-2 px-1">
                {BAND_LABEL[band] ?? band}
              </div>
              <div className="space-y-2">
                {bandActors.map((a: any) => (
                  <AntActorCard
                    key={a.id}
                    actor={a}
                    isHotspot={hotspotSet.has(a.id)}
                    isExpanded={expanded === a.id}
                    onToggle={() => setExpanded(expanded === a.id ? null : a.id)}
                  />
                ))}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function AntActorCard({ actor, isHotspot, isExpanded, onToggle }: {
  actor: any; isHotspot: boolean; isExpanded: boolean; onToggle: () => void;
}) {
  const crit = CRIT_COLOR[actor.criticality] ?? "bg-slate-50 text-slate-500 border-slate-200";
  const pp = actor.propagated_pressure ?? 0;
  const dp = actor.direct_pressure ?? 0;

  return (
    <div
      className={`rounded-xl border bg-white transition-colors cursor-pointer
        ${isHotspot ? "border-orange-200 bg-orange-50/30" : "border-slate-200"}
        ${isExpanded ? "shadow-sm" : "hover:border-slate-300"}`}
      onClick={onToggle}
    >
      <div className="flex items-center gap-3 px-4 py-3">
        {/* Criticality chip */}
        <span className={`text-[10px] font-bold px-2 py-0.5 rounded border ${crit} shrink-0`}>
          {actor.criticality?.slice(0, 4).toUpperCase()}
        </span>

        {/* Name */}
        <span className="text-sm font-semibold text-slate-800 flex-1 truncate">
          {actor.label}
          {isHotspot && (
            <span className="ml-2 text-[10px] font-bold text-orange-600 bg-orange-50 border border-orange-200 px-1.5 py-0.5 rounded">
              HOTSPOT
            </span>
          )}
        </span>

        {/* Pressure bar */}
        <div className="w-28 flex-shrink-0">
          <div className="flex items-center gap-1.5">
            <div className="flex-1 h-1.5 bg-slate-100 rounded-full overflow-hidden">
              <div
                className={`h-full rounded-full ${
                  pp > 0.66 ? "bg-red-500" : pp > 0.33 ? "bg-orange-400" : "bg-slate-300"
                }`}
                style={{ width: `${Math.round(pp * 100)}%` }}
              />
            </div>
            <span className="text-[10px] font-mono text-slate-500 w-7 text-right">
              {pp.toFixed(2)}
            </span>
          </div>
        </div>

        {/* Signal count */}
        <span className="text-[10px] text-slate-400 w-16 text-right shrink-0">
          {actor.signal_count ?? 0} signals
        </span>

        {/* Expand chevron */}
        <span className="text-slate-300 text-xs shrink-0">
          {isExpanded ? "▲" : "▼"}
        </span>
      </div>

      {isExpanded && (
        <div className="px-4 pb-4 border-t border-slate-100 pt-3 space-y-3">
          <p className="text-xs text-slate-500 leading-relaxed">{actor.definition}</p>
          <p className="text-xs text-slate-400 italic leading-relaxed">{actor.why}</p>

          <div className="grid grid-cols-3 gap-3 text-xs">
            <div className="bg-slate-50 rounded p-2 text-center">
              <div className="font-bold text-slate-700">{(actor.influence ?? 0).toFixed(2)}</div>
              <div className="text-slate-400">Influence</div>
            </div>
            <div className="bg-slate-50 rounded p-2 text-center">
              <div className="font-bold text-slate-700">{dp.toFixed(2)}</div>
              <div className="text-slate-400">Direct</div>
            </div>
            <div className="bg-slate-50 rounded p-2 text-center">
              <div className="font-bold text-slate-700">{pp.toFixed(2)}</div>
              <div className="text-slate-400">Propagated</div>
            </div>
          </div>

          {actor.top_signals?.length > 0 && (
            <div>
              <div className="text-[10px] font-semibold uppercase text-slate-400 mb-1.5">
                Contributing signals (top {actor.top_signals.length})
              </div>
              <div className="space-y-1">
                {actor.top_signals.map((s: any, i: number) => (
                  <div key={i} className="flex items-start gap-2 text-xs">
                    <span className="text-slate-300 shrink-0 mt-0.5">·</span>
                    <span className="text-slate-500 flex-1 leading-snug line-clamp-1">{s.title || s.source}</span>
                    <span className="text-slate-400 shrink-0 font-mono">+{s.pressure?.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
