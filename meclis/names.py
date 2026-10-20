"""Takım adı normalleştirme ve kaynaklar arası eşleştirme."""
from __future__ import annotations

import difflib
import re
import unicodedata

_TR_MAP = str.maketrans({
    "ç": "c", "Ç": "c", "ğ": "g", "Ğ": "g", "ı": "i", "İ": "i", "ö": "o", "Ö": "o",
    "ş": "s", "Ş": "s", "ü": "u", "Ü": "u", "â": "a", "î": "i", "û": "u",
})

_DROP_TOKENS = {
    "fc", "fk", "sk", "jk", "afc", "cf", "ac", "as", "ssc", "sc", "bk", "if", "cd", "ud", "rc", "rcd",
    "kulubu", "futbol", "spor kulubu", "the", "club", "calcio", "sv", "vfb", "vfl", "tsg", "1", "de",
}

# normalleştirilmiş anahtar -> kanonik anahtar
ALIASES: dict[str, str] = {
    # İngiltere League Two / İskoçya Championship: football-data.co.uk kısaltmaları (yinelenen takım önleme)
    "accrington": "accringtonstanley", "bristolrvs": "bristolrovers", "crewe": "crewealexandra",
    "oldham": "oldhamathletic", "tranmere": "tranmererovers", "ayr": "ayrunited", "dunfermline": "dunfermlineathletic",
    "morton": "greenockmorton", "invernessc": "invernesscaledonianthistle", "partick": "partickthistle",
    "raithrvs": "raithrovers",
    # Türkiye
    "buyuksehyr": "basaksehir", "istanbulbasaksehir": "basaksehir", "basaksehir": "basaksehir",
    "ibasaksehir": "basaksehir", "medipolbasaksehir": "basaksehir", "rams basaksehir": "basaksehir",
    "goztep": "goztepe", "goztepe": "goztepe",
    "corum": "corum", "corumfk": "corum", "yenicorumspor": "corum",
    "amed": "amedspor", "amedspor": "amedspor", "amedsk": "amedspor", "amedsportiffaaliyetler": "amedspor",
    "rizespor": "rizespor", "caykurrizespor": "rizespor",
    "karagumruk": "karagumruk", "fatihkaragumruk": "karagumruk",
    "gaziantep": "gaziantep", "gaziantepfk": "gaziantep",
    "erzurumspor": "erzurumspor", "bberzurumspor": "erzurumspor", "erzurum": "erzurumspor",
    "eyupspor": "eyupspor", "eyup": "eyupspor",
    "kayserispor": "kayserispor", "kayseri": "kayserispor",
    "antalyaspor": "antalyaspor", "antalya": "antalyaspor",
    "alanyaspor": "alanyaspor", "corendonalanyaspor": "alanyaspor",
    "genclerbirligi": "genclerbirligi", "genclerbirligisk": "genclerbirligi",
    "kocaelispor": "kocaelispor", "kocaeli": "kocaelispor",
    "konyaspor": "konyaspor", "konya": "konyaspor", "tumosankonyaspor": "konyaspor",
    "sivasspor": "sivasspor", "hatayspor": "hatayspor", "adanademirspor": "adanademirspor",
    "besiktas": "besiktas", "besiktasjk": "besiktas", "fenerbahce": "fenerbahce",
    "galatasaray": "galatasaray", "trabzonspor": "trabzonspor", "kasimpasa": "kasimpasa",
    "samsunspor": "samsunspor", "bodrumspor": "bodrumspor", "bodrumfk": "bodrumspor",
    # İngiltere
    "mancity": "manchestercity", "manchestercity": "manchestercity",
    "manunited": "manchesterunited", "manchesterunited": "manchesterunited", "manutd": "manchesterunited",
    "nottmforest": "nottinghamforest", "nottinghamforest": "nottinghamforest",
    "wolves": "wolverhampton", "wolverhamptonwanderers": "wolverhampton", "wolverhampton": "wolverhampton",
    "spurs": "tottenham", "tottenhamhotspur": "tottenham", "tottenham": "tottenham",
    "newcastleunited": "newcastle", "newcastle": "newcastle", "westham": "westham", "westhamunited": "westham",
    "brightonhovealbion": "brighton", "brightonandhovealbion": "brighton", "brightonhove": "brighton", "brighton": "brighton", "leedsunited": "leeds", "leeds": "leeds",
    "sheffieldunited": "sheffieldunited", "sheffieldutd": "sheffieldunited", "hullcity": "hull", "hull": "hull",
    "ipswichtown": "ipswich", "ipswich": "ipswich", "coventrycity": "coventry", "coventry": "coventry",
    "leicestercity": "leicester", "leicester": "leicester", "afcbournemouth": "bournemouth",
    # İspanya / İtalya / Almanya / Fransa
    "athbilbao": "athleticbilbao", "athleticclub": "athleticbilbao", "athleticbilbao": "athleticbilbao",
    "athmadrid": "atleticomadrid", "atleticomadrid": "atleticomadrid", "clubatleticodemadrid": "atleticomadrid",
    "realmadrid": "realmadrid", "barcelona": "barcelona", "betis": "realbetis", "realbetis": "realbetis",
    "sociedad": "realsociedad", "realsociedad": "realsociedad", "celta": "celtavigo", "celtavigo": "celtavigo",
    "espanol": "espanyol", "espanyol": "espanyol", "vallecano": "rayovallecano", "rayovallecano": "rayovallecano",
    "inter": "inter", "internazionale": "inter", "intermilan": "inter", "milan": "milan", "acmilan": "milan",
    "roma": "roma", "asroma": "roma", "napoli": "napoli", "juventus": "juventus", "lazio": "lazio",
    "bayernmunich": "bayernmunchen", "bayernmunchen": "bayernmunchen", "fcbayernmunchen": "bayernmunchen",
    "dortmund": "dortmund", "borussiadortmund": "dortmund", "leverkusen": "leverkusen",
    "bayerleverkusen": "leverkusen", "bayer04leverkusen": "leverkusen", "mgladbach": "gladbach", "borussiamgladbach": "gladbach",
    "borussiamonchengladbach": "gladbach", "monchengladbach": "gladbach", "einfrankfurt": "frankfurt",
    "eintrachtfrankfurt": "frankfurt", "rbleipzig": "leipzig", "leipzig": "leipzig",
    "parissg": "psg", "parissaintgermain": "psg", "psg": "psg", "marseille": "marseille",
    "olympiquemarseille": "marseille", "lyon": "lyon", "olympiquelyonnais": "lyon",
    # OpenLigaDB / openfootball resmî adları
    "athletic": "athleticbilbao", "deportivolacoruna": "lacoruna", "deportivoacoruna": "lacoruna",
    "lacoruna": "lacoruna", "espanyolbarcelona": "espanyol", "espanyoldebarcelona": "espanyol",
    "realbetisbalompie": "realbetis", "realracingsantander": "santander", "racingsantander": "santander", "queensparkrangers": "qpr", "oxfordunited": "oxford",
    "sportingcp": "splisbon", "sportingclubeportugal": "splisbon", "sportinglisbon": "splisbon", "aekathens": "aek",
    "apsatromitosathinon": "atromitos", "royaleunionsaintgilloise": "stgilloise", "unionsaintgilloise": "stgilloise",
    "unionsg": "stgilloise", "sinttruidensevv": "sttruiden", "sinttruiden": "sttruiden", "kaagent": "gent",
    "krcgenk": "genk", "zultewaregem": "waregem", "royalantwerp": "antwerp", "sportingcharleroi": "charleroi", "deportivoalaves": "alaves", "cdalaves": "alaves", "realracing": "santander", "realracingclub": "santander",
    "internazionalemilano": "inter", "genoacfc": "genoa", "sslazio": "lazio", "uslecce": "lecce",
    "lilleosc": "lille", "ogcnice": "nice", "racinglens": "lens", "stadebrestois": "brest",
    "stadebrestois29": "brest", "staderennais": "rennes", "07elversberg": "elversberg",
    "paderborn07": "paderborn", "scpaderborn07": "paderborn", "fsvmainz05": "mainz", "mainz05": "mainz",
    "hamburger": "hamburg", "hamburgersv": "hamburg", "hsv": "hamburg",
    "caosasuna": "osasuna", "villareal": "villarreal",
}

