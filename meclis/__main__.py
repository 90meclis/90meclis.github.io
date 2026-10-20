"""Komut satırı: python -m meclis <komut>

  yenile [--gecmis]   Veri havuzunu yenile (--gecmis: iki sezonluk sonuç + istatistik CSV'leri)
  gundem              Sabah haber taraması ve maçlara bağlama
  bot [--kuru]        Tahmin botu (--kuru: deftere yazmadan analiz)
  sonuclandir         Biten maçların tahmin/kuponlarını sonuçlandır
  kadro [--zorla]     Güncel kadrolar (Wikipedia + BSD) ve yaklaşan maçların sakat/cezalı + ilk 11 listesi
  gecmis              Gece: BU SEZONUN eksikleri (API-Football fikstür kimliğiyle + BSD sezon işi); geçmiş sezon çekilmez
  sezon               BSD: bu sezonun oyuncu dakikaları / resmî ilk 11 / maç istatistikleri
  analiz              Yaklaşan 7 günün her maçının tam analizini yenile (tahmin/kupon yazmaz)
  yedek [--cikti]     predictions/coupons/matches/odds_snapshots/leagues JSON+CSV
  gunici              yenile + kadro + bot + sonuclandir + KAÇIRILAN adımların telafisi (gündem, sezon, gece doldurma)
  sabah               yenile (bu sezon CSV) + gundem + kadro + bot + sezon + sonuclandir
  durum               Depo ve kaynak durumunu yazdır
"""
from __future__ import annotations

import argparse
import sys

