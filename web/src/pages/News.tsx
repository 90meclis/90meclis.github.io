import { useMemo, useState } from "react";
import { Link } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { dateTime, relTime } from "../lib/format";
import { matchPath } from "../lib/match";
import { usePageMeta, ROUTES } from "../lib/seo";
import { Empty, Gate, PageHead } from "../components/ui";

const CAT_ORDER = ["sakatlık", "teknik direktör", "kadro", "transfer", "genel"];
const CAT_LABEL: Record<string, string> = { "sakatlık": "Sakatlık", "teknik direktör": "Teknik direktör", kadro: "Kadro", transfer: "Transfer", genel: "Genel" };
const PAGE = 30;

function matchTitle(id: string) {
  // "T1:2026-10-19:trabzonspor:besiktas" → yalnızca bağlantı için; başlık maç sayfasında
  return id.split(":").slice(2).join(" – ");
}

export default function News() {
  const meta = ROUTES[5];
  usePageMeta(meta.title, meta.description);
  const q = useAsync("news:all", () => api.news(600));
  const [cat, setCat] = useState("");
  const [linked, setLinked] = useState(false);
  const [text, setText] = useState("");
  const [n, setN] = useState(PAGE);
  const items = q.data ?? [];
  const cats = useMemo(() => {
    const c: Record<string, number> = {};
    for (const x of items) c[x.category ?? "genel"] = (c[x.category ?? "genel"] ?? 0) + 1;
    return Object.entries(c).sort((a, b) => CAT_ORDER.indexOf(a[0]) - CAT_ORDER.indexOf(b[0]));
  }, [items]);
  const t = text.toLocaleLowerCase("tr-TR");
  const rows = items.filter((x) => (!cat || (x.category ?? "genel") === cat) && (!linked || x.match_ids?.length) &&
    (!t || `${x.title} ${x.summary ?? ""}`.toLocaleLowerCase("tr-TR").includes(t)));

  return (
    <>
      <PageHead kicker="Her sabah taranır" title="Gündem Masası">
        Transfer, sakatlık ve teknik direktör haberleri, yayıncıların açık akışlarından derlenir ve günün maçlarıyla eşleştirilir. Bağlantılar yayıncıya gider.
      </PageHead>
      <Gate loading={q.loading} error={q.error} rows={6}>
        <div className="toolbar">
          <div className="chips scroll" role="radiogroup" aria-label="Kategori">
            <button type="button" role="radio" aria-checked={!cat} className={`chip ${!cat ? "on" : ""}`} onClick={() => setCat("")}>Tümü <small>{items.length}</small></button>
            {cats.map(([c, k]) => (
              <button key={c} type="button" role="radio" aria-checked={cat === c} className={`chip cat-${c.replace(/\s/g, "-")} ${cat === c ? "on" : ""}`} onClick={() => setCat(c)}>
                {CAT_LABEL[c] ?? c} <small>{k}</small>
              </button>
            ))}
          </div>
          <div className="filters inline">
            <label className="grow"><span className="sr-only">Haberlerde ara</span><input type="search" placeholder="Haberlerde ara" value={text} onChange={(e) => setText(e.target.value)} /></label>
            <label className="toggle"><input type="checkbox" checked={linked} onChange={(e) => setLinked(e.target.checked)} /> <span>Yalnızca maça bağlı</span></label>
          </div>
        </div>
        {rows.length === 0 ? <Empty title="Bu filtrede haber yok" icon="◉" /> : (
          <ul className="news-list">
            {rows.slice(0, n).map((x) => (
              <li key={x.id} className="news-item">
                <div className="news-meta">
                  <span className={`cat cat-${(x.category ?? "genel").replace(/\s/g, "-")}`}>{CAT_LABEL[x.category ?? "genel"] ?? x.category}</span>
                  <span className="muted small">{x.source}</span>
                  <time className="muted small" dateTime={x.published_at ?? undefined} title={dateTime(x.published_at)}>{relTime(x.published_at)}</time>
                </div>
                <a className="news-title" href={x.link} target="_blank" rel="noopener noreferrer">{x.title}</a>
                {x.summary && <p className="news-sum">{x.summary}</p>}
                {!!x.match_ids?.length && (
                  <div className="news-links">
                    {x.match_ids.slice(0, 3).map((id, i) => <Link key={id} to={matchPath(id)} className="mlink">◎ {(i === 0 && x.impact_note?.split(":")[0]) || matchTitle(id)}</Link>)}
                  </div>
                )}
              </li>
            ))}
          </ul>
        )}
        {rows.length > n && <button className="btn ghost wide" onClick={() => setN(n + PAGE)}>Daha fazla göster</button>}
        <p className="muted tiny">Eşleştirme otomatiktir ve hatalı olabilir. Haberler model girdisi değildir. Haberlerin hakları yayıncılarına aittir; yalnızca başlık, kısa özet ve bağlantı gösterilir.</p>
      </Gate>
    </>
  );
}