# Kanonik anahtar -> Türkçe görünen ad (yalnızca karakterleri bozulan isimler için)
DISPLAY: dict[str, str] = {
    "basaksehir": "Başakşehir", "goztepe": "Göztepe", "corum": "Çorum FK", "amedspor": "Amedspor",
    "rizespor": "Çaykur Rizespor", "karagumruk": "Fatih Karagümrük", "besiktas": "Beşiktaş",
    "fenerbahce": "Fenerbahçe", "kasimpasa": "Kasımpaşa", "genclerbirligi": "Gençlerbirliği",
    "eyupspor": "Eyüpspor", "erzurumspor": "Erzurumspor", "gaziantep": "Gaziantep FK",
    "manchestercity": "Manchester City", "manchesterunited": "Manchester United",
    "nottinghamforest": "Nottingham Forest",
}


def strip_accents(text: str) -> str:
    text = (text or "").translate(_TR_MAP)
    text = unicodedata.normalize("NFKD", text)
    return "".join(c for c in text if not unicodedata.combining(c))


def basic_key(name: str) -> str:
    s = strip_accents(name).lower()
    s = re.sub(r"\b([a-z])\.([a-z])\.", r"\1\2", s)  # "F.C." -> "fc"
    s = s.replace("&", " ").replace("'", "").replace(".", " ")
    tokens = [t for t in re.split(r"[^a-z0-9]+", s) if t]
    tokens = [t for t in tokens if t not in _DROP_TOKENS and not re.fullmatch(r"(18|19|20)\d\d", t)]
    return "".join(tokens)


