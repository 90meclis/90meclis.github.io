// Kanıt Mührü: kayıt → mühür dizini (tek sorgu, önbellekli) ve tarayıcıda SHA-256 zincir doğrulaması.
import { sealsLite, type SealRow } from "./data";

export interface SealLite { seq: number; sha256: string; table: string; at: string }
let idx: Map<string, SealLite> | null = null;
let pending: Promise<Map<string, SealLite>> | null = null;

export function sealIndex(): Promise<Map<string, SealLite>> {
  if (idx) return Promise.resolve(idx);
  pending ??= sealsLite().then((rows) => (idx = new Map(rows.map((r) => [r.ref_id, { seq: r.seq, sha256: r.sha256, table: r.ref_table, at: r.muhurlendi_at }]))));
  return pending;
}
/** Eşzamanlı okuma (paylaşım kartı): dizin yüklenmişse mühür, yoksa null. */
export const sealOf = (id: string) => idx?.get(id) ?? null;

async function sha256(s: string): Promise<string> {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}

export interface VerifyResult { n: number; okContent: number; okChain: number; broken: { seq: number; why: string }[]; root: string | null }
/** Her mühür: sha256(kanonik) = içerik özeti; sha256(önceki + içerik) = mühür; önceki = bir önceki satırın mührü. */
export async function verifyChain(rows: SealRow[]): Promise<VerifyResult> {
  const out: VerifyResult = { n: rows.length, okContent: 0, okChain: 0, broken: [], root: rows.length ? rows[rows.length - 1].sha256 : null };
  let prev = "0".repeat(64);
  for (const r of [...rows].sort((a, b) => a.seq - b.seq)) {
    const c = await sha256(r.kanonik);
    const h = await sha256(r.onceki_sha256 + c);
    const okC = c === r.icerik_sha256, okH = h === r.sha256 && r.onceki_sha256 === prev;
    if (okC) out.okContent++;
    if (okH) out.okChain++;
    if (!okC || !okH) out.broken.push({ seq: r.seq, why: !okC ? "içerik özeti tutmuyor" : r.onceki_sha256 !== prev ? "zincir halkası kopuk" : "mühür özeti tutmuyor" });
    prev = r.sha256;
  }
  return out;
}

/** Kanonik kaydı bugünkü kayıtla alan alan karşılaştırır (sayılarda 1e-6 tolerans). Farklı alanların listesi. */
export function diffCanonical(kanonik: string, current: Record<string, unknown>): string[] {
  let c: Record<string, unknown>;
  try { c = JSON.parse(kanonik); } catch { return ["kanonik okunamadı"]; }
  const bad: string[] = [];
  for (const [k, v] of Object.entries(c)) {
    const w = current[k];
    if (v == null && w == null) continue;
    if (typeof v === "number" || typeof w === "number") { if (Math.abs(Number(v) - Number(w)) > 1e-6) bad.push(k); continue; }
    if (k.endsWith("_at") && v && w) { if (new Date(String(v)).getTime() !== new Date(String(w)).getTime()) bad.push(k); continue; }
    if (String(v) !== String(w)) bad.push(k);
  }
  return bad;
}
