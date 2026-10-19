// Bahse yönlendiren çağrılar ("Bunu oyna", "1 birim yatır", "pas geç" vb.) sitede gösterilmez
const PUSH = /(?<!\p{L})(?:oyna(?:yın|yin|yabilirsin|yabilirsiniz|nır|nmalı|maya değer)?|pas geç\p{L}*|kaçırmayın|\d+(?:[.,]\d+)?\s*birim(?:le)?\s+(?:yatır|oyna|bas|koy|gir)\p{L}*|birim (?:yatır|oyna|bas|koy)\p{L}*|stake)(?!\p{L})/iu;

/** Bir satırdan bahis çağrısı içeren cümleleri çıkarır. */
export function stripPush(line: string): string {
  if (!PUSH.test(line)) return line;
  const lead = line.match(/^\s*[-•]\s*/)?.[0] ?? "";
  const kept = line.slice(lead.length).split(/(?<=[.!?…])\s+|\s+[—–-]\s+/).filter((x) => x && !PUSH.test(x));
  return kept.length ? lead + kept.join(" ") : "";
}
