/**
 * Statik veri katmanı (Supabase egress tasarrufu). Arka uç işleri her çalışmada site verisini JSON olarak depodaki
 * `veri` dalına yazar (meclis/statik.py, meclis/canli.py). Site önce bu dosyaları okur (GitHub CDN), yalnızca dosyada
 * olmayan ya da bayat kalan veri için Supabase'e gider. Böylece ziyaretçi sayısı veritabanı egress'ini büyütmez.
 */
import type { BotAnalysis } from "./data";
import type { Canli, Coupon, Match, Prediction } from "./types";
import { addDays, trDay } from "./format";

const BASE = (import.meta.env.VITE_VERI_URL as string | undefined)
  || "https://raw.githubusercontent.com/90meclis/90meclis.github.io/veri";

type Stamped = { uretildi?: string };
export type GunDosyasi = Stamped & { gun: string; maclar: Match[]; analizler: Record<string, BotAnalysis> };
export type Defter = Stamped & { predictions: Prediction[]; coupons: Coupon[] };
export type Gunler = Stamped & { gunler: Record<string, Record<string, number>> };
export type Editoryal = Stamped & { anahtarlar: Record<string, unknown> };
export type CanliDosyasi = Stamped & { maclar: Record<string, Canli> };

const cache = new Map<string, Promise<unknown | null>>();

function load<T>(path: string, ttlMs = 0): Promise<T | null> {
  const k = ttlMs ? `${path}@${Math.floor(Date.now() / ttlMs)}` : path;
  let p = cache.get(k);
  if (!p) {
    p = fetch(`${BASE}/${path}${ttlMs ? `?t=${Math.floor(Date.now() / ttlMs)}` : ""}`)
      .then((r) => (r.ok ? r.json() : null))
      .catch(() => null);
    cache.set(k, p);
  }
  return p.then((d) => (d == null ? null : (structuredClone(d) as T)));
}

/** Dosya yeterince taze mi? (iş saatlik çalışır; birkaç saatlik gecikme kabul, sonra canlı okumaya düşülür) */
export function fresh(d: Stamped | null | undefined, maxH = 6): boolean {
  if (!d?.uretildi) return false;
  return Date.now() - new Date(d.uretildi).getTime() < maxH * 3600_000;
}

export const gunDosyasi = (day: string) => load<GunDosyasi>(`gun/${day}.json`);
export const defter = () => load<Defter>("defter.json");
export const gunler = () => load<Gunler>("gunler.json");
export const editoryal = () => load<Editoryal>("editoryal.json");
/** Canlı skor dosyası 10 dakikada bir yenilenir; tarayıcı 2 dakikalık dilimlerle yeniden ister. */
export const canliDosyasi = () => load<CanliDosyasi>("canli.json", 120_000);

/** Bugün −2 … +3 gün dosyalarındaki analizler (maç kimliğine göre). */
export async function statikAnalizler(): Promise<Record<string, BotAnalysis>> {
  const t = trDay();
  const days = [-2, -1, 0, 1, 2, 3].map((i) => addDays(t, i));
  const files = await Promise.all(days.map(gunDosyasi));
  const out: Record<string, BotAnalysis> = {};
  for (const f of files) if (f && fresh(f, 12)) Object.assign(out, f.analizler);
  return out;
}

/** Maç listesine canlı skoru bindirir (canli.json; yoksa satırdaki değer kalır). */
export async function canliBindir(rows: Match[]): Promise<Match[]> {
  const c = await canliDosyasi();
  if (!c?.maclar) return rows;
  for (const m of rows) if (c.maclar[m.id]) m.canli = c.maclar[m.id];
  return rows;
}

/** Takımların bu sezonki maç satırları (v_takim_mac_istatistik ile aynı sütunlar). Dosyası olmayan slug'lar `eksik`te. */
export async function takimSatirlari<T extends { kickoff_at: string }>(slugs: string[], sinceIso: string, beforeIso: string):
  Promise<{ rows: T[]; eksik: string[] }> {
  const files = await Promise.all(slugs.map((s) => load<Stamped & { satirlar: T[] }>(`takim/${encodeURIComponent(s)}.json`)));
  const rows: T[] = [], eksik: string[] = [];
  const lo = new Date(sinceIso).getTime(), hi = new Date(beforeIso).getTime();
  files.forEach((f, i) => {
    if (!f || !fresh(f, 12)) { eksik.push(slugs[i]); return; }
    for (const r of f.satirlar) { const t = new Date(r.kickoff_at).getTime(); if (t >= lo && t < hi) rows.push(r); }
  });
  return { rows, eksik };
}
