"""Maç analizi: lig bağlamı (modeller + geçmiş), tüm pazarlar, senaryolar, anlatı ve veri kalitesi."""
from __future__ import annotations

from dataclasses import dataclass, field

from . import MODEL_VERSION
from .markets import attach_odds
from .model.counts import STATS, CountModel, count_markets, fit_count_model
from .model.elo import BLEND_WEIGHT, EloModel, blend, fit_elo
from .model.goals import GoalModel, fit_dixon_coles, goal_markets, lambdas_from_odds, most_likely_scores, score_matrix
from .model.injuries import injury_adjustment
from .timeutil import now_utc, parse_dt, to_iso


# Model girdisi YALNIZCA GÜNCEL sezondur (kullanıcı kuralı: "geçmiş sezon değil bu sezon genelinde").
# Geçmiş sezon maçları modele hiç girmez; sezon başında veri azsa piyasa oranı devreye girer (aşağıda).
# Takımın bu sezonki maç sayısı bundan azsa piyasa oranı (varsa) gol beklentisine yarı ağırlıkla katılır.
THIN_CURRENT = 3
LEAGUE_BASELINE = (1.45, 1.15)  # hiçbir model/oran yoksa (yalnızca bilgi; bu tabanla tahmin YAYIMLANMAZ)


def season_start(now=None):
    from datetime import datetime, timezone

    d = (now or now_utc()).date()
    y = d.year if d.month >= 7 else d.year - 1
    return datetime(y, 7, 1, tzinfo=timezone.utc)


