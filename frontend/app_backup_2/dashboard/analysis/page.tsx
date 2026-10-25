"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type Kpi = {
  key: string;
  label: string;
  value: number | string | { start?: string; end?: string } | null;
  format?: string;
  aggregation?: string;
  column?: string | null;
  reason?: string;
};
type Profile = {
  row_count: number;
  column_count: number;
  missing_value_count: number;
  duplicate_row_count: number;
  columns: { name: string; dtype: string; missing: number; unique_values: number }[];
  numeric_columns: string[];
  text_columns: string[];
  date_columns: string[];
};
type Context = {
  fileName?: string;
  profile?: Profile | null;
  kpis?: Kpi[];
  intelligence?: {
    metric_candidates?: { column?: string; name?: string; reason?: string }[];
    analysis_opportunities?: { type?: string; name?: string; description?: string }[];
  } | null;
  analysisType?: string;
  column?: string | null;
};

const titleFor = (type: string) => {
  const t = type.toLowerCase().replaceAll("-", "_").replaceAll(" ", "_");
  if (t.includes("time") || t.includes("trend")) return "Time trend";
  if (t.includes("dimension") || t.includes("breakdown") || t.includes("categor")) return "Dimension breakdown";
  if (t.includes("relationship") || t.includes("correlation")) return "Numeric relationships";
  if (t.includes("distribution")) return "Category distribution";
  return "Numeric summary";
};
const fmt = (value: unknown) => {
  if (typeof value === "number") return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "object") {
    const v = value as { start?: string; end?: string };
    return [v.start, v.end].filter(Boolean).join(" – ") || "—";
  }
  return String(value);
};

