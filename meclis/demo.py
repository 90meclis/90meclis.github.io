"""ÖRNEK VERİ modu (DEMO_MODE=1).

Buradaki tüm takımlar, maçlar, oranlar ve geçmiş tahminler UYDURMADIR; yalnızca arayüzü anahtarsız ve
internetsiz denemek içindir. Bellekte ayrı bir veritabanında tutulur, gerçek veriyle asla karışmaz.
Arayüz bu moddayken her sayfada "ÖRNEK VERİ" uyarısı gösterir.
"""
from __future__ import annotations

import uuid
from datetime import timedelta

import numpy as np

from .store import _SQLITE_SCHEMA, SQLiteStore
from .timeutil import now_utc, to_iso

DEMO_TEAMS = [f"Örnek {n}" for n in ("Kartal", "Aslan", "Kanarya", "Fırtına", "Martı", "Timsah", "Şimşek",
                                        "Boğa", "Kurt", "Yunus", "Akrep", "Pars")]


def _settings():
    from .config import Settings

    return Settings(leagues=["DEMO"], demo_mode=True)


def build_demo_store(seed: int = 90) -> SQLiteStore:
    from .bot import Bot
    from .pool import DataPool, merge_records
    from .settlement import run_settlement

    rng = np.random.default_rng(seed)
    store = SQLiteStore(":memory:")
    store.label = "ÖRNEK VERİ (bellek içi)"
    s = _settings()
    att = {t: rng.normal(0, 0.25) for t in DEMO_TEAMS}
    dfn = {t: rng.normal(0, 0.2) for t in DEMO_TEAMS}
    crn = {t: rng.normal(5, 1.0) for t in DEMO_TEAMS}
    now = now_utc().replace(minute=0, second=0)
    recs = []
    day = 320
    for _ in range(2):
        for h in DEMO_TEAMS:
            for a in DEMO_TEAMS:
                if h == a:
                    continue
                day -= 1.15
                ko = now - timedelta(days=max(3.0, day))
                lh = np.exp(0.12 + 0.25 + att[h] - dfn[a])
                la = np.exp(0.12 + att[a] - dfn[h])
                hg, ag = int(rng.poisson(lh)), int(rng.poisson(la))
                hh, ha = int(rng.binomial(hg, 0.45)), int(rng.binomial(ag, 0.45))
                recs.append({
                    "source": "örnek", "league": "DEMO", "kickoff_at": to_iso(ko), "home_name": h, "away_name": a,
                    "status": "bitti", "home_goals": hg, "away_goals": ag, "ht_home_goals": hh, "ht_away_goals": ha,
                    "referee": "Örnek Hakem", "venue": "Örnek Stadyum",
                    "stats": {"home": {"shots": int(rng.poisson(13 * lh)), "shots_on_target": int(rng.poisson(4.5 * lh)),
                                       "corners": int(rng.poisson(max(1, crn[h]))), "yellow": int(rng.poisson(2.0)),
                                       "red": int(rng.random() < 0.05), "fouls": int(rng.poisson(12))},
                              "away": {"shots": int(rng.poisson(11 * la)), "shots_on_target": int(rng.poisson(4 * la)),
                                       "corners": int(rng.poisson(max(1, crn[a] - 1))), "yellow": int(rng.poisson(2.3)),
                                       "red": int(rng.random() < 0.06), "fouls": int(rng.poisson(13))}},
                })
    order = list(DEMO_TEAMS)
    rng.shuffle(order)
    for i in range(6):
        h, a = order[2 * i], order[2 * i + 1]
        ko = now + timedelta(hours=3 + 4 * i)
        lh = np.exp(0.12 + 0.25 + att[h] - dfn[a])
        la = np.exp(0.12 + att[a] - dfn[h])
        from .model.goals import goal_markets, score_matrix

        mk = {(m["market"], m["selection"], m["line"]): m["probability"] for m in goal_markets(score_matrix(lh, la), lh, la)}

        def price(p):
            return round(max(1.05, 1 / (p * 1.06) * rng.uniform(0.95, 1.08)), 2)

        recs.append({"source": "örnek", "league": "DEMO", "kickoff_at": to_iso(ko), "home_name": h, "away_name": a,
                     "status": "planlandi", "venue": "Örnek Stadyum",
                     "odds": {"1X2": {"1": price(mk[("1X2", "1", None)]), "X": price(mk[("1X2", "X", None)]),
                                      "2": price(mk[("1X2", "2", None)]), "src": "örnek"},
                              "OU_GOALS_2.5": {"ÜST": price(mk[("OU_GOALS", "ÜST", 2.5)]),
                                               "ALT": price(mk[("OU_GOALS", "ALT", 2.5)]), "src": "örnek"}}})
    pool = DataPool(store, s)
    pool.save(merge_records(recs))
    _seed_past_predictions(store, rng)
    run_settlement(store, now=now)
    bot = Bot(store, s, pool)
    bot.run(record=True, fetch_extras=False)
    store.upsert("agenda", [{
        "id": f"demo{i}", "title": t, "link": "https://example.com/ornek-haber", "source": "ÖRNEK VERİ",
        "published_at": to_iso(now - timedelta(hours=i + 1)), "summary": "Bu haber örnek veridir, gerçek değildir.",
        "category": c, "team_ids": [], "match_ids": [], "fetched_at": to_iso(now)} for i, (t, c) in enumerate([
            (f"{order[0]} golcüsü sakatlandı (örnek haber)", "sakatlık"),
            (f"{order[3]} yeni teknik direktörünü açıkladı (örnek haber)", "teknik direktör"),
            (f"{order[5]} kiralık stoper transferini bitirdi (örnek haber)", "transfer")])])
    from .news import link_news

    upcoming = store.select("matches", [("status", "eq", "planlandi")])
    rows = link_news(store.select("agenda"), upcoming)
    store.upsert("agenda", rows)
    return store


