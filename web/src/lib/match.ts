import type { Canli, Match } from "./types";
import { DURUM_LABELS } from "./labels";

/** Maç kimliği "LG:YYYY-AA-GG:ev:dep" → arama motoru dostu yol "/mac/lg-ev-dep-YYYY-AA-GG/" (slug'lar yalnızca a-z0-9). */
export function matchSlug(id: string): string | null {
  const p = id.split(":");
  if (p.length !== 4 || !/^[A-Za-z0-9]+$/.test(p[0]) || !/^\d{4}-\d{2}-\d{2}$/.test(p[1]) || !/^[a-z0-9]+$/.test(p[2]) || !/^[a-z0-9]+$/.test(p[3])) return null;
  return `${p[0].toLowerCase()}-${p[2]}-${p[3]}-${p[1]}`;
}
export function idFromSlug(s: string): string | null {
  const m = s.match(/^([a-z0-9]+)-([a-z0-9]+)-([a-z0-9]+)-(\d{4}-\d{2}-\d{2})$/);
  return m ? `${m[1].toUpperCase()}:${m[4]}:${m[2]}:${m[3]}` : null;
}
export const matchPath = (id: string, bolum?: string) => {
  const s = matchSlug(id);
  return s ? `/mac/${s}/${bolum ? `?bolum=${bolum}` : ""}` : `/mac/?id=${encodeURIComponent(id)}${bolum ? `&bolum=${bolum}` : ""}`;
};

export function hasScore(m: Pick<Match, "home_goals" | "away_goals"> & { status?: string | null }) {
  if (m.status === "planlandi" || m.status === "ertelendi" || m.status === "iptal") return false;
  return m.home_goals !== null && m.home_goals !== undefined && m.away_goals !== null && m.away_goals !== undefined;
}

/** Görünen durum: başlama saati geçmiş ama sonucu gelmemiş maç "gelecek" görünmez. */
/** Canlı skor: son 20 dakikada güncellendiyse ve resmî sonuç henüz yoksa. */
export function liveScore(m: Match): { hg: number; ag: number; label: string; final: boolean } | null {
  const c = m.canli ?? ((m.sources as { _canli?: Canli } | null)?._canli ?? null);
  if (!c || m.status === "bitti" || m.durum === "bitti") return null;
  if (Date.now() - new Date(c.at).getTime() > 20 * 60000) return null;
  const [hg, ag] = c.skor.split("-").map(Number);
  if (!Number.isFinite(hg) || !Number.isFinite(ag)) return null;
  const label = c.bitti ? "MS*" : c.durum === "Devre arası" ? "İY" : c.dakika && c.dakika !== "0'" ? c.dakika : c.durum ?? "Canlı";
  return { hg, ag, label, final: c.bitti };
}

export function matchState(m: Match): { key: string; label: string } {
  const started = Date.now() >= new Date(m.kickoff_at).getTime();
  if (m.durum === "ertelendi" || m.durum === "iptal") return { key: m.durum, label: DURUM_LABELS[m.durum] };
  if (m.durum === "bitti" || (hasScore(m) && m.status === "bitti")) return { key: "bitti", label: "MS" };
  const lv = liveScore(m);
  if (lv) return { key: lv.final ? "sonuc" : "canli", label: lv.label };
  if (m.durum === "canlı") return { key: "canli", label: "Canlı" };
  if (started) {
    const mins = (Date.now() - new Date(m.kickoff_at).getTime()) / 60000;
    return mins < 120 ? { key: "canli", label: "Oynanıyor" } : { key: "sonuc", label: "Sonuç bekleniyor" };
  }
  return { key: "gelecek", label: "" };
}

export function odds1x2(m: Match): { "1"?: number; X?: number; "2"?: number } | null {
  const o = m.odds?.["1X2"];
  if (!o) return null;
  const n = (v: unknown) => (typeof v === "number" ? v : undefined);
  return { "1": n(o["1"]), X: n(o["X"]), "2": n(o["2"]) };
}

export function result(m: Match, teamId: string): "G" | "B" | "M" | null {
  if (!hasScore(m)) return null;
  const home = sameTeam(m.home_team_id, teamId);
  const gf = home ? m.home_goals! : m.away_goals!;
  const ga = home ? m.away_goals! : m.home_goals!;
  return gf > ga ? "G" : gf === ga ? "B" : "M";
}

const UEFA = new Set(["CL", "EL", "ECL"]);
export const teamSlug = (id: string) => id.slice(id.indexOf(":") + 1);
/** Takım kimlikleri lig önekli (T1:fenerbahce, CL:fenerbahce). Avrupa kupası maçında aynı kulübü eşleştirir. */
export function sameTeam(a: string, b: string): boolean {
  if (a === b) return true;
  const la = a.split(":")[0], lb = b.split(":")[0];
  return (UEFA.has(la) || UEFA.has(lb)) && teamSlug(a) === teamSlug(b);
}
