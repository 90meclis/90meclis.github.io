#!/usr/bin/env bash
# Statik site verisi (`veri` dalı, tek commit'lik yetim dal; geçmiş tutulmaz → depo şişmez).
#   scripts/veri.sh al <dizin>              → dalın güncel içeriğini dizine açar (dal yoksa boş dizin)
#   scripts/veri.sh gonder <dizin> <mesaj>  → yalnızca bu işin değiştirdiği dosyaları dalın EN GÜNCEL hâlinin
#                                             üstüne koyup force-with-lease ile iter (eşzamanlı işler birbirini ezmez)
set -euo pipefail
cmd=$1; dir=$2
base_list=/tmp/veri-base.sha
fetch() { git fetch -q --depth 1 origin "+refs/heads/veri:refs/remotes/origin/veri" 2>/dev/null; }
case "$cmd" in
  al)
    mkdir -p "$dir"
    if fetch; then git archive refs/remotes/origin/veri | tar -x -C "$dir"; fi
    (cd "$dir" && find . -type f -print0 | sort -z | xargs -0 -r sha1sum) > "$base_list"
    echo "veri dalı → $dir ($(wc -l < "$base_list") dosya)"
    ;;
  gonder)
    msg=${3:-"Veri güncellemesi"}
    now_list=$(mktemp)
    (cd "$dir" && find . -type f ! -name '*.tmp' -print0 | sort -z | xargs -0 -r sha1sum) > "$now_list"
    changed=$(comm -13 <(sort "$base_list") <(sort "$now_list") | awk '{print $2}')
    removed=$(comm -23 <(awk '{print $2}' "$base_list" | sort) <(awk '{print $2}' "$now_list" | sort))
    if [ -z "$changed$removed" ]; then echo "veri değişmedi"; exit 0; fi
    git config user.name "90-meclis-bot"
    git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
    for i in 1 2 3 4 5 6; do
      tmp=$(mktemp -d); old=""
      if fetch; then old=$(git rev-parse refs/remotes/origin/veri); git archive "$old" | tar -x -C "$tmp"; fi
      for f in $changed; do mkdir -p "$tmp/$(dirname "$f")"; cp "$dir/$f" "$tmp/$f"; done
      for f in $removed; do rm -f "$tmp/$f"; done
      export GIT_INDEX_FILE=$(mktemp -u)
      git --work-tree="$tmp" add -A . >/dev/null
      tree=$(git write-tree); unset GIT_INDEX_FILE
      c=$(git commit-tree "$tree" -m "$msg ($(date -u '+%F %H:%M') UTC)")
      if git push -q --force-with-lease="refs/heads/veri:$old" origin "$c:refs/heads/veri"; then
        echo "veri dalı güncellendi: $(echo "$changed" | wc -w) dosya, $(echo "$removed" | wc -w) silindi"; exit 0
      fi
      echo "yarış: veri dalı başka bir işçe güncellendi, yeniden deneniyor ($i)"; sleep $((RANDOM % 7 + 3))
    done
    echo "::warning::veri dalı itilemedi"; exit 0
    ;;
esac
