"""Komisyon adından resmi site adresini (xxx.adalet.gov.tr) bulur.

Adalet komisyonlarının siteleri çoğunlukla `<ad>.adalet.gov.tr` biçimindedir. İstisnalar
(bölge mahkemeleri, aynı adlı ilçeler) için birden fazla aday denenir; çalışan adres
scraper/komisyon_siteleri.json dosyasına kaydedilir ve elle düzeltilebilir.
"""
from __future__ import annotations

import re

from common import ROOT, read_json, slug, write_json

SITE_DOSYASI = ROOT / "scraper" / "komisyon_siteleri.json"

# Elle bilinen istisnalar (ilk aday önce denenir)
OZEL = {
    "ereglikonya": ["eregli", "ereglikonya", "konyaeregli"],
    "ereglizonguldak": ["kdzeregli", "karadenizeregli", "ereglizonguldak", "zonguldakeregli"],
    "mustafakemalpasa": ["mustafakemalpasa", "mkemalpasa"],
}


def adaylar(komisyon_id: str, ad: str) -> list[str]:
    if komisyon_id in OZEL:
        return OZEL[komisyon_id]
    m = re.match(r"(.+?)\s+Bölge\s+(Adliye|İdare)\s+Mahkemesi", ad)
    if m:
        sehir = slug(m.group(1))
        if m.group(2) == "Adliye":
            return [f"{sehir}bam", f"{sehir}bolgeadliye", komisyon_id]
        return [f"{sehir}bim", f"{sehir}bolgeidare", komisyon_id]
    return [komisyon_id]


def host(alt: str) -> str:
    return f"{alt}.adalet.gov.tr"


def kayitli() -> dict[str, str | None]:
    return read_json(SITE_DOSYASI, {}) or {}


def kaydet(siteler: dict[str, str | None]) -> None:
    write_json(SITE_DOSYASI, dict(sorted(siteler.items())))
