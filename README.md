# Adliye Alım Takip

2026 sözleşmeli personel alımlarında hangi adalet komisyonunun sonuç açıkladığını,
hangi komisyonun hangi aşamada olduğunu ve nerede kaç kişi alındığını gösteren site.

Takip edilen ilanlar:

| Kurum | İlan | Kadro | Komisyon |
|---|---|---:|---:|
| Adalet Bakanlığı Personel Genel Müdürlüğü (PGM) | [06.06.2026](https://pgm.adalet.gov.tr/Home/SayfaDetay/2026sozlesmelitasra) | 7.615 | 192 |
| İcra İşleri Dairesi Başkanlığı (İcra kâtibi) | [06.06.2026](https://iidb.adalet.gov.tr/Home/SayfaDetay/sozlesmeli-icra-k-tibi-personel-istihdami-sinav-ilani05062026110033) | 900 | 65 |
| Ceza ve Tevkifevleri Genel Müdürlüğü (CTE) | [05.06.2026](https://cte.adalet.gov.tr/Home/SayfaDetay/5766-sozlesmeli-personel-komisyon-alim-ilani05062026050723) | 5.766 | 117 |

## Nasıl çalışıyor?

1. **Kontenjanlar** (`scraper/parse_kontenjan.py`): Üç ilanın Ek-1 PDF'leri indirilir,
   tablolar okunur ve komisyon → kurum → ünvan → adliye/kurum kırılımında
   `site/data/kontenjan.json` üretilir. Toplamlar ilan metinleriyle birebir tutar
   (PGM 7.615, genel 5.308, öncelikli 992; İcra 900; CTE 5.766).
2. **Durum** (`scraper/scrape_duyurular.py`): Her komisyonun `https://<komisyon>.adalet.gov.tr/Arsiv/duyuru`
   sayfası taranır. Bu döngüye ait (05.06.2026 sonrası) duyurular başlığına göre
   sınıflandırılır (`scraper/siniflandir.py`):
   - **kurum**: “CTE / Ceza ve Tevkifevleri”, “Personel Genel Müdürlüğü / PGM”, “İcra kâtibi” ifadeleri;
     yoksa ünvandan (zabıt kâtibi → PGM, infaz ve koruma → CTE…). Şoför, aşçı, teknisyen gibi iki
     kurumda da olan ünvanlarda komisyonun gerçekten hangi kurum için sınav yaptığına bakılır.
   - **aşama**: aday listesi → uygulama sınavı → sözlü sınav → sonuç.
   - Başlığı belirsiz (“… Sözlü Sınavına İlişkin Duyuru”) duyuruların metni de okunur;
     “sözlü sınav sonucunda başarılı olan adaylar”, “asıl / yedek” gibi ifadeler varsa sonuç sayılır.
   Görülen duyurular birikimli saklanır; arşiv sayfasından düşse bile kaybolmaz. Her duyurunun
   ilk görüldüğü an (`ilk_gorulme`) kaydedilir; sitede son 3 günün sonuçları en üstte öne çıkarılır.
3. **Site** (`site/`): Bağımlılıksız statik sayfa. `data/kontenjan.json`, `data/durum.json` ve
   `data/tarama.json` dosyalarını okur.

Komisyon adından site adresi tahmin edilir (`Ankara Batı` → `ankarabati.adalet.gov.tr`).
Tahmin tutmazsa adres `scraper/komisyon_siteleri.json` dosyasına elle yazılabilir.

## Otomatik güncelleme ve yayın

`.github/workflows/guncelle.yml` her saat komisyon sitelerini tarar, yeni duyuru varsa
veriyi depoya işler ve siteyi GitHub Pages'e yayımlar. Bunun için bir kez:

1. Bu dalı `main`'e birleştirin (zamanlanmış görevler yalnızca varsayılan dalda çalışır).
2. **Settings → Pages → Build and deployment → Source: GitHub Actions** seçin.
3. **Actions** sekmesinden “Verileri güncelle ve yayımla”yı bir kez elle çalıştırın.

## Yerelde çalıştırma

```bash
pip install -r scraper/requirements.txt
python scraper/parse_kontenjan.py          # Ek-1 PDF'lerinden kontenjanlar
python scraper/scrape_duyurular.py         # tüm komisyonlar (ya da: ... adana ankara)
python -m http.server -d site 8000         # http://localhost:8000
```

## Uyarı

Bu site resmi değildir; bilgiler otomatik toplanır ve sınıflandırma hatalı olabilir.
Her duyuru kaynağına bağlantı verir. Sonucunuzu her zaman ilgili komisyonun kendi sitesinden doğrulayın.
