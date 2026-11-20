"""Ortak yardımcılar: HTTP, Türkçe metin normalleştirme, dosya yolları."""
from __future__ import annotations

import json
import re
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "site" / "data"
CACHE_DIR = ROOT / ".cache"

USER_AGENT = "Mozilla/5.0 (compatible; alim-ilan-takip/1.0)"

# Bu döngünün ilan tarihleri: bu tarihten önceki duyurular önceki yılın alımına aittir.
DONEM_BASLANGIC = "2026-06-05"

KAYNAKLAR = {
    "pgm": {
        "ad": "Personel Genel Müdürlüğü",
        "kisa": "Adalet Bakanlığı (PGM)",
        "ilan_url": "https://pgm.adalet.gov.tr/Home/SayfaDetay/2026sozlesmelitasra",
        "pdf_url": "https://pgm.adalet.gov.tr/Resimler/SayfaDokuman/5062026164814Ek-1%20%C3%9Cnvan,%20say%C4%B1,%20yer%20ve%20kontenjan%20bilgileri.pdf",
        "ilan_tarihi": "2026-06-06",
    },
    "icra": {
        "ad": "İcra İşleri Dairesi Başkanlığı",
        "kisa": "İcra Kâtibi",
        "ilan_url": "https://iidb.adalet.gov.tr/Home/SayfaDetay/sozlesmeli-icra-k-tibi-personel-istihdami-sinav-ilani05062026110033",
        "pdf_url": "https://iidb.adalet.gov.tr/Resimler/SayfaDokuman/20260605110139657Ek-1%20%C4%B0cra%20K%C3%A2tibi%20Say%C4%B1,%20Yer%20ve%20Kontenjan%20Bilgileri.pdf",
        "ilan_tarihi": "2026-06-06",
    },
    "cte": {
        "ad": "Ceza ve Tevkifevleri Genel Müdürlüğü",
        "kisa": "CTE",
        "ilan_url": "https://cte.adalet.gov.tr/Home/SayfaDetay/5766-sozlesmeli-personel-komisyon-alim-ilani05062026050723",
        "pdf_url": "https://cte.adalet.gov.tr/Resimler/SayfaDokuman/20260605170752911Ek-1%20-%205.766%20S%C3%B6zle%C5%9Fmeli%20pozisyonlar%20i%C3%A7in%20s%C4%B1nav%20izni%20verilen%20komisyonlar%20(S%C4%B1nav%20merkezleri).pdf",
        "ilan_tarihi": "2026-06-05",
    },
}

_TR_LOWER = str.maketrans({"I": "ı", "İ": "i"})
_TR_UPPER = str.maketrans({"i": "İ", "ı": "I"})
_ASCII = str.maketrans("çğıöşüâîûÇĞİÖŞÜÂÎÛ", "cgiosuaiuCGIOSUAIU")


def tr_lower(s: str) -> str:
    return s.translate(_TR_LOWER).lower()


def tr_upper(s: str) -> str:
    return s.translate(_TR_UPPER).upper()


def tr_title(s: str) -> str:
    """'ANKARA BATI' -> 'Ankara Batı', 'ORTAKÖY(AKSARAY)' -> 'Ortaköy(Aksaray)'."""
    out = []
    for part in re.split(r"(\s+|[()\-./])", tr_lower(s.strip())):
        if part and part[0].isalpha():
            part = tr_upper(part[0]) + part[1:]
        out.append(part)
    return "".join(out)


def ascii_fold(s: str) -> str:
    s = tr_lower(s).translate(_ASCII)
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


_TR_ALFABE = "abcçdefgğhıijklmnoöprsştuüvyz"


def tr_sort_key(s: str):
    """Türk alfabesine göre sıralama anahtarı (Ç, Ğ, İ, Ö, Ş, Ü doğru yerde)."""
    t = tr_lower(s).replace("â", "a").replace("î", "i").replace("û", "u")
    return [(_TR_ALFABE.index(c) if c in _TR_ALFABE else 100 + ord(c)) for c in t]


def slug(s: str) -> str:
    """Komisyon adından alt alan adı tahmini: 'Ankara Batı' -> 'ankarabati'."""
    return re.sub(r"[^a-z0-9]", "", ascii_fold(s))


def sayi(v) -> int:
    if v is None:
        return 0
    v = str(v).strip().replace(".", "").replace(",", "")
    return int(v) if v.isdigit() else 0


def fetch(url: str, *, tries: int = 3, timeout: int = 30) -> bytes:
    last: Exception | None = None
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if 400 <= e.code < 500 and e.code != 429:
                raise
            last = e
        except Exception as e:  # ağ hataları
            last = e
        time.sleep(1.5 * (i + 1))
    assert last is not None
    raise last


def write_json(path: Path, obj, *, kompakt: bool | None = None) -> None:
    """site/data altındaki dosyalar tarayıcıya gittiği için kompakt yazılır."""
    if kompakt is None:
        kompakt = DATA_DIR in path.parents
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    metin = json.dumps(obj, ensure_ascii=False, separators=(",", ":")) if kompakt else json.dumps(obj, ensure_ascii=False, indent=1)
    tmp.write_text(metin + "\n", encoding="utf-8")
    tmp.replace(path)


def read_json(path: Path, default=None):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default
