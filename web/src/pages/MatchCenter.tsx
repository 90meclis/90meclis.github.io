import { useMemo } from "react";
import { useSearchParams } from "react-router-dom";
import * as api from "../lib/data";
import { useAsync } from "../lib/useAsync";
import { addDays, dateLong, dayLabel, trDay } from "../lib/format";
import { league } from "../lib/labels";
import { usePageMeta, ROUTES } from "../lib/seo";
import { groupBy } from "../lib/trust";
import { MatchRow } from "../components/MatchRow";
import { Empty, Gate, PageHead, Skeleton } from "../components/ui";

const BACK = 3, AHEAD = 14;

export default function MatchCenter() {
  const meta = ROUTES[1];
  usePageMeta(meta.title, meta.description);
  const [sp, setSp] = useSearchParams();
  const today = trDay();
  const lig = sp.get("lig") ?? "";

  const daysQ = useAsync(`days:${today}`, () => api.matchDays(addDays(today, -BACK), addDays(today, AHEAD)));
  const lgQ = useAsync("leagues", api.leaguesInDb);

  const counts = useMemo(() => {
    const out: Record<string, number> = {};
    for (const [d, byL] of Object.entries(daysQ.data ?? {})) {
      out[d] = lig ? byL[lig] ?? 0 : Object.values(byL).reduce((a, b) => a + b, 0);
    }
    return out;
  }, [daysQ.data, lig]);

  const defaultDay = useMemo(() => {
    const ds = Object.keys(counts).filter((d) => counts[d] > 0).sort();
    if (counts[today]) return today;
    return ds.find((d) => d > today) ?? ds.reverse().find((d) => d < today) ?? today;
  }, [counts, today]);

  const day = sp.get("gun") ?? (daysQ.data ? defaultDay : null);
  const dayQ = useAsync(day ? `day:${day}` : null, () => api.matchesOnDay(day!), [day]);
  const ids = (dayQ.data ?? []).map((m) => m.id);
  const predQ = useAsync(day && dayQ.data ? `daypreds:${day}:${ids.length}` : null, () => api.predictionsForMatches(ids), [day, ids.length]);

  const leagues = useMemo(() => {
    const set = new Set<string>([...(lgQ.data ?? [])]);
    for (const byL of Object.values(daysQ.data ?? {})) Object.keys(byL).forEach((l) => set.add(l));
    return [...set].sort((a, b) => league(a).order - league(b).order);
  }, [lgQ.data, daysQ.data]);

  const strip = Array.from({ length: BACK + AHEAD + 1 }, (_, i) => addDays(today, i - BACK));
  const set = (k: string, v: string | null) => {
    const n = new URLSearchParams(sp);
    if (v) n.set(k, v); else n.delete(k);
    setSp(n, { replace: true });
  };

  const matches = (dayQ.data ?? []).filter((m) => !lig || m.league === lig);
  const groups = groupBy(matches, (m) => m.league).sort((a, b) => league(a[0]).order - league(b[0]).order);
  const pickBy = new Map((predQ.data ?? []).filter((p) => p.tag === "meclis_gorusu").map((p) => [p.match_id, p]));
  const nextDay = Object.keys(counts).sort().find((d) => d > (day ?? today) && counts[d] > 0);

  return (
    <>
      <PageHead kicker="Bülten" title="Maç Merkezi">
        Maça dokun: form, maç maç istatistik, eksik oyuncular, ilk 11, hava durumu, oranlar ve meclisin senaryoları.
      </PageHead>

      <div className="toolbar sticky">
        <div className="datestrip" role="tablist" aria-label="Tarih seç">
          {strip.map((d) => {
            const l = dayLabel(d);
            const n = counts[d] ?? 0;
            return (
              <button key={d} role="tab" aria-selected={d === day} className={`dchip ${d === day ? "on" : ""} ${n ? "" : "none"}`}
                onClick={() => set("gun", d)} aria-label={`${dateLong(d + "T12:00:00+03:00")}, ${n} maç`}>
                <span className="d-top">{l.top}</span>
                <span className="d-bot">{l.bottom}</span>
                <span className="d-n">{daysQ.loading ? "·" : n || "–"}</span>
              </button>
            );
          })}
          <label className="dpick">
            <span className="sr-only">Başka bir tarih</span>
            <input type="date" value={day ?? ""} onChange={(e) => e.target.value && set("gun", e.target.value)} />
          </label>
        </div>
        <div className="chips scroll" role="radiogroup" aria-label="Lig filtresi">
          <button type="button" role="radio" aria-checked={!lig} className={`chip ${!lig ? "on" : ""}`} onClick={() => set("lig", null)}>Tüm ligler</button>
          {leagues.map((l) => (
            <button key={l} type="button" role="radio" aria-checked={lig === l} className={`chip ${lig === l ? "on" : ""}`} onClick={() => set("lig", l)}>
              <span aria-hidden="true">{league(l).flag}</span> {league(l).name}
            </button>
          ))}
        </div>
      </div>

      <Gate loading={daysQ.loading || !day} error={daysQ.error ?? dayQ.error} rows={6}>
        <h2 className="day-title">{day && dateLong(day + "T12:00:00+03:00")} <span className="muted">· {matches.length} maç</span></h2>
        {dayQ.loading ? <Skeleton rows={6} /> : matches.length === 0 ? (
          <Empty title="Bu tarihte maç yok" icon="◎">
            {nextDay && <button className="btn primary" onClick={() => set("gun", nextDay)}>Sıradaki maç günü: {dayLabel(nextDay).bottom}</button>}
          </Empty>
        ) : (
          <div className="league-groups">
            {groups.map(([code, ms]) => (
              <section key={code} className="lgroup">
                <h3 className="lgroup-title"><span aria-hidden="true">{league(code).flag}</span> {league(code).name}<small>{league(code).country}</small></h3>
                <div className="mlist">{ms.map((m) => <MatchRow key={m.id} m={m} pick={pickBy.get(m.id)} />)}</div>
              </section>
            ))}
          </div>
        )}
      </Gate>
    </>
  );
}
