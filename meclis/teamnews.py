"""Takım haberleri havuzu: güncel kadro (players), sakat/cezalı (injuries) ve ilk 11 (lineups).

Kural (kullanıcı): kaynak sınırı yok, hepsi havuza girer, biri boşsa diğeri doldurur.

Kadro (players)
  1. Wikipedia güncel A takım kadrosu (anahtarsız, tüm ligler) — iskelet: ad, forma no, mevki.
  2. BSD takım kadrosu (BSD_API_KEY) — ad, mevki, forma no + oyuncunun o anki uygunluğu.
  Oyuncu önemi için istatistik YALNIZCA BU SEZONDAN gelir: player_matches (BSD oyuncu istatistiği ve API-Football
  fikstür kimliğiyle oyuncu dakikaları; bkz. meclis/season.py, meclis/backfill.py) OKUMA ANINDA ad eşleştirmesiyle
  eklenir; `stats_source` alanında yazar. Bu sezon verisi olmayan takımda önem "bilinmiyor" kalır.
  Kadro satırları `player_key = 'k:<ad>'`, API-Football geçmiş satırları `apif:<id>:<sezon>` anahtarıyla tutulur;
  bir takımın "güncel kadrosu" en son kadro yenilemesinin damgasını taşıyan satırlardır (silme yapılmaz).

Sakat/cezalı (injuries) — maç başına, aynı oyuncu iki kaynakta varsa ilk kaynak kazanır, kaynaklar birlikte yazılır:
  BSD maç listesi (unavailable_players) → BSD kadro uygunluğu → API-Football (ücretsiz plan: dün/bugün/yarın
  için günlük tek istek, daha ileri maçlar için fikstür kimliğiyle) → SportDevs kadro eksikleri. En az bir kaynak geçerli yanıt verdiyse "liste biliniyor" sayılır (boş liste = bildirilen eksik yok).

İlk 11 (lineups): resmî ilk 11 her zaman tahminin önüne geçer.
  BSD resmî → API-Football → SportDevs → TheSportsDB (Patreon anahtarıyla) → BSD tahmini (AI, `confidence`).
  Tahmini ilk 11 "Açıklanan ilk 11" tamlık maddesini DOLDURMAZ; arayüzde "tahmini" etiketiyle görünür.
"""
from __future__ import annotations

import re

from datetime import timedelta

from . import names
from .model.injuries import _key, find_player, player_importance
from .timeutil import now_utc, parse_dt, to_iso

SQUAD_MAX_AGE_DAYS = 7
PREDICTED_MAX_AGE_H = 3


def squad_key(name: str) -> str:
    return "k:" + _key(name)


def latest_batch(rows: list[dict], field: str) -> list[dict]:
    """Aynı toplu yazımın (aynı zaman damgası) satırları — kaynaktan düşen eski kayıtlar böylece görünmez."""
    if not rows:
        return []
    stamps = [r.get(field) for r in rows if r.get(field)]
    if not stamps:
        return rows
    last = max(stamps, key=lambda x: parse_dt(x) or parse_dt("1970-01-01T00:00:00+00:00"))
    return [r for r in rows if r.get(field) == last]


def fresh_injuries(store, match_id: str) -> list[dict]:
    """Maçın GÜNCEL eksik listesi: son başarılı taramadaki satırlar (sonradan listeden çıkan oyuncu görünmez)."""
    rows = store.select("injuries", [("match_id", "eq", match_id)])
    st = store.get("source_status", source=f"injuries:{match_id}")
    if st and st.get("updated_at") and rows:
        cut = parse_dt(st["updated_at"]) - timedelta(minutes=5)
        rows = [r for r in rows if r.get("fetched_at") and parse_dt(r["fetched_at"]) >= cut]
        return rows
    return latest_batch(rows, "fetched_at")


def is_confirmed(lineup: dict) -> bool:
    st = lineup.get("lineup_status")
    if st:
        return st == "resmi"
    return "tahmini" not in (lineup.get("source") or "")