from .config import load_settings
from .store import get_store


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m meclis", description="90 Meclis komut satırı")
    ap.add_argument("komut", choices=["yenile", "gundem", "bot", "sonuclandir", "sabah", "durum", "kadro",
                                        "gecmis", "analiz", "sezon", "yedek", "gunici"])
    ap.add_argument("--zorla", action="store_true", help="kadro: 7 günlük önbelleği yok say")
    ap.add_argument("--saat", type=float, default=168, help="kadro: kaç saat sonrasına kadarki maçlar (varsayılan 168 = 7 gün)")
    ap.add_argument("--gecmis", action="store_true", help="geçmiş sezon verisini de çek")
    ap.add_argument("--geri", type=int, help="yenile: kaç gün geriye (varsayılan 3; 0 = sezon başından bugüne)")
    ap.add_argument("--kuru", action="store_true", help="bot: kayda yazmadan çalıştır")
    ap.add_argument("--ligler", help="virgülle lig kodları (ör. T1,E0)")
    ap.add_argument("--cikti", help="yedek: çıktı klasörü (varsayılan ./yedek)")
    a = ap.parse_args(argv)
    s = load_settings()
    if a.ligler:
        s.leagues = [x.strip().upper() for x in a.ligler.split(",") if x.strip()]
    store = get_store(s)
    print(f"Depo: {store.label} | Ligler: {', '.join(s.leagues)}" + (" | ÖRNEK VERİ MODU" if s.demo_mode else ""))
    if not s.supabase_enabled and not s.demo_mode:
        print("UYARI: SUPABASE_URL/SUPABASE_KEY yok — yerel SQLite kullanılıyor (kalıcı paylaşım yok).")
    from .bot import Bot
    from .news import scan_news
    from .pool import DataPool
    from .settlement import run_settlement

    pool = DataPool(store, s)
    out_logs: list[str] = []
    STEPS = {"sabah": {"yenile_s", "gundem", "kadro", "bot", "sezon", "sonuclandir"},
             "gunici": {"yenile", "kadro", "bot", "sonuclandir"}, "gecmis": {"gecmis", "sezon"}}
    steps = set(STEPS.get(a.komut, {a.komut}))
    if a.komut == "yenile" and a.gecmis:
        steps = {"yenile_s"}
    if a.komut == "gunici" and not s.demo_mode:
        # Kaçırılan / geç kalan zamanlanmış işlerin telafisi: son başarılı çalışması eskiyse bu çalışmada yapılır.
        for step, hours in (("gundem", 26), ("sezon", 30), ("gecmis", 30), ("yedek", 30)):
            if _overdue(store, step, hours):
                steps.add(step)
                out_logs.append(f"ℹ️ telafi: '{step}' son {hours} saatte çalışmamış — bu çalışmada yapılıyor")
    if not a.ligler:
        from .leagues import discover

        new = discover(store, s, pool.bsd)
        pool.bsd._leagues = None  # lig eşlemesi yeni liglerle yeniden kurulsun
        if new:
            out_logs.append(f"ℹ️ ligler: çekirdek {len(s.leagues) - len(new)} + kaynaklardan keşfedilen {len(new)} lig")
    if steps & {"yenile", "yenile_s"} and not s.demo_mode:
        back = 3
        if a.geri is not None:
            from .analysis import season_start
            from .timeutil import now_utc

            back = a.geri if a.geri > 0 else (now_utc().date() - season_start().date()).days + 1
            pool.bsd.max_calls = max(pool.bsd.max_calls, 5000)  # sezon taraması: BSD günlük kota 7.500
        r = pool.refresh(days_back=back, history="yenile_s" in steps or a.geri is not None)
        out_logs += r["log"] + [f"Havuz: {r['records']} kaynak kaydı → {r['matches']} birleşik maç"]
        pool.log.clear()
    if "gundem" in steps and not s.demo_mode:
        out_logs += scan_news(store, s)["log"]
        _done(store, "gundem")
    if "kadro" in steps and not s.demo_mode:
        sq = pool.news.refresh_squads(force=a.zorla)
        out_logs.append(f"Kadro: {sq['due']}/{sq['teams']} takım yenilendi (Wikipedia {sq['wikipedia']}, BSD {sq['bsd']}), "
                        f"{sq['players']} oyuncu, {sq['with_stats']} oyuncuda geçmiş istatistik"
                        + (f"; kadrosu bulunamayan: {', '.join(sq['failed'][:8])}" if sq["failed"] else ""))
        tn = pool.news.run_upcoming(hours_ahead=a.saat)
        out_logs.append(f"Takım haberleri: {tn['matches']} maç, {tn['injury_known']} maçta eksik listesi, "
                        f"{tn['injury_rows']} eksik kaydı, ilk 11: {tn['lineups_confirmed']} resmî / "
                        f"{tn['lineups_predicted']} tahmini taraf")
        out_logs += pool.log
        pool.log.clear()
    if "gecmis" in steps and not s.demo_mode:
        from .backfill import Backfill
        from .analysis import season_start
        from .timeutil import now_utc

        # gece: bu sezonun oynanmış bütün maçları (BSD lig listeleri + football-data.co.uk sezon CSV'leri) —
        # havuzda olan istatistik/hakem/stadyum yeniden istenmez, yalnızca boşluk dolar
        pool.bsd.max_calls = max(pool.bsd.max_calls, 3000)
        pool.refresh(days_back=(now_utc().date() - season_start().date()).days + 1, days_ahead=7, history=True)

        out_logs += Backfill(pool).run()["log"]
        _done(store, "gecmis")
    if "bot" in steps:
        r = Bot(store, s, pool).run(record=not a.kuru)
        out_logs += r["log"]
    if "sezon" in steps and not s.demo_mode:
        from .season import SeasonFill

        cap = {"sabah": 400, "gunici": 300}.get(a.komut, 1500)  # BSD günlük kota 7.500
        pool.bsd.max_calls = max(pool.bsd.max_calls, pool.bsd.calls + cap)
        out_logs += SeasonFill(pool, max_calls=cap).run()["log"]
        _done(store, "sezon")
    if "yedek" in steps:
        if a.komut == "gunici":  # telafi: yedeği iş akışının 'backups' adımı yazar (bayrak dosyası)
            open("/tmp/meclis_yedek_gerekli", "w").write("1")
        else:
            from .backup import export_all

            out_logs += export_all(store, a.cikti or "yedek")["log"]
            _done(store, "yedek")
    if a.komut == "analiz":  # tüm maçların analizini yenile; tahmin/kupon yazmaz
        r = Bot(store, s, pool).run(record=not a.kuru, publish=False)
        out_logs += r["log"]
    if "sonuclandir" in steps:
        if a.komut in ("sonuclandir", "gunici") and not s.demo_mode:
            pool.refresh(days_back=5, days_ahead=0, history=True)
        out_logs += run_settlement(store, pool)["log"]
    if a.komut == "durum":
        for st in store.select("source_status", order="source"):
            if not st["source"].startswith(("injuries:", "gecmis:", "api-football:tarih:")):
                print(f"  {st['source']}: {'OK' if st['ok'] else 'SORUN'} — {st['message']} ({st['updated_at']})")
        print(f"  maç: {len(store.select('matches'))}, tahmin: {len(store.select('predictions'))}, "
              f"oyuncu: {len(store.select('players'))}, sakat/cezalı: {len(store.select('injuries'))}, "
              f"ilk 11: {len(store.select('lineups'))}")
        from .coverage import format_coverage, upcoming_coverage

        print("  Önümüzdeki 7 günün kapsamı (maç sayısı / ilgili alanı dolu maç sayısı):")
        for line in format_coverage(upcoming_coverage(store, s.leagues)):
            print("   ", line)
    for line in out_logs:
        print(line)
    return 0


def _overdue(store, step: str, hours: float) -> bool:
    from datetime import timedelta

    from .timeutil import now_utc, parse_dt

    try:
        st = store.get("source_status", source=f"adim:{step}")
    except Exception:
        return False
    return not st or not st.get("updated_at") or now_utc() - parse_dt(st["updated_at"]) > timedelta(hours=hours)


def _done(store, step: str) -> None:
    try:
        store.set_source_status(f"adim:{step}", True, "son başarılı çalışma")
    except Exception:
        pass


if __name__ == "__main__":
    sys.exit(main())
