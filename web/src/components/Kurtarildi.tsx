const URL = "https://github.com/90meclis/90meclis.github.io/blob/main/defter/kurtarma-2026-10-28.json";

/** 28.10.2026 veri kurtarmasıyla geri yazılan resmî kayıt etiketi (asıl kayıt 27.10 akşamı kilitlenmişti). */
export function Kurtarildi({ mv }: { mv: string | null | undefined }) {
  if (mv !== "kurtarildi") return null;
  return (
    <a className="tag-recovered" href={URL} target="_blank" rel="noreferrer"
       title="Asıl kayıt 27.10 akşamı kilitlendi ve mühürlendi; eski veritabanına erişim kesilince iş günlüklerinden ve ekran görüntülerinden geri yazıldı. Mühür içeriği doğrulanamıyor.">
      ↺ Kurtarılan resmî kayıt
    </a>
  );
}