def season_players(store, team_id: str) -> list[dict]:
    """Takımın BU SEZONKİ oyuncu özeti (player_matches; bkz. meclis/season.py). Tablo yoksa boş."""
    from .analysis import season_start
    from .season import team_season_players

    lo = to_iso(season_start())
    try:
        pm = store.select("player_matches", [("team_id", "eq", team_id), ("kickoff_at", "gte", lo)])
    except Exception:
        return []
    if not pm:
        return []
    lg = team_id.split(":", 1)[0]
    cache = store.__dict__.setdefault("_season_matches_cache", {})
    if (lg, lo) not in cache:  # lig başına bir kez (bot çalışması boyunca)
        cache[(lg, lo)] = store.select("matches", [("league", "eq", lg), ("kickoff_at", "gte", lo),
                                                   ("status", "eq", "bitti")])
    ms = [m for m in cache[(lg, lo)] if team_id in (m["home_team_id"], m["away_team_id"])]
    return team_season_players(pm, ms, team_id)


def team_current_players(store, team_id: str) -> list[dict]:
    return current_players(store.select("players", [("team_id", "eq", team_id)]), season_players(store, team_id))


def current_players(rows: list[dict], season: list[dict] | None = None) -> list[dict]:
    """Takımın güncel oyuncu listesi ve oyuncu önemi istatistiği.

    Esas: BU SEZON (season = season_players(); dakika, ilk 11, G+A, yedek açığı r, var/yok farkı d).
    Bu sezon verisi olan takımda kadrodaki ama bu sezon hiç oynamamış oyuncunun dakikası 0'dır (bilinen sıfır).
    Bu sezon verisi yoksa geçmiş sezon istatistiği KULLANILMAZ; önem "bilinmiyor" kalır."""
    stat_f = ("minutes", "appearances", "lineups", "goals", "assists")
    squad = [r for r in rows if str(r.get("player_key", "")).startswith("k:")]
    if season:
        n = max((p.get("season_matches") or 0) for p in season)
        label = f"bsd 2026/27 ({n} maç)"
        if not squad:
            return [dict(p, stats_source=label) for p in season]
        out = []
        for r in latest_batch(squad, "updated_at"):
            h = find_player(r.get("name"), season)
            if h:
                r = dict(r, **{f: h.get(f) for f in stat_f}, r=h.get("r"), d=h.get("d"), stats_source=label)
                r["position"] = r.get("position") or h.get("position")
            else:
                r = dict(r, **{f: 0 for f in stat_f}, stats_source=label + ": bu sezon oynamadı")
            out.append(r)
        return out
    # Bu sezon verisi yok: geçmiş sezon istatistiği KULLANILMAZ (kullanıcı kuralı); önem "bilinmiyor" kalır.
    if squad:
        from .analysis import season_start

        cur_season = str(season_start().year)

        def current(r):  # satırın istatistiği bu sezondan mı? (eski kayıtlarda 'api-football 2024' yazar)
            yrs = re.findall(r"20\d\d", str(r.get("stats_source") or ""))
            return str(r.get("season") or "") == cur_season and all(y == cur_season for y in yrs)

        return [r if current(r) else dict(r, **{f: None for f in stat_f}, stats_source=None)
                for r in latest_batch(squad, "updated_at")]
    return [r for r in rows if not str(r.get("player_key", "")).startswith("apif:")]


