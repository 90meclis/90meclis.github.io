import { Link } from "react-router-dom";
import { usePageMeta, ROUTES } from "../lib/seo";
import { Card, Disclaimer, PageHead, TagPill, StatusPill } from "../components/ui";

export default function About() {
  const meta = ROUTES[7];
  usePageMeta(meta.title, meta.description);
  return (
    <>
      <PageHead kicker="Şeffaflık" title="Yöntem ve Sorumlu Oyun">
        90 Meclis bir bahis sitesi değildir; bahis almaz, yönlendirmez. Maçları veriyle tartışan ve kayıtlarını herkesin önünde tutan bir analiz masasıdır.
      </PageHead>
      <div className="grid-2">
        <Card title="Etiketler">
          <ul className="def">
            <li><TagPill tag="gunun_karari" /><span>Meclis'in ana tercihlerinden oluşan günün kuponu.</span></li>
            <li><TagPill tag="meclis_gorusu" /><span>Meclis'in bir maç için verdiği tekli karar.</span></li>
            <li><TagPill tag="karar_birligi" /><span>Günün en güvenilen tekli kararlarından kurulan kombinasyon.</span></li>
          </ul>
        </Card>
        <Card title="Durumlar">
          <ul className="def">
            <li><StatusPill status="bekliyor" /><span>Karar kilitlendi, maç başlamadı.</span></li>
            <li><StatusPill status="basladi" /><span>Maç oynanıyor.</span></li>
            <li><StatusPill status="kazandi" /><span>Seçim tuttu.</span></li>
            <li><StatusPill status="kaybetti" /><span>Seçim tutmadı. Kayıp silinmez, Güven Panosu'nda görünür.</span></li>
            <li><StatusPill status="iade" /><span>Maç ertelendi/iptal oldu ya da çizgi tam tuttu.</span></li>
                      </ul>
        </Card>
      </div>
      <Card title="Veri ve model">
        <ul className="steps">
          <li><b>Çok kaynaklı havuz.</b> Fikstür, sonuç, istatistik, oran, kadro, sakatlık ve hava durumu birden çok açık kaynaktan birleştirilir; bir kaynakta eksik olan alan diğerinden tamamlanır. Her alanın hangi kaynaktan geldiği saklanır.</li>
          <li><b>Modeller.</b> Gol için Dixon-Coles düzeltmeli Poisson ve Meclis Elo; korner, kart ve şut için negatif binom/Poisson. Eksik oyuncular dakika payı ve gol katkısına göre ağırlıklandırılır.</li>
          <li><b>Her maç analiz edilir.</b> Bültendeki bütün maçlar taranır; Meclis kararlarını maç başlamadan verir. Güven göstergesi kararın ne kadar sağlam olduğunu söyler. Uydurma veri asla konmaz.</li>
          <li><b>Kilitli defter.</b> Kayıtlar maç başlamadan yazılır; veritabanı kuralları gereği sonradan değiştirilemez ve silinemez.</li>
        </ul>
      </Card>
      <Card title="Sorumlu oyun" className="responsible">
        <p><b>18 yaşından küçüklerin bahis oynaması yasaktır.</b> Burada yayımlanan her şey olasılık hesabıdır; hiçbir tahmin kesin değildir ve kazanç garantisi verilmez. Geçmiş performans geleceği göstermez.</p>
        <p>Kaybetmeyi göze alamayacağın parayla oynama. Kayıpları kovalama. Oyun alışkanlığın kontrolden çıkıyorsa profesyonel destek al; Türkiye'de Yeşilay Danışmanlık Merkezi'ne (YEDAM) <b>115</b> numaralı hattan ulaşabilirsin.</p>
        <p className="muted small">Yalnızca yasal ve lisanslı kanalları kullan.</p>
      </Card>
      <p><Link to="/guven-panosu" className="btn ghost">Performans kaydını gör →</Link></p>
      <Disclaimer />
    </>
  );
}
