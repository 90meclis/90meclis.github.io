// Site hiçbir veritabanı anahtarı kullanmaz: bütün veri `veri` dalındaki statik JSON dosyalarından okunur.
// Derlemeye yanlışlıkla bir Supabase anahtarı verilirse durdurulur (gizli anahtar sızıntısına karşı kapı).
for (const k of ["VITE_SUPABASE_PUBLISHABLE_KEY", "VITE_SUPABASE_URL", "VITE_SUPABASE_KEY"]) {
  if (process.env[k]) {
    console.error(`[90 Meclis] HATA: ${k} tanımlı. Site artık veritabanına bağlanmaz; bu değişkeni kaldırın.`);
    process.exit(1);
  }
}
console.log("[90 Meclis] Statik veri modu (veri dalı); veritabanı anahtarı yok.");