class TeamNews:
    def __init__(self, pool):
        self.pool = pool
        self.store = pool.store
        self.s = pool.s

    def _note(self, src, ok, msg, calls=0):
        self.pool._note(src, ok, msg, calls)

    # ------------------------------------------------------------------ kadro
    def team_players(self, team_id: str) -> list[dict]:
        return team_current_players(self.store, team_id)

    def _hist_stats(self, team_id: str) -> tuple[list[dict], str | None]:
        rows = [r for r in self.store.select("players", [("team_id", "eq", team_id)])
                if str(r.get("player_key", "")).startswith("apif:")]
        if not rows:
            return [], None
        from .analysis import season_start

        cur = str(season_start().year)  # yalnızca bu sezonun API-Football oyuncu satırları (geçmiş sezon kullanılmaz)
        rows = [r for r in rows if str(r.get("season") or "") == cur]
        return (rows, cur) if rows else ([], None)

    def refresh_squads(self, leagues: list[str] | None = None, force: bool = False, max_teams: int = 400) -> dict:
        from .sources import wikipedia

        leagues = leagues or self.s.leagues
        teams = [t for t in self.store.select("teams") if t["league"] in leagues]
        # yalnızca bu sezon maçı olan takımlar (küme düşmüş eski takımlara istek atılmaz)
        lo = to_iso(now_utc() - timedelta(days=60))
        hi = to_iso(now_utc() + timedelta(days=30))
        active, bsd_ids = set(), {}
        for m in self.store.select("matches", [("kickoff_at", "gte", lo), ("kickoff_at", "lte", hi)]):
            active.update((m["home_team_id"], m["away_team_id"]))
            ext = m.get("ext_ids") or {}
            for side in ("home", "away"):
                if ext.get(f"bsd_{side}"):
                    bsd_ids[m[f"{side}_team_id"]] = ext[f"bsd_{side}"]
        teams = [t for t in teams if t["id"] in active]
        today = now_utc().date()
        bsd = getattr(self.pool, "bsd", None)
        due = []
        for t in teams:
            ext0 = t.get("ext_ids") or {}
            chk = ext0.get("squad_checked")
            # yeni bir kaynak devreye girdiyse (ör. BSD anahtarı sonradan eklendi) 7 günlük önbellek beklenmez
            have = set(ext0.get("squad_sources") or [])
            new_src = (bsd is not None and bsd.available and bsd_ids.get(t["id"]) and "bsd" not in have) or \
                      ("squad_sources" not in ext0)
            if force or not chk or new_src or \
                    (today - parse_dt(chk + "T00:00:00+00:00").date()).days >= SQUAD_MAX_AGE_DAYS:
                due.append(t)
        due = due[:max_teams]
        stats = {"teams": len(teams), "due": len(due), "wikipedia": 0, "bsd": 0, "players": 0, "with_stats": 0,
                 "failed": []}
        if not due:
            return stats
        qids = [(t.get("ext_ids") or {}).get("wikidata") for t in due]
        try:
            titles = wikipedia.enwiki_titles([q for q in qids if q])
        except Exception as e:
            titles = {}
            self._note("wikipedia", False, f"Wikidata→Wikipedia bağlantısı: {e}")
        for t in due:
            ext = dict(t.get("ext_ids") or {})
            squad, src = [], []
            try:
                hint = ext.get("enwiki") or titles.get(ext.get("wikidata"))
                wp, title = wikipedia.team_squad(names.display_name(t["name"]), hint)
                if wp:
                    squad = [dict(p, _src="wikipedia") for p in wp]
                    ext["enwiki"] = title
                    src.append("wikipedia")
                    stats["wikipedia"] += 1
            except Exception as e:
                self._note("wikipedia", False, f"{t['name']}: {e}")
            if bsd is not None and bsd.available and bsd_ids.get(t["id"]):
                try:
                    bs = bsd.squad(bsd_ids[t["id"]])
                    if bs:
                        stats["bsd"] += 1
                        src.append("bsd")
                        for p in bs:
                            hit = find_player(p["name"], squad)
                            if hit:
                                hit.setdefault("number", p.get("number"))
                                hit["position"] = hit.get("position") or p.get("position")
                            else:
                                squad.append(dict(p, _src="bsd"))
                except Exception as e:
                    self._note("bsd", False, f"kadro {t['name']}: {e}")
            ext["squad_sources"] = src
            if not squad:
                stats["failed"].append(t["name"])
                ext["squad_checked"] = today.isoformat()
                self.store.upsert("teams", [dict(t, ext_ids=ext)])
                continue
            hist, hist_season = self._hist_stats(t["id"])
            ts = to_iso(now_utc())
            rows = []
            for p in squad:
                h = find_player(p["name"], hist) if hist else None
                st_src = f"api-football {hist_season}" if h else None
                row = {"team_id": t["id"], "player_key": squad_key(p["name"]), "name": p["name"],
                       "position": p.get("position") or (h or {}).get("position"),
                       "shirt_number": p.get("number"),
                       "minutes": (h or {}).get("minutes"), "appearances": (h or {}).get("appearances"),
                       "lineups": (h or {}).get("lineups"), "goals": (h or {}).get("goals"),
                       "assists": (h or {}).get("assists"),
                       "season": str(self._season_label()), "stats_source": st_src,
                       "source": "+".join(dict.fromkeys(src)) + (f"; istatistik: {st_src}" if st_src else ""),
                       "updated_at": ts}
                rows.append(row)
                stats["with_stats"] += 1 if h else 0
            # aynı anahtar iki kez gelirse (aynı ad) sonuncusu kalsın
            rows = list({r["player_key"]: r for r in rows}.values())
            self.store.upsert("players", rows)
            stats["players"] += len(rows)
            ext["squad_checked"] = today.isoformat()
            self.store.upsert("teams", [dict(t, ext_ids=ext)])
        self._note("wikipedia", True, f"{stats['wikipedia']}/{len(due)} takım kadrosu, {stats['players']} oyuncu "
                                      f"({stats['with_stats']} oyuncuda API-Football geçmiş istatistiği)",
                   calls=len(due))
        return stats

    def _season_label(self) -> int:
        d = now_utc().date()
        return d.year if d.month >= 7 else d.year - 1

    # ------------------------------------------------------------------ sakat / cezalı
    def _side_of(self, match: dict, team_name: str | None, team_ext: int | None, prefix: str) -> str:
        ext = match.get("ext_ids") or {}
        if team_ext is not None:
            if team_ext == ext.get(f"{prefix}_home"):
                return "home"
            if team_ext == ext.get(f"{prefix}_away"):
                return "away"
        return "home" if names.same_team(team_name or "", match["home_name"]) else "away"

    def collect_injuries(self, match: dict) -> tuple[list[dict], bool, list[str]]:
        """Döner: (ham kayıtlar [{side, player_name, kind, reason, source}], liste_biliniyor_mu, log)."""
        ext = match.get("ext_ids") or {}
        out, known, log = [], False, []
        ko = parse_dt(match["kickoff_at"])
        bsd = getattr(self.pool, "bsd", None)
        if bsd is not None and bsd.available and ext.get("bsd"):
            try:
                lu = bsd.lineups(int(ext["bsd"]))
                self._bsd_lineup_cache = (match["id"], lu)
                if lu.get("unavailable") is not None:
                    known = True
                    for side in ("home", "away"):
                        out += [dict(x, side=side, source="bsd") for x in lu["unavailable"].get(side) or []]
                else:  # maç listesi henüz yok → kadro uygunluğu
                    got = 0
                    for side in ("home", "away"):
                        tid = ext.get(f"bsd_{side}")
                        if not tid:
                            continue
                        sq = bsd.squad(int(tid))
                        got += 1
                        out += [{"side": side, "player_name": p["name"], "kind": p["kind"], "reason": p.get("reason"),
                                 "source": "bsd (kadro)"} for p in sq if p.get("kind")]
                    known = known or got == 2
            except Exception as e:
                log.append(f"bsd: {e}")
                self._note("bsd", False, f"eksikler: {e}")
        apif = self.pool.apif
        in_window = abs((ko.date() - now_utc().date()).days) <= 1 or ko - now_utc() <= timedelta(hours=36)
        if apif.available and ext.get("apif") and in_window:
            try:
                for it in self._apif_injuries(int(ext["apif"]), ko.date()):
                    side = self._side_of(match, it.get("team_name"), it.get("team_apif"), "apif")
                    kind = {"Missing Fixture": "kesin yok", "Questionable": "şüpheli"}.get(it.get("kind"), it.get("kind"))
                    out.append({"side": side, "player_name": it["player_name"], "player_id": it.get("player_id"),
                                "kind": kind, "reason": it.get("reason"), "source": "api-football"})
                known = True
            except Exception as e:
                log.append(f"api-football: {e}")
        sd = getattr(self.pool, "sportdevs", None)
        if sd is not None and sd.available and ext.get("sportdevs") and ko - now_utc() <= timedelta(hours=2):
            try:
                for lu in sd.lineups(int(ext["sportdevs"])):
                    out += [dict(x, side=lu["side"], source="sportdevs") for x in lu.get("missing") or []]
            except Exception as e:
                log.append(f"sportdevs: {e}")
        return out, known, log

    def _apif_injuries(self, fixture_id: int, d) -> list[dict]:
        """Maç tarihi dün/bugün/yarın ise o günün tüm sakatlıkları TEK istekte (çalıştırma içinde önbellekli);
        değilse fikstür kimliğiyle tek maç sorgusu."""
        cache = self.__dict__.setdefault("_apif_day", {})
        if abs((d - now_utc().date()).days) <= 1:
            if d not in cache:
                try:
                    cache[d] = self.pool.apif.injuries_by_date(d)
                except Exception as e:
                    cache[d] = e
            if not isinstance(cache[d], Exception):
                return [x for x in cache[d] if x.get("fixture_apif") == fixture_id]
            raise cache[d]
        return self.pool.apif.injuries(fixture_id)

    def injuries(self, match: dict, max_age_h: float = 8) -> tuple[list[dict], bool]:
        cached = fresh_injuries(self.store, match["id"])
        fetched_ok = self.store.get("source_status", source=f"injuries:{match['id']}")
        if fetched_ok and (now_utc() - parse_dt(fetched_ok["updated_at"])).total_seconds() < max_age_h * 3600:
            return cached, True
        if getattr(self.store, "read_only", False):  # arayüz (anon): yalnızca botun yazdığını okur
            return cached, bool(fetched_ok) or bool(cached)
        raw, known, _log = self.collect_injuries(match)
        if not known and not raw:
            return cached, bool(fetched_ok)
        merged: dict[tuple, dict] = {}
        for r in raw:
            k = (r["side"], _key(r.get("player_name")))
            if k in merged:
                if r["source"] not in merged[k]["sources"]:
                    merged[k]["sources"].append(r["source"])
                continue
            merged[k] = dict(r, sources=[r["source"]])
        ts = to_iso(now_utc())
        players = {side: self.team_players(match[f"{side}_team_id"]) for side in ("home", "away")}
        rows = []
        for (side, pk), it in merged.items():
            tid = match[f"{side}_team_id"]
            pl = find_player(it["player_name"], players[side])
            imp = player_importance(pl, players[side], it.get("kind"))
            rows.append({"id": f"{match['id']}:{pk}", "match_id": match["id"], "team_id": tid,
                         "team_name": match[f"{side}_name"], "player_name": it["player_name"],
                         "injury_status": it.get("kind"), "reason": it.get("reason"),
                         "matches_played": (pl or {}).get("appearances"), "key_matches": (pl or {}).get("lineups"),
                         "goal_contribution": imp.get("ga_share"), "defensive_contribution": imp.get("defensive_share"),
                         "minutes_share": imp.get("minutes_share"), "weight_score": imp["importance"],
                         "is_key": imp["is_key"], "source": "+".join(it["sources"]), "fetched_at": ts})
        if rows:
            self.store.upsert("injuries", rows)
        if known:
            srcs = sorted({s for r in rows for s in r["source"].split("+")}) or ["kaynak yanıtı: eksik yok"]
            self.store.set_source_status(f"injuries:{match['id']}", True, f"{len(rows)} kayıt ({', '.join(srcs)})")
        return rows, known

    # ------------------------------------------------------------------ ilk 11
    def lineups(self, match: dict) -> list[dict]:
        cached = self.store.select("lineups", [("match_id", "eq", match["id"])])
        if (cached and all(is_confirmed(x) for x in cached)) or getattr(self.store, "read_only", False):
            return cached
        ko = parse_dt(match["kickoff_at"])
        now = now_utc()
        if cached and not any(is_confirmed(x) for x in cached):
            age = min((now - parse_dt(x["updated_at"])).total_seconds() for x in cached)
            if age < PREDICTED_MAX_AGE_H * 3600 and ko - now > timedelta(minutes=75):
                return cached
        ext = match.get("ext_ids") or {}
        near = ko - now <= timedelta(minutes=75)
        found: dict[str, dict] = {}
        predicted: dict[str, dict] = {}
        bsd = getattr(self.pool, "bsd", None)
        if bsd is not None and bsd.available and ext.get("bsd"):
            try:
                c = getattr(self, "_bsd_lineup_cache", None)
                lu = c[1] if c and c[0] == match["id"] else bsd.lineups(int(ext["bsd"]))
                tgt = found if lu["status"] == "resmi" else predicted if lu["status"] == "tahmini" else None
                if tgt is not None:
                    for side, x in lu["lineups"].items():
                        tgt[side] = {"formation": x.get("formation"), "start_xi": x["start_xi"], "subs": x["subs"],
                                     "coach": None, "source": "bsd" if tgt is found else "bsd (tahmini)",
                                     "lineup_status": lu["status"]}
            except Exception as e:
                self._note("bsd", False, f"ilk 11: {e}")
        apif = self.pool.apif
        if len(found) < 2 and near and apif.available and ext.get("apif"):
            try:
                for it in apif.lineups(int(ext["apif"])):
                    side = self._side_of(match, it.get("team_name"), it.get("team_apif"), "apif")
                    found.setdefault(side, {"formation": it.get("formation"), "start_xi": it.get("start_xi"),
                                            "subs": it.get("subs"), "coach": it.get("coach"),
                                            "source": "api-football", "lineup_status": "resmi"})
            except Exception as e:
                self._note("api-football", False, f"kadro: {e}")
        sd = getattr(self.pool, "sportdevs", None)
        if len(found) < 2 and near and sd is not None and sd.available and ext.get("sportdevs"):
            try:
                for it in sd.lineups(int(ext["sportdevs"])):
                    tgt = found if it.get("confirmed") else predicted
                    tgt.setdefault(it["side"], {"formation": it.get("formation"), "start_xi": it["start_xi"],
                                                "subs": it["subs"], "coach": None,
                                                "source": "sportdevs" if it.get("confirmed") else "sportdevs (tahmini)",
                                                "lineup_status": "resmi" if it.get("confirmed") else "tahmini"})
            except Exception as e:
                self._note("sportdevs", False, f"ilk 11: {e}")
        if len(found) < 2 and near and ext.get("tsdb"):
            try:
                for it in self.pool.tsdb.lineup(str(ext["tsdb"])):
                    found.setdefault(it["side"], {"formation": it.get("formation"), "start_xi": it["start_xi"],
                                                  "subs": it["subs"], "coach": None, "source": "thesportsdb",
                                                  "lineup_status": "resmi"})
            except Exception:
                pass
        final = dict(predicted)
        final.update(found)  # resmî her zaman tahmini ezer
        if not final:
            return cached
        ts = to_iso(now)
        from .xi import with_grid

        rows = [with_grid({"match_id": match["id"], "side": side, **v, "updated_at": ts}) for side, v in final.items()]
        self.store.upsert("lineups", rows)
        return rows

    # ------------------------------------------------------------------ toplu
    def run_upcoming(self, hours_ahead: float = 168, leagues: list[str] | None = None) -> dict:
        leagues = leagues or self.s.leagues
        now = now_utc()
        ms = self.pool.matches_between(to_iso(now - timedelta(hours=2)), to_iso(now + timedelta(hours=hours_ahead)),
                                       leagues)
        ms = [m for m in ms if m.get("status") in ("planlandi", "basladi", None)]
        out = {"matches": len(ms), "injury_known": 0, "injury_rows": 0, "lineups_confirmed": 0, "lineups_predicted": 0}
        for m in ms:
            try:
                rows, known = self.injuries(m)
                out["injury_known"] += 1 if known else 0
                out["injury_rows"] += len(rows)
            except Exception as e:
                self.pool.log.append(f"⚠️ eksikler {m['id']}: {e}")
            try:
                lus = self.lineups(m)
                out["lineups_confirmed"] += sum(1 for x in lus if is_confirmed(x))
                out["lineups_predicted"] += sum(1 for x in lus if not is_confirmed(x))
            except Exception as e:
                self.pool.log.append(f"⚠️ ilk 11 {m['id']}: {e}")
        return out


