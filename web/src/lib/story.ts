// "Maç konuşuyor": yalnızca bu maçın gerçek sayılarından kurulan anlatı. Kalıp cümle yok; her cümle bir veriye bağlı
// ve veri yoksa cümle de yok.
import type { AnalysisPayload, Match, Prediction } from "./types";
import type { GameRow, TableRow } from "./dossier";
import type { ScanRow } from "./scan";
import { num, pct } from "./format";
import { fmtLine, pickLabel } from "./labels";

export interface StoryIn {
  m: Match; a?: AnalysisPayload; homeVen: GameRow[]; awayVen: GameRow[]; table: TableRow[] | null;
  restH: number | null; restA: number | null; implied: [number, number, number] | null;
  best: ScanRow | null; pick: Prediction | null; streakH: string[]; streakA: string[]; cup: boolean;
}

const tr = (s: string) => s.charAt(0).toLocaleUpperCase("tr-TR") + s.slice(1);
const rec = (r: GameRow[]) => {
  const w = r.filter((x) => x.res === "G").length, d = r.filter((x) => x.res === "B").length, l = r.length - w - d;
  const gf = r.reduce((s, x) => s + x.gf, 0) / (r.length || 1), ga = r.reduce((s, x) => s + x.ga, 0) / (r.length || 1);
  return { n: r.length, w, d, l, ppg: (3 * w + d) / (r.length || 1), gf, ga };
};

