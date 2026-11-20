"""Her adalet komisyonunun duyuru arşivini tarar ve alım sürecinin hangi aşamada olduğunu çıkarır.

Girdi : site/data/kontenjan.json   (parse_kontenjan.py üretir)
Çıktı : site/data/durum.json

Duyurular birikimli tutulur: bir kez görülen duyuru, sitenin arşiv sayfasından düşse bile
kaybolmaz. Sınıflandırma her çalıştırmada başlıktan yeniden yapılır (kurallar iyileşirse
geçmiş duyurular da düzelir).

Kullanım:
    python scraper/scrape_duyurular.py                  # hepsi
    python scraper/scrape_duyurular.py adana ankara     # yalnızca bunlar
"""
from __future__ import annotations

import argparse
import html
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urljoin

from common import DATA_DIR, DONEM_BASLANGIC, fetch, read_json, tr_lower, write_json
from siniflandir import ASAMALAR, siniflandir
from siteler import adaylar, host, kaydet, kayitli

DURUM = DATA_DIR / "durum.json"    # içerik: duyurular ve aşamalar (yalnızca gerçekten değişince değişir)
TARAMA = DATA_DIR / "tarama.json"  # her taramada değişen bilgiler: zaman damgaları, erişim hataları
TARAMA_ALANLARI = ("erisim", "hata", "son_kontrol", "son_basarili")
SIRA = {a: i for i, a in enumerate(ASAMALAR)}

LINK_RE = re.compile(r"<a\b[^>]*?href=(?:\"([^\"]+)\"|'([^']+)'|([^\s>]+))[^>]*>(.*?)</a>", re.S | re.I)
TARIH_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})\s+(.+)$")


