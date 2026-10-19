// Anlatım metni süzgeçleri.
// Yayımlanmış kararı olan maçta Meclis kararını net sesle söyler ("bunu oyna" hissi, kullanıcının v1 isteği).
// Yayımlanmamış maçta ise metin, olmayan bir kararı ima eden çağrılar içermemeli.

const CALL = /(?<!\p{L})(?:oyna(?:yın|yin|yabilirsin|yabilirsiniz|nır|nmalı|maya değer)?|kaçırmayın)(?!\p{L})/iu;
// Kullanıcı: "veri yeterli değilse diye bir bahane üretmeyeceğiz". Eksik-veri gerekçeleri ziyaretçiye gösterilmez.
const EXCUSE = /(ertelenen pazarlar|verisi yok|veri yetersiz|kurulamadı|hesaplanmadı)/iu;
const PASS = /kararı:\s*\**\s*pas/iu;

function dropSentences(line: string, re: RegExp): string {
  if (!re.test(line)) return line;
  const lead = line.match(/^\s*[-•]\s*/)?.[0] ?? "";
  const kept = line.slice(lead.length).split(/(?<=[.!?…;])\s+/).filter((x) => x && !re.test(x));
  return kept.length ? lead + kept.join(" ") : "";
}

/** published: bu maç için yayımlanmış bir Meclis kararı var mı. */
export function cleanLine(line: string, published: boolean): string {
  let out = dropSentences(line, EXCUSE).replace(/[;,·]?\s*(?:veri\s+)?tamlı(?:k|ğı)\s*:?\s*\d+(?:[.,]\d+)?\s*\/\s*100/giu, "");
  if (!published) out = dropSentences(out, CALL);
  else if (PASS.test(out)) out = ""; // yayımlanmış karar varken eski "pas" notu çelişki yaratır
  return out.replace(/^\s*(form|eksik etkisi|hava):\s*$/iu, "");
}
