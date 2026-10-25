"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";

type DatasetCache = {
  fileName?: string;
  profile?: { row_count?: number; column_count?: number; missing_value_count?: number; duplicate_row_count?: number } | null;
  intelligence?: {
    dataset_domain?: { domain?: string; confidence?: number };
    metric_candidates?: Array<{ column?: string; name?: string; reason?: string }>;
    analysis_opportunities?: Array<{ type?: string; name?: string; description?: string }>;
  } | null;
};
type RowData = Record<string, string>;
type NumericMetric = { column: string; values: number[]; total: number; average: number; min: number; max: number; count: number };
type ChartPoint = { label: string; value: number };

const CACHE_KEY = "dataflow_dashboard_session_v1";
const DB_NAME = "dataflow_dashboard_files_v1";
const STORE_NAME = "files";

function readCachedFile(): Promise<File | null> {
  return new Promise((resolve) => {
    try {
      const request = indexedDB.open(DB_NAME, 1);
      request.onupgradeneeded = () => {
        if (!request.result.objectStoreNames.contains(STORE_NAME)) request.result.createObjectStore(STORE_NAME);
      };
      request.onerror = () => resolve(null);
      request.onsuccess = () => {
        const db = request.result;
        if (!db.objectStoreNames.contains(STORE_NAME)) { db.close(); resolve(null); return; }
        const tx = db.transaction(STORE_NAME, "readonly");
        const get = tx.objectStore(STORE_NAME).get("current");
        get.onsuccess = () => { const file = get.result as File | undefined; db.close(); resolve(file ?? null); };
        get.onerror = () => { db.close(); resolve(null); };
      };
    } catch { resolve(null); }
  });
}

function parseCsv(text: string): RowData[] {
  const matrix: string[][] = [];
  let row: string[] = [], cell = "", quoted = false;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch === '"') {
      if (quoted && text[i + 1] === '"') { cell += '"'; i++; }
      else quoted = !quoted;
    } else if (ch === "," && !quoted) { row.push(cell); cell = ""; }
    else if ((ch === "\n" || ch === "\r") && !quoted) {
      if (ch === "\r" && text[i + 1] === "\n") i++;
      row.push(cell); cell = "";
      if (row.some((value) => value.trim() !== "")) matrix.push(row);
      row = [];
    } else cell += ch;
  }
  if (cell.length || row.length) { row.push(cell); if (row.some((v) => v.trim() !== "")) matrix.push(row); }
  if (matrix.length < 2) return [];
  const headers = matrix[0].map((h, i) => (h.trim() || `column_${i + 1}`));
  return matrix.slice(1).map((values) => Object.fromEntries(headers.map((h, i) => [h, (values[i] ?? "").trim()])));
}

