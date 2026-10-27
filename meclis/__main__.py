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
                                        "gecmis", "analiz", "sezon", "yedek", "gunici", "yayin", "yerel", "geritest", "muhur", "simulasyon"])
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
    from .sources.bsd import BsdBudget

    def _bsd_ledger_load():
        try:
            from .timeutil import now_utc as _n

            row = store.get("source_status", source="bsd:kota") or {}
            BsdBudget.used_before = int(row.get("calls_today") or 0) if row.get("calls_date") == _n().date().isoformat() else 0
        except Exception:
            BsdBudget.used_before = 0

    _bsd_ledger_load()
    try:  # saatlik pay: kalan günlük kota / kalan saat (×2 esneklik); tek çalışma günü bitiremez
        from .timeutil import now_utc as _n2

        _share = BsdBudget.remaining() / max(1, 24 - _n2().hour)
        pool.bsd.max_calls = int(min(pool.bsd.max_calls, max(150, 2 * _share), BsdBudget.remaining()))
    except Exception:
        pass
    _bsd_logged = [0]

    def _bsd_ledger_flush():
        """Bu çalışmanın BSD isteklerini günlük deftere ekler (adım adım: iptal olsa da kayıt kalır)."""
        try:
            delta = pool.bsd.calls - _bsd_logged[0]
            if BsdBudget.exhausted:
                delta = max(delta, BsdBudget.DAILY + 200 - BsdBudget.used_before - _bsd_logged[0])
            if delta > 0:
                _bsd_logged[0] += delta
                store.set_source_status("bsd:kota", not BsdBudget.exhausted,
                                        f"günlük kota defteri (UTC): bu çalışmada +{delta}; kalan ≈ "
                                        f"{BsdBudget.remaining(pool.bsd.calls)}", add_calls=delta)
        except Exception:
            pass
    out_logs = _LiveLog()
    # İŞ DÜZENİ (her biri ayrı iş akışı, ayrı zaman bütçesi — biri yavaşlarsa yayın beklemez):
    #   yayin       : fikstür/oran (bugün+yarın+2 gün) → eksik/ilk 11 (48 saat) → analiz + seçim + kilit → mühür
    #   sonuclandir : biten maçlar, kapanış oranı (CLV)
    #   gundem      : haber taraması
    #   gecmis      : gece ağır işleri (sezon doldurma, yerel lig, geri test, simülasyon) — kaldığı yerden devam eder
    STEPS = {"sabah": ["yenile", "gundem", "kadro", "bot", "sonuclandir"],
             "gunici": ["yenile", "kadro", "bot", "kadro_s", "sonuclandir"],
             "yayin": ["yenile", "kadro", "bot", "kadro_s"],
             "gecmis": ["gecmis", "yerel", "sezon", "geritest", "simulasyon", "muhur"],
             "analiz": ["analiz"]}
    steps = list(STEPS.get(a.komut, [a.komut]))
    if a.komut == "yenile" and a.gecmis:
        steps = ["yenile_s"]
    # adım başına zaman bütçesi (saniye) — aşılırsa adım kesilir, sonraki adımlar yine çalışır
    BUDGET = {"kesif": 180, "yenile": 600, "yenile_s": 1800, "kadro": 600, "kadro_s": 600, "bot": 1500, "gundem": 1200, "gecmis": 2400,
              "yerel": 900, "sezon": 1500, "geritest": 600, "simulasyon": 900, "muhur": 300, "sonuclandir": 1200,
              "analiz": 2400, "yedek": 600}
    is_adi = a.komut
    state = {"failed": []}

    def run(step, fn):
        import signal
        import time as _t

        t0 = _t.monotonic()
        budget = int(BUDGET.get(step, 900) * float(__import__("os").environ.get("MECLIS_BUTCE_CARPAN", "1")))
        print(f"▶ {step} (bütçe {budget} sn)", flush=True)

        def _alarm(*_):
            raise _StepTimeout(f"{step}: {budget} sn bütçe aşıldı")

        old = signal.signal(signal.SIGALRM, _alarm)
        signal.alarm(budget)
        ok, msg = True, "tamam"
        try:
            fn()
        except (Exception, _StepTimeout) as e:  # bir adımın düşmesi diğerlerini durdurmaz
            import traceback

            ok, msg = False, f"{type(e).__name__}: {e}"[:400]
            out_logs.append(f"⚠️ {step} başarısız: {msg}")
            traceback.print_exc()
            state["failed"].append(step)
        finally:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old)
        dt = _t.monotonic() - t0
        _bsd_ledger_flush()
        print(f"■ {step}: {'OK' if ok else 'HATA'} {dt:.0f} sn (BSD bu çalışmada {pool.bsd.calls}, "
              f"bugün kalan ≈ {BsdBudget.remaining(pool.bsd.calls)})", flush=True)
        try:
            store.set_source_status(f"is:{is_adi}:{step}", ok, f"{dt:.0f} sn — {msg}")
            if ok:
                _done(store, step)
        except Exception:
            pass

    if s.demo_mode:
        steps = [x for x in steps if x in ("bot", "sonuclandir", "durum", "analiz")]

    def kesif():
        from .leagues import discover

        new = discover(store, s, pool.bsd)
        pool.bsd._leagues = None  # lig eşlemesi yeni liglerle yeniden kurulsun
        if new:
            out_logs.append(f"ℹ️ ligler: çekirdek {len(s.leagues) - len(new)} + kaynaklardan keşfedilen {len(new)} lig")

    def yenile():
        back = 3
        if a.geri is not None:
            from .analysis import season_start
            from .timeutil import now_utc

            back = a.geri if a.geri > 0 else (now_utc().date() - season_start().date()).days + 1
            pool.bsd.max_calls = pool.bsd.calls + min(5000, BsdBudget.heavy_cap(pool.bsd.calls))
        ahead = 7 if a.komut in ("gecmis", "yenile") else 3  # yayın işi: bugün + 2 gün (hız)
        r = pool.refresh(days_back=back, days_ahead=ahead, history="yenile_s" in steps or a.geri is not None)
        out_logs.extend(r["log"] + [f"Havuz: {r['records']} kaynak kaydı → {r['matches']} birleşik maç"])
        pool.log.clear()

    def gundem():
        out_logs.extend(scan_news(store, s)["log"])

    def kadro():
        hours = a.saat if a.komut == "kadro" else 48
        tn = pool.news.run_upcoming(hours_ahead=hours)
        out_logs.append(f"Takım haberleri: {tn['matches']} maç, {tn['injury_known']} maçta eksik listesi, "
                        f"ilk 11: {tn['lineups_confirmed']} resmî / {tn['lineups_predicted']} tahmini taraf")
        out_logs.extend(pool.log)
        pool.log.clear()
        if a.komut == "kadro":
            kadro_s()

    def kadro_s():  # kadro önbelleği (Wikipedia + BSD); yayından SONRA, kalan süreyle
        sq = pool.news.refresh_squads(force=a.zorla, max_teams=400 if a.komut == "kadro" else 80)
        out_logs.append(f"Kadro: {sq['due']}/{sq['teams']} takım yenilendi (Wikipedia {sq['wikipedia']}, BSD {sq['bsd']}), "
                        f"{sq['players']} oyuncu")
        out_logs.extend(pool.log)
        pool.log.clear()

    def gecmis():
        from .analysis import season_start
        from .backfill import Backfill
        from .timeutil import now_utc

        pool.bsd.max_calls = pool.bsd.calls + min(3000, BsdBudget.heavy_cap(pool.bsd.calls))
        pool.refresh(days_back=(now_utc().date() - season_start().date()).days + 1, days_ahead=7, history=True)
        out_logs.extend(Backfill(pool).run()["log"])

    def yerel():
        from .domestic import DomesticTrack

        r = DomesticTrack(store, s, s.api_football_key, max_apif=40).run(hours=60)
        out_logs.extend(r["log"] + [f"ℹ️ yerel lig: {len(r['resolved'])} takım çözüldü, çözülemeyen: "
                                    f"{', '.join(r['missing']) or 'yok'} ({r['apif_calls']} API-Football isteği)"])

    def geritest():
        from .backtest import run_backtest

        from .motor import run as motor_run

        try:  # öğrenen isabet motoru (korumalı): w + izotonik kalibrasyon + seçim kuralının bant geri testi
            motor_run(store, out_logs)
        except Exception as e:
            out_logs.append(f"⚠️ motor: {e}")
        r = run_backtest(store)
        out_logs.append(f"ℹ️ geri test: {r['rows']} tahmin; " + "; ".join(
            f"{x['market']}: n={x['n']} LL model {x['ll_model']} / piyasa {x['ll_market']} (w*={x['w_opt']})"
            for x in r["markets"]))

    def bot():
        r = Bot(store, s, pool).run(record=not a.kuru)
        out_logs.extend(r["log"])

    def sezon():
        from .gapstats import GapStats
        from .season import SeasonFill

        cap = min(1500, BsdBudget.heavy_cap(pool.bsd.calls))  # saatlik yayın payı (RESERVE) korunur
        pool.bsd.max_calls = max(pool.bsd.max_calls, pool.bsd.calls + cap)
        out_logs.extend(SeasonFill(pool, max_calls=cap).run()["log"])
        try:
            out_logs.extend(GapStats(pool).run()["log"])
        except Exception as e:
            out_logs.append(f"⚠️ ek istatistik: {e}")

    def simulasyon():
        from .config import LEAGUES
        from .simulasyon import simulate_league

        b = Bot(store, s, pool)
        n_sim = 0
        for lg in s.leagues:
            if LEAGUES.get(lg) and LEAGUES[lg].cup:
                continue
            try:
                rows = simulate_league(b.context(lg))
                if rows:
                    store.upsert("sezon_simulasyonu", rows)
                    n_sim += 1
            except Exception as e:
                out_logs.append(f"⚠️ simülasyon {lg}: {e}")
        out_logs.append(f"ℹ️ sezon simülasyonu: {n_sim} lig × 10.000 koşu")

    def muhur():
        from datetime import timedelta as _td

        from .muhur import seal_all, write_manifest
        from .paylasim import build_drafts
        from .timeutil import now_utc as _now

        r = seal_all(store)
        out_logs.append(f"ℹ️ Kanıt Mührü: {r['yeni']} yeni mühür, toplam {r['toplam']}, kök {str(r['kok'])[:16]}…")
        if a.komut in ("muhur", "gecmis"):
            out_logs.append(f"ℹ️ mühür manifestosu: {write_manifest(store, a.cikti or 'muhur')['kayit']} kayıt")
        lo = _now() - _td(hours=6)
        out_logs.append(f"ℹ️ paylaşım taslağı: {build_drafts(store, lo.isoformat(), (lo + _td(hours=48)).isoformat())}")

    def yedek():
        from .backup import export_all

        out_logs.extend(export_all(store, a.cikti or "yedek")["log"])

    def analiz():
        r = Bot(store, s, pool).run(record=not a.kuru, publish=False)
        out_logs.extend(r["log"])

    def sonuclandir():
        if a.komut in ("sonuclandir", "gunici") and not s.demo_mode:
            pool.refresh(days_back=7, days_ahead=0, history=True)
        out_logs.extend(run_settlement(store, pool)["log"])

    def durum():
        for st in store.select("source_status", order="source"):
            if not st["source"].startswith(("injuries:", "gecmis:", "api-football:tarih:")):
                print(f"  {st['source']}: {'OK' if st['ok'] else 'SORUN'} — {st['message']} ({st['updated_at']})")

    FN = {"kadro_s": kadro_s, "yenile": yenile, "yenile_s": yenile, "gundem": gundem, "kadro": kadro, "gecmis": gecmis, "yerel": yerel,
          "geritest": geritest, "bot": bot, "sezon": sezon, "simulasyon": simulasyon, "muhur": muhur, "yedek": yedek,
          "analiz": analiz, "sonuclandir": sonuclandir, "durum": durum}
    if not a.ligler and not s.demo_mode and any(x in steps for x in ("yenile", "yenile_s", "gecmis", "bot")):
        run("kesif", kesif)
    for step in steps:
        run(step, FN[step])
        if step == "bot":  # yayımlanan kayıtlar hemen mühürlenir
            run("muhur", muhur)
    try:
        store.set_source_status(f"is:{is_adi}", not state["failed"],
                                "başarısız adımlar: " + ", ".join(state["failed"]) if state["failed"] else "tamam")
    except Exception:
        pass
    # kritik adım (bot / sonuclandir) düştüyse iş akışı kırmızı olsun → otomatik GitHub issue
    return 1 if set(state["failed"]) & {"bot", "sonuclandir", "analiz"} else 0


class _StepTimeout(BaseException):  # BaseException: kaynak kodundaki geniş 'except Exception' blokları yutmasın
    pass


class _LiveLog(list):
    """Günlük satırlarını anında yazar (iş akışı kesilse bile nerede kaldığı görünür)."""

    def append(self, x):
        print(x, flush=True)
        super().append(x)

    def extend(self, xs):
        for x in xs:
            self.append(x)

    def __iadd__(self, xs):
        self.extend(xs)
        return self


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
