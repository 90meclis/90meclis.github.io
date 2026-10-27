import { supabase } from "./supabase";

/** Editoryal katman: arka uç 'analyses' tablosuna anahtarlı satırlar yazar (meclis:bulten:GÜN, meclis:not:GÜN, meclis:motor). */
export type Kart = { maddeler: string[]; risk: string | null; bant: { bant: string; isabet: number | null; n: number; metin: string } | null; etiket: string };
export type Bulten = { tarih: string; metin: string; maddeler: { baslik: string; metin: string }[]; kartlar: Record<string, Kart>; uretildi: string; kaynak?: string };
export type Notlar = { tarih: string; notlar: Record<string, string> };
export type Agg = { n: number; isabet?: number; ort_olasilik?: number; ort_oran?: number; roi?: number };
export type Motor = {
  geritest: { toplam: Agg; bantlar: (Agg & { bant: string; alt: number; ust: number })[]; pazarlar: (Agg & { pazar: string })[]; mac: number };
  derin_pazarlar: string[];
  params: Record<string, { w?: number; n?: number; iso?: unknown }>;
  uretildi?: string;
  elo_w?: number;
  topluluk?: { w: number; durum: string; n_dogrula?: number };
  params_lig?: Record<string, Record<string, unknown>>;
  guncellendi?: string;
};

async function payload<T>(key: string): Promise<T | null> {
  if (!supabase) return null;
  const { data, error } = await supabase.from("analyses").select("payload").eq("match_id", key)
    .order("created_at", { ascending: false }).limit(1);
  if (error || !data?.length) return null;
  return (data[0] as { payload: T }).payload;
}

export const bulten = (day: string) => payload<Bulten>(`meclis:bulten:${day}`);
export const notlar = (day: string) => payload<Notlar>(`meclis:not:${day}`);
export const motor = () => payload<Motor>("meclis:motor");

/** Birden çok günün kartları + notları tek sözlükte (anahtar: tahmin/kupon id). */
export async function editorialFor(days: string[]): Promise<{ kart: Record<string, Kart>; not: Record<string, string> }> {
  const uniq = [...new Set(days)].slice(0, 14);
  const res = await Promise.all(uniq.map(async (d) => [await bulten(d), await notlar(d)] as const));
  const kart: Record<string, Kart> = {}, not: Record<string, string> = {};
  for (const [b, n] of res) {
    Object.assign(kart, b?.kartlar ?? {});
    Object.assign(not, n?.notlar ?? {});
  }
  return { kart, not };
}

export const GROUP_TR: Record<string, string> = {
  "1X2": "Maç sonucu", DC: "Çifte şans", BTTS: "Karşılıklı gol",
  "OU_GOALS_1.5": "1.5 gol", "OU_GOALS_2.5": "2.5 gol", "OU_GOALS_3.5": "3.5 gol",
};
export const groupOf = (market: string, line: number | null | undefined) =>
  market === "OU_GOALS" && line != null ? `OU_GOALS_${Number(line)}` : market;
