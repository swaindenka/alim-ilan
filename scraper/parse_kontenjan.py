"""Üç alım ilanının Ek-1 PDF'lerini indirip komisyon bazında kontenjan verisine dönüştürür.

Çıktı: site/data/kontenjan.json

Kullanım:
    python scraper/parse_kontenjan.py            # PDF'leri indir (önbellek varsa onu kullan)
    python scraper/parse_kontenjan.py --yenile   # önbelleği yok say, yeniden indir
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone

import pdfplumber

from common import CACHE_DIR, DATA_DIR, KAYNAKLAR, fetch, sayi, slug, tr_lower, tr_sort_key, tr_title, write_json

# Ünvanları sınıflandırmada kullanılan gruplar (duyuru başlıklarındaki anahtar kelimelerle eşleşir)
def unvan_grubu(unvan: str) -> str:
    u = tr_lower(unvan)
    for key, pat in [
        ("zabit", r"zab[ıi]t"),
        ("mubasir", r"müba[şs]ir"),
        ("koruma", r"koruma ve güvenlik"),
        ("hizmetli", r"hizmetli"),
        ("sofor", r"[şs]oför"),
        ("asci", r"a[şs][çc][ıi]"),
        ("kaloriferci", r"kalorifer"),
        ("hemsire", r"hem[şs]ire"),
        ("buro", r"büro|kâtib|katib"),
        ("ikm", r"infaz ve koruma|\bikm\b"),
        ("teknisyen", r"teknisyen"),
    ]:
        if re.search(pat, u):
            return key
    return "diger"


def pdf_path(kurum: str, yenile: bool):
    p = CACHE_DIR / f"{kurum}_ek1.pdf"
    if yenile or not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(fetch(KAYNAKLAR[kurum]["pdf_url"]))
    return p


def tum_satirlar(path):
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            for table in page.extract_tables():
                for row in table:
                    yield [(c or "").replace("\n", " ").strip() for c in row]


# ---------------------------------------------------------------- PGM
def parse_pgm(path):
    """Sütunlar: Komisyon | Yer | Ünvan | Sayı | Genel Mezuniyet | Öncelikli Mezuniyet | Toplam"""
    gruplar: dict[tuple[str, str], dict] = {}
    komisyon = None
    for row in tum_satirlar(path):
        if len(row) < 7:
            continue
        kom, yer, unvan, adet, genel, oncelikli, toplam = row[:7]
        if kom.startswith("İstihdam") or yer.upper() == "TOPLAM" or not unvan:
            continue
        if kom:
            komisyon = re.sub(r"\bidare\b", "İdare", kom)
        if not komisyon or not adet:
            continue
        key = (komisyon, unvan)
        g = gruplar.get(key)
        if g is None:
            g = gruplar[key] = {
                "unvan": unvan,
                "grup": unvan_grubu(unvan),
                "sayi": 0,
                "genel": None,
                "oncelikli": None,
                "toplam": None,
                "yerler": [],
            }
        if toplam:
            g["toplam"] = (g["toplam"] or 0) + sayi(toplam)
        if genel:
            g["genel"] = (g["genel"] or 0) + sayi(genel)
        if oncelikli:
            g["oncelikli"] = (g["oncelikli"] or 0) + sayi(oncelikli)
        g["sayi"] += sayi(adet)
        g["yerler"].append({"yer": yer, "sayi": sayi(adet)})

    komisyonlar: dict[str, dict] = {}
    for (kom, _), g in gruplar.items():
        k = komisyonlar.setdefault(kom, {"ad": kom, "toplam": 0, "unvanlar": []})
        # Tabloda "Toplam" sütunu komisyonun kontenjanıdır; adliye sayılarının toplamından farklı
        # olabilir (ör. Adana zabıt kâtibi: adliyeler 98+3=101, toplam 101).
        g["toplam"] = g["toplam"] if g["toplam"] is not None else g["sayi"]
        k["unvanlar"].append(g)
        k["toplam"] += g["toplam"]
    return komisyonlar


# ---------------------------------------------------------------- İcra
def parse_icra(path):
    """Sütunlar: Komisyon | Mahal | Pozisyon sayısı | Toplam"""
    komisyonlar: dict[str, dict] = {}
    komisyon = None
    ilk_komisyon = None
    for row in tum_satirlar(path):
        if len(row) < 3:
            continue
        kom, mahal, adet = row[0], row[1], row[2]
        if kom.startswith("SINAVI YAPACAK") or kom.startswith("EK") or "TOPLAM" in kom.upper() or "TOPLAM" in mahal.upper():
            continue
        if kom:
            # PDF'in 2. ve 3. sayfalarında ilk sayfadaki "ADANA" yazısı hayalet metin olarak
            # tekrar ediyor ("ADANA DİYARBAKIR", "MARDİN ADANA"); onu ayıkla.
            parcalar = kom.split()
            if ilk_komisyon and len(parcalar) > 1 and ilk_komisyon in parcalar:
                parcalar.remove(ilk_komisyon)
                kom = " ".join(parcalar)
            ilk_komisyon = ilk_komisyon or kom
            komisyon = tr_title(kom)
        if not komisyon or not mahal or not adet.replace(".", "").isdigit():
            continue
        k = komisyonlar.setdefault(
            komisyon,
            {"ad": komisyon, "toplam": 0, "unvanlar": [{"unvan": "İcra Kâtibi", "grup": "icra", "sayi": 0, "toplam": 0, "yerler": []}]},
        )
        u = k["unvanlar"][0]
        u["sayi"] += sayi(adet)
        u["toplam"] += sayi(adet)
        u["yerler"].append({"yer": tr_title(mahal), "sayi": sayi(adet)})
        k["toplam"] += sayi(adet)
    return komisyonlar


# ---------------------------------------------------------------- CTE
CTE_UNVANLAR = [
    "İnfaz ve Koruma Memuru (Erkek)",
    "İnfaz ve Koruma Memuru (Erkek) - Ceza İnfaz ve Güvenlik Hizmetleri Mezunu",
    "İnfaz ve Koruma Memuru (Kadın)",
    "İnfaz ve Koruma Memuru (Kadın) - Ceza İnfaz ve Güvenlik Hizmetleri Mezunu",
    "Büro Personeli (Cezaevi Kâtibi)",
    "Büro Personeli (Cezaevi Kâtibi) - Özel Kontenjan",
    "Hemşire",
    "Destek Personeli (Şoför)",
    "Destek Personeli (Aşçı)",
    "Destek Personeli (Kaloriferci)",
    "Teknisyen (Elektrik)",
    "Teknisyen (Gıda Teknolojisi)",
    "Teknisyen (Makine)",
    "Teknisyen (Ziraat)",
    "Teknisyen (İklimlendirme ve Soğutma)",
    "Teknisyen (Metal)",
    "Teknisyen (Motor)",
    "Teknisyen (Et İşleme)",
    "Teknisyen (Tekstil)",
    "Teknisyen (Süt İşleme)",
    "Teknisyen (Sıhhi Tesisat)",
]
CTE_ILK_SAYI_SUTUNU = 4  # 0 il merkezi, 1 sınav merkezi, 2 ağır ceza, 3 kurum


def parse_cte(path):
    n = len(CTE_UNVANLAR)
    komisyonlar: dict[str, dict] = {}
    blok_kurumlar: list[dict] = []
    blok_adlar: list[str] = []
    blok_il: list[str] = []
    blok_toplam = None

    def vals(row):
        return [sayi(v) for v in row[CTE_ILK_SAYI_SUTUNU : CTE_ILK_SAYI_SUTUNU + n]]

    for row in tum_satirlar(path):
        if len(row) < CTE_ILK_SAYI_SUTUNU + n + 1:
            continue
        il, merkez, agir, kurum = row[0], row[1], row[2], row[3]
        if il.startswith("5.766") or il == "İL MERKEZİ":
            continue
        if not any(row) or (not kurum and not il and not merkez):
            continue  # genel toplam satırı vb.
        if merkez:
            blok_adlar.append(merkez)
        if il:
            blok_il.append(il)
        ku = kurum.upper()
        if ku.startswith("TOPLAM SAYI"):
            blok_toplam = vals(row)
            continue
        if ku.startswith("UYGULAMA SINAVINA"):
            cagri = vals(row)
            ad = tr_title(blok_adlar[0] if blok_adlar else (blok_il[0] if blok_il else "?"))
            toplam = blok_toplam or [sum(k["dagilim"][i] for k in blok_kurumlar) for i in range(n)]
            k = komisyonlar.setdefault(ad, {"ad": ad, "il": tr_title(blok_il[0]) if blok_il else ad, "toplam": 0, "cagrilacak": 0, "unvanlar": [], "kurumlar": []})
            for i, unvan in enumerate(CTE_UNVANLAR):
                if toplam[i]:
                    k["unvanlar"].append({
                        "unvan": unvan,
                        "grup": unvan_grubu(unvan),
                        "sayi": toplam[i],
                        "toplam": toplam[i],
                        "cagrilacak": cagri[i],
                        "yerler": [
                            {"yer": tr_title(x["kurum"]), "sayi": x["dagilim"][i]}
                            for x in blok_kurumlar if x["dagilim"][i]
                        ],
                    })
            k["toplam"] += sum(toplam)
            k["cagrilacak"] += sum(cagri)
            for x in blok_kurumlar:
                k["kurumlar"].append({"kurum": tr_title(x["kurum"]), "agir_ceza": tr_title(x["agir"]), "toplam": sum(x["dagilim"])})
            blok_kurumlar, blok_adlar, blok_il, blok_toplam = [], [], [], None
            continue
        if kurum:
            blok_kurumlar.append({"kurum": kurum, "agir": agir, "dagilim": vals(row)})
    if blok_kurumlar:
        print(f"UYARI: CTE tablosunda kapanmamış blok kaldı ({len(blok_kurumlar)} kurum)", file=sys.stderr)
    return komisyonlar


# ---------------------------------------------------------------- birleştirme
# PDF'lerde aynı komisyon farklı yazılabiliyor; anahtar her zaman slug(ad).
def birlestir(kaynak: dict[str, dict[str, dict]]):
    out: dict[str, dict] = {}
    for kurum, komisyonlar in kaynak.items():
        for ad, k in komisyonlar.items():
            sid = slug(ad)
            o = out.setdefault(sid, {"id": sid, "ad": ad, "il": None, "kurumlar": {}})
            if kurum == "pgm":  # PGM ad yazımı en düzgünü
                o["ad"] = ad
            if k.get("il"):
                o["il"] = k["il"]
            k = {key: v for key, v in k.items() if not key.startswith("_") and key not in ("ad", "il")}
            o["kurumlar"][kurum] = k
    for o in out.values():
        o["toplam"] = sum(k["toplam"] for k in o["kurumlar"].values())
    return dict(sorted(out.items(), key=lambda kv: tr_sort_key(kv[1]["ad"])))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--yenile", action="store_true")
    args = ap.parse_args()

    parsers = {"pgm": parse_pgm, "icra": parse_icra, "cte": parse_cte}
    kaynak = {}
    ozet = {}
    for kurum, fn in parsers.items():
        komisyonlar = fn(pdf_path(kurum, args.yenile))
        kaynak[kurum] = komisyonlar
        toplam = sum(k["toplam"] for k in komisyonlar.values())
        unvan_top: dict[str, int] = {}
        for k in komisyonlar.values():
            for u in k["unvanlar"]:
                unvan_top[u["unvan"]] = unvan_top.get(u["unvan"], 0) + u["toplam"]
        ozet[kurum] = {**KAYNAKLAR[kurum], "toplam": toplam, "komisyon_sayisi": len(komisyonlar), "unvanlar": unvan_top}
        print(f"{kurum}: {len(komisyonlar)} komisyon, {toplam} kişi")

    data = {
        "olusturma": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "kurumlar": ozet,
        "komisyonlar": list(birlestir(kaynak).values()),
    }
    write_json(DATA_DIR / "kontenjan.json", data)
    print(f"toplam {len(data['komisyonlar'])} komisyon → {DATA_DIR / 'kontenjan.json'}")


if __name__ == "__main__":
    main()