def metin(s: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def arsiv_oku(site: str) -> list[dict]:
    """https://xxx.adalet.gov.tr/Arsiv/duyuru sayfasındaki "GG.AA.YYYY Başlık" bağlantıları."""
    sayfa = fetch(f"{site}/Arsiv/duyuru").decode("utf-8", "replace")
    out, gorulen = [], set()
    for m in LINK_RE.finditer(sayfa):
        href = next(g for g in m.groups()[:3] if g is not None)
        t = metin(m.group(4))
        tm = TARIH_RE.match(t)
        if not tm:
            continue
        gun, ay, yil, baslik = tm.groups()
        url = urljoin(site + "/", html.unescape(href))
        key = (url, baslik)
        if key in gorulen:
            continue
        gorulen.add(key)
        out.append({"tarih": f"{yil}-{ay}-{gun}", "baslik": baslik, "url": url})
    if not out and "duyuru" not in sayfa.lower():
        raise ValueError("arşiv sayfası tanınmadı")
    return out


SONUC_ICERIK = re.compile(
    r"sözlü sınav[ıi]? sonucunda|sözlü sınav sonuçlar|mülakat sonucunda|"
    r"\bas[iı]l (olarak|aday|liste)|\byedek (olarak|aday|liste)|başarı durumu|atanmaya hak|"
    r"kesin başarı|nihai başarı|başarı sıralaması"
)


def icerik_sonuc_mu(url: str) -> bool | None:
    """Başlığı belirsiz duyurunun gövdesinde sonuç ifadesi var mı? (AMP sürümü daha sade)"""
    m = re.match(r"(https?://[^/]+)/(.+)$", url)
    if not m or "adalet.gov.tr" not in m.group(1) or m.group(2).lower().endswith((".pdf", ".doc", ".docx", ".xls", ".xlsx")):
        return None
    try:
        s = fetch(f"{m.group(1)}/amp/{m.group(2)}", tries=2).decode("utf-8", "replace")
    except Exception:
        try:
            s = fetch(url, tries=2).decode("utf-8", "replace")
        except Exception:
            return None
    s = re.sub(r"<script.*?</script>|<style.*?</style>", " ", s, flags=re.S)
    body = metin(s.split("<body", 1)[-1])
    # Menüden sonra gelen asıl içerik: "T.C." veya "ADALET BAKANLIĞI" ile başlar; bulamazsak tamamı
    i = body.find("T.C.")
    govde = tr_lower(body[i:] if i >= 0 else body)[:6000]
    return bool(SONUC_ICERIK.search(govde))


def site_bul(kid: str, ad: str, siteler: dict) -> str | None:
    if siteler.get(kid):
        return siteler[kid]
    for alt in adaylar(kid, ad):
        site = f"https://{host(alt)}"
        try:
            arsiv_oku(site)
            return site
        except Exception:
            continue
    return None


def komisyon_gruplari(k: dict) -> dict[str, set[str]]:
    return {kur: {u["grup"] for u in v["unvanlar"]} for kur, v in k["kurumlar"].items()}


def durum_hesapla(k: dict, duyurular: list[dict]) -> dict:
    """Her kurum ve ünvan için ulaşılan en ileri aşama."""
    sonuc = {}
    for kur, v in k["kurumlar"].items():
        unv = {u["unvan"]: "yok" for u in v["unvanlar"]}
        gr = {u["unvan"]: u["grup"] for u in v["unvanlar"]}
        son_tarih = None
        for d in duyurular:
            s = d.get("sinif")
            if not s or kur not in s["kurumlar"]:
                continue
            gs = set(s["kurumlar"][kur])
            for u in unv:
                if not gs or gr[u] in gs:
                    if SIRA[d["asama"]] > SIRA[unv[u]]:
                        unv[u] = d["asama"]
            son_tarih = max(son_tarih or d["tarih"], d["tarih"])
        degerler = list(unv.values())
        if all(a == "sonuc" for a in degerler):
            genel = "sonuc"
        elif any(a == "sonuc" for a in degerler):
            genel = "kismen"
        else:
            genel = max(degerler, key=lambda a: SIRA[a])
        sonuc[kur] = {"asama": genel, "unvanlar": unv, "son_duyuru": son_tarih}
    return sonuc


def isle(k: dict, siteler: dict, onceki: dict) -> dict:
    kid = k["id"]
    eski = onceki.get(kid, {})
    simdi = datetime.now(timezone.utc).isoformat(timespec="seconds")
    site = site_bul(kid, k["ad"], siteler)
    kayit = {"site": site, "son_kontrol": simdi}
    tum = {(d["url"], d["baslik"]): d for d in eski.get("duyurular", [])}
    if site is None:
        kayit.update(erisim="bulunamadi", hata="Komisyonun sitesi bulunamadı")
    else:
        try:
            for d in arsiv_oku(site):
                if d["tarih"] < DONEM_BASLANGIC:
                    continue
                tum.setdefault((d["url"], d["baslik"]), d)
            kayit.update(erisim="ok", son_basarili=simdi)
        except Exception as e:
            kayit.update(erisim="hata", hata=f"{type(e).__name__}: {e}"[:200], son_basarili=eski.get("son_basarili"))

    gruplar = komisyon_gruplari(k)
    duyurular = []
    for d in sorted(tum.values(), key=lambda d: d["tarih"], reverse=True):
        s = siniflandir(d["baslik"], gruplar)
        if s is None:
            continue
        asama = s["asama"]
        # Başlık "sözlü sınavına ilişkin duyuru" gibi belirsizse gövdeye bak (bir kez; sonuç önbellekte)
        if asama == "sozlu" and not re.search(r"girmeye hak|katılmaya hak|tarih|yer ve saat|çağrı|katılacak", tr_lower(d["baslik"])):
            if d.get("icerik_sonuc") is None:
                r = icerik_sonuc_mu(d["url"])
                if r is not None:  # erişilemediyse bir dahaki çalıştırmada tekrar dene
                    d["icerik_sonuc"] = r
            if d.get("icerik_sonuc"):
                asama = "sonuc"
        d = {**d, "sinif": s, "asama": asama}
        duyurular.append(d)
    kayit["duyurular"] = duyurular
    kayit["durum"] = durum_hesapla(k, duyurular)
    return kid, kayit, site


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("komisyonlar", nargs="*", help="yalnızca bu komisyon kimlikleri (ör. adana ankara)")
    ap.add_argument("--paralel", type=int, default=8)
    args = ap.parse_args()

    kontenjan = read_json(DATA_DIR / "kontenjan.json")
    if not kontenjan:
        sys.exit("Önce parse_kontenjan.py çalıştırın")
    onceki = (read_json(DURUM, {}) or {}).get("komisyonlar", {})
    for kid, t in ((read_json(TARAMA, {}) or {}).get("komisyonlar", {})).items():
        onceki.setdefault(kid, {}).update(t)
    siteler = kayitli()

    hedef = [k for k in kontenjan["komisyonlar"] if not args.komisyonlar or k["id"] in args.komisyonlar]
    sonuc = dict(onceki)
    with ThreadPoolExecutor(max_workers=args.paralel) as ex:
        for kid, kayit, site in ex.map(lambda k: isle(k, siteler, onceki), hedef):
            sonuc[kid] = kayit
            if site:
                siteler[kid] = site
            elif kid not in siteler:
                siteler[kid] = None
            durumlar = " ".join(f"{kur}:{v['asama']}" for kur, v in kayit["durum"].items())
            print(f"{kid:28} {kayit['erisim']:10} {len(kayit['duyurular']):3} duyuru  {durumlar}", flush=True)

    kaydet(siteler)
    sirali = dict(sorted(sonuc.items()))
    write_json(DURUM, {
        "donem_baslangic": DONEM_BASLANGIC,
        "komisyonlar": {kid: {a: v for a, v in k.items() if a not in TARAMA_ALANLARI} for kid, k in sirali.items()},
    })
    write_json(TARAMA, {
        "guncelleme": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "komisyonlar": {kid: {a: k[a] for a in TARAMA_ALANLARI if k.get(a) is not None} for kid, k in sirali.items()},
    })
    ok = sum(1 for v in sonuc.values() if v.get("erisim") == "ok")
    print(f"\n{ok}/{len(sonuc)} komisyon sitesi okundu → {DURUM}")


if __name__ == "__main__":
    main()
