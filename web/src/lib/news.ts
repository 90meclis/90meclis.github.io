import type { Agenda } from "./types";

const STOP = new Set("ve ile bir bu da de mi mı için gibi daha çok en son yeni oldu olan sonra önce the a of to in".split(" "));
const tokens = (t: string) =>
  new Set(
    t.toLocaleLowerCase("tr-TR").replace(/\s[-|–]\s[^-|–]+$/u, "") // "… - Fotomaç" gibi kaynak eki
      .replace(/[^\p{L}\p{N}\s]/gu, " ").split(/\s+/).filter((w) => w.length > 1 && !STOP.has(w)),
  );

function same(a: Set<string>, b: Set<string>) {
  if (!a.size || !b.size) return false;
  let i = 0;
  for (const w of a) if (b.has(w)) i++;
  return i / (a.size + b.size - i) >= 0.6;
}

export type NewsItem = Agenda & { alsoIn: string[] };

/** Aynı haberi veren farklı siteleri tek kayıtta toplar (sunucu tarafı tekilleştirme tamamlanana kadar). Liste yeni→eski sıralı gelir. */
export function dedupNews(items: Agenda[]): NewsItem[] {
  const out: (NewsItem & { _t: Set<string> })[] = [];
  for (const it of items) {
    const t = tokens(it.title);
    const hit = out.find((o) => o.link === it.link || same(o._t, t));
    if (hit) {
      if (it.source && it.source !== hit.source && !hit.alsoIn.includes(it.source)) hit.alsoIn.push(it.source);
      for (const id of it.match_ids ?? []) if (!hit.match_ids.includes(id)) hit.match_ids = [...hit.match_ids, id];
      continue;
    }
    out.push({ ...it, match_ids: it.match_ids ?? [], alsoIn: [], _t: t });
  }
  return out.map(({ _t, ...x }) => { void _t; return x; });
}