def _seed_past_predictions(store: SQLiteStore, rng) -> None:
    """Güven Panosu'nun boş görünmemesi için GEÇMİŞE dönük örnek kayıtlar (yalnızca örnek modda,
    tetikleyiciler geçici olarak kapatılarak). Gerçek modda bu mümkün değildir."""
    store.conn.executescript("drop trigger if exists predictions_bi; drop trigger if exists predictions_ai;")
    past = store.select("matches", [("status", "eq", "bitti")], order="kickoff_at", desc=True, limit=60)
    rows = []
    for m in past:
        if rng.random() < 0.5:
            continue
        choice = rng.integers(0, 3)
        market, sel, line, p = [("OU_GOALS", "ÜST", 2.5, rng.uniform(.5, .66)), ("1X2", "1", None, rng.uniform(.45, .62)),
                                ("BTTS", "VAR", None, rng.uniform(.5, .64))][choice]
        odds = round(1 / p * rng.uniform(1.0, 1.12), 2)
        rows.append({"id": str(uuid.uuid4()), "match_id": m["id"],
                     "kickoff_at": m["kickoff_at"], "league": "DEMO", "home_name": m["home_name"],
                     "away_name": m["away_name"], "tag": "meclis_gorusu", "market": market, "selection": sel,
                     "line": line, "probability": round(p, 4), "odds": odds, "odds_source": "örnek",
                     "fair_odds": round(1 / p, 3), "edge": round(p * odds - 1, 4), "confidence": round(p, 4),
                     "stake": 1, "rationale": "ÖRNEK VERİ", "model_version": "örnek", "status": "bekliyor"})
    store.insert("predictions", rows)
    # örnek kayıtların kayıt zamanı: maçtan 1 gün önce (yalnızca örnek mod)
    store.conn.execute("update predictions set recorded_at = strftime('%Y-%m-%dT%H:%M:%S+00:00', kickoff_at, '-1 day') "
                       "where recorded_at is null")
    store.conn.executescript(_SQLITE_SCHEMA)  # tetikleyicileri geri kur
