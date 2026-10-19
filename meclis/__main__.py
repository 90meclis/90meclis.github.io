"""Komut satırı: python -m meclis <komut>

  yenile [--gecmis]   Veri havuzunu yenile (--gecmis: iki sezonluk sonuç + istatistik CSV'leri)
  gundem              Sabah haber taraması ve maçlara bağlama
  bot [--kuru]        Tahmin botu (--kuru: deftere yazmadan analiz)
  sonuclandir         Biten maçların tahmin/kuponlarını sonuçlandır
  kadro [--zorla]     Güncel kadrolar (Wikipedia + BSD) ve yaklaşan maçların sakat/cezalı + ilk 11 listesi
  gecmis              API-Football ücretsiz plan (2022–2024) geçmiş veri doldurma; günlük bütçe içinde, devam eder
  sabah               yenile --gecmis + gundem + kadro + bot + sonuclandir
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
                                        "gecmis"])
    ap.add_argument("--zorla", action="store_true", help="kadro: 7 günlük önbelleği yok say")
    ap.add_argument("--saat", type=float, default=168, help="kadro: kaç saat sonrasına kadarki maçlar (varsayılan 168 = 7 gün)")
    ap.add_argument("--gecmis", action="store_true", help="geçmiş sezon verisini de çek")
    ap.add_argument("--kuru", action="store_true", help="bot: kayda yazmadan çalıştır")
    ap.add_argument("--ligler", help="virgülle lig kodları (ör. T1,E0)")
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
    if a.komut in ("yenile", "sabah") and not s.demo_mode:
        r = pool.refresh(history=a.gecmis or a.komut == "sabah")
        out_logs += r["log"] + [f"Havuz: {r['records']} kaynak kaydı → {r['matches']} birleşik maç"]
        pool.log.clear()
    if a.komut in ("gundem", "sabah") and not s.demo_mode:
        out_logs += scan_news(store, s)["log"]
    if a.komut in ("kadro", "sabah") and not s.demo_mode:
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
    if a.komut == "gecmis" and not s.demo_mode:
        from .backfill import Backfill

        out_logs += Backfill(pool).run()["log"]
    if a.komut in ("bot", "sabah"):
        r = Bot(store, s, pool).run(record=not a.kuru)
        out_logs += r["log"]
    if a.komut in ("sonuclandir", "sabah"):
        if a.komut == "sonuclandir" and not s.demo_mode:
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


if __name__ == "__main__":
    sys.exit(main())
