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
    r"\biup\b|iyup|i̇şkur|işkur|iş ?gücü|işgücü|temizlik|tercüman|lojman|staj|bilirkişi|arabulucu|uzlaştırma|"
    r"aday memur|hazırlayıcı|görevde yükselme|unvan değişikliği|ünvan değişikliği|izleme kurulu|ek ders|"
    r"engelli|ekpss|basın açıklaması|broşür|faaliyet raporu|zabıt kâtipliği eğitim|temel eğitim|"
    r"31\.07\.2025|2025 yılı sözleşmeli|tarihli ilanı ile sözleşmeli infaz koruma memuru, hemşire"
)

KATIP = r"k[aâ]ti[bp]"  # "kâtibi", "katipliği", "kâtipliği"…
ILGILI = re.compile(
    rf"sözleşmeli|sozlesmeli|sınav|mülakat|aday tespit|aday listesi|zabıt|mübaşir|icra {KATIP}|"
    rf"infaz|\bcte\b|c\.t\.e|\bpgm\b|hizmetli|şoför|aşçı|teknisyen|koruma ve güvenlik|"
    rf"hemşire|kaloriferci|cezaevi {KATIP}|ceza infaz kurumu {KATIP}|büro personel|personel alım|boy\W{0,3}kilo|\bikm\b"
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
    ("buro", rf"cezaevi {KATIP}|ceza infaz kurumu {KATIP}|büro personel|\bcik {KATIP}"),
    ("ikm", r"infaz ve koruma|infaz koruma|\bikm\b|boy\W{0,3}kilo"),
    ("teknisyen", r"teknisyen"),
    ("icra", rf"icra {KATIP}|icra işleri"),
]

KURUM_GRUPLARI = {
    "pgm": {"zabit", "mubasir", "koruma", "hizmetli", "sofor", "asci", "teknisyen"},
    "icra": {"icra"},
    "cte": {"ikm", "buro", "hemsire", "sofor", "asci", "kaloriferci", "teknisyen"},
}
SADECE = {g: [k for k, gs in KURUM_GRUPLARI.items() if g in gs] for g in set().union(*KURUM_GRUPLARI.values())}

CTE_DESEN = re.compile(r"\bcte\b|c\.t\.e|ceza ve tevkif|tevkifevleri|05\.06\.2026|5766|5\.766|ceza infaz kurum|cezaevi")
PGM_DESEN = re.compile(r"\bpgm\b|personel genel müdürlü")
ICRA_DESEN = re.compile(r"icra işleri|iidb")

SONUC = r"sonu[çc]|netice"          # sonuç, sonucu, sonuçları, sonucuna…
KESIN = re.compile(
    r"nihai|kesin (sonu[çc]|başarı|liste)|kesinleşen|başarı (sıra|liste)|as[iı]l ve yedek|"
    r"(as[iı]l|yedek) (aday|liste)|yerleştirme sonu[çc]|kazananlar(ın)? listesi|başarılı (olan )?aday|atanmaya hak"
)
ON_ASAMA = re.compile(r"başvuru|başsvuru|aday tespit|tespit|ön değerlendirme|boy\W{0,3}kilo|mazeret|itiraz|ertele")
UYGULAMA = re.compile(r"uygulama|uyglama|klavye|daktilo")
SOZLU = re.compile(r"sözlü|mülakat")
SOZLU_CAGRI = re.compile(r"girmeye hak|katılmaya hak|çağrılmaya hak|çağrılacak|katılacak|hak kazanan adayların sorgu")


def asama_bul(t: str) -> tuple[str, bool]:
    """t: küçük harfli başlık. Dönüş: (aşama, doğrulanmalı_mı).

    doğrulanmalı=True: başlık yalnızca "… Sonuçları" diyor; hangi aşamanın sonucu olduğu belli
    değil. Tarayıcı duyuru metnine bakar, metin de net değilse tarihe göre karar verir.
    """
    sonuc_var = re.search(SONUC, t)
    if KESIN.search(t) and not SOZLU_CAGRI.search(t):
        return "sonuc", False
    # "Sözlü Sınav Sonucu", "Mülakat Sonuçları" (arada en fazla bir kelime)
    if re.search(rf"(sözlü|mülakat)\w*\s+(\w+\s+)?({SONUC})", t) and not ON_ASAMA.search(t):
        return "sonuc", False
    if UYGULAMA.search(t):
        if SOZLU.search(t):
            return "sozlu", False      # "uygulama sonuçları ve sözlü sınav tarihleri"
        if sonuc_var and not ON_ASAMA.search(t) and not re.search(r"girmeye|katılmaya|çağrıl", t):
            return "sozlu", False      # uygulama sınavı sonuçlandı → sıradaki aşama sözlü
        return "uygulama", False       # uygulama sınavına çağrı, mazeret, başvuru sonuçları
    if "hak kazan" in t:
        if SOZLU.search(t) or SOZLU_CAGRI.search(t):
            return "sozlu", False
        return "sonuc", True           # "Şoför hak kazanan adaylara ilişkin liste" → metne/tarihe bak
    if SOZLU.search(t):
        return "sozlu", False
    if sonuc_var and not ON_ASAMA.search(t):
        return "sonuc", True           # "Sözleşmeli Hemşire Sonuçları", "Personel Alım Sonuçları"
    if re.search(r"aday|başvuru|boy\W{0,3}kilo|red listesi|ön değerlendirme|tespit", t):
        return "aday", False
    if re.search(r"sınav", t):
        return "uygulama", False
    if re.search(r"alım ilan|alımı ilan|personel alım|istihdam", t):
        return "ilan", False
    return "aday", False


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
    for k in sorted(kurumlar):  # sıralı: set sırası süreçten sürece değişir, gereksiz commit üretir
        gs = gruplar & KURUM_GRUPLARI[k]
        if gruplar and not gs:
            # bu kurum ünvan üzerinden değil, açık bir kurum adıyla geldi; ünvan yoksa genel duyuru
            gs = set()
        kurum_gruplari[k] = sorted(gs)
    if not kurum_gruplari:
        return None
    asama, dogrula = asama_bul(t)
    return {"kurumlar": kurum_gruplari, "asama": asama, "dogrula": dogrula, "belirsiz": belirsiz}
