"""Duyuru başlıklarını kurum / ünvan / aşama olarak sınıflandırır.

Komisyon siteleri sonuçları standart bir biçimde yayımlamıyor; başlıklar serbest metin.
Bu yüzden kural tabanlı, açıklanabilir bir sınıflandırma yapıyoruz. Her duyuru sitede
başlığı ve bağlantısıyla gösterildiği için kullanıcı her zaman kaynağı kontrol edebilir.
"""
from __future__ import annotations

import re

from common import tr_lower

# Aşamalar (sıralı). Bir komisyonun durumu, gördüğümüz en ileri aşamadır.
ASAMALAR = ["yok", "ilan", "aday", "uygulama", "sozlu", "sonuc"]
ASAMA_ETIKET = {
    "yok": "Henüz duyuru yok",
    "ilan": "Alım ilanı paylaşıldı",
    "aday": "Aday listesi yayımlandı",
    "uygulama": "Uygulama sınavı aşamasında",
    "sozlu": "Sözlü sınav aşamasında",
    "sonuc": "Sonuç açıklandı",
}

# Bu döngüyle ilgisi olmayan duyurular
HARIC = re.compile(
    r"\biup\b|iyup|i̇şkur|işkur|temizlik|tercüman|lojman|staj|bilirkişi|arabulucu|"
    r"aday memur|hazırlayıcı|görevde yükselme|unvan değişikliği|ünvan değişikliği|"
    r"engelli|ekpss|basın açıklaması|broşür|faaliyet raporu|zabıt kâtipliği eğitim|"
    r"31\.07\.2025|2025 yılı sözleşmeli|tarihli ilanı ile sözleşmeli infaz koruma memuru, hemşire"
)

ILGILI = re.compile(
    r"sözleşmeli|sozlesmeli|sınav|mülakat|aday tespit|aday listesi|zabıt|mübaşir|icra k[aâ]tib|"
    r"icra k[aâ]tipli|infaz|\bcte\b|\bpgm\b|hizmetli|şoför|aşçı|teknisyen|koruma ve güvenlik|"
    r"hemşire|kaloriferci|cezaevi k[aâ]tib|ceza infaz kurumu k[aâ]tib|personel alım|boy[ -]kilo|\bikm\b"
)

# Ünvan grupları: (grup, desen)
GRUP_DESEN = [
    ("zabit", r"zab[ıi]t"),
    ("mubasir", r"müba[şs]ir"),
    ("koruma", r"koruma ve güvenlik"),
    ("hizmetli", r"hizmetli"),
    ("sofor", r"[şs]oför"),
    ("asci", r"a[şs][çc][ıi]"),
    ("kaloriferci", r"kalorifer"),
    ("hemsire", r"hem[şs]ire"),
    ("buro", r"cezaevi k[aâ]tib|ceza infaz kurumu k[aâ]tib|büro personel|\bcik k[aâ]tib"),
    ("ikm", r"infaz ve koruma|infaz koruma|\bikm\b|boy[ -]kilo"),
    ("teknisyen", r"teknisyen"),
    ("icra", r"icra k[aâ]tib|icra k[aâ]tipli|icra işleri"),
]

KURUM_GRUPLARI = {
    "pgm": {"zabit", "mubasir", "koruma", "hizmetli", "sofor", "asci", "teknisyen"},
    "icra": {"icra"},
    "cte": {"ikm", "buro", "hemsire", "sofor", "asci", "kaloriferci", "teknisyen"},
}
SADECE = {g: [k for k, gs in KURUM_GRUPLARI.items() if g in gs] for g in set().union(*KURUM_GRUPLARI.values())}

CTE_DESEN = re.compile(r"\bcte\b|ceza ve tevkif|tevkifevleri|05\.06\.2026|5766|5\.766")
PGM_DESEN = re.compile(r"\bpgm\b|personel genel müdürlü")
ICRA_DESEN = re.compile(r"icra işleri|iidb")


def asama_bul(t: str) -> str:
    """t: küçük harfli başlık"""
    sozlu = r"sözlü|mülakat"
    if re.search(rf"({sozlu})\s*(sınav[ıi]?|mülakat[ıi]?)?\s*(sonuç|netice)", t) or re.search(
        r"nihai|kesin (sonuç|başarı|liste)|başarı (sıra|liste)|asıl ve yedek|asil ve yedek|"
        r"(asıl|yedek) (aday|liste)|yerleştirme sonuç|kazananlar(ın)? listesi|başarılı (olan )?aday", t
    ):
        if "girmeye hak" not in t and "katılmaya hak" not in t:
            return "sonuc"
    if re.search(rf"uygulama(lı)?\s*sınav[ıi]?\s*(sonuç|netice)", t) or re.search(
        rf"({sozlu})", t
    ):
        return "sozlu"
    if re.search(r"uygulama|klavye|daktilo|uygulamalı", t):
        return "uygulama"
    if re.search(r"aday|başvuru|boy[ -]kilo|red listesi|ön değerlendirme|tespit", t):
        return "aday"
    if re.search(r"sınav", t):
        return "uygulama"
    if re.search(r"alım ilan|alımı ilan|personel alım|istihdam", t):
        return "ilan"
    return "aday"


def siniflandir(baslik: str, komisyon_gruplari: dict[str, set[str]] | None = None) -> dict | None:
    """Başlığı sınıflandırır; ilgisizse None döner.

    komisyon_gruplari: {kurum: {grup,...}} — bu komisyonda hangi kurum hangi ünvanla alım
    yapıyor. Belirsiz başlıkları (ör. yalnızca "Şoför") doğru kuruma bağlamakta kullanılır.
    """
    t = tr_lower(baslik)
    if HARIC.search(t) or not ILGILI.search(t):
        return None

    gruplar = {g for g, d in GRUP_DESEN if re.search(d, t)}
    # "koruma ve güvenlik" içinde "koruma" geçtiği için ikm ile karışmasın
    if "koruma" in gruplar and not re.search(r"infaz", t):
        gruplar.discard("ikm")

    kurumlar: set[str] = set()
    if CTE_DESEN.search(t):
        kurumlar.add("cte")
    if PGM_DESEN.search(t):
        kurumlar.add("pgm")
    if ICRA_DESEN.search(t) or "icra" in gruplar:
        kurumlar.add("icra")
    # Ünvandan kurum çıkarımı
    for g in gruplar:
        sahipler = SADECE.get(g, [])
        if len(sahipler) == 1:
            kurumlar.add(sahipler[0])
    belirsiz = False
    if not kurumlar:
        adaylar = set(KURUM_GRUPLARI)
        if gruplar:
            adaylar = {k for k in adaylar if KURUM_GRUPLARI[k] & gruplar}
        if komisyon_gruplari is not None:
            adaylar = {k for k in adaylar if k in komisyon_gruplari and (not gruplar or komisyon_gruplari[k] & gruplar)}
        kurumlar = adaylar
        belirsiz = len(kurumlar) != 1
    # Kurumla uyuşmayan grupları ele (ör. "zabıt ve icra kâtipliği" → pgm:zabit, icra:icra)
    kurum_gruplari = {}
    for k in kurumlar:
        gs = gruplar & KURUM_GRUPLARI[k]
        if gruplar and not gs:
            # bu kurum ünvan üzerinden değil, açık bir kurum adıyla geldi; ünvan yoksa genel duyuru
            gs = set()
        kurum_gruplari[k] = sorted(gs)
    if not kurum_gruplari:
        return None
    return {"kurumlar": kurum_gruplari, "asama": asama_bul(t), "belirsiz": belirsiz}