@dataclass
class LeagueContext:
    league: str
    matches: list[dict]
    stats: dict[str, dict]
    goal_model: GoalModel | None = None
    elo_model: EloModel | None = None
    count_models: dict[str, CountModel | None] = field(default_factory=dict)
    error: str | None = None
    n_current: dict[str, int] = field(default_factory=dict)  # takım başına bu sezon oynanmış maç

    @classmethod
    def build(cls, league: str, matches: list[dict], stats: dict[str, dict],
              elo_priors: dict[str, float] | None = None) -> "LeagueContext":
        ctx = cls(league, matches, stats)
        now = now_utc()
        s0 = season_start(now)
        rows = []

        matches = [m for m in matches if parse_dt(m["kickoff_at"]) >= s0]
        ctx.matches = matches

        def wt(m):
            return 1.0

        for m in matches:
            if m.get("home_goals") is None:
                continue
            if parse_dt(m["kickoff_at"]) >= s0:
                for t in (m["home_team_id"], m["away_team_id"]):
                    ctx.n_current[t] = ctx.n_current.get(t, 0) + 1
            rows.append({"home": m["home_team_id"], "away": m["away_team_id"], "hg": m["home_goals"],
                         "ag": m["away_goals"], "hthg": m.get("ht_home_goals"), "htag": m.get("ht_away_goals"),
                         "days_ago": (now - parse_dt(m["kickoff_at"])).total_seconds() / 86400, "weight": wt(m)})
        try:
            ctx.goal_model = fit_dixon_coles(rows)
        except Exception as e:
            ctx.error = f"Gol modeli kurulamadı: {e}"
        try:
            ctx.elo_model = fit_elo(rows, elo_priors)
            if elo_priors:
                ctx.elo_model.source = "meclis-elo"
        except Exception:
            ctx.elo_model = None  # az maç: yalnızca Dixon-Coles
        for stat in STATS:
            crow = []
            for m in matches:
                st = stats.get(m["id"]) or {}
                h, a = st.get("home") or {}, st.get("away") or {}
                hv, av = _stat_value(h, stat), _stat_value(a, stat)
                if hv is None or av is None:
                    continue
                crow.append({"home": m["home_team_id"], "away": m["away_team_id"], "h": hv, "a": av,
                             "days_ago": (now - parse_dt(m["kickoff_at"])).total_seconds() / 86400, "weight": wt(m)})
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
                  weather: dict | None = None, lineups_known: bool = False, xi: dict | None = None) -> dict:
    """Her maç ve her pazar analiz edilir; eksik veri maçı ya da analizi DURDURMAZ (tamlık yalnızca güven
    göstergesidir). Gol beklentisi sırası: güncel sezon ağırlıklı Dixon-Coles + Elo → (takımın bu sezonki verisi
    azsa) piyasa oranıyla harmanlama → model yoksa piyasa oranından türetilen λ → hiçbiri yoksa lig tabanı
    (bu tabanla tahmin yayımlanmaz). Yayın kuralı select_single'dadır (değer kuralı)."""
    hid, aid = match["home_team_id"], match["away_team_id"]
    gaps, postponed = [], {}
    gm = ctx.goal_model
    payload: dict = {"match_id": match["id"], "model_version": MODEL_VERSION, "created_at": to_iso(now_utc()),
                     "home": match["home_name"], "away": match["away_name"], "kickoff_at": match["kickoff_at"],
                     "league": match["league"], "markets": [], "count_info": {}, "postponed_markets": postponed}
    nh_cur, na_cur = ctx.n_current.get(hid, 0), ctx.n_current.get(aid, 0)
    payload["current_season_matches"] = {"home": nh_cur, "away": na_cur}
    payload["model_matches"] = {"home": gm.n_matches.get(hid, 0) if gm else 0, "away": gm.n_matches.get(aid, 0) if gm else 0}
    payload["min_team_matches"] = settings.min_team_matches
    payload["form"] = {"home": ctx.form(hid), "away": ctx.form(aid)}
    payload["h2h"] = ctx.h2h(hid, aid)
    payload["injuries_known"] = injuries_known
    inj_rows = injuries or []
    players_by_team = players_by_team or {}
    xi = xi or {}
    eff_h = (xi.get("home") or {}).get("effect_rows")
    eff_a = (xi.get("away") or {}).get("effect_rows")
    eff_h = eff_h if eff_h is not None else _inj_effect_rows(inj_rows, players_by_team, hid)
    eff_a = eff_a if eff_a is not None else _inj_effect_rows(inj_rows, players_by_team, aid)
    adj = injury_adjustment(eff_h, eff_a)
    payload["injury_effect"] = {**{k: (round(v, 3) if isinstance(v, float) else v) for k, v in adj.items()},
                                "home_missing": eff_h, "away_missing": eff_a}
    if xi:
        payload["predicted_xi"] = {side: {k: v for k, v in (xi.get(side) or {}).items() if k != "effect_rows"}
                                   for side in ("home", "away")}
    payload["weather"] = weather
    odds = match.get("odds") or {}
    rho = gm.rho if gm else 0.0
    mkt = lambdas_from_odds(odds, rho) if odds.get("1X2") else None
    basis, dc, el = None, None, None
    if gm is not None:
        dc = gm.lambdas(hid, aid)
        el = ctx.elo_model.lambdas(hid, aid) if ctx.elo_model else None
        lh0, la0 = blend(dc, el)
        basis = "model (güncel sezon ağırlıklı Dixon-Coles" + (" + Elo)" if el else ")")
        if mkt and min(nh_cur, na_cur) < THIN_CURRENT:
            lh0, la0 = blend((lh0, la0), mkt, 0.5)
            basis += " + piyasa oranı (bu sezon verisi az)"
            gaps.append(f"bu sezon az maç ({nh_cur}/{na_cur}) — piyasa oranıyla güçlendirildi")
    elif mkt:
        lh0, la0 = mkt
        basis = "piyasa oranı (lig geçmişi yok)"
        gaps.append(ctx.error or "lig geçmişi yok — gol beklentisi piyasa oranından")
    else:
        lh0, la0 = LEAGUE_BASELINE
        basis = "lig tabanı"
        gaps.append((ctx.error or "lig geçmişi yok") + "; piyasa oranı da yok — yalnızca bilgi amaçlı")
    payload["basis"] = basis
    lh, la = lh0 * adj["home_mult"], la0 * adj["away_mult"]
    mtx = score_matrix(lh, la, rho)
    payload["lambdas"] = {"home": round(lh, 3), "away": round(la, 3), "base_home": round(lh0, 3),
                          "base_away": round(la0, 3), "rho": round(rho, 4),
                          "ht_ratio": round(gm.ht_ratio if gm else 0.44, 3),
                          "dc_home": round(dc[0], 3) if dc else None, "dc_away": round(dc[1], 3) if dc else None,
                          "market_home": round(mkt[0], 3) if mkt else None, "market_away": round(mkt[1], 3) if mkt else None,
                          "elo_weight": BLEND_WEIGHT if el else 0.0}
    if el and ctx.elo_model:
        payload["elo"] = {"home": round(ctx.elo_model.ratings[hid]), "away": round(ctx.elo_model.ratings[aid]),
                          "source": ctx.elo_model.source}
    payload["top_scores"] = most_likely_scores(mtx, 5)
    markets = goal_markets(mtx, lh, la, gm.ht_ratio if gm else 0.44)
    for stat, (mk, label) in STATS.items():
        cm = ctx.count_models.get(stat)
        if cm is None:
            postponed[mk] = f"{label}: ligde bu istatistiğin verisi yok — pazar hesaplanmadı"
            continue
        nh, na = cm.n_matches.get(hid, 0), cm.n_matches.get(aid, 0)
        if nh < 1 or na < 1:
            postponed[mk] = f"{label}: takımın bu istatistikte hiç maçı yok ({nh}/{na}) — pazar hesaplanmadı"
            continue
        cmk, info = count_markets(cm, hid, aid)  # az maçlı takım lig ortalamasına çekilir (büzülme)
        markets += cmk
        payload["count_info"][stat] = info
    payload["markets"] = [attach_odds(dict(m), odds) for m in markets]
    xi_ok = sum(1 for side in ("home", "away") if (xi.get(side) or {}).get("players"))
    payload["quality"] = completeness(match, gm, ctx.count_models, injuries_known, xi_ok / 2, nh_cur, na_cur)
    payload["missing"] = gaps  # bilgi amaçlı; analizi/yayını kapatmaz
    payload["ready"] = True
    payload["best_pick"] = select_single(payload, settings)
    from .scenarios import build_scenarios, narrative

    payload["scenarios"] = build_scenarios(payload)
    payload["narrative"] = narrative(match, payload)
    return payload


