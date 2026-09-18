"""
HGS Mutabakat Otomasyonu - Streamlit Arayüzü (v3)
Çalıştırmak için: streamlit run app_v3.py

v3 yenilikleri:
- Toplam parasal etki (tutar farklarının TL toplamı)
- Zaman bazlı trend grafiği (günlük uyuşmazlık sayısı)
- Operatör ve geçiş noktası bazında kırılım
- Excel (xlsx) olarak dışa aktarma (özet + detay sekmeli)
"""

import streamlit as st
import pandas as pd
import html as html_lib
from io import BytesIO

st.set_page_config(page_title="Mutabakat Otomasyonu", layout="wide", page_icon="🔄")

TUTAR_TOLERANS = 0.01
TARIH_TOLERANS_SAAT = 2

HATA_RENKLERI = {
    "TUTAR_FARKI": "#1A1A1A",
    "GECIKMELI_BILDIRIM": "#1A1A1A",
    "EKSIK_KAYIT": "#1A1A1A",
    "MUKERRER_KAYIT": "#1A1A1A",
    "HGS_TARAFINDA_YOK": "#1A1A1A",
}

HATA_YAZI_RENKLERI = {
    "TUTAR_FARKI": "#FFFFFF",
    "GECIKMELI_BILDIRIM": "#FFFFFF",
    "EKSIK_KAYIT": "#FFFFFF",
    "MUKERRER_KAYIT": "#FFFFFF",
    "HGS_TARAFINDA_YOK": "#FFFFFF",
}

HATA_ETIKETLERI = {
    "TUTAR_FARKI": "Tutar farkı",
    "GECIKMELI_BILDIRIM": "Gecikmeli bildirim",
    "EKSIK_KAYIT": "Eksik kayıt",
    "MUKERRER_KAYIT": "Mükerrer kayıt",
    "HGS_TARAFINDA_YOK": "Karşı tarafta yok",
}