export default function AnalysisPage() {
  const router = useRouter();
  const [context, setContext] = useState<Context | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [type, setType] = useState("numeric_summary");
  const [column, setColumn] = useState<string | null>(null);

  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    setType(params.get("type") ?? "numeric_summary");
    setColumn(params.get("column"));
    try {
      const raw = window.sessionStorage.getItem("dataflow_analysis_context");
      if (raw) setContext(JSON.parse(raw) as Context);
    } catch {
      setContext(null);
    } finally {
      setLoaded(true);
    }
  }, []);

  const title = titleFor(type);
  const profile = context?.profile;
  const selectedKpi = useMemo(
    () => (context?.kpis ?? []).find((k) => column && k.column === column),
    [context?.kpis, column]
  );
  const selectedColumn = profile?.columns?.find((c) => c.name === column);
  const missingPct = profile && profile.row_count > 0 && profile.column_count > 0
    ? (profile.missing_value_count / (profile.row_count * profile.column_count)) * 100
    : 0;
  const opportunities = context?.intelligence?.analysis_opportunities ?? [];

  if (!loaded) {
    return <main className="min-h-screen bg-[#07050d] p-8 text-white/60">Loading analysis…</main>;
  }

  return (
    <main className="min-h-screen bg-[#07050d] text-white">
      <div className="pointer-events-none fixed inset-0 overflow-hidden">
        <div className="absolute -right-40 top-0 h-96 w-96 rounded-full bg-violet-700/10 blur-[140px]" />
        <div className="absolute -left-40 bottom-0 h-96 w-96 rounded-full bg-sky-700/10 blur-[140px]" />
      </div>
      <div className="relative mx-auto max-w-[1500px] px-5 py-8 sm:px-8 lg:px-10">
        <header className="flex flex-col justify-between gap-5 border-b border-white/[0.08] pb-6 sm:flex-row sm:items-center">
          <div>
            <button onClick={() => router.push("/dashboard")} className="mb-4 inline-flex items-center gap-2 text-xs text-violet-200/80 transition hover:text-violet-100">← Back to dashboard</button>
            <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-violet-300/70">DataFlow AI / Deep analysis</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight sm:text-4xl">{title}</h1>
            <p className="mt-2 text-sm text-white/45">
              {context?.fileName ? `Dataset: ${context.fileName}` : "Dataset-specific analysis"}
              {column ? ` · Column: ${column}` : ""}
            </p>
          </div>
          <div className="flex gap-2">
            <span className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/60">{profile ? `${profile.row_count.toLocaleString("en-IN")} rows` : "No dataset context"}</span>
            <span className="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-white/60">{profile ? `${profile.column_count} columns` : "Upload required"}</span>
          </div>
        </header>

        {!profile ? (
          <section className="mt-8 rounded-3xl border border-amber-300/15 bg-amber-400/[0.04] p-6">
            <h2 className="text-lg font-semibold">No analysis context found</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-white/55">Open this page from the dashboard after uploading and inspecting a dataset. This page uses the current browser session's dataset profile and KPI metadata.</p>
            <button onClick={() => router.push("/dashboard")} className="mt-4 rounded-xl bg-violet-600 px-4 py-2.5 text-sm font-semibold hover:bg-violet-500">Return to dashboard</button>
          </section>
        ) : (
          <>
            <section className="mt-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {[
                { label: "Rows analyzed", value: fmt(profile.row_count), note: "Records in current dataset", tone: "from-violet-500/15" },
                { label: "Columns analyzed", value: fmt(profile.column_count), note: "Available fields", tone: "from-sky-500/15" },
                { label: "Missing values", value: fmt(profile.missing_value_count), note: `${missingPct.toFixed(1)}% of all cells`, tone: "from-amber-500/15" },
                { label: "Duplicate rows", value: fmt(profile.duplicate_row_count), note: "Exact row matches", tone: "from-fuchsia-500/15" },
              ].map((item) => (
                <div key={item.label} className={`rounded-2xl border border-white/[0.08] bg-gradient-to-br ${item.tone} to-[#0d0b16] p-5`}>
                  <p className="text-xs uppercase tracking-[0.12em] text-white/45">{item.label}</p>
                  <p className="mt-3 text-3xl font-semibold">{item.value}</p>
                  <p className="mt-2 text-xs text-white/35">{item.note}</p>
                </div>
              ))}
            </section>

            <section className="mt-5 grid gap-5 xl:grid-cols-[1.2fr_0.8fr]">
              <div className="rounded-3xl border border-white/[0.08] bg-[#0d0b16]/80 p-5 sm:p-7">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-semibold">{column ? `Column profile: ${column}` : "Dataset numeric profile"}</h2>
                    <p className="mt-1 text-sm text-white/40">Calculated from the dataset profile and available KPI metadata.</p>
                  </div>
                  <span className="rounded-full border border-emerald-300/15 bg-emerald-400/[0.06] px-3 py-1.5 text-xs text-emerald-200">Source-grounded</span>
                </div>

                {selectedKpi && (
                  <div className="mt-5 rounded-2xl border border-violet-300/15 bg-violet-400/[0.06] p-5">
                    <p className="text-xs uppercase tracking-wider text-violet-200/70">{selectedKpi.label}</p>
                    <p className="mt-2 text-3xl font-semibold">{fmt(selectedKpi.value)}</p>
                    <p className="mt-2 text-sm text-white/45">{selectedKpi.reason ?? `Aggregation: ${selectedKpi.aggregation ?? "provided by dataset KPI engine"}`}</p>
                  </div>
                )}

                <div className="mt-5 grid gap-3 sm:grid-cols-2">
                  {(column && selectedColumn ? [selectedColumn] : profile.columns ?? []).map((item) => {
                    const miss = item.missing ?? 0;
                    const pct = profile.row_count ? (miss / profile.row_count) * 100 : 0;
                    return (
                      <div key={item.name} className="rounded-xl border border-white/[0.06] bg-white/[0.02] p-4">
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <p className="break-words text-sm font-medium">{item.name}</p>
                            <p className="mt-1 text-xs text-white/35">{item.dtype} · {fmt(item.unique_values)} unique values</p>
                          </div>
                          <span className={`shrink-0 text-xs ${miss ? "text-amber-200" : "text-emerald-200"}`}>{miss.toLocaleString("en-IN")} missing</span>
                        </div>
                        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-white/[0.07]">
                          <div className={`h-full rounded-full ${miss ? "bg-amber-400" : "bg-emerald-400"}`} style={{ width: `${Math.min(100, Math.max(0, pct))}%` }} />
                        </div>
                        <p className="mt-2 text-[11px] text-white/30">{pct.toFixed(1)}% missing in this column</p>
                      </div>
                    );
                  })}
                </div>
              </div>

              <aside className="rounded-3xl border border-violet-300/15 bg-gradient-to-br from-violet-500/[0.08] to-[#0d0b16] p-5 sm:p-7">
                <div className="flex items-center gap-3">
                  <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-violet-300/15 bg-violet-400/10 text-lg text-violet-200">✦</span>
                  <div>
                    <h2 className="font-semibold">Suggested next analyses</h2>
                    <p className="mt-1 text-xs text-white/40">Based on detected columns and analysis opportunities</p>
                  </div>
                </div>
                <div className="mt-5 space-y-3">
                  {opportunities.map((item, i) => (
                    <button key={`${item.type ?? item.name ?? "item"}-${i}`} onClick={() => router.replace(`/dashboard/analysis?type=${encodeURIComponent(item.type ?? item.name ?? "numeric_summary")}${column ? `&column=${encodeURIComponent(column)}` : ""}`)} className="flex w-full items-start gap-3 rounded-xl border border-white/[0.07] bg-black/20 p-3 text-left transition hover:border-violet-300/25 hover:bg-violet-400/[0.05]">
                      <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-violet-400/10 text-xs text-violet-100">{i + 1}</span>
                      <span><span className="block text-sm font-medium text-white/80">{item.name ?? item.type ?? "Explore data"}</span><span className="mt-1 block text-xs leading-5 text-white/40">{item.description ?? "Explore this analysis using the available dataset profile."}</span></span>
                    </button>
                  ))}
                  {opportunities.length === 0 && <p className="rounded-xl border border-white/[0.06] p-4 text-sm text-white/45">No additional opportunities were supplied by the profiler.</p>}
                </div>
                <button onClick={() => router.push("/dashboard")} className="mt-5 rounded-xl border border-violet-300/20 bg-violet-400/10 px-4 py-2.5 text-sm font-semibold text-violet-100 hover:bg-violet-400/15">Back to overview →</button>
              </aside>
            </section>

            <section className="mt-5 rounded-3xl border border-white/[0.08] bg-[#0d0b16]/80 p-5 sm:p-7">
              <h2 className="text-lg font-semibold">Available metric candidates</h2>
              <p className="mt-1 text-sm text-white/40">Choose a detected metric to inspect its KPI metadata and column quality.</p>
              <div className="mt-4 flex flex-wrap gap-2">
                {(context.intelligence?.metric_candidates ?? []).map((metric, i) => {
                  const name = metric.column ?? metric.name ?? `Metric ${i + 1}`;
                  return <button key={`${name}-${i}`} onClick={() => router.push(`/dashboard/analysis?type=numeric_summary&column=${encodeURIComponent(metric.column ?? "")}`)} className={`rounded-xl border px-3 py-2 text-xs transition ${column === metric.column ? "border-violet-300/30 bg-violet-400/15 text-violet-100" : "border-white/10 bg-white/[0.03] text-white/60 hover:border-violet-300/25 hover:text-white"}`}>{name}</button>;
                })}
              </div>
            </section>
          </>
        )}
      </div>
    </main>
  );
}