function numeric(value: string | undefined): number | null {
  if (value == null || value.trim() === "") return null;
  const cleaned = value.replace(/[₹$€£,%\s]/g, "").replace(/,/g, "");
  const parsed = Number(cleaned);
  return Number.isFinite(parsed) ? parsed : null;
}
function fmt(value: number): string {
  return value.toLocaleString("en-IN", { maximumFractionDigits: 2 });
}
function titleCase(value: string): string {
  return value.replace(/[_-]+/g, " ").replace(/\s+/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}
function detectDateColumn(headers: string[], rows: RowData[]): string | null {
  const likely = headers.filter((h) => /date|time|timestamp|created|ordered|month|day/i.test(h));
  for (const header of [...likely, ...headers]) {
    let seen = 0, valid = 0;
    for (const row of rows.slice(0, 100)) {
      if (!row[header]) continue;
      seen++;
      if (!Number.isNaN(Date.parse(row[header]))) valid++;
    }
    if (seen >= 3 && valid / seen >= 0.7) return header;
  }
  return null;
}
function detectMetric(headers: string[], rows: RowData[], prefer: string[]): NumericMetric | null {
  const candidates = headers.filter((h) => {
    const vals = rows.slice(0, 200).map((r) => numeric(r[h])).filter((v): v is number => v !== null);
    return vals.length >= Math.min(5, Math.max(2, rows.length * 0.1)) && new Set(vals).size > 1;
  });
  const ordered = [...candidates].sort((a, b) => {
    const score = (name: string) => {
      const low = name.toLowerCase();
      let n = prefer.reduce((sum, p, i) => sum + (low.includes(p) ? (prefer.length - i) * 5 : 0), 0);
      if (/id|zip|pin|code$/.test(low)) n -= 25;
      return n;
    };
    return score(b) - score(a);
  });
  const column = ordered[0];
  if (!column) return null;
  const values = rows.map((r) => numeric(r[column])).filter((v): v is number => v !== null);
  return { column, values, total: values.reduce((a,b)=>a+b,0), average: values.reduce((a,b)=>a+b,0)/values.length, min: Math.min(...values), max: Math.max(...values), count: values.length };
}
function linePath(points: ChartPoint[], width=720, height=220): string {
  if (!points.length) return "";
  const max = Math.max(...points.map(p=>p.value), 1);
  const min = Math.min(...points.map(p=>p.value), 0);
  const span = max-min || 1;
  return points.map((p,i)=>`${i===0?"M":"L"} ${(i/(Math.max(1,points.length-1)))*(width-20)+10} ${height-18-((p.value-min)/span)*(height-36)}`).join(" ");
}
function Icon({ children }: { children: React.ReactNode }) { return <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.05] text-base text-violet-200">{children}</span>; }

export default function DashboardOverview() {
  const router = useRouter();
  const [fileName, setFileName] = useState("");
  const [rows, setRows] = useState<RowData[]>([]);
  const [headers, setHeaders] = useState<string[]>([]);
  const [profile, setProfile] = useState<DatasetCache["profile"]>(null);
  const [loading, setLoading] = useState(true);
  const [activeNav, setActiveNav] = useState("Overview");

  useEffect(() => {
    let cancelled = false;
    async function hydrate() {
      try {
        const cache = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "{}") as DatasetCache;
        const file = await readCachedFile();
        if (cancelled) return;
        if (cache.fileName) setFileName(cache.fileName);
        if (cache.profile) setProfile(cache.profile);
        if (file) {
          const parsed = parseCsv(await file.text());
          if (!cancelled) {
            setRows(parsed);
            setHeaders(parsed.length ? Object.keys(parsed[0]) : []);
            setFileName(file.name || cache.fileName || "Uploaded dataset");
          }
        }
      } catch (error) {
        console.warn("Unable to restore dashboard dataset", error);
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void hydrate();
    return () => { cancelled = true; };
  }, []);

  const metric = useMemo(() => detectMetric(headers, rows, ["revenue", "sales", "amount", "stock_value", "stock_qty", "quantity", "units", "spend", "cost", "price", "profit", "value"]), [headers, rows]);
  const quantityMetric = useMemo(() => detectMetric(headers, rows, ["stock_qty", "quantity", "qty", "inventory", "units", "stock"]), [headers, rows]);
  const unitCostMetric = useMemo(() => detectMetric(headers, rows, ["unit_cost", "cost_price", "purchase_price", "cost"]), [headers, rows]);
  const sellingMetric = useMemo(() => detectMetric(headers, rows, ["selling_price", "unit_price", "sale_price", "price", "revenue", "sales"]), [headers, rows]);
  const dateColumn = useMemo(() => detectDateColumn(headers, rows), [headers, rows]);
  const numericColumns = useMemo(() => headers.filter(h => rows.slice(0,100).filter(r=>numeric(r[h])!==null).length >= Math.min(5,Math.max(2,rows.length*.1))), [headers,rows]);
  const categoryColumn = useMemo(() => headers.filter(h => !numericColumns.includes(h) && !/id|email|phone|zip|pin|code/i.test(h)).sort((a,b)=>new Set(rows.map(r=>r[a]).filter(Boolean)).size-new Set(rows.map(r=>r[b]).filter(Boolean)).size)[0] ?? null, [headers,numericColumns,rows]);
  const contributorData = useMemo<ChartPoint[]>(() => {
    if (!categoryColumn || !metric) return [];
    const grouped = new Map<string, number>();
    for (const row of rows) {
      const label = row[categoryColumn] || "(Missing)";
      const val = numeric(row[metric.column]);
      if (val !== null) grouped.set(label, (grouped.get(label) ?? 0) + val);
    }
    return [...grouped.entries()].map(([label,value])=>({label,value})).sort((a,b)=>b.value-a.value).slice(0,5);
  }, [categoryColumn,metric,rows]);
  const trendData = useMemo<ChartPoint[]>(() => {
    if (!dateColumn || !metric) return [];
    const grouped = new Map<string, number>();
    for (const row of rows) {
      const date = Date.parse(row[dateColumn]);
      const val = numeric(row[metric.column]);
      if (!Number.isFinite(date) || val === null) continue;
      const d = new Date(date);
      const label = `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,"0")}`;
      grouped.set(label, (grouped.get(label) ?? 0) + val);
    }
    return [...grouped.entries()].sort(([a],[b])=>a.localeCompare(b)).slice(-18).map(([label,value])=>({label,value}));
  }, [dateColumn,metric,rows]);
  const missingCount = profile?.missing_value_count ?? rows.reduce((sum,row)=>sum+headers.filter(h=>!row[h]).length,0);
  const duplicateCount = profile?.duplicate_row_count ?? 0;
  const completeness = rows.length && headers.length ? Math.max(0,100-(missingCount/(rows.length*headers.length))*100) : 0;
  const inventorySignals = useMemo(() => {
    const stockCol = headers.find(h => /stock[_ ]?qty|quantity[_ ]?in[_ ]?stock|inventory[_ ]?qty|available[_ ]?stock/i.test(h));
    const reorderCol = headers.find(h => /reorder[_ ]?level|min[_ ]?stock|reorder[_ ]?point/i.test(h));
    const costCol = headers.find(h => /unit[_ ]?cost|cost[_ ]?price|purchase[_ ]?price/i.test(h));
    let below = 0, stockValue = 0, assessed = 0;
    if (stockCol) for (const row of rows) {
      const stock = numeric(row[stockCol]);
      if (stock === null) continue;
      assessed++;
      if (reorderCol) {
        const reorder = numeric(row[reorderCol]);
        if (reorder !== null && stock <= reorder) below++;
      }
      if (costCol) {
        const cost = numeric(row[costCol]);
        if (cost !== null) stockValue += stock * cost;
      }
    }
    return { stockCol, reorderCol, costCol, below, stockValue, assessed };
  }, [headers,rows]);
  const totalContribution = contributorData.reduce((sum,p)=>sum+p.value,0);
  const topShare = totalContribution ? contributorData[0]?.value / totalContribution * 100 : 0;
  const recommendations = useMemo(() => {
    const items: {kind:"attention"|"positive"|"opportunity"; title:string; body:string}[] = [];
    if (inventorySignals.stockCol && inventorySignals.reorderCol && inventorySignals.assessed) {
      items.push({
        kind: inventorySignals.below > 0 ? "attention" : "positive",
        title: inventorySignals.below > 0 ? `${inventorySignals.below} items at/below reorder level` : "No low-stock items detected",
        body: inventorySignals.below > 0 ? `Review these SKUs first; current stock is at or below the configured reorder threshold. This is a rules-based alert, not a demand forecast.` : "No rows crossed the recorded reorder threshold in the available data."
      });
    }
    if (contributorData.length) {
      items.push({kind:"opportunity", title:`Top contributor: ${contributorData[0].label}`, body:`It contributes ${topShare.toFixed(1)}% of the displayed top-five ${titleCase(metric?.column ?? "metric")} total. Check replenishment and supplier lead times if this category is business-critical.`});
    }
    if (inventorySignals.stockCol && inventorySignals.costCol) {
      items.push({kind:"opportunity",title:"Estimated inventory value available",body:`Stock quantity × unit cost sums to ${fmt(inventorySignals.stockValue)} for rows with both values. Review high-value slow-moving stock only if movement history is available.`});
    }
    if (dateColumn && trendData.length >= 2) {
      const first=trendData[0], last=trendData[trendData.length-1];
      const change=first.value!==0 ? ((last.value-first.value)/Math.abs(first.value))*100 : null;
      if (change!==null) items.push({kind:change>=0?"positive":"attention",title:`${titleCase(metric?.column ?? "Metric")} ${change>=0?"increased":"decreased"} across the displayed period`,body:`The first displayed month (${first.label}) was ${fmt(first.value)} and the latest (${last.label}) was ${fmt(last.value)}, a ${change>=0?"+":""}${change.toFixed(1)}% difference. This compares endpoints, not seasonally adjusted performance.`});
    }
    if (!items.length) items.push({kind:"opportunity",title:"Improve data coverage for stronger insights",body:"Add a numeric measure, a meaningful category, or a valid date field to enable ranked contributors and trends. Current recommendations are limited by the available columns."});
    return items.slice(0,3);
  }, [inventorySignals, contributorData, topShare, metric, dateColumn, trendData]);

  function goWorkspace(section: string) {
    setActiveNav(section);
    const anchors: Record<string,string> = { Datasets:"datasets", "AI Analyst":"ai-analyst", Reports:"dataset-intelligence", Settings:"billing" };
    router.push(`/dashboard/workspace#${anchors[section] ?? "datasets"}`);
  }

  const maxContributor = Math.max(...contributorData.map(p=>p.value), 1);
  const navItems = [
    {label:"Overview", icon:"⌂", action:()=>{setActiveNav("Overview");}},
    {label:"Datasets", icon:"▤", action:()=>goWorkspace("Datasets")},
    {label:"AI Analyst", icon:"✧", action:()=>goWorkspace("AI Analyst")},
    {label:"Reports", icon:"▥", action:()=>goWorkspace("Reports")},
    {label:"Settings", icon:"⚙", action:()=>goWorkspace("Settings")},
  ];

  return (
    <main className="min-h-screen bg-[#070914] text-white">
      <div className="flex min-h-screen">
        <aside className="hidden w-[226px] shrink-0 flex-col border-r border-indigo-200/10 bg-[#080b19] px-4 py-5 lg:flex">
          <button onClick={()=>{setActiveNav("Overview");window.scrollTo({top:0,behavior:"smooth"});}} className="mb-9 flex items-center gap-3 px-2 text-left">
            <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-indigo-600 font-bold shadow-lg shadow-violet-950/40">D</span>
            <span className="text-lg font-semibold tracking-tight">DataFlow <span className="text-violet-300">AI</span></span>
          </button>
          <nav className="space-y-1">
            {navItems.map(item=><button key={item.label} onClick={item.action} className={`flex w-full items-center gap-3 rounded-xl px-3 py-3 text-left text-sm transition ${activeNav===item.label?"border border-violet-400/30 bg-gradient-to-r from-violet-600/30 to-indigo-500/10 text-white":"text-slate-400 hover:bg-white/[0.04] hover:text-white"}`}><span className="w-5 text-center text-lg">{item.icon}</span>{item.label}</button>)}
          </nav>
          <div className="mt-auto rounded-2xl border border-white/10 bg-white/[0.03] p-3">
            <p className="truncate text-sm font-medium">Your workspace</p>
            <p className="mt-1 truncate text-xs text-slate-500">{fileName || "No dataset loaded"}</p>
            <button onClick={()=>goWorkspace("Datasets")} className="mt-3 w-full rounded-lg bg-white/[0.06] px-3 py-2 text-xs text-slate-300 hover:bg-white/10">Manage dataset →</button>
          </div>
        </aside>
        <div className="min-w-0 flex-1">
          <header className="sticky top-0 z-20 flex flex-wrap items-center justify-between gap-4 border-b border-white/[0.07] bg-[#080b18]/90 px-5 py-4 backdrop-blur-xl sm:px-8">
            <div><p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-violet-300/70">DataFlow AI / Workspace</p><h1 className="mt-1 text-2xl font-semibold tracking-tight sm:text-3xl">Analytics Overview</h1><p className="mt-1 text-sm text-slate-400">{fileName ? `Insights from ${fileName}` : "Your data, translated into decisions."}</p></div>
            <div className="flex items-center gap-2">
              {fileName && <span className="hidden rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2 text-xs text-slate-300 sm:inline">{rows.length.toLocaleString("en-IN")} rows · {headers.length} columns</span>}
              <button onClick={()=>goWorkspace("Datasets")} className="rounded-xl border border-violet-300/20 bg-violet-500/10 px-4 py-2.5 text-sm text-violet-100 hover:bg-violet-500/20">{fileName?"Change dataset":"Upload dataset"}</button>
            </div>
          </header>
          <div className="mx-auto max-w-[1600px] space-y-5 px-4 py-5 sm:px-8 sm:py-7">
            {!fileName || !rows.length ? (
              <section className="flex min-h-[440px] flex-col items-center justify-center rounded-3xl border border-dashed border-violet-300/20 bg-gradient-to-br from-[#17122b] to-[#0b1020] p-8 text-center">
                <span className="flex h-16 w-16 items-center justify-center rounded-2xl border border-violet-300/20 bg-violet-400/10 text-3xl text-violet-200">✦</span>
                <h2 className="mt-5 text-2xl font-semibold">Your data, translated into decisions.</h2>
                <p className="mt-2 max-w-lg text-sm leading-6 text-slate-400">{loading?"Restoring your last dataset…":"Upload a CSV to build a live overview with local calculations and no Groq calls for charts."}</p>
                <button onClick={()=>goWorkspace("Datasets")} className="mt-6 rounded-xl bg-gradient-to-r from-violet-600 to-indigo-600 px-5 py-3 text-sm font-semibold hover:brightness-110">Open datasets →</button>
                {!loading && <p className="mt-3 text-xs text-slate-600">No dataset is cached in this browser session yet.</p>}
              </section>
            ) : (
              <>
                <section className="relative overflow-hidden rounded-3xl border border-violet-300/15 bg-gradient-to-br from-[#17122b] via-[#0d1224] to-[#091321] p-5 sm:p-7">
                  <div className="pointer-events-none absolute -right-10 -top-16 h-60 w-60 rounded-full bg-violet-500/10 blur-3xl"/>
                  <div className="relative flex flex-col justify-between gap-5 lg:flex-row lg:items-end">
                    <div><div className="inline-flex items-center gap-2 rounded-full border border-emerald-300/20 bg-emerald-400/[0.06] px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-emerald-200"><span className="h-1.5 w-1.5 rounded-full bg-emerald-400"/> Local analytics · no LLM calls</div><h2 className="mt-4 text-2xl font-semibold sm:text-3xl">Executive summary</h2><p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">{rows.length.toLocaleString("en-IN")} records across {headers.length} columns. {metric ? `${titleCase(metric.column)} is the selected measure for ranking and trend analysis.` : "No suitable numeric measure could be detected automatically."} {categoryColumn ? `Contributor grouping: ${titleCase(categoryColumn)}.` : "No suitable category column found."}</p></div>
                    <div className="flex flex-wrap gap-2 text-xs"><span className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-slate-300">{titleCase(profile?.row_count ? "dataset profile ready" : "browser profile")}</span><span className="rounded-lg border border-white/10 bg-black/20 px-3 py-2 text-slate-300">{dateColumn ? `Date: ${titleCase(dateColumn)}` : "No date trend available"}</span></div>
                  </div>
                </section>

                <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
                  {[
                    {label:"Total rows",value:fmt(rows.length),sub:"Records in current dataset",accent:"from-violet-500/20 to-purple-500/5",icon:"◇"},
                    {label:metric?`Total ${titleCase(metric.column)}`:"Numeric columns",value:metric?fmt(metric.total):String(numericColumns.length),sub:metric?`${metric.count.toLocaleString("en-IN")} non-empty numeric values`:"Detected from actual CSV values",accent:"from-sky-500/15 to-blue-500/5",icon:"↗"},
                    {label:sellingMetric?`Average ${titleCase(sellingMetric.column)}`:"Completeness",value:sellingMetric?fmt(sellingMetric.average):`${completeness.toFixed(1)}%`,sub:sellingMetric?`${sellingMetric.count.toLocaleString("en-IN")} numeric records`:"Non-empty cells across the dataset",accent:"from-emerald-500/15 to-teal-500/5",icon:"◎"},
                    {label:quantityMetric?`Total ${titleCase(quantityMetric.column)}`:"Missing values",value:quantityMetric?fmt(quantityMetric.total):fmt(missingCount),sub:quantityMetric?"Summed from the uploaded records":`${completeness.toFixed(1)}% completeness`,accent:"from-fuchsia-500/15 to-pink-500/5",icon:"✦"},
                  ].map(k=><div key={k.label} className={`rounded-2xl border border-white/[0.08] bg-gradient-to-br ${k.accent} p-5 transition hover:-translate-y-0.5 hover:border-white/20`}><div className="flex items-start justify-between gap-3"><p className="text-xs font-semibold uppercase tracking-[0.12em] text-slate-400">{k.label}</p><Icon>{k.icon}</Icon></div><p className="mt-4 break-words text-2xl font-semibold tracking-tight sm:text-3xl">{k.value}</p><p className="mt-3 border-t border-white/10 pt-3 text-xs leading-5 text-slate-500">{k.sub}</p></div>)}
                </section>

                <section className="grid gap-4 xl:grid-cols-[1.5fr_1fr]">
                  <div className="rounded-2xl border border-white/[0.08] bg-[#0b0e1a] p-5 sm:p-6">
                    <div className="flex flex-wrap items-start justify-between gap-3"><div><h3 className="font-semibold">Performance over time</h3><p className="mt-1 text-xs text-slate-500">{dateColumn&&metric?`${titleCase(metric.column)} grouped by month using ${titleCase(dateColumn)} · local calculation`:"No usable date + numeric measure pair found; showing why a time trend is unavailable."}</p></div><span className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-400">{trendData.length?`${trendData.length} monthly points`:"No trend"}</span></div>
                    {trendData.length>=2 ? <div className="mt-5"><svg viewBox="0 0 720 220" className="h-[230px] w-full overflow-visible" role="img" aria-label={`${metric?.column} monthly trend`}>{[0,1,2,3,4].map(i=><line key={i} x1="10" x2="710" y1={20+i*43} y2={20+i*43} stroke="rgba(255,255,255,.07)" strokeDasharray="4 5"/>)}<path d={`${linePath(trendData)} L 710 202 L 10 202 Z`} fill="url(#trendFill)"/><defs><linearGradient id="trendFill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stopColor="#8b5cf6" stopOpacity=".35"/><stop offset="100%" stopColor="#8b5cf6" stopOpacity="0"/></linearGradient></defs><path d={linePath(trendData)} fill="none" stroke="#a78bfa" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round"/>{trendData.map((p,i)=><circle key={p.label} cx={(i/(Math.max(1,trendData.length-1)))*700+10} cy={202-18-((p.value-Math.min(...trendData.map(x=>x.value),0))/(Math.max(...trendData.map(x=>x.value),1)-Math.min(...trendData.map(x=>x.value),0)||1))*184} r="3.5" fill="#c4b5fd"><title>{`${p.label}: ${fmt(p.value)}`}</title></circle>)}</svg><div className="mt-2 flex flex-wrap justify-between gap-2 text-[10px] text-slate-500">{trendData.filter((_,i)=>i===0||i===trendData.length-1||i%Math.ceil(trendData.length/5)===0).map(p=><span key={p.label}>{p.label}</span>)}</div></div> : <div className="mt-5 flex min-h-[210px] flex-col items-center justify-center rounded-xl border border-dashed border-white/10 bg-white/[0.015] px-5 text-center"><span className="text-2xl text-slate-500">⌁</span><p className="mt-2 text-sm text-slate-300">A time trend needs a valid date column and a numeric measure.</p><p className="mt-1 max-w-md text-xs leading-5 text-slate-500">This dataset does not currently provide enough valid monthly points. We won't draw a fake trend.</p></div>}
                  </div>
                  <div className="rounded-2xl border border-white/[0.08] bg-[#0b0e1a] p-5 sm:p-6"><div><h3 className="font-semibold">Top 5 contributors</h3><p className="mt-1 text-xs text-slate-500">{categoryColumn&&metric?`Ranked by ${titleCase(metric.column)} grouped by ${titleCase(categoryColumn)}.`:"A category and numeric measure are required for ranking."}</p></div>
                    {contributorData.length ? <div className="mt-6 space-y-5">{contributorData.map((item,index)=><div key={item.label}><div className="mb-2 flex items-center justify-between gap-3 text-xs"><span className="max-w-[70%] truncate text-slate-300">{item.label}</span><span className="font-semibold tabular-nums text-slate-100">{fmt(item.value)}</span></div><div className="h-2.5 overflow-hidden rounded-full bg-white/[0.06]"><div className="h-full rounded-full" style={{width:`${Math.max(2,item.value/maxContributor*100)}%`,background:["#a78bfa","#60a5fa","#34d399","#fbbf24","#f472b6"][index]}}/></div></div>)}</div> : <p className="mt-6 rounded-xl border border-dashed border-white/10 p-4 text-sm text-slate-500">No compatible category/measure pair was detected.</p>}
                    {contributorData.length>0&&<p className="mt-5 border-t border-white/[0.08] pt-4 text-xs leading-5 text-slate-500">Top-five share is calculated against the sum of the displayed top-five values only; it is not the share of all categories.</p>}
                  </div>
                </section>

                <section className="grid gap-4 xl:grid-cols-2">
                  <div className="rounded-2xl border border-white/[0.08] bg-[#0b0e1a] p-5 sm:p-6"><div className="flex items-center gap-3"><Icon>✦</Icon><div><h3 className="font-semibold">Data-backed insights</h3><p className="mt-1 text-xs text-slate-500">Calculated locally from this CSV · no Groq calls</p></div></div><div className="mt-4 space-y-3">{recommendations.map((r,i)=><div key={r.title} className="flex gap-3 rounded-xl border border-white/[0.07] bg-white/[0.02] p-4"><span className={`mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-lg text-xs ${r.kind==="attention"?"bg-amber-400/10 text-amber-200":r.kind==="positive"?"bg-emerald-400/10 text-emerald-200":"bg-sky-400/10 text-sky-200"}`}>{r.kind==="attention"?"!":r.kind==="positive"?"↑":"↗"}</span><div><p className="text-sm font-semibold text-slate-100">{r.title}</p><p className="mt-1 text-xs leading-5 text-slate-400">{r.body}</p></div></div>)}</div></div>
                  <div className="rounded-2xl border border-white/[0.08] bg-[#0b0e1a] p-5 sm:p-6"><div className="flex items-center gap-3"><Icon>◎</Icon><div><h3 className="font-semibold">Data quality & next actions</h3><p className="mt-1 text-xs text-slate-500">Signals to consider before acting</p></div></div><div className="mt-5 grid grid-cols-2 gap-3"><div className="rounded-xl bg-white/[0.03] p-4"><p className="text-xs text-slate-500">Missing values</p><p className="mt-2 text-2xl font-semibold">{fmt(missingCount)}</p></div><div className="rounded-xl bg-white/[0.03] p-4"><p className="text-xs text-slate-500">Duplicate rows</p><p className="mt-2 text-2xl font-semibold">{fmt(duplicateCount)}</p></div><div className="rounded-xl bg-white/[0.03] p-4"><p className="text-xs text-slate-500">Numeric fields</p><p className="mt-2 text-2xl font-semibold">{numericColumns.length}</p></div><div className="rounded-xl bg-white/[0.03] p-4"><p className="text-xs text-slate-500">Completeness</p><p className="mt-2 text-2xl font-semibold">{completeness.toFixed(1)}%</p></div></div><div className="mt-4 h-2 overflow-hidden rounded-full bg-white/[0.07]"><div className="h-full rounded-full bg-gradient-to-r from-violet-500 to-emerald-400" style={{width:`${completeness}%`}}/></div><button onClick={()=>goWorkspace("Reports")} className="mt-5 rounded-xl border border-violet-300/20 bg-violet-500/10 px-4 py-2.5 text-sm text-violet-100 hover:bg-violet-500/20">Open full data profile →</button></div>
                </section>
              </>
            )}
            <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-white/[0.07] pt-4 text-[11px] text-slate-600"><span>DataFlow AI · dataset-driven analytics</span><span>Charts and rules-based recommendations run locally in your browser. No Groq tokens are used by this overview.</span></footer>
          </div>
        </div>
      </div>
      <nav className="fixed inset-x-3 bottom-3 z-30 flex justify-around rounded-2xl border border-white/10 bg-[#0b0e1a]/95 p-2 shadow-2xl backdrop-blur-xl lg:hidden">
        {navItems.slice(0,4).map(item=><button key={item.label} onClick={item.action} className={`flex flex-col items-center gap-1 rounded-xl px-3 py-2 text-[10px] ${activeNav===item.label?"bg-violet-500/20 text-violet-100":"text-slate-400"}`}><span className="text-lg">{item.icon}</span>{item.label}</button>)}
      </nav>
    </main>
  );
}
