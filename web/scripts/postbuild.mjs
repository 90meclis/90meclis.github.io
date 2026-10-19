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
