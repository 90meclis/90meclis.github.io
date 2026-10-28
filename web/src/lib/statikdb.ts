/**
 * Statik veritabanı istemcisi: Supabase istemcisinin kullandığımız sorgu yüzeyini (from/select/eq/neq/gt/gte/lt/lte/in/is/
 * like/contains/or/not/order/limit/range) `veri` dalındaki JSON dosyaları üzerinde tarayıcıda çalıştırır.
 * Hiçbir ziyaretçi okuması veritabanına gitmez. Dosya bölümlemesi: meclis/statik_q.py.
 */
const BASE = ((import.meta.env.VITE_VERI_URL as string | undefined)
  || "https://raw.githubusercontent.com/90meclis/90meclis.github.io/veri") + "/q";

type Row = Record<string, unknown>;
type Res<T = Row[]> = { data: T | null; error: { message: string } | null };

export const fkey = (s: string) => [...String(s)].map((c) => (/[A-Za-z0-9._-]/.test(c) ? c : `~${c.codePointAt(0)!.toString(16)}`)).join("");

const cache = new Map<string, Promise<unknown>>();
function load<T>(rel: string): Promise<T | null> {
  let p = cache.get(rel);
  if (!p) {
    p = fetch(`${BASE}/${rel}`).then((r) => (r.ok ? r.json() : null)).catch(() => null);
    cache.set(rel, p);
  }
  return p as Promise<T | null>;
}
const rows = async (rel: string): Promise<Row[]> => ((await load<Row[]>(rel)) ?? []).map((r) => ({ ...r }));
const meta = () => load<{ gun_ilk: string; gun_son: string; uretildi: string }>("_meta.json");
const idx = () => load<Record<string, string>>("matches/idx.json");

// ---- karşılaştırma -------------------------------------------------------------------------------------------
const ISO = /^\d{4}-\d{2}-\d{2}T/;
function norm(v: unknown): unknown {
  if (typeof v === "string" && ISO.test(v)) { const t = Date.parse(v); if (!Number.isNaN(t)) return t; }
  return v;
}
function cmp(a: unknown, b: unknown): number {
  const x = norm(a), y = norm(b);
  if (typeof x === "number" && typeof y === "number") return x - y;
  if (typeof x === "number" && typeof y === "string" && y.trim() !== "" && !Number.isNaN(Number(y))) return x - Number(y);
  return String(x).localeCompare(String(y));
}
const eq = (a: unknown, b: unknown) => a === b || (a != null && b != null && cmp(a, b) === 0);
function like(v: unknown, pat: string, ci = false): boolean {
  if (v == null) return false;
  const re = new RegExp("^" + pat.replace(/[.+?^${}()|[\]\\]/g, "\\$&").replace(/[%*]/g, ".*").replace(/_/g, ".") + "$", ci ? "i" : "");
  return re.test(String(v));
}
function get(r: Row, path: string): unknown {
  // "a->b->>c" yolları
  const parts = path.split(/->>?/);
  let v: unknown = r[parts[0]];
  for (const k of parts.slice(1)) {
    if (typeof v === "string") { try { v = JSON.parse(v); } catch { return null; } }
    v = v == null ? null : (v as Row)[k];
  }
  return v ?? null;
}

type Pred = (r: Row) => boolean;
type Filt = { col: string; op: string; val: unknown; pred: Pred };

function opPred(col: string, op: string, val: unknown): Pred {
  switch (op) {
    case "eq": return (r) => eq(get(r, col), val);
    case "neq": return (r) => !eq(get(r, col), val);
    case "gt": return (r) => get(r, col) != null && cmp(get(r, col), val) > 0;
    case "gte": return (r) => get(r, col) != null && cmp(get(r, col), val) >= 0;
    case "lt": return (r) => get(r, col) != null && cmp(get(r, col), val) < 0;
    case "lte": return (r) => get(r, col) != null && cmp(get(r, col), val) <= 0;
    case "in": { const vs = val as unknown[]; return (r) => vs.some((v) => eq(get(r, col), v)); }
    case "is": return (r) => (val === null || val === "null" ? get(r, col) == null : get(r, col) === val);
    case "like": return (r) => like(get(r, col), String(val));
    case "ilike": return (r) => like(get(r, col), String(val), true);
    case "contains": {
      const want = (typeof val === "string" ? JSON.parse(val) : val) as unknown[];
      return (r) => { let v = get(r, col); if (typeof v === "string") { try { v = JSON.parse(v); } catch { return false; } }
        return Array.isArray(v) && want.every((w) => (v as unknown[]).includes(w)); };
    }
    default: return () => true;
  }
}

