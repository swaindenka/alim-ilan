/* Adliye Alım Takip — veriler: data/kontenjan.json (PDF'lerden), data/durum.json (komisyon siteleri) */
(() => {
  "use strict";

  const ASAMA = {
    sonuc:      { ad: "Sonuç açıklandı",          kisa: "Sonuç açıklandı", sira: 7 },
    kismen:     { ad: "Bazı ünvanlarda sonuç var", kisa: "Kısmen açıklandı", sira: 6 },
    sozlu:      { ad: "Sözlü sınav aşamasında",   kisa: "Sözlü sınav",     sira: 5 },
    uygulama:   { ad: "Uygulama sınavı aşamasında", kisa: "Uygulama sınavı", sira: 4 },
    aday:       { ad: "Aday listesi yayımlandı",  kisa: "Aday listesi",    sira: 3 },
    ilan:       { ad: "Yalnızca ilan paylaşıldı", kisa: "İlan paylaşıldı", sira: 2 },
    yok:        { ad: "Henüz duyuru yok",         kisa: "Duyuru yok",      sira: 1 },
    bilinmiyor: { ad: "Komisyon sitesi henüz kontrol edilemedi", kisa: "Kontrol edilemedi", sira: 0 },
  };
  const OZET_SIRA = ["sonuc", "kismen", "sozlu", "uygulama", "aday", "ilan", "yok", "bilinmiyor"];
  const KURUM = {
    pgm:  { kisa: "PGM",  ad: "Adalet Bakanlığı Personel Genel Müdürlüğü" },
    icra: { kisa: "İcra", ad: "İcra İşleri Dairesi Başkanlığı" },
    cte:  { kisa: "CTE",  ad: "Ceza ve Tevkifevleri Genel Müdürlüğü" },
  };
  const KURUMLAR = ["pgm", "icra", "cte"];
  const IZ = ["aday", "uygulama", "sozlu", "sonuc"];

  let K = null, D = { komisyonlar: {} };
  const DAR = window.matchMedia && window.matchMedia("(max-width: 1020px)").matches;
  const AKIS_ILK = DAR ? 4 : 8;
  const durum = { q: "", kurum: "", unvan: "", filtre: "", sira: "ad", takip: false, sekme: "sonuc", akisLimit: AKIS_ILK };
  let takip = new Set();

  /* ---------- yardımcılar ---------- */
  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const guvenliUrl = (u) => (/^https?:\/\//i.test(u || "") ? u : "#");
  const fold = (s) => String(s || "").toLocaleLowerCase("tr").normalize("NFD").replace(/[̀-ͯ]/g, "").replace(/ı/g, "i");
  const sayi = (n) => Number(n || 0).toLocaleString("tr-TR");
  const tarih = (t, uzun) => {
    if (!t) return "";
    const [y, m, d] = t.split("-").map(Number);
    return new Date(y, m - 1, d).toLocaleDateString("tr-TR", uzun ? { day: "numeric", month: "long", year: "numeric" } : { day: "numeric", month: "short" });
  };
  const zaman = (iso) => iso ? new Date(iso).toLocaleString("tr-TR", { day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "Europe/Istanbul" }) : "";
  // Akışta uzun resmî ön eki kısalt (kurum etiketi zaten gösteriliyor); tam başlık detayda kalır.
  const kisaBaslik = (b) => {
    const k = String(b || "").replace(/^(T\.C\.\s*)?(Adalet Bakanlığı\s+)?(Personel Genel Müdürlüğü(nün|nce)?|İcra İşleri Dairesi Başkanlığı(nın|nca)?|Ceza ve Tevki[a-zçğıöşü]* Genel Müdürlüğü(nün|nce)?)\s+\d{2}[./]\d{2}[./]\d{4}\s+[Tt]arihli\s+[İi]lanı\s+(Gereği|gereğince|Gereğince|ile)\s+(Yapılan\s+)?/i, "");
    return k.length > 8 ? k.charAt(0).toLocaleUpperCase("tr") + k.slice(1) : b;
  };
  const hap = (a, etiket) => `<span class="hap ${a}" title="${esc(ASAMA[a].ad)}"><i class="nokta st-${a}"></i>${esc(etiket || ASAMA[a].kisa)}</span>`;
  const YILDIZ = '<svg viewBox="0 0 20 20" aria-hidden="true"><path d="M10 2.5l2.3 4.8 5.2.7-3.8 3.6.9 5.2L10 14.3 5.4 16.8l.9-5.2L2.5 8l5.2-.7z"/></svg>';
  const sakla = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (_) {} };
  const oku = (k, v) => { try { const x = localStorage.getItem(k); return x ? JSON.parse(x) : v; } catch (_) { return v; } };

  /* ---------- durum hesapları ---------- */
  function okundu(id) {
    const d = D.komisyonlar[id];
    return !!(d && d.durum && (d.erisim === "ok" || d.son_basarili));
  }
  function kurumAsama(k, kur, unvan) {
    if (!k.kurumlar[kur]) return null;
    if (!okundu(k.id)) return "bilinmiyor";
    const d = D.komisyonlar[k.id].durum[kur];
    if (!d) return "yok";
    if (unvan) return k.kurumlar[kur].unvanlar.some((u) => u.unvan === unvan) ? (d.unvanlar[unvan] || "yok") : null;
    return d.asama;
  }
  function genelAsama(k) {
    const kurs = durum.kurum ? [durum.kurum] : KURUMLAR;
    const a = kurs.map((kur) => kurumAsama(k, kur, durum.kurum ? durum.unvan : "")).filter(Boolean);
    if (!a.length) return null;
    if (a.every((x) => x === "bilinmiyor")) return "bilinmiyor";
    if (a.every((x) => x === "sonuc")) return "sonuc";
    if (a.some((x) => x === "sonuc" || x === "kismen")) return "kismen";
    return a.reduce((m, x) => (ASAMA[x].sira > ASAMA[m].sira ? x : m));
  }
  function kadro(k, kur, unvan) {
    const v = k.kurumlar[kur];
    if (!v) return 0;
    if (unvan) return v.unvanlar.filter((u) => u.unvan === unvan).reduce((s, u) => s + u.toplam, 0);
    return v.toplam;
  }
  function sonDuyuru(k) {
    const d = D.komisyonlar[k.id];
    if (!d || !d.duyurular) return "";
    const kurs = durum.kurum ? [durum.kurum] : KURUMLAR;
    const x = d.duyurular.find((y) => kurs.some((kur) => y.sinif && y.sinif.kurumlar[kur]));
    return x ? x.tarih : "";
  }
  function yerEslesme(k, q) {
    if (!q) return "";
    for (const kur of KURUMLAR) {
      const v = k.kurumlar[kur];
      if (!v) continue;
      for (const u of v.unvanlar) for (const y of u.yerler || []) if (fold(y.yer).includes(q)) return y.yer;
    }
    return "";
  }

  /* ---------- özet kartları ---------- */
  function ozetCiz() {
    const html = KURUMLAR.map((kur) => {
      const ks = K.komisyonlar.filter((k) => k.kurumlar[kur]);
      const say = Object.fromEntries(OZET_SIRA.map((a) => [a, 0]));
      let acik = 0, toplam = 0;
      for (const k of ks) {
        say[kurumAsama(k, kur, "")]++;
        for (const u of k.kurumlar[kur].unvanlar) {
          toplam += u.toplam;
          if (okundu(k.id) && (D.komisyonlar[k.id].durum[kur] || {}).unvanlar?.[u.unvan] === "sonuc") acik += u.toplam;
        }
      }
      const serit = OZET_SIRA.filter((a) => say[a]).map((a) => `<span class="st-${a}" style="width:${(100 * say[a]) / ks.length}%" title="${esc(ASAMA[a].kisa)}: ${say[a]}"></span>`).join("");
      const lejant = OZET_SIRA.filter((a) => say[a]).map((a) => `<li><i class="nokta st-${a}"></i>${esc(ASAMA[a].kisa)} <b>${say[a]}</b></li>`).join("");
      const yuzde = toplam ? Math.round((100 * acik) / toplam) : 0;
      return `<button type="button" class="kart" data-kur="${kur}" aria-pressed="${durum.kurum === kur}">
        <div class="kart-ust">
          <div><h3>${esc(KURUM[kur].kisa === "İcra" ? "İcra Kâtibi" : KURUM[kur].kisa)}</h3><div class="kurum-ad">${esc(KURUM[kur].ad)}</div></div>
          <div class="buyuk">${sayi(toplam)}<small>kadro · ${ks.length} komisyon</small></div>
        </div>
        <div class="serit" role="img" aria-label="${esc(OZET_SIRA.filter((a) => say[a]).map((a) => ASAMA[a].kisa + " " + say[a]).join(", "))}">${serit}</div>
        <ul class="lejant">${lejant}</ul>
        <div class="oran"><b>${sayi(acik)}</b> kadronun sonucu açıklandı (%${yuzde})</div>
      </button>`;
    }).join("");
    $("#ozet").innerHTML = html;
  }

  /* ---------- tablo ---------- */
  function filtrele() {
    const q = fold(durum.q.trim());
    let ks = K.komisyonlar.filter((k) => {
      if (durum.kurum && !k.kurumlar[durum.kurum]) return false;
      if (durum.kurum && durum.unvan && !kadro(k, durum.kurum, durum.unvan)) return false;
      if (durum.takip && !takip.has(k.id)) return false;
      if (q && !fold(k.ad).includes(q) && !fold(k.il).includes(q) && !yerEslesme(k, q)) return false;
      const a = genelAsama(k);
      if (durum.filtre === "sonuc" && a !== "sonuc") return false;
      if (durum.filtre === "kismen" && a !== "kismen") return false;
      if (durum.filtre === "bekliyor" && (a === "sonuc" || a === "kismen" || a === "bilinmiyor")) return false;
      if (durum.filtre === "bilinmiyor" && a !== "bilinmiyor") return false;
      return true;
    });
    const toplamKadro = (k) => (durum.kurum ? kadro(k, durum.kurum, durum.unvan) : k.toplam);
    if (durum.sira === "kadro") ks.sort((a, b) => toplamKadro(b) - toplamKadro(a));
    else if (durum.sira === "son") ks.sort((a, b) => (sonDuyuru(b) || "").localeCompare(sonDuyuru(a) || "") || a.ad.localeCompare(b.ad, "tr"));
    else ks.sort((a, b) => a.ad.localeCompare(b.ad, "tr"));
    if (!durum.takip && takip.size && durum.sira === "ad") {
      ks = [...ks.filter((k) => takip.has(k.id)), ...ks.filter((k) => !takip.has(k.id))];
    }
    return ks;
  }

  function tabloCiz() {
    const ks = filtrele();
    const q = fold(durum.q.trim());
    const tablo = $("#tablo");
    tablo.classList.remove("f-pgm", "f-icra", "f-cte");
    if (durum.kurum) tablo.classList.add("f-" + durum.kurum);
    $("#satirlar").innerHTML = ks.map((k) => {
      const kurHucre = KURUMLAR.map((kur) => {
        const unv = durum.kurum === kur ? durum.unvan : "";
        const a = kurumAsama(k, kur, unv);
        if (!a) return `<span class="c-kur yok-kurum" role="cell" data-kur="${kur}">—</span>`;
        return `<span class="c-kur" role="cell" data-kur="${kur}"><span class="etiket">${KURUM[kur].kisa}</span>${hap(a)}<span class="kadro"><b>${sayi(kadro(k, kur, unv))}</b> kadro</span></span>`;
      }).join("");
      let ipucu = "";
      if (q && !fold(k.ad).includes(q)) {
        const y = yerEslesme(k, q);
        if (y) ipucu = `<span class="ipucu"><mark>${esc(y)}</mark> bu komisyona bağlı</span>`;
      }
      if (!ipucu && k.il && fold(k.il) !== fold(k.ad)) ipucu = `<span class="ipucu">${esc(k.il)}</span>`;
      const son = sonDuyuru(k);
      const t = takip.has(k.id);
      return `<div class="satir" role="row" data-id="${esc(k.id)}" tabindex="0" aria-label="${esc(k.ad)} ayrıntıları">
        <span class="c-yildiz" role="cell"><button type="button" class="yildiz" data-takip="${esc(k.id)}" aria-pressed="${t}" aria-label="${esc(k.ad)} ${t ? "takipten çıkar" : "takip et"}">${YILDIZ}</button></span>
        <span class="c-ad" role="cell"><span class="ad">${esc(k.ad)}${yeniSonucVar(k) ? ' <span class="yeni-rozet kucuk">Yeni sonuç</span>' : ""}</span>${ipucu}</span>
        <span class="kurlar">${kurHucre}</span>
        <span class="c-son" role="cell">${son ? tarih(son) : "—"}</span>
      </div>`;
    }).join("");
    $("#bos").hidden = ks.length > 0;
    $("#sayac").textContent = ks.length === K.komisyonlar.length ? `${K.komisyonlar.length} komisyon` : `${K.komisyonlar.length} komisyondan ${ks.length} tanesi`;
  }

  /* ---------- yeni açıklanan sonuçlar ---------- */
  const YENI_GUN = 3;               // son kaç günün sonuçları öne çıkarılır
  let sonZiyaret = "";              // ziyaretçinin bir önceki gelişi (ISO), tarayıcıda saklanır
  let yeniHepsi = false;
  // Duyurunun "görülme" anı: tarayıcı ilk gördüğü anı kaydeder; yoksa duyuru tarihi
  const gorulme = (x) => x.ilk_gorulme || (x.tarih + "T00:00:00");
  const gunOnce = (n) => { const d = new Date(); d.setDate(d.getDate() - n); return d.toISOString().slice(0, 10); };
  const once = (iso) => {
    const dk = Math.round((Date.now() - new Date(iso).getTime()) / 6e4);
    if (dk < 60) return `${Math.max(dk, 1)} dk önce`;
    if (dk < 1440) return `${Math.round(dk / 60)} saat önce`;
    return `${Math.round(dk / 1440)} gün önce`;
  };
  function unvanEtiketleri(k, kur, gruplar) {
    const v = k.kurumlar[kur];
    if (!v) return { adlar: [], kadro: 0 };
    const us = v.unvanlar.filter((u) => !gruplar.length || gruplar.includes(u.grup));
    const adlar = [...new Set(us.map((u) => u.unvan.replace(/\s+-\s+.*$/, "")))];
    return { adlar, kadro: us.reduce((t, u) => t + u.toplam, 0), hepsi: !gruplar.length };
  }
  function yeniSonuclar() {
    const sinir = gunOnce(YENI_GUN);
    const gruplar = new Map();
    for (const [id, d] of Object.entries(D.komisyonlar)) {
      const k = K.byId[id];
      if (!k || !d.duyurular) continue;
      for (const x of d.duyurular) {
        if (x.asama !== "sonuc" || gorulme(x).slice(0, 10) < sinir) continue;
        for (const [kur, gs] of Object.entries(x.sinif?.kurumlar || {})) {
          if (!k.kurumlar[kur]) continue;
          if (durum.kurum && durum.kurum !== kur) continue;
          const key = id + "|" + kur;
          const g = gruplar.get(key) || { k, kur, gruplar: new Set(), hepsi: false, duyurular: [], zaman: "" };
          if (!gs.length) g.hepsi = true;
          gs.forEach((x2) => g.gruplar.add(x2));
          g.duyurular.push(x);
          if (gorulme(x) > g.zaman) g.zaman = gorulme(x);
          gruplar.set(key, g);
        }
      }
    }
    return [...gruplar.values()].sort((a, b) => b.zaman.localeCompare(a.zaman) || a.k.ad.localeCompare(b.k.ad, "tr"));
  }
  function yeniCiz() {
    const liste = yeniSonuclar();
    const kutu = $("#yeni");
    kutu.hidden = liste.length === 0;
    if (!liste.length) return;
    const yeniSay = sonZiyaret ? liste.filter((g) => g.zaman > sonZiyaret).length : 0;
    const komSay = new Set(liste.map((g) => g.k.id)).size;
    $("#yeni-alt").innerHTML = `Son ${YENI_GUN} günde <b>${komSay}</b> komisyon sonuç açıkladı` +
      (yeniSay ? ` · <span class="yeni-rozet">${yeniSay} sonuç son ziyaretinden sonra</span>` : "");
    const limit = yeniHepsi ? liste.length : (DAR ? 4 : 8);
    $("#yeni-liste").innerHTML = liste.slice(0, limit).map((g) => {
      const e = unvanEtiketleri(g.k, g.kur, g.hepsi ? [] : [...g.gruplar]);
      const yeni = sonZiyaret && g.zaman > sonZiyaret;
      const son = g.duyurular.sort((a, b) => gorulme(b).localeCompare(gorulme(a)))[0];
      const zamanMetni = son.ilk_gorulme ? `${once(son.ilk_gorulme)} tespit edildi` : tarih(son.tarih, true);
      return `<li class="${yeni ? "taze" : ""}">
        <div class="y-ust">
          <button type="button" class="y-ad" data-ac="${esc(g.k.id)}">${esc(g.k.ad)}</button>
          <span class="kur-etiket">${KURUM[g.kur].kisa}</span>
          ${yeni ? '<span class="yeni-rozet">Yeni</span>' : ""}
          <span class="y-zaman">${esc(zamanMetni)}</span>
        </div>
        <div class="y-unvan">${e.hepsi ? "Tüm ünvanlar" : esc(e.adlar.join(", "))}${e.kadro ? ` · <b class="num">${sayi(e.kadro)}</b> kadro` : ""}</div>
        <a href="${esc(guvenliUrl(son.url))}" target="_blank" rel="noopener" title="${esc(son.baslik)}">${esc(kisaBaslik(son.baslik))}${g.duyurular.length > 1 ? ` <span class="y-ek">+${g.duyurular.length - 1} duyuru</span>` : ""}</a>
      </li>`;
    }).join("");
    $("#yeni-daha").hidden = liste.length <= limit;
    $("#yeni-daha").textContent = `Tümünü göster (${liste.length})`;
  }
  function yeniSonucVar(k) {
    const d = D.komisyonlar[k.id];
    if (!d || !d.duyurular) return false;
    const sinir = gunOnce(YENI_GUN);
    return d.duyurular.some((x) => x.asama === "sonuc" && gorulme(x).slice(0, 10) >= sinir &&
      Object.keys(x.sinif?.kurumlar || {}).some((kur) => k.kurumlar[kur] && (!durum.kurum || durum.kurum === kur)));
  }

  /* ---------- akış ---------- */
  function akisCiz() {
    const liste = [];
    for (const [id, d] of Object.entries(D.komisyonlar)) {
      const k = K.byId[id];
      if (!k || !d.duyurular) continue;
      for (const x of d.duyurular) {
        if (durum.sekme === "sonuc" && x.asama !== "sonuc") continue;
        const kurs = Object.keys(x.sinif?.kurumlar || {});
        if (durum.kurum && !kurs.includes(durum.kurum)) continue;
        if (durum.takip && !takip.has(id)) continue;
        liste.push({ ...x, k, kurs });
      }
    }
    liste.sort((a, b) => b.tarih.localeCompare(a.tarih) || gorulme(b).localeCompare(gorulme(a)) || a.k.ad.localeCompare(b.k.ad, "tr"));
    const goster = liste.slice(0, durum.akisLimit);
    $("#akis").innerHTML = goster.length ? goster.map((x) => `<li>
        <div class="akis-meta"><span>${tarih(x.tarih)}</span><button type="button" data-ac="${esc(x.k.id)}">${esc(x.k.ad)}</button>${x.kurs.map((kur) => `<span class="kur-etiket">${KURUM[kur].kisa}</span>`).join("")}${durum.sekme === "tum" ? hap(x.asama) : ""}</div>
        <a href="${esc(guvenliUrl(x.url))}" target="_blank" rel="noopener" title="${esc(x.baslik)}">${esc(kisaBaslik(x.baslik))}</a>
      </li>`).join("") : `<li class="akis-bos">${Object.keys(D.komisyonlar).length ? "Bu seçimle eşleşen duyuru yok." : "Duyurular henüz toplanmadı."}</li>`;
    $("#daha").hidden = liste.length <= durum.akisLimit;
  }

  /* ---------- detay ---------- */
  function detayAc(id, hashGuncelle = true) {
    const k = K.byId[id];
    if (!k) return;
    const d = D.komisyonlar[id] || {};
    const t = takip.has(id);
    let h = `<div class="d-bas">
      <div><p class="eyebrow">Adalet Komisyonu Başkanlığı</p><h2 id="d-baslik">${esc(k.ad)}</h2></div>
      <div class="d-dugmeler">
        <button type="button" class="yildiz" data-takip="${esc(id)}" aria-pressed="${t}" aria-label="${t ? "Takipten çıkar" : "Takip et"}">${YILDIZ}</button>
        <button type="button" class="kapat" id="kapat" aria-label="Kapat"><svg viewBox="0 0 20 20"><path d="M5 5l10 10M15 5L5 15"/></svg></button>
      </div>
      <div class="d-alt"><span><b class="num">${sayi(k.toplam)}</b> kadro</span>${d.site ? `<a href="${esc(guvenliUrl(d.site + "/Arsiv/duyuru"))}" target="_blank" rel="noopener">Komisyonun duyuru arşivi ↗</a>` : ""}${d.son_kontrol ? `<span>Son kontrol: ${zaman(d.son_kontrol)}</span>` : ""}</div>
    </div>`;
    if (!okundu(id)) h += `<div class="d-uyari">Bu komisyonun sitesi henüz okunamadı${d.hata ? ` (${esc(d.hata)})` : ""}. Kontenjan bilgileri ilan eklerinden alınmıştır; durumu komisyonun kendi sitesinden kontrol edin.</div>`;
    else if (d.erisim !== "ok") h += `<div class="d-uyari">Son denemede siteye ulaşılamadı; gösterilen durum ${zaman(d.son_basarili)} tarihli okumaya aittir.</div>`;

    for (const kur of KURUMLAR) {
      const v = k.kurumlar[kur];
      if (!v) continue;
      const kd = okundu(id) ? (d.durum[kur] || { asama: "yok", unvanlar: {} }) : null;
      const a = kd ? kd.asama : "bilinmiyor";
      h += `<section class="d-kurum"><div class="d-kurum-bas"><h3>${esc(KURUM[kur].ad)}</h3><span class="num">${sayi(v.toplam)} kadro${v.cagrilacak ? ` · ${sayi(v.cagrilacak)} aday çağrılacak` : ""}</span>${hap(a)}</div><div class="unvan-liste">`;
      for (const u of v.unvanlar) {
        const ua = kd ? kd.unvanlar[u.unvan] || "yok" : "bilinmiyor";
        const seviye = IZ.indexOf(ua);
        const iz = IZ.map((_, i) => `<span class="${i <= seviye ? "dolu" : ""}"></span>`).join("");
        const alt = [];
        if (u.genel != null || u.oncelikli != null) alt.push(`Genel ${sayi(u.genel)} · Öncelikli ${sayi(u.oncelikli)}`);
        if (u.cagrilacak) alt.push(`${sayi(u.cagrilacak)} aday çağrılacak`);
        h += `<details class="unvan"><summary>
            <span class="u-ad">${esc(u.unvan)}${alt.length ? `<small>${alt.join(" · ")}</small>` : ""}</span>
            <span class="u-sag">${hap(ua)}<span class="u-sayi">${sayi(u.toplam)}</span></span>
            <span class="iz ${ua === "sonuc" ? "sonuc" : ""}" aria-hidden="true">${iz}</span>
            <span class="iz-etiket" aria-hidden="true"><span>Aday</span><span>Uygulama</span><span>Sözlü</span><span>Sonuç</span></span>
          </summary>
          <ul class="yerler">${(u.yerler || []).map((y) => `<li><span>${esc(y.yer)}</span><span class="num">${sayi(y.sayi)}</span></li>`).join("")}</ul>
        </details>`;
      }
      h += `</div></section>`;
    }

    const dy = d.duyurular || [];
    h += `<section class="d-zaman"><h3>Duyurular</h3>`;
    h += dy.length ? `<ol class="zaman">${dy.map((x) => {
      const kurs = Object.keys(x.sinif?.kurumlar || {});
      const notlar = [];
      if (x.icerik_sonuc && x.asama === "sonuc") notlar.push("Duyuru metninde sonuç ifadesi bulundu");
      if (x.sinif?.belirsiz) notlar.push("Başlıkta kurum belirtilmemiş; ünvana göre eşleştirildi");
      return `<li class="${x.asama}"><div class="akis-meta"><span>${tarih(x.tarih, true)}</span>${kurs.map((kur) => `<span class="kur-etiket">${KURUM[kur].kisa}</span>`).join("")}${hap(x.asama)}</div>
        <a href="${esc(guvenliUrl(x.url))}" target="_blank" rel="noopener">${esc(x.baslik)}</a>${notlar.length ? `<span class="not">${notlar.join(" · ")}</span>` : ""}</li>`;
    }).join("")}</ol>` : `<p class="akis-bos">${okundu(id) ? "Bu alımlarla ilgili duyuru bulunamadı." : "Duyurular henüz toplanmadı."}</p>`;
    h += `</section>`;

    $("#d-ic").innerHTML = h;
    const dlg = $("#detay");
    if (!dlg.open) { try { dlg.showModal(); } catch (_) { dlg.setAttribute("open", ""); } }
    dlg.scrollTop = 0;
    $("#kapat").focus();
    if (hashGuncelle && location.hash !== "#k-" + id) location.hash = "k-" + id;
  }
  function detayKapat() {
    const dlg = $("#detay");
    if (dlg.open) dlg.close();
    if (location.hash.startsWith("#k-")) {
      try { history.replaceState(null, "", location.pathname + location.search); } catch (_) { location.hash = ""; }
    }
  }
  function hashOku() {
    const m = location.hash.match(/^#k-([a-z0-9]+)$/);
    if (m && K.byId[m[1]]) detayAc(m[1], false);
    else if ($("#detay").open) $("#detay").close();
  }

  /* ---------- kontroller ---------- */
  function unvanSecenek() {
    const sel = $("#f-unvan");
    if (!durum.kurum) { sel.innerHTML = '<option value="">Önce kurum seçin</option>'; sel.disabled = true; durum.unvan = ""; return; }
    const u = K.kurumlar[durum.kurum].unvanlar;
    const sirali = Object.entries(u).sort((a, b) => b[1] - a[1]);
    sel.innerHTML = `<option value="">Tüm ünvanlar</option>` + sirali.map(([ad, n]) => `<option value="${esc(ad)}">${esc(ad)} (${sayi(n)})</option>`).join("");
    sel.disabled = false;
    if (!u[durum.unvan]) durum.unvan = "";
    sel.value = durum.unvan;
  }
  function hepsiniCiz() {
    $("#f-kurum").value = durum.kurum;
    $("#f-sira").value = durum.sira;
    $("#f-takip").setAttribute("aria-pressed", durum.takip);
    document.querySelectorAll("#f-durum [data-durum]").forEach((b) => b.setAttribute("aria-pressed", b.dataset.durum === durum.filtre));
    $("#t-sonuc").setAttribute("aria-selected", durum.sekme === "sonuc");
    $("#t-tum").setAttribute("aria-selected", durum.sekme === "tum");
    yeniCiz(); ozetCiz(); tabloCiz(); akisCiz();
    sakla("alim-filtre", { kurum: durum.kurum, unvan: durum.unvan, filtre: durum.filtre, sira: durum.sira, sekme: durum.sekme });
  }
  function takipDegistir(id) {
    takip.has(id) ? takip.delete(id) : takip.add(id);
    sakla("alim-takip", [...takip]);
    hepsiniCiz();
    if ($("#detay").open) detayAc(id, false);
  }

  function baglan() {
    let zam;
    $("#ara").addEventListener("input", (e) => { clearTimeout(zam); zam = setTimeout(() => { durum.q = e.target.value; tabloCiz(); }, 120); });
    $("#f-kurum").addEventListener("change", (e) => { durum.kurum = e.target.value; durum.unvan = ""; unvanSecenek(); hepsiniCiz(); });
    $("#f-unvan").addEventListener("change", (e) => { durum.unvan = e.target.value; hepsiniCiz(); });
    $("#f-sira").addEventListener("change", (e) => { durum.sira = e.target.value; tabloCiz(); sakla("alim-filtre", { ...durum, q: undefined }); });
    $("#f-durum").addEventListener("click", (e) => {
      const b = e.target.closest("button");
      if (!b) return;
      if (b.id === "f-takip") durum.takip = !durum.takip;
      else durum.filtre = b.dataset.durum;
      hepsiniCiz();
    });
    $("#ozet").addEventListener("click", (e) => {
      const b = e.target.closest(".kart");
      if (!b) return;
      durum.kurum = durum.kurum === b.dataset.kur ? "" : b.dataset.kur;
      durum.unvan = "";
      unvanSecenek(); hepsiniCiz();
      $("#kayit-baslik").scrollIntoView({ behavior: "smooth", block: "start" });
    });
    $("#satirlar").addEventListener("click", (e) => {
      const y = e.target.closest("[data-takip]");
      if (y) { e.stopPropagation(); takipDegistir(y.dataset.takip); return; }
      const s = e.target.closest(".satir");
      if (s) detayAc(s.dataset.id);
    });
    $("#satirlar").addEventListener("keydown", (e) => {
      if ((e.key === "Enter" || e.key === " ") && e.target.classList.contains("satir")) { e.preventDefault(); detayAc(e.target.dataset.id); }
    });
    $("#akis").addEventListener("click", (e) => { const b = e.target.closest("[data-ac]"); if (b) detayAc(b.dataset.ac); });
    $("#yeni-liste").addEventListener("click", (e) => { const b = e.target.closest("[data-ac]"); if (b) detayAc(b.dataset.ac); });
    $("#yeni-daha").addEventListener("click", () => { yeniHepsi = true; yeniCiz(); });
    $("#t-sonuc").addEventListener("click", () => { durum.sekme = "sonuc"; durum.akisLimit = AKIS_ILK; hepsiniCiz(); });
    $("#t-tum").addEventListener("click", () => { durum.sekme = "tum"; durum.akisLimit = AKIS_ILK; hepsiniCiz(); });
    $("#daha").addEventListener("click", () => { durum.akisLimit += 12; akisCiz(); });
    const dlg = $("#detay");
    dlg.addEventListener("click", (e) => {
      if (e.target === dlg || e.target.closest("#kapat")) { detayKapat(); return; }
      const y = e.target.closest("[data-takip]");
      if (y) takipDegistir(y.dataset.takip);
    });
    dlg.addEventListener("cancel", (e) => { e.preventDefault(); detayKapat(); });
    window.addEventListener("hashchange", hashOku);
  }

  function kaynaklarCiz() {
    $("#kaynaklar").innerHTML = KURUMLAR.map((kur) => {
      const k = K.kurumlar[kur];
      return `<li><a href="${esc(guvenliUrl(k.ilan_url))}" target="_blank" rel="noopener">${esc(KURUM[kur].ad)} ilanı ↗</a>
        <small>${tarih(k.ilan_tarihi, true)} · ${sayi(k.toplam)} kadro · <a href="${esc(guvenliUrl(k.pdf_url))}" target="_blank" rel="noopener">Ek-1 kontenjan listesi (PDF)</a></small></li>`;
    }).join("");
  }
  function guncellemeCiz() {
    const el = $("#guncelleme");
    if (!D.guncelleme) { el.innerHTML = `<span class="canli eski"></span>Komisyon siteleri henüz taranmadı`; return; }
    const ok = Object.values(D.komisyonlar).filter((d) => d.erisim === "ok").length;
    const saat = (Date.now() - new Date(D.guncelleme).getTime()) / 36e5;
    el.innerHTML = `<span class="canli ${saat > 3 ? "eski" : ""}"></span><span>Son tarama ${esc(zaman(D.guncelleme))} · ${ok}/${K.komisyonlar.length} komisyon sitesi okundu</span>`;
  }

  async function yukle() {
    const al = async (u) => { const r = await fetch(u, { cache: "no-cache" }); if (!r.ok) throw new Error(u + " " + r.status); return r.json(); };
    try {
      K = await al("data/kontenjan.json");
    } catch (e) {
      $("#guncelleme").textContent = "Veriler yüklenemedi. Sayfayı yenileyin.";
      return;
    }
    try { D = await al("data/durum.json"); } catch (_) { D = { komisyonlar: {} }; }
    try {
      const t = await al("data/tarama.json");
      D.guncelleme = t.guncelleme;
      for (const [id, x] of Object.entries(t.komisyonlar || {})) Object.assign((D.komisyonlar[id] ||= {}), x);
    } catch (_) {}
    K.byId = Object.fromEntries(K.komisyonlar.map((k) => [k.id, k]));
    takip = new Set(oku("alim-takip", []));
    sonZiyaret = oku("alim-son-ziyaret", "");
    // Aynı oturumda yenilemelerde "yeni" işaretleri kaybolmasın: 30 dakikadan eski ziyareti güncelle
    const simdi = new Date().toISOString();
    if (!sonZiyaret || Date.now() - new Date(sonZiyaret).getTime() > 30 * 6e4) sakla("alim-son-ziyaret", simdi);
    const f = oku("alim-filtre", {});
    if (f && typeof f === "object") {
      if (KURUM[f.kurum]) durum.kurum = f.kurum;
      if (typeof f.unvan === "string") durum.unvan = f.unvan;
      if (["", "sonuc", "kismen", "bekliyor", "bilinmiyor"].includes(f.filtre)) durum.filtre = f.filtre;
      if (["ad", "kadro", "son"].includes(f.sira)) durum.sira = f.sira;
      if (["sonuc", "tum"].includes(f.sekme)) durum.sekme = f.sekme;
    }
    unvanSecenek();
    kaynaklarCiz();
    guncellemeCiz();
    baglan();
    hepsiniCiz();
    hashOku();
  }
  yukle();
})();
