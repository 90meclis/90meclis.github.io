"""Supabase egress bütçesi (Free plan: ayda 5 GB, site trafiği dahil).

* Her çalışma Supabase'ten gelen yanıt baytlarını ölçer (meclis.ayna.Egress) ve aylık deftere ekler
  (source_status 'egress:ay'; iş mesajında da görünür → v_sistem_durumu.son_mesaj).
* Defter bütçenin %70'ini geçerse vazgeçilebilir adımlar atlanır; %95'te yalnızca yayın ve sonuçlandırma çalışır.
* 402 (proje kısıtlı) yoklaması: iş sessizce atlanır, kırmızı/issue yağmuru olmaz.
"""
from __future__ import annotations

import json
import os

from .timeutil import now_utc, to_iso

BUDGET_MB = float(os.environ.get("MECLIS_EGRESS_AY_MB", "2500"))  # işlerin payı; kalan ~2.5 GB site + pay
NONESSENTIAL = {"kadro", "kadro_s", "editoryal", "notlar", "gundem", "simulasyon", "canli", "yerel", "sezon", "kesif"}
ESSENTIAL = {"yenile", "bot", "muhur", "sonuclandir", "statik"}


def probe(url: str, key: str) -> int:
    """Tek küçük istek; HTTP durum kodu (ağ hatasında 0)."""
    import requests

    try:
        r = requests.get(f"{url}/rest/v1/leagues", params={"select": "code", "limit": "1"},
                         headers={"apikey": key, "Authorization": f"Bearer {key}"}, timeout=20)
        return r.status_code
    except Exception:
        return 0


class Ledger:
    def __init__(self, store, job: str):
        self.store, self.job = store, job
        self.month = now_utc().strftime("%Y-%m")
        self.used = 0
        self.by_job: dict = {}

    def load(self) -> None:
        try:
            row = self.store.get("source_status", source="egress:ay") or {}
            d = json.loads(row.get("message") or "{}")
            if d.get("ay") == self.month:
                self.used = int(d.get("bayt") or 0)
                self.by_job = d.get("is") or {}
        except Exception:
            pass

    def frac(self) -> float:
        return self.used / (BUDGET_MB * 1e6) if BUDGET_MB > 0 else 0.0

    def skip_reason(self, step: str) -> str | None:
        f = self.frac()
        if f >= 0.95 and step not in ESSENTIAL:
            return f"aylık egress bütçesinin %{f * 100:.0f}'i kullanıldı — yalnızca yayın/sonuç adımları"
        if f >= 0.70 and step in NONESSENTIAL:
            return f"aylık egress bütçesinin %{f * 100:.0f}'i kullanıldı — vazgeçilebilir adım"
        return None

    def commit(self) -> str:
        from .ayna import Egress

        run = Egress.total()
        try:  # yeniden oku-ekle-yaz (eşzamanlı işler küçük sapma yaratabilir; bütçe koruması için yeterli)
            self.load()
            self.used += run
            self.by_job[self.job] = int(self.by_job.get(self.job, 0)) + run
            msg = json.dumps({"ay": self.month, "bayt": self.used, "is": self.by_job, "butce_mb": BUDGET_MB,
                              "guncellendi": to_iso(now_utc())})
            self.store.upsert("source_status", [{"source": "egress:ay", "ok": self.frac() < 0.95, "message": msg,
                                                 "calls_today": int(self.used / 1e6), "calls_date": self.month,
                                                 "updated_at": to_iso(now_utc())}])
        except Exception:
            pass
        return f"egress {run / 1e6:.1f} MB (ay: {self.used / 1e6:.0f}/{BUDGET_MB:.0f} MB)"