// PostgREST "or" sözdizimi: a.eq.x,and(b.in.(1,2),c.like.*:y)
function splitTop(s: string): string[] {
  const out: string[] = []; let depth = 0, q = false, cur = "";
  for (const c of s) {
    if (c === '"') q = !q;
    if (!q && c === "(") depth++;
    if (!q && c === ")") depth--;
    if (!q && depth === 0 && c === ",") { out.push(cur); cur = ""; continue; }
    cur += c;
  }
  if (cur) out.push(cur);
  return out;
}
const unq = (v: string) => (v.startsWith('"') && v.endsWith('"') ? v.slice(1, -1) : v);
type Term = { kind: "and" | "or"; items: Term[] } | { kind: "leaf"; col: string; op: string; val: unknown };
function parseTerm(t: string): Term {
  const m = /^(and|or)\((.*)\)$/.exec(t.trim());
  if (m) return { kind: m[1] as "and" | "or", items: splitTop(m[2]).map(parseTerm) };
  const [col, op, ...rest] = t.trim().split(".");
  let raw = rest.join(".");
  if (op === "in") raw = raw.replace(/^\(|\)$/g, "");
  const val = op === "in" ? splitTop(raw).map(unq) : op === "is" ? (raw === "null" ? null : raw) : unq(raw);
  return { kind: "leaf", col, op, val };
}
function termPred(t: Term): Pred {
  if (t.kind === "leaf") return opPred(t.col, t.op, t.val);
  const ps = t.items.map(termPred);
  return t.kind === "and" ? (r) => ps.every((p) => p(r)) : (r) => ps.some((p) => p(r));
}
function leaves(t: Term): { col: string; op: string; val: unknown }[] {
  return t.kind === "leaf" ? [t] : t.items.flatMap(leaves);
}

// ---- seçim (select) ------------------------------------------------------------------------------------------
function project(r: Row, sel: string): Row {
  const items = splitTop(sel.replace(/\s+/g, ""));
  if (items.length === 1 && items[0] === "*") return r;
  const o: Row = {};
  for (const it of items) {
    if (it === "*") { Object.assign(o, r); continue; }
    const i = it.indexOf(":");
    const alias = i > 0 && !it.slice(0, i).includes("-") ? it.slice(0, i) : null;
    const expr = alias ? it.slice(i + 1) : it;
    const name = alias ?? expr.split(/->>?/).pop()!;
    let v = get(r, expr);
    if (expr.includes("->>") && v != null && typeof v === "object") v = JSON.stringify(v);
    o[name] = v;
  }
  return o;
}

// ---- tablo çözümleyici (hangi dosyalar?) -----------------------------------------------------------------------
const PER_DAY = new Set(["match_stats", "lineups", "weather", "injuries", "odds_snapshots", "analyses", "v_bot_tarama",
  "v_dinlenme", "v_oran_hareketi"]);

function trDayOf(t: number): string {
  return new Date(t + 3 * 3600_000).toISOString().slice(0, 10);
}
function daysBetween(lo: number, hi: number): string[] {
  const out: string[] = [];
  for (let t = lo; t < hi + 86400_000; t += 86400_000) { const d = trDayOf(t); if (!out.includes(d)) out.push(d); }
  return out.filter((d) => d <= trDayOf(hi));
}
function vals(fs: Filt[], col: string): unknown[] | null {
  const f = fs.find((x) => x.col === col && (x.op === "eq" || x.op === "in"));
  return f ? (f.op === "in" ? (f.val as unknown[]) : [f.val]) : null;
}
async function daysForIds(ids: unknown[]): Promise<string[]> {
  const ix = (await idx()) ?? {};
  return [...new Set(ids.map((i) => ix[String(i)]).filter(Boolean))];
}
async function many(paths: string[]): Promise<Row[]> {
  return (await Promise.all([...new Set(paths)].map(rows))).flat();
}

