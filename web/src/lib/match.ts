import type { Match } from "./types";
import { DURUM_LABELS } from "./labels";

export const matchPath = (id: string) => `/mac/${encodeURIComponent(id)}`;

export function hasScore(m: Pick<Match, "home_goals" | "away_goals">) {
  return m.home_goals !== null && m.home_goals !== undefined && m.away_goals !== null && m.away_goals !== undefined;
}

/** Görünen durum: başlama saati geçmiş ama sonucu gelmemiş maç "gelecek" görünmez. */
export function matchState(m: Match): { key: string; label: string } {
  const started = Date.now() >= new Date(m.kickoff_at).getTime();
  if (m.durum === "ertelendi" || m.durum === "iptal") return { key: m.durum, label: DURUM_LABELS[m.durum] };
  if (m.durum === "bitti" || (hasScore(m) && m.status === "bitti")) return { key: "bitti", label: "MS" };
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
  const home = m.home_team_id === teamId;
  const gf = home ? m.home_goals! : m.away_goals!;
  const ga = home ? m.away_goals! : m.home_goals!;
  return gf > ga ? "G" : gf === ga ? "B" : "M";
}
