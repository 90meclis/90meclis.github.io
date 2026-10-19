"""Maç analizi: lig bağlamı (modeller + geçmiş), tüm pazarlar, senaryolar, anlatı ve veri kalitesi."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import MODEL_VERSION
from .markets import attach_odds
from .model.counts import STATS, CountModel, count_markets, fit_count_model
from .model.goals import GoalModel, fit_dixon_coles, goal_markets, most_likely_scores, score_matrix
from .model.injuries import injury_adjustment
from .timeutil import now_utc, parse_dt, to_iso


@dataclass
class LeagueContext:
    league: str
    matches: list[dict]
    stats: dict[str, dict]
    goal_model: GoalModel | None = None
    count_models: dict[str, CountModel | None] = field(default_factory=dict)
    error: str | None = None

    @classmethod
    def build(cls, league: str, matches: list[dict], stats: dict[str, dict]) -> "LeagueContext":
        ctx = cls(league, matches, stats)
        now = now_utc()
        rows = []
        for m in matches:
            if m.get("home_goals") is None:
                continue
            rows.append({"home": m["home_team_id"], "away": m["away_team_id"], "hg": m["home_goals"],
                         "ag": m["away_goals"], "hthg": m.get("ht_home_goals"), "htag": m.get("ht_away_goals"),
                         "days_ago": (now - parse_dt(m["kickoff_at"])).total_seconds() / 86400})
        try:
            ctx.goal_model = fit_dixon_coles(rows)
        except Exception as e:
            ctx.error = f"Gol modeli kurulamadı: {e}"
        for stat in STATS:
            crow = []
            for m in matches:
                st = stats.get(m["id"]) or {}
                h, a = st.get("home") or {}, st.get("away") or {}
                hv, av = _stat_value(h, stat), _stat_value(a, stat)
                if hv is None or av is None:
                    continue
                crow.append({"home": m["home_team_id"], "away": m["away_team_id"], "h": hv, "a": av,
                             "days_ago": (now - parse_dt(m["kickoff_at"])).total_seconds() / 86400})
            ctx.count_models[stat] = fit_count_model(crow, stat)
        return ctx

    def team_matches(self, team_id: str, n: int | None = None) -> list[dict]:
        ms = [m for m in self.matches if team_id in (m["home_team_id"], m["away_team_id"])
              and m.get("home_goals") is not None]
        ms = sorted(ms, key=lambda m: m["kickoff_at"], reverse=True)
        return ms[:n] if n else ms

    def form(self, team_id: str, n: int = 5) -> list[dict]:
        out = []
        for m in self.team_matches(team_id, n):
            home = m["home_team_id"] == team_id
            gf, ga = (m["home_goals"], m["away_goals"]) if home else (m["away_goals"], m["home_goals"])
            out.append({"tarih": m["kickoff_at"][:10], "rakip": m["away_name"] if home else m["home_name"],
                        "yer": "İç saha" if home else "Deplasman", "skor": f"{gf}-{ga}",
                        "sonuç": "G" if gf > ga else "B" if gf == ga else "M"})
        return out

    def h2h(self, home_id: str, away_id: str, n: int = 8) -> list[dict]:
        ms = [m for m in self.matches if {m["home_team_id"], m["away_team_id"]} == {home_id, away_id}
              and m.get("home_goals") is not None]
        ms = sorted(ms, key=lambda m: m["kickoff_at"], reverse=True)[:n]
        return [{"tarih": m["kickoff_at"][:10], "maç": f"{m['home_name']} – {m['away_name']}",
                 "skor": f"{m['home_goals']}-{m['away_goals']}",
                 "İY": f"{m.get('ht_home_goals')}-{m.get('ht_away_goals')}" if m.get("ht_home_goals") is not None else "—"}
                for m in ms]

    def series(self, team_id: str, n: int = 10) -> list[dict]:
        """Takımın maç maç serisi (ortalama değil)."""
        out = []
        for m in self.team_matches(team_id, n):
            home = m["home_team_id"] == team_id
            st = self.stats.get(m["id"]) or {}
            mine, opp = (st.get("home") or {}, st.get("away") or {}) if home else (st.get("away") or {}, st.get("home") or {})
            gf, ga = (m["home_goals"], m["away_goals"]) if home else (m["away_goals"], m["home_goals"])
            hgf, hga = (m.get("ht_home_goals"), m.get("ht_away_goals")) if home else (m.get("ht_away_goals"), m.get("ht_home_goals"))
            out.append({
                "tarih": m["kickoff_at"][:10], "rakip": m["away_name"] if home else m["home_name"],
                "yer": "İ" if home else "D", "skor": f"{gf}-{ga}",
                "İY gol (A-Y)": f"{hgf}-{hga}" if hgf is not None else "—",
                "şut": mine.get("shots"), "isabetli şut": mine.get("shots_on_target"),
                "rakip isabetli şut": opp.get("shots_on_target"), "korner": mine.get("corners"),
                "rakip korner": opp.get("corners"), "kart": _stat_value(mine, "cards"),
                "faul": mine.get("fouls"), "xG": mine.get("xg"), "kale vuruşu": mine.get("goal_kicks"),
                "KG": "Var" if gf > 0 and ga > 0 else "Yok",
            })
        return out


def _stat_value(side: dict, stat: str):
    if stat == "cards":
        y, r = side.get("yellow"), side.get("red")
        return None if y is None else y + (r or 0)
    return side.get(stat)


def _inj_effect_rows(rows: list[dict], players_by_team: dict[str, list[dict]], team_id: str) -> list[dict]:
    from .model.injuries import find_player, player_importance

    players = players_by_team.get(team_id) or []
    out = []
    for r in rows:
        if r.get("team_id") != team_id:
            continue
        p = find_player(r.get("player_name"), players)
        imp = player_importance(p, players, r.get("injury_status"))
        imp["name"] = r.get("player_name")
        imp["reason"] = r.get("reason")
        imp["kind"] = r.get("injury_status")
        out.append(imp)
    return out


def analyze_match(match: dict, ctx: LeagueContext, settings, injuries: list[dict] | None = None,
                  injuries_known: bool = False, players_by_team: dict | None = None,
                  weather: dict | None = None, lineups_known: bool = False) -> dict:
    hid, aid = match["home_team_id"], match["away_team_id"]
    missing, postponed = [], {}
    gm = ctx.goal_model
    min_n = settings.min_team_matches
    payload: dict = {"match_id": match["id"], "model_version": MODEL_VERSION, "created_at": to_iso(now_utc()),
                     "home": match["home_name"], "away": match["away_name"], "kickoff_at": match["kickoff_at"],
                     "league": match["league"], "markets": [], "count_info": {}, "postponed_markets": postponed}
    if gm is None:
        missing.append(ctx.error or "lig geçmişi yok")
    else:
        for tid, nm in ((hid, match["home_name"]), (aid, match["away_name"])):
            n = gm.n_matches.get(tid, 0)
            if n < min_n:
                missing.append(f"{nm}: geçmiş maç sayısı yetersiz ({n}/{min_n})")
    if settings.require_injury_data and not injuries_known:
        missing.append("sakatlık verisi (REQUIRE_INJURY_DATA açık)")
    payload["form"] = {"home": ctx.form(hid), "away": ctx.form(aid)}
    payload["h2h"] = ctx.h2h(hid, aid)
    payload["injuries_known"] = injuries_known
    inj_rows = injuries or []
    players_by_team = players_by_team or {}
    eff_h = _inj_effect_rows(inj_rows, players_by_team, hid)
    eff_a = _inj_effect_rows(inj_rows, players_by_team, aid)
    adj = injury_adjustment(eff_h, eff_a)
    payload["injury_effect"] = {**{k: (round(v, 3) if isinstance(v, float) else v) for k, v in adj.items()},
                                "home_missing": eff_h, "away_missing": eff_a}
    payload["weather"] = weather
    odds = match.get("odds") or {}
    if not missing:
        lh0, la0 = gm.lambdas(hid, aid)
        lh, la = lh0 * adj["home_mult"], la0 * adj["away_mult"]
        mtx = score_matrix(lh, la, gm.rho)
        payload["lambdas"] = {"home": round(lh, 3), "away": round(la, 3), "base_home": round(lh0, 3),
                              "base_away": round(la0, 3), "rho": round(gm.rho, 4), "ht_ratio": round(gm.ht_ratio, 3)}
        payload["top_scores"] = most_likely_scores(mtx, 5)
        markets = goal_markets(mtx, lh, la, gm.ht_ratio)
        for stat, (mk, label) in STATS.items():
            cm = ctx.count_models.get(stat)
            if cm is None:
                postponed[mk] = f"{label}: ligde yeterli maç verisi yok — tahmin ertelendi"
                continue
            nh, na = cm.n_matches.get(hid, 0), cm.n_matches.get(aid, 0)
            if nh < min_n or na < min_n:
                postponed[mk] = f"{label}: takım verisi yetersiz ({nh}/{na} maç) — tahmin ertelendi"
                continue
            cmk, info = count_markets(cm, hid, aid)
            markets += cmk
            payload["count_info"][stat] = info
        payload["markets"] = [attach_odds(dict(m), odds) for m in markets]
    payload["quality"] = completeness(match, gm, ctx.count_models, injuries_known, lineups_known)
    min_c = getattr(settings, "completeness_min", 60.0)
    if not missing and payload["quality"]["score"] < min_c:
        eksik = [k for k, v in payload["quality"]["fields"].items() if v < 1]
        missing.append(f"tamlık puanı {payload['quality']['score']:.0f} < {min_c:.0f} (eksik: {', '.join(eksik)})")
    payload["missing"] = missing
    payload["ready"] = not missing
    payload["best_pick"] = select_single(payload, settings)
    from .scenarios import build_scenarios, narrative

    payload["scenarios"] = build_scenarios(payload) if payload["ready"] else []
    payload["narrative"] = narrative(match, payload)
    return payload


COMPLETENESS_WEIGHTS = {
    "Fikstür (takımlar, saat, durum)": 20, "Son maçlar (her iki takım ≥ 8)": 20, "Maç öncesi piyasa oranı": 15,
    "Sakat/cezalı listesi": 15, "Takım istatistik geçmişi (korner, kart, isabetli şut)": 15, "Hakem": 5,
    "Açıklanan ilk 11": 10,
}


def completeness(match: dict, gm, ctx_counts: dict, injuries_known: bool, lineups_known: bool) -> dict:
    """Tamlık = Σ(ağırlık × var_mı) / Σ ağırlık  (0–100). Kısmi alanlar 0–1 arası sayılır."""
    hid, aid = match["home_team_id"], match["away_team_id"]
    n_h = gm.n_matches.get(hid, 0) if gm else 0
    n_a = gm.n_matches.get(aid, 0) if gm else 0
    stats_ok = [1.0 if (cm and cm.has_team(hid, 4) and cm.has_team(aid, 4)) else 0.0
                for k, cm in ctx_counts.items() if k != "goal_kicks"]
    have = {
        "Fikstür (takımlar, saat, durum)": 1.0 if match.get("kickoff_at") and match.get("home_name") else 0.0,
        "Son maçlar (her iki takım ≥ 8)": min(1.0, min(n_h, n_a) / 8),
        "Maç öncesi piyasa oranı": 1.0 if (match.get("odds") or {}).get("1X2") else 0.0,
        "Sakat/cezalı listesi": 1.0 if injuries_known else 0.0,
        "Takım istatistik geçmişi (korner, kart, isabetli şut)": (sum(stats_ok) / len(stats_ok)) if stats_ok else 0.0,
        "Hakem": 1.0 if match.get("referee") else 0.0,
        "Açıklanan ilk 11": 1.0 if lineups_known else 0.0,
    }
    tot = sum(COMPLETENESS_WEIGHTS.values())
    score = 100 * sum(COMPLETENESS_WEIGHTS[k] * v for k, v in have.items()) / tot
    return {"score": round(score, 1), "fields": {k: round(v, 2) for k, v in have.items()},
            "weights": COMPLETENESS_WEIGHTS, "factor": round(0.85 + 0.15 * score / 100, 3),
            "provenance": match.get("sources") or {}}


def select_single(payload: dict, settings) -> dict | None:
    """Meclis Görüşü adayı: maç başına en güçlü TEK seçim (korelasyonlu çoklu seçimden kaçınmak için)."""
    if not payload.get("ready"):
        return None
    q = payload["quality"]["factor"]
    best, best_score = None, 0.0
    for m in payload["markets"]:
        if m["market"] == "CS":
            continue
        p = m["probability"]
        if m.get("odds"):
            if p < 0.40 or m["edge"] is None or m["edge"] < settings.value_edge_min or m["odds"] > 3.2:
                continue
            score = (p * q) * (1 + min(m["edge"], 0.25))
            kind = "değer"
        else:
            if not (settings.no_odds_min_prob <= p <= 0.86) or m["market"] == "DC":
                continue
            score = p * q * 0.97
            kind = "yüksek olasılık (piyasa oranı yok)"
        if score > best_score:
            best, best_score = dict(m, kind=kind), score
    if best:
        best["confidence"] = round(best_score, 4)
    return best
