import { useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { Card, Gate, PageHead } from "../components/ui";
import { allCoupons, allPredictionsRaw, sealsFull } from "../lib/data";
import { dateTime } from "../lib/format";
import { pickLabel, TAG_LABELS } from "../lib/labels";
import { matchPath } from "../lib/match";
import { diffCanonical, verifyChain } from "../lib/seal";
import { useAsync } from "../lib/useAsync";

const MANIFEST = "https://raw.githubusercontent.com/90meclis/90meclis.github.io/main/muhur/manifest.json";
const MANIFEST_PAGE = "https://github.com/90meclis/90meclis.github.io/blob/main/muhur/manifest.json";

export default function Seal() {
  const [q, setQ] = useSearchParams();
  const [term, setTerm] = useState(q.get("id") ?? "");
  const d = useAsync("seal:verify", async () => {
    const [rows, preds, coupons] = await Promise.all([sealsFull(), allPredictionsRaw(), allCoupons()]);
    const v = await verifyChain(rows);
    const cur = new Map<string, Record<string, unknown>>([...preds.map((p) => [p.id, p as unknown as Record<string, unknown>] as const), ...coupons.map((c) => [c.id, c as unknown as Record<string, unknown>] as const)]);
    const diffs = new Map(rows.map((r) => [r.ref_id, cur.has(r.ref_id) ? diffCanonical(r.kanonik, cur.get(r.ref_id)!) : ["kayıt bulunamadı"]]));
    let man: { kok: string | null; kayit: number; olusturuldu: string } | null = null;
    try { const r = await fetch(MANIFEST, { cache: "no-store", signal: AbortSignal.timeout(4000) }); if (r.ok) man = await r.json(); } catch { /* depo kopyası yoksa gösterilmez */ }
    return { rows, v, diffs, cur, man };
  }, []);
  const sel = useMemo(() => {
    const id = q.get("id"); if (!id || !d.data) return null;
    return d.data.rows.find((r) => r.ref_id === id) ?? null;
  }, [q, d.data]);
  const same = d.data ? [...d.data.diffs.values()].filter((x) => !x.length).length : 0;
  const label = (id: string) => {
    const r = d.data?.cur.get(id) as Record<string, string | number | null> | undefined;
    if (!r) return id;
    if ("market" in r) return `${r.home_name} – ${r.away_name} · ${pickLabel(String(r.market), String(r.selection), r.line as number | null, String(r.home_name), String(r.away_name))}`;
    return `${(TAG_LABELS as Record<string, string>)[String(r.tag)] ?? "Kupon"} · ${r.coupon_date} · ${r.legs_count} maç`;
  };
  if (d.data && !d.data.rows.length) return <PageHead kicker="Kanıt Mührü" title="Mühür defteri" >Kayıtlar mühürlendiğinde doğrulama burada, tarayıcında yapılır.</PageHead>;
  return (
    <>
      <PageHead kicker="Kanıt Mührü" title="Kayıt değişmedi. Kanıtı burada.">
        Her tahmin ve kupon kilitlendiği an SHA-256 ile mühürlenir; her mühür bir öncekini içerir. Aşağıdaki doğrulama sunucuda değil, şu an senin tarayıcında yapılıyor.
      </PageHead>
      <Gate loading={d.loading} error={d.error} rows={6}>
        {d.data && (<>
          <div className="seal-sum">
            <div className={d.data.v.broken.length ? "bad" : "ok"}><small>Zincir</small><b>{d.data.v.broken.length ? `${d.data.v.broken.length} kopuk` : "Sağlam ✓"}</b><span>{d.data.v.okChain}/{d.data.v.n} halka doğrulandı</span></div>
            <div className={same === d.data.rows.length ? "ok" : "bad"}><small>Bugünkü kayıtla</small><b>{same === d.data.rows.length ? "Birebir ✓" : `${d.data.rows.length - same} fark`}</b><span>{same}/{d.data.rows.length} kayıt alan alan aynı</span></div>
            {d.data.man && <div className={d.data.man.kok === d.data.v.root || d.data.rows.some((r) => r.sha256 === d.data!.man!.kok) ? "ok" : "bad"}><small>Depodaki kök</small><b>{d.data.rows.some((r) => r.sha256 === d.data!.man!.kok) ? "Eşleşiyor ✓" : "Eşleşmiyor"}</b><span><a href={MANIFEST_PAGE} target="_blank" rel="noreferrer">manifest.json</a> · {d.data.man.kayit} kayıt</span></div>}
          </div>
          <Card title="Bir kaydı doğrula">
            <form className="seal-find" onSubmit={(e) => { e.preventDefault(); setQ(term ? { id: term.trim() } : {}, { replace: true }); }}>
              <input value={term} onChange={(e) => setTerm(e.target.value)} placeholder="Kayıt kimliği (paylaşım kartında ya da arşivde)" aria-label="Kayıt kimliği" />
              <button className="btn primary" type="submit">Doğrula</button>
            </form>
            {q.get("id") && !sel && <p className="muted small">Bu kimlikle mühürlü kayıt yok.</p>}
            {sel && (() => {
              const df = d.data!.diffs.get(sel.ref_id) ?? [];
              const br = d.data!.v.broken.find((b) => b.seq === sel.seq);
              const cur = d.data!.cur.get(sel.ref_id) as Record<string, string> | undefined;
              return (
                <div className="seal-one">
                  <p className={`seal-verdict ${df.length || br ? "bad" : "ok"}`}>{df.length || br ? `⚠ ${br ? br.why : `değişen alan: ${df.join(", ")}`}` : "✓ Bu kayıt mühürlendiği andan beri değişmedi."}</p>
                  <p><b>{label(sel.ref_id)}</b>{cur?.match_id && <> · <Link to={matchPath(cur.match_id)}>maç sayfası</Link></>}</p>
                  <dl>
                    <dt>Mühür no</dt><dd>#{sel.seq}</dd>
                    <dt>Mühürlendi</dt><dd>{dateTime(sel.muhurlendi_at)} TSİ</dd>
                    <dt>İçerik özeti</dt><dd><code>{sel.icerik_sha256}</code></dd>
                    <dt>Önceki mühür</dt><dd><code>{sel.onceki_sha256}</code></dd>
                    <dt>Mühür</dt><dd><code>{sel.sha256}</code></dd>
                  </dl>
                  <details><summary>Kanonik kayıt (mühürlenen metin)</summary><pre>{JSON.stringify(JSON.parse(sel.kanonik), null, 1)}</pre></details>
                  <p className="muted tiny">Kendin de hesaplayabilirsin: sha256(kanonik metin) = içerik özeti; sha256(önceki mühür + içerik özeti) = mühür.</p>
                </div>
              );
            })()}
          </Card>
          <Card title="Son mühürler">
            <ul className="seal-list">
              {[...d.data.rows].sort((a, b) => b.seq - a.seq).slice(0, 30).map((r) => {
                const ok = !(d.data!.diffs.get(r.ref_id) ?? []).length && !d.data!.v.broken.some((b) => b.seq === r.seq);
                return (
                  <li key={r.seq}><button type="button" onClick={() => { setTerm(r.ref_id); setQ({ id: r.ref_id }, { replace: true }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>
                    <span className={ok ? "ok" : "bad"}>{ok ? "✓" : "⚠"}</span><b>#{r.seq}</b><span className="sl-l">{label(r.ref_id)}</span><code>{r.sha256.slice(0, 10)}…</code>
                  </button></li>
                );
              })}
            </ul>
          </Card>
        </>)}
      </Gate>
    </>
  );
}
