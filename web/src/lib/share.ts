// Paylaşılabilir karar/kupon kartı (1080×1350 PNG, tarayıcıda canvas). Kazanan da kaybeden de aynı şablonla.
import type { Coupon, Prediction } from "./types";
import { pickLabel, league, TAG_LABELS } from "./labels";
import { dateTime, num, pct } from "./format";

const W = 1080, H = 1350;
const STAMP: Record<string, [string, string]> = { kazandi: ["KAZANDI", "#5fe39a"], kaybetti: ["KAYBETTİ", "#ff6b6b"], iade: ["İADE", "#9aa8b8"] };

function wrap(ctx: CanvasRenderingContext2D, text: string, max: number): string[] {
  const out: string[] = []; let line = "";
  for (const w of text.split(" ")) { const t = line ? `${line} ${w}` : w; if (ctx.measureText(t).width > max && line) { out.push(line); line = w; } else line = t; }
  if (line) out.push(line);
  return out;
}

export async function renderCard(opts: { kind: string; legs: Prediction[]; total?: number | null; status: string; lockedAt: string; seal?: string | null; prob?: number | null }): Promise<Blob> {
  await document.fonts?.ready;
  const c = document.createElement("canvas"); c.width = W; c.height = H;
  const x = c.getContext("2d")!;
  const bg = x.createLinearGradient(0, 0, W, H); bg.addColorStop(0, "#0d1520"); bg.addColorStop(1, "#05080c");
  x.fillStyle = bg; x.fillRect(0, 0, W, H);
  const glow = x.createRadialGradient(W * 0.15, 80, 10, W * 0.15, 80, 700); glow.addColorStop(0, "rgba(215,255,63,.20)"); glow.addColorStop(1, "rgba(215,255,63,0)");
  x.fillStyle = glow; x.fillRect(0, 0, W, H);
  const D = "'Barlow Condensed', 'Arial Narrow', sans-serif", T = "'Inter Variable', Inter, system-ui, sans-serif";
  // marka
  x.fillStyle = "#d7ff3f"; x.beginPath(); x.roundRect(72, 72, 84, 84, 20); x.fill();
  x.fillStyle = "#0a0e14"; x.font = `800 46px ${D}`; x.textAlign = "center"; x.fillText("90", 114, 130);
  x.textAlign = "left"; x.fillStyle = "#fff"; x.font = `800 52px ${D}`; x.fillText("90 MECLİS", 180, 132);
  x.fillStyle = "#d7ff3f"; x.font = `800 30px ${T}`; x.fillText(opts.kind.toLocaleUpperCase("tr-TR"), 72, 250);
  x.fillStyle = "#fff"; x.font = `800 96px ${D}`;
  const head = opts.legs.length > 1 ? `${opts.legs.length} MAÇ` : "MECLİS'İN KARARI";
  x.fillText(head, 72, 345);
  // ayaklar
  let y = 420;
  for (const p of opts.legs.slice(0, 5)) {
    x.fillStyle = "rgba(255,255,255,.06)"; x.beginPath(); x.roundRect(72, y, W - 144, 150, 22); x.fill();
    x.fillStyle = "#8a98aa"; x.font = `600 26px ${T}`; x.fillText(`${league(p.league).name} · ${dateTime(p.kickoff_at)}`, 104, y + 46);
    x.fillStyle = "#fff"; x.font = `700 34px ${T}`; x.fillText(`${p.home_name} – ${p.away_name}`.slice(0, 44), 104, y + 92);
    x.fillStyle = "#d7ff3f"; x.font = `700 30px ${T}`; x.fillText(pickLabel(p.market, p.selection, p.line, p.home_name ?? "Ev", p.away_name ?? "Dep").slice(0, 40), 104, y + 132);
    x.textAlign = "right"; x.fillStyle = "#fff"; x.font = `800 60px ${D}`; x.fillText(num(p.odds ?? p.fair_odds), W - 104, y + 100); x.textAlign = "left";
    const st = STAMP[p.status]; if (st && opts.legs.length > 1) { x.fillStyle = st[1]; x.font = `800 22px ${T}`; x.textAlign = "right"; x.fillText(st[0], W - 104, y + 136); x.textAlign = "left"; }
    y += 168;
  }
  if (opts.legs.length > 5) { x.fillStyle = "#8a98aa"; x.font = `600 26px ${T}`; x.fillText(`+${opts.legs.length - 5} maç daha`, 72, y + 10); y += 40; }
  // toplam
  y = Math.max(y + 20, 1000);
  x.fillStyle = "#8a98aa"; x.font = `600 26px ${T}`;
  x.fillText(opts.legs.length > 1 ? "Toplam oran" : "Oran", 72, y); if (opts.prob != null) x.fillText("Olasılık", 420, y);
  x.fillStyle = "#fff"; x.font = `800 84px ${D}`; x.fillText(num(opts.total ?? opts.legs[0]?.odds ?? opts.legs[0]?.fair_odds), 72, y + 82);
  if (opts.prob != null) x.fillText(pct(opts.prob), 420, y + 82);
  // sonuç damgası
  const st = STAMP[opts.status];
  if (st) {
    x.save(); x.translate(W - 250, y + 30); x.rotate(-0.18);
    x.strokeStyle = st[1]; x.lineWidth = 8; x.beginPath(); x.roundRect(-170, -60, 340, 120, 20); x.stroke();
    x.fillStyle = st[1]; x.font = `800 72px ${D}`; x.textAlign = "center"; x.fillText(st[0], 0, 24); x.restore();
  }
  // kilit, mühür, 18+
  x.fillStyle = "rgba(255,255,255,.12)"; x.fillRect(72, H - 170, W - 144, 2);
  x.fillStyle = "#c6d0dc"; x.font = `600 25px ${T}`;
  x.fillText(`🔒 Kilit: ${dateTime(opts.lockedAt)} TSİ${opts.seal ? ` · Mühür ${opts.seal.slice(0, 10)}…` : ""}`, 72, H - 120);
  x.fillStyle = "#8a98aa"; x.font = `500 22px ${T}`;
  for (const [i, l] of wrap(x, "18+ · Tahminler olasılık hesabıdır, garanti değildir. Kaybetmeyi göze alamayacağın parayla oynama. Yardım: YEDAM 115 · 90meclis.github.io", W - 144).entries()) x.fillText(l, 72, H - 82 + i * 30);
  return await new Promise<Blob>((res) => c.toBlob((b) => res(b!), "image/png"));
}

export async function shareBlob(blob: Blob, name: string, text: string) {
  const file = new File([blob], name, { type: "image/png" });
  const nav = navigator as Navigator & { canShare?: (d: unknown) => boolean };
  if (nav.canShare?.({ files: [file] })) {
    try { await navigator.share({ files: [file], text }); return; } catch { /* kullanıcı vazgeçti → indir */ }
  }
  const u = URL.createObjectURL(blob); const a = document.createElement("a"); a.href = u; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(u), 2000);
}

export const cardForPick = (p: Prediction) => renderCard({ kind: TAG_LABELS[p.tag] ?? "Meclis Görüşü", legs: [p], status: p.status, lockedAt: p.recorded_at, prob: p.probability, seal: (p as Prediction & { seal?: string | null }).seal ?? null });
export const cardForCoupon = (c: Coupon, legs: Prediction[]) => renderCard({ kind: TAG_LABELS[c.tag] ?? "Günün Kararı", legs, total: c.total_odds, status: c.status, lockedAt: c.created_at, prob: c.joint_probability, seal: (c as Coupon & { seal?: string | null }).seal ?? null });
