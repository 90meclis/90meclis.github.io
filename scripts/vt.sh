#!/usr/bin/env bash
# Veritabanı (SQLite) kalıcılığı: GitHub Release "veritabani" varlıkları.
#   meclis.db.gz              → güncel kopya (her işin sonunda yüklenir)
#   meclis-YYYY-MM-DD.db.gz   → günlük anlık görüntü (14 gün saklanır)
# Aynı anda tek iş yazar: iş akışları 'meclis-veritabani' concurrency grubunu paylaşır.
#   scripts/vt.sh indir <hedef.db>   |   scripts/vt.sh yukle <kaynak.db>
set -euo pipefail
REL=veritabani
cmd=$1; db=$2
check() { python - "$1" <<'PY'
import sqlite3, sys
c = sqlite3.connect(sys.argv[1]); r = c.execute("pragma integrity_check").fetchone()[0]
n = c.execute("select count(*) from matches").fetchone()[0]
print(f"bütünlük: {r}, maç: {n}"); sys.exit(0 if r == "ok" and n > 1000 else 1)
PY
}
case "$cmd" in
  indir)
    mkdir -p "$(dirname "$db")" /tmp/vtd
    for pat in meclis.db.gz "meclis-$(date -u +%F).db.gz" "meclis-$(date -u -d yesterday +%F).db.gz"; do
      rm -f /tmp/vtd/*
      if gh release download "$REL" -p "$pat" -D /tmp/vtd --clobber 2>/dev/null; then
        gunzip -c "/tmp/vtd/$pat" > "$db"
        if check "$db"; then echo "veritabanı indirildi: $pat ($(du -h "$db" | cut -f1))"; exit 0; fi
        echo "::warning::$pat bozuk, bir öncekine geçiliyor"
      fi
    done
    echo "::error::Veritabanı indirilemedi"; exit 1
    ;;
  yukle)
    check "$db"
    gzip -c -6 "$db" > /tmp/meclis.db.gz
    gh release upload "$REL" /tmp/meclis.db.gz --clobber
    snap="meclis-$(date -u +%F).db.gz"
    have=$(gh release view "$REL" --json assets -q '.assets[].name')
    if ! grep -qx "$snap" <<<"$have"; then cp /tmp/meclis.db.gz "/tmp/$snap"; gh release upload "$REL" "/tmp/$snap"; fi
    cut=$(date -u -d '14 days ago' +%F)
    for a in $(grep -E '^meclis-[0-9]{4}-[0-9]{2}-[0-9]{2}\.db\.gz$' <<<"$have" || true); do
      d=${a#meclis-}; d=${d%.db.gz}; [[ "$d" < "$cut" ]] && gh release delete-asset "$REL" "$a" -y || true
    done
    echo "veritabanı yüklendi ($(du -h /tmp/meclis.db.gz | cut -f1) sıkıştırılmış)"
    ;;
esac
