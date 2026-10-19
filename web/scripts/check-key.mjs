// Derleme öncesi güvenlik kapısı: sitede YALNIZCA publishable/anon anahtar kullanılabilir.
// service_role / secret anahtar verilirse derleme durur. Anahtar yoksa site veri göstermeden derlenir.
const key = process.env.VITE_SUPABASE_PUBLISHABLE_KEY || "";
if (!key) {
  console.warn("[90 Meclis] VITE_SUPABASE_PUBLISHABLE_KEY tanımlı değil: site veri olmadan derlenecek.");
  process.exit(0);
}
if (key.startsWith("sb_secret_")) {
  console.error("[90 Meclis] HATA: secret anahtar verildi. Sitede yalnızca sb_publishable_ / anon anahtar kullanılır.");
  process.exit(1);
}
if (key.split(".").length === 3) {
  try {
    const payload = JSON.parse(Buffer.from(key.split(".")[1], "base64url").toString("utf8"));
    if (payload.role !== "anon") {
      console.error(`[90 Meclis] HATA: JWT rolü "${payload.role}". Yalnızca anon anahtar kabul edilir.`);
      process.exit(1);
    }
  } catch {
    console.error("[90 Meclis] HATA: anahtar çözümlenemedi.");
    process.exit(1);
  }
} else if (!key.startsWith("sb_publishable_")) {
  console.error("[90 Meclis] HATA: tanınmayan anahtar biçimi. sb_publishable_… ya da anon JWT bekleniyor.");
  process.exit(1);
}
console.log("[90 Meclis] Publishable anahtar doğrulandı (salt okunur).");
