# 90 Meclis — web sitesi

Herkese açık, statik site (Vite + React + TypeScript). Veriler tarayıcıda, Supabase'den **publishable (anon)**
anahtarla okunur; RLS nedeniyle salt okunurdur. Yayın: GitHub Pages → https://90meclis.github.io/

## Bölümler
Maç Merkezi · Tahmin Botu · Tahmin Arşivi · Güven Panosu · Gündem Masası · Veri Laboratuvarı (+ Yöntem ve Sorumlu Oyun)

## Anahtar
- GitHub → Settings → Secrets and variables → Actions → `SUPABASE_PUBLISHABLE_KEY` (`sb_publishable_…` ya da anon JWT).
- Derleme anında `VITE_SUPABASE_PUBLISHABLE_KEY` olarak verilir. `scripts/check-key.mjs` secret/service_role anahtarı reddeder.
- Anahtar koda ya da depoya **asla** yazılmaz.

## Yerel çalıştırma
```bash
cd web
npm ci
VITE_SUPABASE_PUBLISHABLE_KEY=sb_publishable_... npm run dev
npm run lint && npm run build
```

## Yayın
`.github/workflows/pages.yml`: `main`'e `web/**` değişikliği gelince derler ve Pages'e yayımlar. Elle: Actions → "90 Meclis web sitesi" → Run workflow.
Bölüm sayfaları statik kopyalarla (her biri kendi başlığı/açıklamasıyla) üretilir; maç sayfası `/mac/?id=…`; bilinmeyen yollar `404.html` ile uygulamaya döner.