def canonical_key(name: str) -> str:
    """Kaynaktan bağımsız takım anahtarı."""
    k = basic_key(name)
    if k in ALIASES:
        return ALIASES[k]
    if k.startswith("istanbul") and k[8:] in ALIASES:
        return ALIASES[k[8:]]
    return k


def team_id(league: str, name: str) -> str:
    return f"{league}:{canonical_key(name)}"


def display_name(name: str) -> str:
    return DISPLAY.get(canonical_key(name), name)


def _strip_spor(k: str) -> str:
    return k[:-4] if k.endswith("spor") and len(k) > 6 else k


def same_team(a: str, b: str, threshold: float = 0.90) -> bool:
    """Temkinli eşleştirme: yanlış birleştirme (iki farklı takımı tek takım sanmak) eksik eşleşmeden daha
    zararlıdır; bu yüzden bulanık eşleşme yüksek eşikle ve ek koşullarla yapılır."""
    ka, kb = canonical_key(a), canonical_key(b)
    if ka == kb:
        return True
    if _strip_spor(ka) == _strip_spor(kb):
        return True
    if not ka or not kb or ka[:-1] == kb[:-1] or ka[-1:].isdigit() or kb[-1:].isdigit():
        return False  # yalnızca son harfi farklı (ör. "... A" / "... B") ya da numaralı takımlar
    short, long_ = sorted((ka, kb), key=len)
    if len(short) >= 6 and short in long_ and len(short) / len(long_) >= 0.6:
        return True
    return difflib.SequenceMatcher(None, ka, kb).ratio() >= threshold


def best_match(name: str, candidates: list[str], threshold: float = 0.90) -> str | None:
    """Aday listesinden en iyi eşleşen takım adını döndürür (yoksa None)."""
    k = canonical_key(name)
    best, best_score = None, 0.0
    for c in candidates:
        if same_team(name, c, threshold=1.01):  # kesin kurallar
            return c
        score = difflib.SequenceMatcher(None, k, canonical_key(c)).ratio()
        if score > best_score:
            best, best_score = c, score
    return best if best_score >= threshold else None


def mentions_team(text: str, team_name: str) -> bool:
    """Haber metninde takım adı geçiyor mu (aksan/ek duyarsız)."""
    t = " " + re.sub(r"[^a-z0-9]+", " ", strip_accents(text).lower()) + " "
    disp = display_name(team_name)
    variants = {strip_accents(team_name).lower(), strip_accents(disp).lower()}
    out = set()
    for v in variants:
        v = re.sub(r"\b(fk|fc|sk|jk|as|a s)\b", " ", v)
        v = re.sub(r"[^a-z0-9]+", " ", v).strip()
        if len(v) >= 4:
            out.add(v)
            if v.endswith("spor") and len(v) > 7:
                out.add(v[:-4].strip())
    for v in out:
        if re.search(r"(?<![a-z0-9])" + re.escape(v) + r"(?:[a-z]{0,4})(?![a-z0-9])", t):
            return True
    return False