COMPLETENESS_WEIGHTS = {
    "Fikstür (takımlar, saat, durum)": 15, "Bu sezonki maçlar (her iki takım ≥ 6)": 25, "Maç öncesi piyasa oranı": 15,
    "Sakat/cezalı listesi": 15, "Takım istatistik geçmişi (korner, kart, isabetli şut)": 15, "Hakem": 5,
    "Meclis tahmini ilk 11": 10,
}


def completeness(match: dict, gm, ctx_counts: dict, injuries_known: bool, xi_share: float,
                 n_h: int = 0, n_a: int = 0) -> dict:
    """Tamlık = Σ(ağırlık × var_mı) / Σ ağırlık  (0–100). Kısmi alanlar 0–1 arası sayılır.
    YALNIZCA güven göstergesidir: tahmini durdurmaz, seçimde olasılığı hafifçe (0.85–1.0) çarpar."""
    hid, aid = match["home_team_id"], match["away_team_id"]
    stats_ok = [1.0 if (cm and cm.has_team(hid, 4) and cm.has_team(aid, 4)) else 0.0
                for k, cm in ctx_counts.items() if k != "goal_kicks"]
    have = {
        "Fikstür (takımlar, saat, durum)": 1.0 if match.get("kickoff_at") and match.get("home_name") else 0.0,
        "Bu sezonki maçlar (her iki takım ≥ 6)": min(1.0, min(n_h, n_a) / 6),
        "Maç öncesi piyasa oranı": 1.0 if (match.get("odds") or {}).get("1X2") else 0.0,
        "Sakat/cezalı listesi": 1.0 if injuries_known else 0.0,
        "Takım istatistik geçmişi (korner, kart, isabetli şut)": (sum(stats_ok) / len(stats_ok)) if stats_ok else 0.0,
        "Hakem": 1.0 if match.get("referee") else 0.0,
        "Meclis tahmini ilk 11": float(xi_share),
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
    model_based = str(payload.get("basis") or "").startswith("model")
    mm = payload.get("model_matches") or {}
    if model_based and min(mm.get("home", 0), mm.get("away", 0)) < payload.get("min_team_matches", 4):
        return None  # takım hakkında modelde hiç/az veri var: "değer" iddiası kurulamaz (sonraki çalışmada yeniden)
    ranked = rank_picks(payload, settings, model_based, q)
    return ranked[0] if ranked else None


# Seçim kuralı (kullanıcı: "hangi pazarda değer varsa maçın verisi söylesin; varsayılan pazar yok"):
#  * Bütün pazarlar adaydır (1X2, çifte şans, AH, gol A/Ü tüm çizgiler, KG, İY gol, takım golü, korner, kart,
#    isabetli şut, kale vuruşu). Sıralama OLASILIĞA göre değil DEĞERE göre yapılır.
#  * Kalibrasyon: model olasılığı piyasanın marjsız olasılığına doğru büzülür (p_kal = 0.65·p_model + 0.35·p_piyasa)
#    → modelin aşırı güveni değer gibi görünmez.
#  * Tekli için alt oran sınırı SINGLE_MIN_ODDS (1.50): 1.20'lik "kesin gibi" seçimler değer üretmez.
#  * Piyasa oranı olmayan pazarlarda değer ölçülemez: bu adaylar yalnızca bot bülteninde "adil oran" olarak görünür
#    (adil oran ≥ 1.50 ve p ≥ 0.55), arşive (Meclis Görüşü) girmez.
SINGLE_MIN_ODDS = 1.50
SINGLE_MAX_ODDS = 5.00
CAL_W = 0.65


def _market_implied(markets: list[dict]) -> dict:
    groups: dict = {}
    for m in markets:
        if m.get("odds") and m["odds"] > 1:
            ln = m.get("line")
            if m["market"] == "AH" and ln is not None:
                ln = ln if m["selection"] == "1" else -ln  # aynı handikap çizgisinin iki tarafı
            groups.setdefault((m["market"], ln), []).append(m)
    out = {}
    for _, ms in groups.items():
        inv = sum(1 / x["odds"] for x in ms)
        if len(ms) >= 2 and inv > 0:
            k = 2.0 if ms[0]["market"] == "DC" else 1.0  # çifte şans tarafları toplamı 2'dir
            for x in ms:
                out[(x["market"], x["selection"], x.get("line"))] = k * (1 / x["odds"]) / inv
    return out


def slate_bias(payloads: list[dict], min_n: int = 20) -> dict:
    """Bültendeki maçlarda model − piyasa (marjsız) olasılık farkının ortalaması, pazar/seçim/çizgi başına."""
    acc: dict = {}
    for p in payloads:
        imp = _market_implied(p.get("markets") or [])
        for m in p.get("markets") or []:
            k = (m["market"], m["selection"], m.get("line"))
            if k in imp:
                acc.setdefault(f"{k[0]}|{k[1]}|{k[2]}", []).append(m["probability"] - imp[k])
    return {k: round(sum(v) / len(v), 4) for k, v in acc.items() if len(v) >= min_n}


def rank_picks(payload: dict, settings, model_based: bool | None = None, q: float | None = None) -> list[dict]:
    """Maçın bütün pazarlarındaki adaylar, değere göre sıralı (en iyisi başta)."""
    if q is None:
        q = payload["quality"]["factor"]
    if model_based is None:
        model_based = str(payload.get("basis") or "").startswith("model")
    implied = _market_implied(payload["markets"])
    edge_min = getattr(settings, "value_edge_min", 0.03)
    value, fair = [], []
    bias = payload.get("bias") or {}
    for m in payload["markets"]:
        if m["market"] == "CS":
            continue
        p = m["probability"]
        o = m.get("odds")
        if o:
            # bülten genelinde modelin piyasadan sistematik sapması (ör. hep "alt"a kayma) düzeltilir
            p = min(0.99, max(0.01, p - bias.get(f"{m['market']}|{m['selection']}|{m.get('line')}", 0.0)))
            pm = implied.get((m["market"], m["selection"], m.get("line")))
            w = payload.get("cal_w", CAL_W)
            pc = w * p + (1 - w) * pm if pm else p
            edge = pc * o - 1
            if not (SINGLE_MIN_ODDS <= o <= SINGLE_MAX_ODDS) or pc < 0.30 or edge < edge_min:
                continue
            score = edge * q
            value.append(dict(m, kind="değer", probability_model=round(p, 4), probability=round(pc, 4),
                              edge=round(edge, 4), confidence=round(score, 4)))
        elif model_based and m["market"] != "DC":
            fo = 1 / p if p > 0 else 99
            if p < 0.55 or fo < SINGLE_MIN_ODDS:
                continue
            fair.append(dict(m, kind="adil oran (piyasa oranı yok)", confidence=round(p * q * 0.25, 4)))
    value.sort(key=lambda x: -x["confidence"])
    fair.sort(key=lambda x: -x["confidence"])
    return value + fair