st.markdown(
    """
    <style>
    .rozet {
        display: inline-block;
        padding: 3px 10px;
        border-radius: 4px;
        font-size: 12.5px;
        font-weight: 600;
        background-color: #1A1A1A;
        color: #FFFFFF;
    }
    .kart {
        border: 1px solid #E0E0E0;
        border-left: 4px solid #F5B301;
        border-radius: 4px;
        padding: 16px 20px;
        margin-bottom: 8px;
        background-color: #FAFAFA;
    }
    .baslik-seridi {
        height: 4px;
        background-color: #F5B301;
        margin-bottom: 18px;
    }
    div[data-testid="stAlert"] {
        background-color: #FFF6DE !important;
        border-left: 4px solid #F5B301 !important;
    }
    div[data-testid="stAlert"] p,
    div[data-testid="stAlert"] span,
    div[data-testid="stAlert"] div {
        color: #1A1A1A !important;
    }
    div[data-testid="stAlert"] svg {
        fill: #F5B301 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def mutabakat_yap(hgs: pd.DataFrame, banka: pd.DataFrame,
                   tutar_toleransi: float = TUTAR_TOLERANS,
                   tarih_toleransi_saat: float = TARIH_TOLERANS_SAAT,
                   kaynak_adi: str = "HGS") -> pd.DataFrame:
    baglam = "pos" if kaynak_adi.upper() == "POS" else "hgs"
    sonuclar = []

    mukerrer_idler = banka["islem_id"].value_counts()
    mukerrer_idler = set(mukerrer_idler[mukerrer_idler > 1].index)

    banka_gruplu = banka.groupby("islem_id")
    hgs_gruplu = hgs.groupby("islem_id")
    tum_idler = set(hgs["islem_id"]) | set(banka["islem_id"])

    for islem_id in sorted(tum_idler):
        hgs_satir = hgs[hgs["islem_id"] == islem_id]
        banka_var_mi = islem_id in banka_gruplu.groups

        # Kırılım (operatör / geçiş noktası) için referans satır - varsa HGS, yoksa banka
        ref = hgs_satir.iloc[0] if len(hgs_satir) > 0 else banka_gruplu.get_group(islem_id).iloc[0]
        operator = ref.get("operator", "Bilinmiyor")
        gecis_noktasi = ref.get("gecis_noktasi", "Bilinmiyor")
        plaka = ref.get("plaka", "Bilinmiyor")

        temel = {"islem_id": islem_id, "operator": operator, "gecis_noktasi": gecis_noktasi, "plaka": plaka,
                 "hgs_tutar": None, "banka_tutar": None, "hgs_tarih": None, "banka_tarih": None,
                 "tutar_farki_tl": 0.0}

        if len(hgs_satir) == 0 and banka_var_mi:
            sebep = olasi_sebep("HGS_TARAFINDA_YOK", 0, 0, "", baglam)
            sonuclar.append({**temel, "durum": "UYUSMUYOR", "hata_tipi": "HGS_TARAFINDA_YOK",
                              "detay": f"Kayıt bankada var, {kaynak_adi}'de yok. {sebep}"})
            continue

        if len(hgs_satir) > 0 and not banka_var_mi:
            sebep = olasi_sebep("EKSIK_KAYIT", 0, 0, "", baglam)
            sonuclar.append({**temel, "durum": "UYUSMUYOR", "hata_tipi": "EKSIK_KAYIT",
                              "detay": f"{kaynak_adi}'de var, bankaya hiç düşmemiş. {sebep}"})
            continue

        if islem_id in mukerrer_idler:
            sebep = olasi_sebep("MUKERRER_KAYIT", 0, 0, "", baglam)
            sonuclar.append({**temel, "durum": "UYUSMUYOR", "hata_tipi": "MUKERRER_KAYIT",
                              "detay": f"Bankada {len(banka_gruplu.get_group(islem_id))} kez tekrar etmiş. {sebep}"})
            continue

        h = hgs_satir.iloc[0]
        b = banka_gruplu.get_group(islem_id).iloc[0]

        tutar_farki = round(abs(h["tutar"] - b["tutar"]), 2)
        tarih_farki_saat = abs((pd.to_datetime(h["gecis_tarihi"]) - pd.to_datetime(b["gecis_tarihi"])).total_seconds()) / 3600

        ortak = {**temel, "hgs_tutar": h["tutar"], "banka_tutar": b["tutar"],
                 "hgs_tarih": h["gecis_tarihi"], "banka_tarih": b["gecis_tarihi"]}

        if tutar_farki > tutar_toleransi:
            sebep = olasi_sebep("TUTAR_FARKI", tutar_farki, h["tutar"], h["gecis_tarihi"], baglam)
            sonuclar.append({**ortak, "durum": "UYUSMUYOR", "hata_tipi": "TUTAR_FARKI",
                              "detay": f"{kaynak_adi}: {h['tutar']} TL, Banka: {b['tutar']} TL "
                                       f"(fark: {tutar_farki} TL). {sebep}",
                              "tutar_farki_tl": tutar_farki})
        elif tarih_farki_saat > tarih_toleransi_saat:
            sebep = olasi_sebep("GECIKMELI_BILDIRIM", 0, 0, h["gecis_tarihi"], baglam)
            sonuclar.append({**ortak, "durum": "UYUSMUYOR", "hata_tipi": "GECIKMELI_BILDIRIM",
                              "detay": f"Fark: {tarih_farki_saat:.1f} saat. {sebep}"})
        else:
            sonuclar.append({**ortak, "durum": "UYUSTU", "hata_tipi": "-", "detay": "-"})

    return pd.DataFrame(sonuclar)


def esnek_mutabakat_yap(hgs: pd.DataFrame, banka: pd.DataFrame,
                         tutar_toleransi: float = TUTAR_TOLERANS,
                         tarih_toleransi_saat: float = TARIH_TOLERANS_SAAT,
                         kaynak_adi: str = "HGS") -> pd.DataFrame:
    """
    İşlem ID'nin iki sistemde de ortak/güvenilir olmadığı gerçek dünya senaryoları için:
    plaka + geçiş tarihi + tutar üzerinden en yakın eşleşmeyi bulan yaklaşık mutabakat motoru.
    Her HGS kaydı için aynı plakaya sahip, henüz kullanılmamış en yakın tarihli banka kaydı aranır.
    """
    hgs = hgs.copy()
    banka = banka.copy()
    hgs["gecis_tarihi"] = pd.to_datetime(hgs["gecis_tarihi"])
    banka["gecis_tarihi"] = pd.to_datetime(banka["gecis_tarihi"])

    baglam = "pos" if kaynak_adi.upper() == "POS" else "hgs"
    banka_kullanildi = [False] * len(banka)
    banka_by_plaka = {}
    for idx, row in banka.iterrows():
        banka_by_plaka.setdefault(row["plaka"], []).append(idx)

    sonuclar = []

    for i, h in hgs.iterrows():
        adaylar = [idx for idx in banka_by_plaka.get(h["plaka"], []) if not banka_kullanildi[idx]]

        operator = h.get("operator", "Bilinmiyor")
        gecis_noktasi = h.get("gecis_noktasi", "Bilinmiyor")
        temel = {"islem_id": h.get("islem_id", f"HGS-{i}"), "operator": operator, "gecis_noktasi": gecis_noktasi,
                 "plaka": h["plaka"], "hgs_tutar": h["tutar"], "banka_tutar": None,
                 "hgs_tarih": h["gecis_tarihi"].strftime("%Y-%m-%d %H:%M"), "banka_tarih": None, "tutar_farki_tl": 0.0}

        if not adaylar:
            sebep = olasi_sebep("EKSIK_KAYIT", 0, 0, "", baglam)
            sonuclar.append({**temel, "durum": "UYUSMUYOR", "hata_tipi": "EKSIK_KAYIT",
                              "detay": f"'{h['plaka']}' değerine ait kayıt karşı tarafta bulunamadı. {sebep}"})
            continue

        # Aynı plakadaki adaylar arasından tarihçe en yakın olanı seç
        en_yakin_idx = min(adaylar, key=lambda idx: abs((banka.loc[idx, "gecis_tarihi"] - h["gecis_tarihi"]).total_seconds()))
        b = banka.loc[en_yakin_idx]
        banka_kullanildi[en_yakin_idx] = True

        tutar_farki = round(abs(h["tutar"] - b["tutar"]), 2)
        tarih_farki_saat = abs((h["gecis_tarihi"] - b["gecis_tarihi"]).total_seconds()) / 3600

        ortak = {**temel, "banka_tutar": b["tutar"], "banka_tarih": b["gecis_tarihi"].strftime("%Y-%m-%d %H:%M")}

        if tutar_farki > tutar_toleransi:
            sebep = olasi_sebep("TUTAR_FARKI", tutar_farki, h["tutar"], str(h["gecis_tarihi"]), baglam)
            sonuclar.append({**ortak, "durum": "UYUSMUYOR", "hata_tipi": "TUTAR_FARKI",
                              "detay": f"{kaynak_adi}: {h['tutar']} TL, Banka: {b['tutar']} TL "
                                       f"(fark: {tutar_farki} TL) — plaka+tarih ile eşleştirildi. {sebep}",
                              "tutar_farki_tl": tutar_farki})
        elif tarih_farki_saat > tarih_toleransi_saat:
            sebep = olasi_sebep("GECIKMELI_BILDIRIM", 0, 0, str(h["gecis_tarihi"]), baglam)
            sonuclar.append({**ortak, "durum": "UYUSMUYOR", "hata_tipi": "GECIKMELI_BILDIRIM",
                              "detay": f"Fark: {tarih_farki_saat:.1f} saat — plaka+tarih ile eşleştirildi. {sebep}"})
        else:
            sonuclar.append({**ortak, "durum": "UYUSTU", "hata_tipi": "-", "detay": "Plaka+tarih ile eşleştirildi"})

    # Bankada kalıp hiç kullanılmayan kayıtlar: HGS'de karşılığı bulunamamış demektir
    for idx, kullanildi in enumerate(banka_kullanildi):
        if not kullanildi:
            b = banka.loc[idx]
            sebep = olasi_sebep("HGS_TARAFINDA_YOK", 0, 0, "", baglam)
            sonuclar.append({
                "islem_id": b.get("islem_id", f"BANKA-{idx}"), "operator": b.get("operator", "Bilinmiyor"),
                "gecis_noktasi": b.get("gecis_noktasi", "Bilinmiyor"), "plaka": b["plaka"],
                "hgs_tutar": None, "banka_tutar": b["tutar"], "hgs_tarih": None,
                "banka_tarih": b["gecis_tarihi"].strftime("%Y-%m-%d %H:%M"),
                "tutar_farki_tl": 0.0, "durum": "UYUSMUYOR", "hata_tipi": "HGS_TARAFINDA_YOK",
                "detay": f"'{b['plaka']}' değerine ait bu kayda diğer tarafta karşılık bulunamadı. {sebep}",
            })

    return pd.DataFrame(sonuclar)


def olasi_sebep(hata_tipi: str, tutar_farki: float, tutar: float, tarih_str: str, baglam: str = "hgs") -> str:
    """
    Hata tipine, tutar oranına ve tarihe (haftanın günü) bakarak gerçekçi bir
    'muhtemel sebep' çıkarımı üretir. Rastgele metin değil, hesaplanan değerlere
    dayalı kural tabanlı bir çıkarımdır - dummy veride bile mantığı gerçektir.
    """
    try:
        oran = (tutar_farki / tutar * 100) if tutar else 0
    except (TypeError, ZeroDivisionError):
        oran = 0

    if hata_tipi == "TUTAR_FARKI":
        if baglam == "pos":
            if 0 < oran <= 5:
                return f"Muhtemel sebep: POS komisyonu/interchange kesintisi (~%{oran:.1f})"
            return "Muhtemel sebep: kur farkı veya kısmi iade olabilir"
        else:
            if 0 < oran <= 3:
                return "Muhtemel sebep: yuvarlama farkı veya güncellenmiş geçiş ücreti"
            return "Muhtemel sebep: farklı araç sınıfı/tarife uygulanmış olabilir"

    if hata_tipi == "GECIKMELI_BILDIRIM":
        gun_adi = None
        try:
            gun_no = pd.to_datetime(tarih_str).weekday()  # Pazartesi=0 ... Pazar=6
            gun_adi = ["Pazartesi", "Salı", "Çarşamba", "Perşembe", "Cuma", "Cumartesi", "Pazar"][gun_no]
            haftasonu_oncesi = gun_no in (4, 5)  # Cuma veya Cumartesi
        except (ValueError, TypeError):
            haftasonu_oncesi = False
        if baglam == "pos":
            if haftasonu_oncesi:
                return f"Muhtemel sebep: {gun_adi} günü işlem — hafta sonu nedeniyle T+2 settlement gecikmesi"
            return "Muhtemel sebep: standart T+1 settlement gecikmesi"
        else:
            return "Muhtemel sebep: HGS operatöründen bankaya toplu bildirim gecikmesi"

    if hata_tipi == "EKSIK_KAYIT":
        if baglam == "pos":
            return "Olası sebep: authorization alınmış, capture/settlement tamamlanmamış olabilir"
        return "Olası sebep: geçiş kaydı oluşmuş, banka bildirimi henüz yapılmamış olabilir"

    if hata_tipi == "MUKERRER_KAYIT":
        return "Olası sebep: iletişim zaman aşımı sonrası otomatik tekrar gönderim (retry)"

    if hata_tipi == "HGS_TARAFINDA_YOK":
        if baglam == "pos":
            return "Olası sebep: bankada manuel düzeltme kaydı veya POS'a hiç yansımamış bir hareket"
        return "Olası sebep: banka tarafında manuel düzeltme kaydı veya HGS'e hiç yansımamış bir geçiş"

    return ""


def rozet_html(hata_tipi: str) -> str:
    renk = HATA_RENKLERI.get(hata_tipi, "#7A7A7A")
    yazi_renk = HATA_YAZI_RENKLERI.get(hata_tipi, "#FFFFFF")
    etiket = HATA_ETIKETLERI.get(hata_tipi, hata_tipi)
    return f'<span class="rozet" style="background-color:{renk}; color:{yazi_renk}">{etiket}</span>'


def anomali_tespit_et(sonuc_df: pd.DataFrame, z_esik: float = 2.5, gunluk_esik: int = 5):
    """
    Uyuşan kayıtlar dahil TÜM işlemler içinde istatistiksel olarak sıra dışı olanları bulur.
    Mutabakat hatası olmasa bile şüpheli örüntüleri (fraud/hata ihtimali) yakalamak içindir.

    1) Tutar anomalisi: işlem tutarı, genel ortalamadan z_esik standart sapmadan fazla uzaksa işaretlenir.
    2) Sık geçiş anomalisi: bir plaka aynı gün içinde gunluk_esik'ten fazla geçiş yapmışsa işaretlenir.
    """
    df = sonuc_df.copy()
    df["tutar"] = df["hgs_tutar"].fillna(df["banka_tutar"])
    df["tarih"] = pd.to_datetime(df["hgs_tarih"].fillna(df["banka_tarih"]), errors="coerce")

    # --- Tutar anomalisi (z-score) ---
    tutar_anomali_df = pd.DataFrame()
    gecerli = df.dropna(subset=["tutar"])
    if len(gecerli) > 1 and gecerli["tutar"].std() > 0:
        ortalama = gecerli["tutar"].mean()
        std = gecerli["tutar"].std()
        df["z_skor"] = (df["tutar"] - ortalama) / std
        tutar_anomali_df = df[df["z_skor"].abs() > z_esik][
            ["islem_id", "plaka", "operator", "gecis_noktasi", "tutar", "z_skor", "durum"]
        ].copy()
        tutar_anomali_df["z_skor"] = tutar_anomali_df["z_skor"].round(2)
        tutar_anomali_df = tutar_anomali_df.sort_values("z_skor", key=abs, ascending=False)

    # --- Sık geçiş anomalisi (plaka + gün bazında sayım) ---
    df_gun = df.dropna(subset=["tarih", "plaka"]).copy()
    df_gun["gun"] = df_gun["tarih"].dt.date
    sayim = df_gun.groupby(["plaka", "gun"]).size().reset_index(name="gecis_sayisi")
    siklik_anomali_df = sayim[sayim["gecis_sayisi"] > gunluk_esik].sort_values("gecis_sayisi", ascending=False)

    return tutar_anomali_df, siklik_anomali_df


def excel_raporu_uret(sonuc_df: pd.DataFrame) -> bytes:
    """Özet + detay sekmeli Excel raporu üretir, bytes döner."""
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        # Özet sekmesi
        toplam = len(sonuc_df)
        uyusan = int((sonuc_df["durum"] == "UYUSTU").sum())
        uyusmayan = toplam - uyusan
        toplam_parasal_etki = sonuc_df["tutar_farki_tl"].sum()

        ozet_satirlari = [
            {"Metrik": "Toplam işlem", "Değer": toplam},
            {"Metrik": "Uyuşan kayıt", "Değer": uyusan},
            {"Metrik": "Uyuşmayan kayıt", "Değer": uyusmayan},
            {"Metrik": "Toplam parasal etki (TL)", "Değer": round(toplam_parasal_etki, 2)},
        ]
        hata_dagilimi = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"]["hata_tipi"].value_counts()
        for hata_tipi, adet in hata_dagilimi.items():
            ozet_satirlari.append({"Metrik": HATA_ETIKETLERI.get(hata_tipi, hata_tipi), "Değer": adet})

        pd.DataFrame(ozet_satirlari).to_excel(writer, sheet_name="Özet", index=False)

        # Detay sekmesi (sadece uyuşmayanlar)
        detay_df = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"].copy()
        detay_df["hata_tipi"] = detay_df["hata_tipi"].map(lambda x: HATA_ETIKETLERI.get(x, x))
        detay_df.to_excel(writer, sheet_name="Uyuşmayan kayıtlar", index=False)

        # Tüm kayıtlar sekmesi
        sonuc_df.to_excel(writer, sheet_name="Tüm kayıtlar", index=False)

    return buffer.getvalue()


def ornek_veri_uret(mod: str = "hgs"):
    """Kullanıcı kendi dosyası olmadan uygulamayı denemek isterse küçük bir örnek veri seti üretir.
    Çıktı her zaman kanonik kolon isimleriyle (islem_id, plaka, gecis_tarihi, tutar, gecis_noktasi, operator)
    döner - 'plaka' HGS modunda plaka, POS modunda maskeli kart no anlamına gelir."""
    import random
    from datetime import datetime, timedelta

    random.seed(7)
    baslangic = datetime(2026, 9, 1)

    if mod == "pos":
        noktalar = ["Migros Kadıköy", "CarrefourSA Ataşehir", "Boyner Nişantaşı", "Opet Maslak"]
        operatorler = ["POS-Param", "POS-PayTR", "POS-VakıfPOS"]
        anahtar_uret = lambda i: f"{4000+i:04d} **** **** {1000+i:04d}"
        tutar_secenekleri = [24.90, 49.50, 89.00, 149.90]
    else:
        noktalar = ["Kavacık G.", "Zincirlikuyu G.", "Fatih SM G.", "TEM Otoyol G."]
        operatorler = ["HGS-A", "HGS-B", "HGS-C"]
        anahtar_uret = lambda i: f"34 AB {1000+i}"
        tutar_secenekleri = [13.25, 17.50, 22.00, 35.75]

    hgs_kayitlar, banka_kayitlar = [], []
    for i in range(1, 121):
        islem_id = f"TX{i:05d}"
        tarih = baslangic + timedelta(days=random.randint(0, 9), hours=random.randint(0, 23))
        tutar = round(random.choice(tutar_secenekleri), 2)
        kayit = {
            "islem_id": islem_id, "plaka": anahtar_uret(i),
            "gecis_tarihi": tarih.strftime("%Y-%m-%d %H:%M"), "tutar": tutar,
            "gecis_noktasi": random.choice(noktalar), "operator": random.choice(operatorler),
        }
        banka_kayit = dict(kayit)
        senaryo = random.random()
        if senaryo < 0.15:
            banka_kayit["tutar"] = round(tutar + random.choice([-3.0, 2.0]), 2)
        elif senaryo < 0.22:
            gecikme = timedelta(hours=random.randint(3, 30))
            banka_kayit["gecis_tarihi"] = (tarih + gecikme).strftime("%Y-%m-%d %H:%M")
        elif senaryo < 0.26:
            banka_kayit = None

        hgs_kayitlar.append(kayit)
        if banka_kayit is not None:
            banka_kayitlar.append(banka_kayit)

    return pd.DataFrame(hgs_kayitlar), pd.DataFrame(banka_kayitlar)


MOD_BILGI = {
    "hgs": {
        "icon": "🚗",
        "baslik": "HGS Mutabakat Otomasyonu",
        "aciklama": "HGS ve banka tahsilat kayıtlarını yükle, otomatik eşleştirme ve hata sınıflandırması yap.",
        "kaynak1_etiket": "HGS kayıtları (CSV)",
        "kaynak2_etiket": "Banka kayıtları (CSV)",
        "beklenen_kolonlar_metni": "islem_id, plaka, gecis_tarihi, tutar, gecis_noktasi, operator",
        "kolon_eslestirme": {"islem_id": "islem_id", "plaka": "plaka", "gecis_tarihi": "gecis_tarihi",
                              "tutar": "tutar", "gecis_noktasi": "gecis_noktasi", "operator": "operator"},
        "anahtar_terim": "Plaka", "nokta_terim": "Geçiş noktası", "operator_terim": "Operatör",
        "esnek_yontem_adi": "Plaka + Tarih + Tutar (yaklaşık)",
        "kaynak_kisa_adi": "HGS",
        "eksik_kayit_aciklama": "plakasına ait kayıt bankada bulunamadı",
        "hgs_tarafinda_yok_aciklama": "plakasına ait bu kayda HGS tarafında karşılık bulunamadı",
    },
    "pos": {
        "icon": "💳",
        "baslik": "POS Kart İşlemleri Mutabakat Otomasyonu",
        "aciklama": "POS kayıtlarını ve banka hesap hareketlerini yükle, otomatik eşleştirme ve hata sınıflandırması yap.",
        "kaynak1_etiket": "POS kayıtları (CSV)",
        "kaynak2_etiket": "Banka hesap hareketleri (CSV)",
        "beklenen_kolonlar_metni": "islem_id, kart_no, islem_tarihi, tutar, isyeri, pos_saglayici",
        "kolon_eslestirme": {"islem_id": "islem_id", "kart_no": "plaka", "islem_tarihi": "gecis_tarihi",
                              "tutar": "tutar", "isyeri": "gecis_noktasi", "pos_saglayici": "operator"},
        "anahtar_terim": "Kart No", "nokta_terim": "İşyeri", "operator_terim": "POS Sağlayıcı",
        "esnek_yontem_adi": "Kart No + Tarih + Tutar (yaklaşık)",
        "kaynak_kisa_adi": "POS",
        "eksik_kayit_aciklama": "kartına ait kayıt banka hesap hareketlerinde bulunamadı",
        "hgs_tarafinda_yok_aciklama": "kartına ait bu kayda POS tarafında karşılık bulunamadı",
    },
}



mod = st.radio(
    "Mutabakat türü",
    ["hgs", "pos"],
    format_func=lambda x: "🚗 HGS Geçişleri" if x == "hgs" else "💳 POS Kart İşlemleri",
    horizontal=True,
    label_visibility="collapsed",
)
M = MOD_BILGI[mod]

st.title(M["baslik"])
st.markdown('<div class="baslik-seridi"></div>', unsafe_allow_html=True)
st.caption(M["aciklama"])

if "ornek_veri_aktif" not in st.session_state:
    st.session_state.ornek_veri_aktif = False

with st.sidebar:
    st.header("Veri yükle")
    hgs_dosya = st.file_uploader(M["kaynak1_etiket"], type="csv", key=f"hgs_{mod}")
    banka_dosya = st.file_uploader(M["kaynak2_etiket"], type="csv", key=f"banka_{mod}")
    st.caption(f"Beklenen kolonlar: {M['beklenen_kolonlar_metni']}")

    if st.button("🎲 Örnek veriyle dene"):
        st.session_state.ornek_veri_aktif = True
    if hgs_dosya or banka_dosya:
        st.session_state.ornek_veri_aktif = False

    st.divider()
    st.header("Eşleştirme yöntemi")
    eslestirme_yontemi = st.radio(
        "Kayıtlar hangi bilgiyle eşleştirilsin?",
        ["İşlem ID (birebir)", M["esnek_yontem_adi"]],
        help=f"İki sistemde ortak/güvenilir bir işlem ID yoksa 'yaklaşık' modu kullan — "
             f"{M['anahtar_terim'].lower()} ve en yakın zamana göre eşleştirme yapar.",
    )

    st.divider()
    st.header("Eşik ayarları")
    tutar_toleransi = st.slider("Tutar farkı toleransı (TL)", 0.0, 10.0, 0.01, 0.5,
                                 help="Bu tutarın üzerindeki farklar 'uyuşmuyor' sayılır")
    tarih_toleransi = st.slider("Gecikme toleransı (saat)", 0, 24, 2, 1,
                                 help="Bu süreden uzun gecikmeler 'uyuşmuyor' sayılır")

if st.session_state.ornek_veri_aktif and not (hgs_dosya and banka_dosya):
    hgs_df, banka_df = ornek_veri_uret(mod)
    st.info("Örnek veriyle çalışıyorsun. Kendi dosyalarını yüklemek için sol menüyü kullan.")
    veri_hazir = True
elif hgs_dosya and banka_dosya:
    hgs_df = pd.read_csv(hgs_dosya).rename(columns=M["kolon_eslestirme"])
    banka_df = pd.read_csv(banka_dosya).rename(columns=M["kolon_eslestirme"])
    veri_hazir = True
else:
    veri_hazir = False

if veri_hazir:
    if eslestirme_yontemi.startswith("İşlem ID"):
        gerekli_kolonlar = {"islem_id", "gecis_tarihi", "tutar"}
    else:
        gerekli_kolonlar = {"plaka", "gecis_tarihi", "tutar"}

    eksik_hgs = gerekli_kolonlar - set(hgs_df.columns)
    eksik_banka = gerekli_kolonlar - set(banka_df.columns)

    if eksik_hgs or eksik_banka:
        st.error(
            f"Beklenen kolonlar eksik. \"{M['kaynak1_etiket']}\" dosyasında eksik: {eksik_hgs or 'yok'} | "
            f"\"{M['kaynak2_etiket']}\" dosyasında eksik: {eksik_banka or 'yok'}"
        )
    else:
        with st.spinner("Mutabakat yapılıyor..."):
            if eslestirme_yontemi.startswith("İşlem ID"):
                sonuc_df = mutabakat_yap(hgs_df, banka_df, tutar_toleransi, tarih_toleransi, M["kaynak_kisa_adi"])
            else:
                sonuc_df = esnek_mutabakat_yap(hgs_df, banka_df, tutar_toleransi, tarih_toleransi, M["kaynak_kisa_adi"])

        toplam = len(sonuc_df)
        uyusan = int((sonuc_df["durum"] == "UYUSTU").sum())
        uyusmayan = toplam - uyusan
        toplam_parasal_etki = sonuc_df["tutar_farki_tl"].sum()

        # --- Üst metrikler ---
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Toplam işlem", toplam)
        m2.metric("Uyuşan kayıt", uyusan, f"%{uyusan/toplam*100:.1f}")
        m3.metric("Uyuşmayan kayıt", uyusmayan, f"%{uyusmayan/toplam*100:.1f}", delta_color="inverse")
        m4.metric("Toplam parasal etki", f"{toplam_parasal_etki:,.2f} TL")

        st.divider()

        sekme1, sekme2, sekme3, sekme4 = st.tabs(
            ["📊 Genel bakış", "📈 Zaman trendi", "🏷️ Operatör / nokta kırılımı", "🚨 Anomali tespiti"]
        )

        with sekme1:
            st.subheader("Hata tipi dağılımı")
            hata_dagilimi = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"]["hata_tipi"].value_counts()
            if len(hata_dagilimi) > 0:
                hata_dagilimi_okunabilir = hata_dagilimi.rename(index=HATA_ETIKETLERI)
                st.bar_chart(hata_dagilimi_okunabilir, color="#1A1A1A")
            else:
                st.info("Hiç uyuşmazlık bulunamadı.")

            st.subheader("Uyuşmayan kayıtlar")
            uyusmayan_df = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"].reset_index(drop=True)

            fc1, fc2 = st.columns([2, 1])
            with fc1:
                secili_hata_tipleri = st.multiselect(
                    "Hata tipine göre filtrele",
                    options=sorted(uyusmayan_df["hata_tipi"].unique()),
                    default=sorted(uyusmayan_df["hata_tipi"].unique()),
                    format_func=lambda x: HATA_ETIKETLERI.get(x, x),
                )
            with fc2:
                arama = st.text_input("İşlem ID / plaka ara", placeholder="örn. TX00012")

            filtreli_df = uyusmayan_df[uyusmayan_df["hata_tipi"].isin(secili_hata_tipleri)]
            if arama:
                filtreli_df = filtreli_df[filtreli_df["islem_id"].str.contains(arama, case=False, na=False)]

            st.caption(f"{len(filtreli_df)} / {len(uyusmayan_df)} uyuşmayan kayıt gösteriliyor")

            if len(filtreli_df) > 0:
                goruntu_df = filtreli_df.copy()
                goruntu_df["hata tipi"] = goruntu_df["hata_tipi"].map(lambda x: HATA_ETIKETLERI.get(x, x))

                # st.dataframe uzun metinleri kırptığı ve kullanıcının manuel genişletmesini
                # gerektirdiği için, burada satırı asla kesmeyen kendi HTML tablomuzu kullanıyoruz.
                satirlar_html = ""
                for _, r in goruntu_df.iterrows():
                    islem_id_g = html_lib.escape(str(r['islem_id']))
                    hata_tipi_g = html_lib.escape(str(r['hata tipi']))
                    operator_g = html_lib.escape(str(r['operator']))
                    nokta_g = html_lib.escape(str(r['gecis_noktasi']))
                    detay_g = html_lib.escape(str(r['detay']))
                    satirlar_html += f"""
                    <tr>
                        <td style="padding:8px 10px; border-bottom:1px solid #E5E5E5; white-space:nowrap;">{islem_id_g}</td>
                        <td style="padding:8px 10px; border-bottom:1px solid #E5E5E5; white-space:nowrap;">{hata_tipi_g}</td>
                        <td style="padding:8px 10px; border-bottom:1px solid #E5E5E5; white-space:nowrap;">{operator_g}</td>
                        <td style="padding:8px 10px; border-bottom:1px solid #E5E5E5; white-space:nowrap;">{nokta_g}</td>
                        <td style="padding:8px 10px; border-bottom:1px solid #E5E5E5; white-space:normal; word-wrap:break-word;">{detay_g}</td>
                    </tr>
                    """

                tablo_html = f"""
                <div style="max-height:480px; overflow-y:auto; border:1px solid #E5E5E5; border-radius:6px;">
                <table style="width:100%; border-collapse:collapse; font-size:14px;">
                    <thead style="position:sticky; top:0; background-color:#FAFAFA;">
                        <tr>
                            <th style="text-align:left; padding:8px 10px; border-bottom:2px solid #1A1A1A; white-space:nowrap;">İşlem ID</th>
                            <th style="text-align:left; padding:8px 10px; border-bottom:2px solid #1A1A1A; white-space:nowrap;">Hata tipi</th>
                            <th style="text-align:left; padding:8px 10px; border-bottom:2px solid #1A1A1A; white-space:nowrap;">{M["operator_terim"]}</th>
                            <th style="text-align:left; padding:8px 10px; border-bottom:2px solid #1A1A1A; white-space:nowrap;">{M["nokta_terim"]}</th>
                            <th style="text-align:left; padding:8px 10px; border-bottom:2px solid #1A1A1A; width:40%;">Detay</th>
                        </tr>
                    </thead>
                    <tbody>
                        {satirlar_html}
                    </tbody>
                </table>
                </div>
                """
                # Markdown, satır başındaki 4+ boşluğu kod bloğu sanıp HTML'i düz metin olarak
                # gösterebiliyor - bunu önlemek için her satırın baş boşluğunu temizliyoruz.
                tablo_html = "\n".join(satir.strip() for satir in tablo_html.split("\n"))
                st.markdown(tablo_html, unsafe_allow_html=True)

                st.subheader("İşlem detayı")
                secili_islem = st.selectbox("İncelemek istediğin işlem ID'sini seç", filtreli_df["islem_id"])
                detay = sonuc_df[sonuc_df["islem_id"] == secili_islem].iloc[0]

                st.markdown("<div class='kart'>", unsafe_allow_html=True)
                d1, d2 = st.columns(2)
                with d1:
                    st.markdown(f"**İşlem ID:** {detay['islem_id']}")
                    st.markdown(f"**Durum:** {rozet_html(detay['hata_tipi'])}", unsafe_allow_html=True)
                    st.markdown(f"**{M['operator_terim']}:** {detay['operator']} — **{M['nokta_terim']}:** {detay['gecis_noktasi']}")
                with d2:
                    if pd.notna(detay.get("hgs_tutar")):
                        st.markdown(f"**{M['kaynak_kisa_adi']} tutar / tarih:** {detay['hgs_tutar']} TL — {detay['hgs_tarih']}")
                        st.markdown(f"**Banka tutar / tarih:** {detay['banka_tutar']} TL — {detay['banka_tarih']}")
                st.markdown(f"**Açıklama:** {detay['detay']}")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                st.info("Filtreye uyan kayıt bulunamadı.")

        with sekme2:
            st.subheader("Günlük uyuşmazlık trendi")
            trend_df = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"].copy()
            trend_df["tarih"] = pd.to_datetime(trend_df["hgs_tarih"].fillna(trend_df["banka_tarih"])).dt.date
            gunluk = trend_df.groupby("tarih").size()
            if len(gunluk) > 0:
                st.line_chart(gunluk, color="#F5B301")
                st.caption("En yoğun gün: " + str(gunluk.idxmax()) + f" ({gunluk.max()} uyuşmazlık)")
            else:
                st.info("Trend çizmek için tarih bilgisi bulunamadı.")

        with sekme3:
            st.subheader(f"{M['operator_terim']} bazında uyuşmazlık")
            op_kirilim = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"]["operator"].value_counts()
            if len(op_kirilim) > 0:
                st.bar_chart(op_kirilim, color="#1A1A1A")
            else:
                st.info(f"{M['operator_terim']} bilgisi bulunamadı.")

            st.subheader(f"{M['nokta_terim']} bazında uyuşmazlık")
            nokta_kirilim = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"]["gecis_noktasi"].value_counts()
            if len(nokta_kirilim) > 0:
                st.bar_chart(nokta_kirilim, color="#F5B301")
            else:
                st.info(f"{M['nokta_terim']} bilgisi bulunamadı.")

        with sekme4:
            st.caption(
                "Bu sekme sadece uyuşmayan kayıtları değil, **uyuşan kayıtlar dahil tüm işlemleri** "
                "istatistiksel olarak inceler — mutabakat açısından 'doğru' görünse bile normalden "
                "sapan (olası hata veya usulsüzlük işareti taşıyan) kayıtları yakalamak içindir."
            )

            ac1, ac2 = st.columns(2)
            with ac1:
                z_esik = st.slider("Tutar anomalisi hassasiyeti (z-skor eşiği)", 1.0, 4.0, 2.5, 0.1,
                                    help="Düşük değer = daha fazla (ama daha ufak) sapma yakalar")
            with ac2:
                gunluk_esik = st.slider(f"Aynı {M['anahtar_terim'].lower()}dan günlük geçiş eşiği", 2, 20, 5, 1,
                                         help=f"Bir {M['anahtar_terim'].lower()} bir günde bu sayıdan fazla "
                                              f"geçiş/işlem yaparsa işaretlenir")

            tutar_anomali_df, siklik_anomali_df = anomali_tespit_et(sonuc_df, z_esik, gunluk_esik)

            st.markdown("#### 💰 Tutar anomalileri")
            if len(tutar_anomali_df) > 0:
                st.caption(f"{len(tutar_anomali_df)} işlem, ortalamadan {z_esik} standart sapmadan fazla uzakta.")
                st.dataframe(
                    tutar_anomali_df.rename(columns={
                        "islem_id": "İşlem ID", "plaka": M["anahtar_terim"], "operator": M["operator_terim"],
                        "gecis_noktasi": M["nokta_terim"], "tutar": "Tutar (TL)",
                        "z_skor": "Z-skor", "durum": "Mutabakat durumu",
                    }),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("Bu eşikte tutar anomalisi bulunamadı.")

            st.markdown("#### 🔁 Sık geçiş anomalileri")
            if len(siklik_anomali_df) > 0:
                st.caption(f"{len(siklik_anomali_df)} {M['anahtar_terim'].lower()}-gün kombinasyonu, günlük eşiğin üzerinde işlem yapmış.")
                st.dataframe(
                    siklik_anomali_df.rename(columns={
                        "plaka": M["anahtar_terim"], "gun": "Tarih", "gecis_sayisi": "İşlem sayısı",
                    }),
                    use_container_width=True, hide_index=True,
                )
            else:
                st.info("Bu eşikte sık geçiş anomalisi bulunamadı.")

        st.divider()
        c1, c2 = st.columns(2)
        with c1:
            csv_cikti = sonuc_df.to_csv(index=False).encode("utf-8-sig")
            st.download_button(
                "CSV olarak indir",
                data=csv_cikti,
                file_name="mutabakat_sonuclari.csv",
                mime="text/csv",
            )
        with c2:
            excel_cikti = excel_raporu_uret(sonuc_df)
            st.download_button(
                "Excel raporu indir (özet + detay)",
                data=excel_cikti,
                file_name="mutabakat_raporu.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )

        with st.expander("Tüm kayıtları gör (uyuşan dahil)"):
            st.dataframe(sonuc_df, use_container_width=True, hide_index=True)
else:
    st.info(f"Devam etmek için sol menüden hem \"{M['kaynak1_etiket']}\" hem de \"{M['kaynak2_etiket']}\" "
            f"dosyasını yükle, ya da 'Örnek veriyle dene' butonuna tıkla.")