# ---------------------------------------------------------------------- Meclis tahmini ilk 11
def recent_xis(store, team_id: str, before_iso: str, n: int = 5) -> list[list[str]]:
    """Takımın son n maçındaki RESMÎ ilk 11'leri (en yeni önce)."""
    from datetime import timedelta as _td

    lo = to_iso(parse_dt(before_iso) - _td(days=70))
    ms = [m for m in store.select("matches", [("kickoff_at", "gte", lo), ("kickoff_at", "lt", before_iso)])
          if team_id in (m["home_team_id"], m["away_team_id"])]
    ms = sorted(ms, key=lambda m: m["kickoff_at"], reverse=True)[:12]
    if not ms:
        return []
    side_of = {m["id"]: ("home" if m["home_team_id"] == team_id else "away") for m in ms}
    rows = store.select("lineups", [("match_id", "in", list(side_of))])
    by = {r["match_id"]: r for r in rows if r.get("side") == side_of.get(r["match_id"]) and is_confirmed(r)}
    out = []
    for m in ms:
        r = by.get(m["id"])
        if r and r.get("start_xi"):
            out.append([p.get("name") for p in r["start_xi"] if p.get("name")])
        if len(out) >= n:
            break
    return out


def build_xi(store, match: dict, injuries: list[dict], players_by_team: dict) -> dict:
    """Maçın iki tarafı için Meclis tahmini ilk 11 (bkz. meclis/xi.py)."""
    from .xi import predict_xi

    lus = store.select("lineups", [("match_id", "eq", match["id"])])
    out = {}
    for side in ("home", "away"):
        tid = match[f"{side}_team_id"]
        ext = next((x.get("start_xi") for x in lus if x.get("side") == side and not is_confirmed(x)), None)
        unav = [r for r in injuries or [] if r.get("team_id") == tid]
        out[side] = predict_xi(players_by_team.get(tid) or [], unav, recent_xis(store, tid, match["kickoff_at"]), ext)
    return out
