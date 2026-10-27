import type { PredStatus, Tag } from "./types";

export interface LeagueInfo { name: string; country: string; flag: string; order: number }

// Boru hattının kapsadığı ligler. Filtre listeleri veriden türetilir; bilinmeyen kod, kodun kendisiyle gösterilir.
export const LEAGUES: Record<string, LeagueInfo> = {
  T1: { name: "Süper Lig", country: "Türkiye", flag: "🇹🇷", order: 6 },
  T2: { name: "TFF 1. Lig", country: "Türkiye", flag: "🇹🇷", order: 40 },
  E0: { name: "Premier Lig", country: "İngiltere", flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", order: 1 },
  E1: { name: "Championship", country: "İngiltere", flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", order: 30 },
  E2: { name: "League One", country: "İngiltere", flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", order: 41 },
  E3: { name: "League Two", country: "İngiltere", flag: "🏴󠁧󠁢󠁥󠁮󠁧󠁿", order: 42 },
  SP1: { name: "La Liga", country: "İspanya", flag: "🇪🇸", order: 2 },
  SP2: { name: "La Liga 2", country: "İspanya", flag: "🇪🇸", order: 31 },
  I1: { name: "Serie A", country: "İtalya", flag: "🇮🇹", order: 3 },
  I2: { name: "Serie B", country: "İtalya", flag: "🇮🇹", order: 32 },
  D1: { name: "Bundesliga", country: "Almanya", flag: "🇩🇪", order: 4 },
  D2: { name: "2. Bundesliga", country: "Almanya", flag: "🇩🇪", order: 33 },
  F1: { name: "Ligue 1", country: "Fransa", flag: "🇫🇷", order: 5 },
  F2: { name: "Ligue 2", country: "Fransa", flag: "🇫🇷", order: 34 },
  N1: { name: "Eredivisie", country: "Hollanda", flag: "🇳🇱", order: 10 },
  P1: { name: "Liga Portugal", country: "Portekiz", flag: "🇵🇹", order: 11 },
  B1: { name: "Pro Lig", country: "Belçika", flag: "🇧🇪", order: 12 },
  SC0: { name: "Premiership", country: "İskoçya", flag: "🏴󠁧󠁢󠁳󠁣󠁴󠁿", order: 13 },
  SC1: { name: "Championship", country: "İskoçya", flag: "🏴󠁧󠁢󠁳󠁣󠁴󠁿", order: 43 },
  G1: { name: "Super League", country: "Yunanistan", flag: "🇬🇷", order: 14 },
  CL: { name: "Şampiyonlar Ligi", country: "UEFA", flag: "🇪🇺", order: 0.5 },
  EL: { name: "Avrupa Ligi", country: "UEFA", flag: "🇪🇺", order: 0.6 },
  ECL: { name: "Konferans Ligi", country: "UEFA", flag: "🇪🇺", order: 0.7 },
};

/** Veritabanındaki lig adlarını (leagues tablosu) bilinmeyen kodlar için kaydeder. */
// Sıra: UEFA kupaları → beş büyük lig → Süper Lig → büyük ulusal kupalar → diğer üst ligler → alt ligler → geri kalan.
const BIG_CUPS = /carabao|efl cup|fa cup|dfb|coppa italia|copa del rey|coupe de france|türkiye kupas|ziraat|taça de portugal|knvb/i;
const TOP_FLIGHTS = /brasileirão serie a|liga profesional|mls|eredivisie|saudi pro|liga mx|super league|superliga|allsvenskan|eliteserien|ekstraklasa|bundesliga|czech first|j1 league|k league 1|a-league|copa libertadores/i;

export function registerLeagues(rows: { code: string; name: string | null; country: string | null; cup: boolean | null }[]) {
  rows.forEach((r, i) => {
    if (!r.code || !r.name || LEAGUES[r.code]) return;
    const order = BIG_CUPS.test(r.name) ? 20 : TOP_FLIGHTS.test(r.name) ? 25 : r.cup ? 60 + i / 1000 : 50 + i / 1000;
    LEAGUES[r.code] = { name: r.name, country: r.country ?? "", flag: r.cup ? "🏆" : "⚽", order };
  });
}

export function league(code: string | null | undefined): LeagueInfo {
  if (!code) return { name: "—", country: "", flag: "⚽", order: 99 };
  return LEAGUES[code] ?? { name: code, country: "", flag: "⚽", order: 90 };
}

export const TAG_LABELS: Record<Tag, string> = {
  gunun_karari: "Günün Kararı",
  meclis_gorusu: "Meclis Görüşü",
  karar_birligi: "Karar Birliği",
};
export const TAG_HINT: Record<Tag, string> = {
  gunun_karari: "Meclis'in ana tercihlerinden oluşan günün kuponu",
  meclis_gorusu: "Maç başına tek seçim (tekli)",
  karar_birligi: "Model ile piyasanın birlikte en güçlü gördüğü, başka üründe olmayan 2–3 maç",
};

export const STATUS_LABELS: Record<PredStatus, string> = {
  bekliyor: "Bekliyor",
  basladi: "Başladı",
  kazandi: "Kazandı",
  kaybetti: "Kaybetti",
  iade: "İade",
};

export const MARKET_LABELS: Record<string, string> = {
  "1X2": "Maç Sonucu", DC: "Çifte Şans", AH: "Asya Handikap", OU_GOALS: "Toplam Gol", BTTS: "Karşılıklı Gol",
  TEAM_GOALS_HOME: "Ev Sahibi Gol", TEAM_GOALS_AWAY: "Deplasman Gol", CS: "Skor",
  HT_OU_GOALS: "İlk Yarı Gol", CORNERS_OU: "Toplam Korner", CARDS_OU: "Toplam Kart",
  SOT_OU: "Toplam İsabetli Şut", GOAL_KICKS_OU: "Toplam Kale Vuruşu",
};
export const MARKET_GROUPS: Record<string, string[]> = {
  "Skor / Sonuç": ["1X2", "DC", "AH", "CS"],
  Gol: ["OU_GOALS", "BTTS", "TEAM_GOALS_HOME", "TEAM_GOALS_AWAY", "HT_OU_GOALS"],
  Korner: ["CORNERS_OU"],
  Kart: ["CARDS_OU"],
  "İsabetli Şut": ["SOT_OU"],
  "Kale Vuruşu": ["GOAL_KICKS_OU"],
};

function titleTr(s: string) {
  return s.charAt(0).toLocaleUpperCase("tr-TR") + s.slice(1).toLocaleLowerCase("tr-TR");
}

export function pickLabel(market: string, selection: string, line: number | null | undefined, home = "Ev", away = "Dep"): string {
  const lab = MARKET_LABELS[market] ?? market;
  if (market === "1X2") return ({ "1": `MS 1 · ${home}`, X: "MS X · Beraberlik", "2": `MS 2 · ${away}` } as Record<string, string>)[selection] ?? selection;
  if (market === "DC") return `Çifte Şans ${selection}`;
  if (market === "AH" && line != null) return `AH ${selection === "1" ? home : away} ${line > 0 ? "+" : ""}${fmtLine(line)}`;
  if (market === "BTTS") return `KG ${titleTr(selection)}`;
  if (market === "CS") return `Skor ${selection}`;
  if (line !== null && line !== undefined) return `${lab} ${fmtLine(line)} ${titleTr(selection)}`;
  return `${lab} ${selection}`;
}

export function fmtLine(n: number) {
  return Number(n).toLocaleString("tr-TR", { maximumFractionDigits: 2 });
}

export const DURUM_LABELS: Record<string, string> = {
  gelecek: "Oynanacak", "canlı": "Canlı", bitti: "Bitti", ertelendi: "Ertelendi", iptal: "İptal",
};

export function sourceLabel(src: string | null | undefined): string {
  if (!src) return "";
  const s = src.toLowerCase();
  if (s.includes("konsens")) return "Piyasa konsensüsü";
  if (s.includes("football-data.co.uk")) return "Piyasa ortalaması";
  if (s.includes("pinnacle")) return "Pinnacle";
  if (s === "model_adil") return "Model adil oranı";
  return src.split(":")[0];
}
