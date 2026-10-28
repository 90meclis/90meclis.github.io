// Derleme sonrası: her bölüm için kendi başlığı/açıklaması olan statik giriş sayfası (SEO + 200 yanıtı),
// SPA derin bağlantıları için 404.html, sitemap.xml.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const dist = join(root, "dist");
const SITE = "https://90meclis.github.io";
const routes = JSON.parse(readFileSync(join(root, "src/lib/routes.json"), "utf8"));
const html = readFileSync(join(dist, "index.html"), "utf8");
const esc = (s) => s.replace(/&/g, "&amp;").replace(/"/g, "&quot;").replace(/</g, "&lt;");

for (const r of routes) {
  if (r.path === "/") continue;
  const title = `${r.title} · 90 Meclis`;
  const url = `${SITE}${r.path}/`;
  const page = html
    .replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
    .replace(/(<meta name="description" content=")[^"]*"/, `$1${esc(r.description)}"`)
    .replace(/(<meta property="og:title" content=")[^"]*"/, `$1${esc(title)}"`)
    .replace(/(<meta property="og:description" content=")[^"]*"/, `$1${esc(r.description)}"`)
    .replace(/(<meta property="og:url" content=")[^"]*"/, `$1${url}"`)
    .replace(/(<link rel="canonical" href=")[^"]*"/, `$1${url}"`);
  mkdirSync(join(dist, r.path), { recursive: true });
  writeFileSync(join(dist, r.path, "index.html"), page);
}
// Maç sayfası: /mac/?id=… (200 yanıtı; maç başlığı istemcide yazılır)
mkdirSync(join(dist, "mac"), { recursive: true });
writeFileSync(join(dist, "mac", "index.html"), html.replace(/<link rel="canonical"[^>]*>/, ""));
writeFileSync(join(dist, "404.html"), html.replace(/<link rel="canonical"[^>]*>/, '<meta name="robots" content="noindex" />'));
const today = new Date().toISOString().slice(0, 10);
writeFileSync(
  join(dist, "sitemap.xml"),
  `<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n${routes
    .map((r) => `  <url><loc>${SITE}${r.path === "/" ? "/" : r.path + "/"}</loc><lastmod>${today}</lastmod><changefreq>daily</changefreq></url>`)
    .join("\n")}\n</urlset>\n`,
);
writeFileSync(join(dist, ".nojekyll"), "");
console.log(`[90 Meclis] ${routes.length - 1} bölüm sayfası, 404.html ve sitemap.xml yazıldı.`);

// Maç başına statik SEO sayfası: son 30 gün + önümüzdeki 7 gün. /mac/<lig>-<ev>-<dep>-<tarih>/ ; başlık, açıklama
// (Meclis gol beklentisinden Poisson 1X2), JSON-LD SportsEvent, canonical, sitemap. Anahtar yoksa atlanır.
// Veri: `veri` dalındaki statik sorgu dosyaları (veritabanına bağlanılmaz).
const VERI = (process.env.VITE_VERI_URL || "https://raw.githubusercontent.com/90meclis/90meclis.github.io/veri") + "/q";
async function jget(path) {
  const r = await fetch(`${VERI}/${path}`);
  if (!r.ok) return null;
  return r.json();
}
function pois(l, k) { let p = Math.exp(-l); for (let i = 1; i <= k; i++) p *= l / i; return p; }
function x12(lh, la) {
  let a = 0, d = 0, b = 0;
  for (let i = 0; i <= 10; i++) for (let j = 0; j <= 10; j++) { const p = pois(lh, i) * pois(la, j); if (i > j) a += p; else if (i === j) d += p; else b += p; }
  const s = a + d + b; return [a / s, d / s, b / s];
}
const slugOk = (id) => { const p = id.split(":"); return p.length === 4 && /^[A-Za-z0-9]+$/.test(p[0]) && /^\d{4}-\d{2}-\d{2}$/.test(p[1]) && /^[a-z0-9]+$/.test(p[2]) && /^[a-z0-9]+$/.test(p[3]) ? `${p[0].toLowerCase()}-${p[2]}-${p[3]}-${p[1]}` : null; };
const pc = (x) => `%${Math.round(x * 100)}`;
const trDate = (iso) => new Intl.DateTimeFormat("tr-TR", { timeZone: "Europe/Istanbul", day: "numeric", month: "long", year: "numeric" }).format(new Date(iso));
const trTime = (iso) => new Intl.DateTimeFormat("tr-TR", { timeZone: "Europe/Istanbul", hour: "2-digit", minute: "2-digit" }).format(new Date(iso));
{
  try {
    const meta = await jget("_meta.json");
    if (!meta) throw new Error("veri dalı yok");
    const days = [];
    for (let d = new Date(meta.gun_ilk + "T12:00:00Z"); d.toISOString().slice(0, 10) <= meta.gun_son; d = new Date(+d + 864e5)) days.push(d.toISOString().slice(0, 10));
    const ms = (await Promise.all(days.map((d) => jget(`matches/gun/${d}.json`)))).flat().filter(Boolean)
      .sort((a, b) => a.kickoff_at.localeCompare(b.kickoff_at));
    const lgs = (await jget("leagues.json")) ?? [];
    const lgName = Object.fromEntries(lgs.map((x) => [x.code, x.name]));
    // labels.ts içindeki Türkçe lig adları önceliklidir (T1 → Süper Lig)
    for (const [, c, n] of readFileSync(join(root, "src/lib/labels.ts"), "utf8").matchAll(/^\s*([A-Z0-9]+): \{ name: "([^"]+)"/gm)) lgName[c] = n;
    const recent = new Date(Date.now() - 2 * 864e5).toISOString();
    const an = (await Promise.all(days.map((d) => jget(`analyses/gun/${d}.json`)))).flat().filter(Boolean)
      .map((a) => ({ match_id: a.match_id, lambdas: a.payload?.lambdas, basis: a.payload?.basis }));
    const lam = new Map(); for (const a of an) if (!lam.has(a.match_id) && a.lambdas?.home && String(a.basis ?? "").startsWith("model")) lam.set(a.match_id, a.lambdas);
    const urls = [];
    for (const m of ms) {
      const slug = slugOk(m.id); if (!slug) continue;
      const lg = lgName[m.league] ?? m.league;
      const done = m.status === "bitti" && m.home_goals != null;
      const l = lam.get(m.id);
      const p = l ? x12(l.home, l.away) : null;
      const title = `${m.home_name} – ${m.away_name} ${done ? `${m.home_goals}-${m.away_goals} maç sonucu ve analizi` : "tahmini ve analizi"} (${trDate(m.kickoff_at)}) · 90 Meclis`;
      const desc = done
        ? `${lg}: ${m.home_name} ${m.home_goals}-${m.away_goals} ${m.away_name}. Maç maç istatistik, form, kadrolar ve 90 Meclis'in maç öncesi analizi.`
        : `${lg} · ${trDate(m.kickoff_at)} ${trTime(m.kickoff_at)} TSİ. ${p ? `Meclis olasılıkları: ${m.home_name} ${pc(p[0])}, beraberlik ${pc(p[1])}, ${m.away_name} ${pc(p[2])}; gol beklentisi ${l.home.toFixed(2).replace(".", ",")} – ${l.away.toFixed(2).replace(".", ",")}. ` : ""}Form, eksikler, ilk 11, oranlar ve senaryolar.`;
      const url = `${SITE}/mac/${slug}/`;
      const ld = { "@context": "https://schema.org", "@type": "SportsEvent", name: `${m.home_name} – ${m.away_name}`, sport: "Futbol", startDate: m.kickoff_at,
        eventStatus: "https://schema.org/EventScheduled", url, description: desc,
        homeTeam: { "@type": "SportsTeam", name: m.home_name }, awayTeam: { "@type": "SportsTeam", name: m.away_name },
        ...(m.venue ? { location: { "@type": "Place", name: m.venue, ...(m.city ? { address: m.city } : {}) } } : {}),
        superEvent: { "@type": "SportsEvent", name: lg } };
      const page = html
        .replace(/<title>[^<]*<\/title>/, `<title>${esc(title)}</title>`)
        .replace(/(<meta name="description" content=")[^"]*"/, `$1${esc(desc)}"`)
        .replace(/(<meta property="og:title" content=")[^"]*"/, `$1${esc(title)}"`)
        .replace(/(<meta property="og:description" content=")[^"]*"/, `$1${esc(desc)}"`)
        .replace(/(<meta property="og:url" content=")[^"]*"/, `$1${url}"`)
        .replace(/(<link rel="canonical" href=")[^"]*"/, `$1${url}"`)
        .replace("</head>", `<script type="application/ld+json">${JSON.stringify(ld).replace(/</g, "\\u003c")}</script></head>`)
        .replace(/<div id="root"><\/div>/, `<div id="root"><noscript><h1>${esc(m.home_name)} – ${esc(m.away_name)}</h1><p>${esc(desc)}</p></noscript></div>`);
      mkdirSync(join(dist, "mac", slug), { recursive: true });
      writeFileSync(join(dist, "mac", slug, "index.html"), page);
      if (m.kickoff_at >= recent || done) urls.push(`  <url><loc>${url}</loc><lastmod>${today}</lastmod><changefreq>${done ? "weekly" : "daily"}</changefreq></url>`);
    }
    const sm = readFileSync(join(dist, "sitemap.xml"), "utf8").replace("</urlset>", `${urls.join("\n")}\n</urlset>`);
    writeFileSync(join(dist, "sitemap.xml"), sm);
    console.log(`[90 Meclis] ${urls.length} maç SEO sayfası (sitemap) · ${lam.size} maçta Meclis olasılığı.`);
  } catch (e) {
    console.log(`[90 Meclis] maç SEO sayfaları atlandı: ${e.message}`);
  }
}