export function story(i: StoryIn): string[] {
  const { m, a } = i;
  const H = m.home_name, A = m.away_name;
  const out: string[] = [];

  // 1) Bağlam: puan durumu
  const th = i.table?.find((r) => r.id === m.home_team_id), ta = i.table?.find((r) => r.id === m.away_team_id);
  if (th && ta && th.p >= 3) {
    const gap = Math.abs(th.pts - ta.pts);
    const n = i.table!.length;
    let ctx = "";
    if (th.pos <= 3 && ta.pos <= 3) ctx = " Üst sıraların doğrudan düellosu.";
    else if (th.pos > n - 3 && ta.pos > n - 3) ctx = " Alt sıralarda kritik bir randevu.";
    else if (gap <= 3) ctx = ` Aralarında ${gap === 0 ? "puan farkı yok" : `${gap} puan var`}.`;
    out.push(`${H} ${th.pos}. sırada ${th.pts} puanla, ${A} ${ta.pos}. sırada ${ta.pts} puanla bu maça çıkıyor${i.cup ? " (bu sezonki grup/lig aşaması tablosu)" : ""}.${ctx}`);
  }

  // 2) Piyasa ve model
  const p1 = a?.markets?.filter((x) => x.market === "1X2");
  const mp = p1?.length === 3 ? Object.fromEntries(p1.map((x) => [x.selection, x.probability])) as Record<string, number> : null;
  const modelOwn = (a?.basis ?? "").startsWith("model");
  // model 1X2'si piyasadan 20 puandan fazla uzaksa (veri/model hatası şüphesi) modelin sayıları anlatılmaz
  const off = !!(mp && i.implied && [mp["1"] - i.implied[0], mp["X"] - i.implied[1], mp["2"] - i.implied[2]].some((d) => Math.abs(d) > 0.2));
  if (i.implied) {
    const [q1, qx, q2] = i.implied;
    const favH = q1 >= q2, fq = favH ? q1 : q2, fav = favH ? H : A;
    let s = fq - Math.min(q1, q2) < 0.08 ? `Piyasa iki tarafı neredeyse eşit görüyor (${pct(q1)} – ${pct(q2)}, beraberlik ${pct(qx)}).`
      : `Piyasa ${fav} tarafında: galibiyet ihtimali ${pct(fq)}, beraberlik ${pct(qx)}.`;
    if (mp && modelOwn && off) s += " Meclis modelinin bu maçtaki sayıları piyasadan çok uzak; veri kontrol edilene kadar modelin yorumu yok.";
    else if (mp && modelOwn) {
      const mq = favH ? mp["1"] : mp["2"];
      const diff = mq - fq;
      s += Math.abs(diff) < 0.03 ? ` Meclis modeli de aynı yerde (${pct(mq)}).` : diff > 0 ? ` Meclis modeli ${fav} için daha iddialı: ${pct(mq)}.` : ` Meclis modeli ${fav} konusunda daha temkinli: ${pct(mq)}.`;
    }
    out.push(s);
  }

  // 3) Gol beklentisi
  if (a?.lambdas && !off) {
    const s = a.lambdas.home + a.lambdas.away;
    const tempo = s >= 3.1 ? "açık ve gollü bir oyun" : s <= 2.2 ? "kapalı, az pozisyonlu bir oyun" : "dengeli bir gol temposu";
    const ts = a.top_scores?.[0];
    out.push(`Gol beklentisi ${H} ${num(a.lambdas.home)}, ${A} ${num(a.lambdas.away)}; toplam ${num(s)} ile ${tempo} işaret ediyor${ts ? `. En olası skor ${ts[0]} (${pct(ts[1])})` : ""}.`);
  }

  // 4) İç saha / deplasman formu
  const rh = rec(i.homeVen), ra = rec(i.awayVen);
  if (rh.n >= 3 && ra.n >= 3) {
    out.push(`${H} bu sezon evinde ${rh.n} maçta ${rh.w}G ${rh.d}B ${rh.l}M (maç başı ${num(rh.gf, 1)} attı, ${num(rh.ga, 1)} yedi); ${A} deplasmanda ${ra.n} maçta ${ra.w}G ${ra.d}B ${ra.l}M (${num(ra.gf, 1)} – ${num(ra.ga, 1)}).`);
    if (rh.ppg - ra.ppg >= 1) out.push(`Sahaya göre ayrışma belirgin: ${H} evinde maç başı ${num(rh.ppg, 1)} puan topluyor, ${A} dışarıda ${num(ra.ppg, 1)}.`);
    else if (ra.ppg - rh.ppg >= 1) out.push(`Rakamlar konuğu işaret ediyor: ${A} deplasmanda maç başı ${num(ra.ppg, 1)} puan alırken ${H} evinde ${num(rh.ppg, 1)} ile kalıyor.`);
  }

  // 5) Seriler
  const st = [...i.streakH.slice(0, 1).map((x) => `${H}: ${x}`), ...i.streakA.slice(0, 1).map((x) => `${A}: ${x}`)];
  if (st.length) out.push(`${tr(st.join("; "))}.`);

  // 6) Eksikler
  const ie = (a?.injury_effect ?? {}) as Record<string, unknown>;
  for (const [side, team] of [["home", H], ["away", A]] as const) {
    const tee = ie[`${side}_tee`];
    const miss = ((ie[`${side}_missing`] as { name: string; kind?: string; importance?: number }[] | undefined) ?? [])
      .slice().sort((x, y) => (y.importance ?? 0) - (x.importance ?? 0));
    if (typeof tee === "number" && tee >= 10 && miss.length) {
      const imps = miss.map((x) => x.importance ?? 0);
      const ranked = Math.max(...imps) - Math.min(...imps) >= 0.05;
      const names = miss.slice(0, ranked ? 2 : 3).map((x) => x.name);
      const list = names.length > 1 ? `${names.slice(0, -1).join(", ")} ve ${names[names.length - 1]}` : names[0];
      out.push(`${team} tarafında ${miss.length} eksik var; ${ranked ? `en ağırı ${list}` : `aralarında ${list}`}. Eksik Etkisi ${num(tee, 0)}/100 (${String(ie[`${side}_band`] ?? "").toLocaleLowerCase("tr-TR")}).`);
    }
  }

  // 7) Dinlenme
  if (i.restH != null && i.restA != null && Math.abs(i.restH - i.restA) >= 2 && Math.min(i.restH, i.restA) <= 5) {
    const [f, fd, t, td] = i.restH > i.restA ? [H, i.restH, A, i.restA] : [A, i.restA, H, i.restH];
    out.push(`${f} ${fd} günlük dinlenmeyle geliyor, ${t} ise ${td} gün önce sahadaydı.`);
  }

  // 8) Hava
  const w = a?.weather;
  if (w && ((w.precip_prob ?? 0) >= 60 || (w.wind_kmh ?? 0) >= 30)) {
    out.push(`Hava oyunu etkileyebilir: ${w.summary?.toLocaleLowerCase("tr-TR") ?? ""}, yağış ihtimali %${w.precip_prob ?? "—"}, rüzgâr ${num(w.wind_kmh, 0)} km/sa.`);
  }

  // 9) Karar / değer
  if (i.pick) out.push(`Meclis'in kararı: ${pickLabel(i.pick.market, i.pick.selection, i.pick.line, H, A)}${i.pick.odds ? ` (${num(i.pick.odds)})` : ""}.`);
  else if (i.best && i.best.edge != null && i.best.pModel != null && i.best.pMarket != null)
    out.push(`Pazarlar arasındaki en büyük fiyat farkı ${pickLabel(i.best.market, i.best.selection, i.best.line, H, A)}: Meclis ${pct(i.best.pModel)}, piyasa ${pct(i.best.pMarket)}${i.best.line != null ? "" : ""}.`);
  void fmtLine;
  return out;
}