async function source(table: string, fs: Filt[], ors: Term[], sel: string): Promise<Row[]> {
  if (table === "matches") {
    const ids = vals(fs, "id");
    if (ids) return many((await daysForIds(ids)).map((d) => `matches/gun/${d}.json`)).then(async (r) =>
      r.length ? r : many([...new Set((await daysForIds(ids)).map(() => "matches/sezon.json"))]));
    const lo = fs.find((f) => f.col === "kickoff_at" && (f.op === "gte" || f.op === "gt"));
    const hi = fs.find((f) => f.col === "kickoff_at" && (f.op === "lt" || f.op === "lte"));
    const m = await meta();
    if (lo && hi && m) {
      const a = Date.parse(String(lo.val)), b = Date.parse(String(hi.val));
      const ds = daysBetween(a, b);
      if (ds.length <= 26 && ds[0] >= m.gun_ilk && ds[ds.length - 1] <= m.gun_son) return many(ds.map((d) => `matches/gun/${d}.json`));
    }
    const lg = vals(fs, "league");
    if (lg) return many(lg.map((l) => `matches/lig/${fkey(String(l))}.json`));
    const teamIds = ors.flatMap(leaves).filter((l) => /_team_id$/.test(l.col) && (l.op === "in" || l.op === "eq"))
      .flatMap((l) => (Array.isArray(l.val) ? l.val : [l.val])).map(String);
    if (teamIds.length) return many([...new Set(teamIds.map((t) => t.split(":")[0]))].map((l) => `matches/lig/${fkey(l)}.json`));
    return rows("matches/sezon.json");
  }
  if (table === "analyses") {
    const ids = vals(fs, "match_id") ?? [];
    if (ids.some((i) => String(i).startsWith("meclis:"))) return rows("analyses/meclis.json");
    const full = /(^|,)\s*(\*|payload)\s*(,|$)/.test(sel);
    if (full) {
      const r = await many(ids.map((i) => `analyses/mac/${fkey(String(i))}.json`));
      if (r.length) return r;
    }
    return many((await daysForIds(ids)).map((d) => `analyses/gun/${d}.json`));
  }
  if (table === "injuries" && !vals(fs, "match_id")) return rows("injuries/takim.json");
  if (PER_DAY.has(table)) {
    const ids = vals(fs, "match_id");
    if (!ids) return [];
    return many((await daysForIds(ids)).map((d) => `${table}/gun/${d}.json`));
  }
  if (table === "v_takim_mac_istatistik") {
    const slugs = vals(fs, "team_slug");
    if (slugs) return many(slugs.map((s) => `${table}/takim/${fkey(String(s))}.json`));
    const lg = vals(fs, "league");
    if (lg) return many(lg.map((l) => `${table}/lig/${fkey(String(l))}.json`));
    return [];
  }
  if (table === "trends") {
    const lg = vals(fs, "league");
    return lg ? many(lg.map((l) => `trends/${fkey(String(l))}.json`)) : [];
  }
  if (table === "v_backtest") return [];
  return rows(`${table}.json`);
}

// ---- sorgu oluşturucu ------------------------------------------------------------------------------------------
class Query implements PromiseLike<Res> {
  private fs: Filt[] = [];
  private ors: Term[] = [];
  private nots: Pred[] = [];
  private ord: { col: string; asc: boolean }[] = [];
  private lim: number | null = null;
  private rng: [number, number] | null = null;
  private sel = "*";
  constructor(private table: string) {}
  select(s = "*") { this.sel = s; return this; }
  private add(col: string, op: string, val: unknown) { this.fs.push({ col, op, val, pred: opPred(col, op, val) }); return this; }
  eq(c: string, v: unknown) { return this.add(c, "eq", v); }
  neq(c: string, v: unknown) { return this.add(c, "neq", v); }
  gt(c: string, v: unknown) { return this.add(c, "gt", v); }
  gte(c: string, v: unknown) { return this.add(c, "gte", v); }
  lt(c: string, v: unknown) { return this.add(c, "lt", v); }
  lte(c: string, v: unknown) { return this.add(c, "lte", v); }
  in(c: string, v: readonly unknown[]) { return this.add(c, "in", [...v]); }
  is(c: string, v: unknown) { return this.add(c, "is", v); }
  like(c: string, v: string) { return this.add(c, "like", v); }
  ilike(c: string, v: string) { return this.add(c, "ilike", v); }
  contains(c: string, v: unknown) { return this.add(c, "contains", v); }
  or(s: string) { const t: Term = { kind: "or", items: splitTop(s).map(parseTerm) }; this.ors.push(t); return this; }
  not(c: string, op: string, v: unknown) { const p = opPred(c, op, v); this.nots.push((r) => !p(r)); return this; }
  order(col: string, o?: { ascending?: boolean }) { this.ord.push({ col, asc: o?.ascending !== false }); return this; }
  limit(n: number) { this.lim = n; return this; }
  range(a: number, b: number) { this.rng = [a, b]; return this; }
  async run(): Promise<Res> {
    try {
      let out = await source(this.table, this.fs, this.ors, this.sel);
      const ps = [...this.fs.map((f) => f.pred), ...this.ors.map(termPred), ...this.nots];
      out = out.filter((r) => ps.every((p) => p(r)));
      if (this.ord.length) {
        out.sort((a, b) => {
          for (const o of this.ord) {
            const x = get(a, o.col), y = get(b, o.col);
            if (x == null && y == null) continue;
            if (x == null) return o.asc ? 1 : -1; // asc → null sonda, desc → null başta (PostgREST)
            if (y == null) return o.asc ? -1 : 1;
            const c = cmp(x, y);
            if (c) return o.asc ? c : -c;
          }
          return 0;
        });
      }
      if (this.rng) out = out.slice(this.rng[0], this.rng[1] + 1);
      if (this.lim != null) out = out.slice(0, this.lim);
      return { data: out.map((r) => project(r, this.sel)), error: null };
    } catch (e) {
      return { data: null, error: { message: String(e) } };
    }
  }
  then<A = Res, B = never>(ok?: ((v: Res) => A | PromiseLike<A>) | null, bad?: ((e: unknown) => B | PromiseLike<B>) | null) {
    return this.run().then(ok, bad);
  }
}

export const statikdb = { from: (t: string) => new Query(t) };
export type StatikDb = typeof statikdb;
