"""Wikipedia (MediaWiki API) — güncel A takım kadrosu. Anahtarsız; içerik CC BY-SA 4.0 (kaynak gösterilir).

Kulüp maddesindeki "Current squad / First-team squad / Players" bölümünde yer alan {{Fs player}} şablonları
okunur: forma no, mevki (GK/DF/MF/FW), uyruk, ad. Kiralık gönderilen, altyapı, B takımı ve kadın takımı bölümleri
alınmaz. Wikimedia API kuralları: tanımlayıcı User-Agent, seri istek (paralel yok), maxlag=5.
Sakatlık/ceza bilgisi YOKTUR — yalnızca kadro (oyuncu tablosunun iskeleti ve sakatlık eşleştirmesi için ad listesi).
"""
from __future__ import annotations

import re
import time

from .http import SourceError, get

SOURCE = "wikipedia"
API = "https://en.wikipedia.org/w/api.php"
WD_API = "https://www.wikidata.org/w/api.php"
UA = {"User-Agent": "90MeclisBot/1.0 (https://github.com/ebrarmutlu3434-afk/90-meclis) python-requests"}
MIN_INTERVAL = 0.5
_last = [0.0]

_KEEP = re.compile(r"current squad|first[- ]team|squad|players|kadro", re.I)
_SKIP = re.compile(r"loan|reserve|youth|academy|under[- ]?\d|u-?\d\d|\bb\b|ii\b|women|retired|former|notable|"
                   r"history|staff|captain|record|transfer|personnel|management|coach", re.I)
_FS = re.compile(r"\{\{\s*(?:fs player|football squad player)\s*\|((?:[^{}]|\{\{[^{}]*\}\})*)\}\}", re.I)
_POS = {"GK": "Goalkeeper", "DF": "Defender", "MF": "Midfielder", "FW": "Attacker"}


def _get_json(url: str, params: dict, retries: int = 4) -> dict:
    for attempt in range(retries):
        wait = _last[0] + MIN_INTERVAL - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _last[0] = time.monotonic()
        r = get(url, params={**params, "format": "json", "formatversion": 2, "maxlag": 5}, headers=UA, timeout=30)
        if r.status_code != 200:
            raise SourceError(f"Wikipedia HTTP {r.status_code}")
        data = r.json()
        err = data.get("error")
        if err and err.get("code") == "maxlag" and attempt < retries - 1:
            # sunucu yükü: Wikimedia kuralı gereği bekleyip yeniden dene (Retry-After başlığı saniye cinsinden)
            try:
                delay = float(r.headers.get("Retry-After") or 5)
            except ValueError:
                delay = 5.0
            time.sleep(min(max(delay, 1.0), 15.0))
            continue
        if err:
            raise SourceError(f"Wikipedia: {err.get('info') or err}")
        return data
    raise SourceError("Wikipedia: sunucu gecikmesi (maxlag) sürüyor")


def _clean_name(raw: str) -> str:
    s = raw.strip()
    m = re.search(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]", s)
    if m:
        s = m.group(2) or re.sub(r"\s*\(.*?\)\s*$", "", m.group(1))
    s = re.sub(r"\{\{[^{}]*\}\}|<[^>]+>|'''?", "", s)
    return re.sub(r"\s+", " ", s).strip()


def _fields(body: str) -> dict:
    # şablon içindeki iç şablon/bağlantılardaki '|' işaretlerini korumak için önce maskele
    masked = re.sub(r"\[\[[^\]]*\]\]|\{\{[^{}]*\}\}", lambda m: m.group(0).replace("|", "\x00"), body)
    out = {}
    for part in masked.split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip().lower()] = v.replace("\x00", "|").strip()
    return out


def parse_squad(wikitext: str) -> list[dict]:
    """Wikitext → [{name, number, position, nationality}] (yalnızca A takım bölümü)."""
    sections = re.split(r"(?m)^(={2,4})\s*(.+?)\s*\1\s*$", wikitext or "")
    # sections: [önsöz, '==', başlık, içerik, '==', başlık, içerik, ...]
    out, seen = [], set()
    stack: list[tuple[int, str]] = []
    for i in range(1, len(sections) - 2, 3):
        level, title, body = len(sections[i]), sections[i + 1], sections[i + 2]
        stack = [(lv, t) for lv, t in stack if lv < level] + [(level, title)]
        path = " / ".join(t for _, t in stack)
        if not _KEEP.search(path) or _SKIP.search(title):
            continue
        if any(_SKIP.search(t) for lv, t in stack[:-1] if not _KEEP.search(t)):
            continue
        for m in _FS.finditer(body):
            f = _fields(m.group(1))
            name = _clean_name(f.get("name", ""))
            if not name or name.lower() in seen:
                continue
            seen.add(name.lower())
            pos = (f.get("pos") or "").upper()[:2]
            num = re.sub(r"\D", "", f.get("no", "")) or None
            out.append({"name": name, "number": int(num) if num else None, "position": _POS.get(pos, pos or None),
                        "nationality": f.get("nat") or None})
    return out


def enwiki_titles(qids: list[str]) -> dict[str, str]:
    """Wikidata QID → İngilizce Wikipedia madde başlığı (50'şerli)."""
    out = {}
    for i in range(0, len(qids), 50):
        data = _get_json(WD_API, {"action": "wbgetentities", "ids": "|".join(qids[i:i + 50]),
                                  "props": "sitelinks", "sitefilter": "enwiki"})
        for q, ent in (data.get("entities") or {}).items():
            t = ((ent.get("sitelinks") or {}).get("enwiki") or {}).get("title")
            if t:
                out[q] = t
    return out


def wikitext(title: str) -> str:
    data = _get_json(API, {"action": "parse", "page": title, "prop": "wikitext", "redirects": 1})
    return (data.get("parse") or {}).get("wikitext") or ""


def search_titles(query: str, limit: int = 3) -> list[str]:
    data = _get_json(API, {"action": "query", "list": "search", "srsearch": query, "srlimit": limit})
    return [x["title"] for x in (data.get("query") or {}).get("search", [])]


def team_squad(name: str, title_hint: str | None = None, min_players: int = 15) -> tuple[list[dict], str | None]:
    """Kulübün güncel kadrosu. Önce Wikidata bağlantısı, sonra '(football)' maddesi, sonra arama denenir.
    Döner: (oyuncular, kullanılan madde başlığı)."""
    tried: list[str] = []
    cands = [t for t in [title_hint, f"{title_hint} (football)" if title_hint else None] if t]
    for title in cands:
        tried.append(title)
        try:
            sq = parse_squad(wikitext(title))
        except SourceError:
            continue
        if len(sq) >= min_players:
            return sq, title
    for title in search_titles(f"{name} football club"):
        if title in tried:
            continue
        tried.append(title)
        sq = parse_squad(wikitext(title))
        if len(sq) >= min_players:
            return sq, title
    return [], None
