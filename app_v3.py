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

st.set_page_config(page_title="HGS Mutabakat Otomasyonu", layout="wide", page_icon="🚗")

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
    "HGS_TARAFINDA_YOK": "HGS tarafında yok",
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
                   tarih_toleransi_saat: float = TARIH_TOLERANS_SAAT) -> pd.DataFrame:
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

        temel = {"islem_id": islem_id, "operator": operator, "gecis_noktasi": gecis_noktasi,
                 "hgs_tutar": None, "banka_tutar": None, "hgs_tarih": None, "banka_tarih": None,
                 "tutar_farki_tl": 0.0}

        if len(hgs_satir) == 0 and banka_var_mi:
            sonuclar.append({**temel, "durum": "UYUSMUYOR", "hata_tipi": "HGS_TARAFINDA_YOK",
                              "detay": "Kayıt bankada var, HGS'de yok"})
            continue

        if len(hgs_satir) > 0 and not banka_var_mi:
            sonuclar.append({**temel, "durum": "UYUSMUYOR", "hata_tipi": "EKSIK_KAYIT",
                              "detay": "HGS'de var, bankaya hiç düşmemiş"})
            continue

        if islem_id in mukerrer_idler:
            sonuclar.append({**temel, "durum": "UYUSMUYOR", "hata_tipi": "MUKERRER_KAYIT",
                              "detay": f"Bankada {len(banka_gruplu.get_group(islem_id))} kez tekrar etmiş"})
            continue

        h = hgs_satir.iloc[0]
        b = banka_gruplu.get_group(islem_id).iloc[0]

        tutar_farki = round(abs(h["tutar"] - b["tutar"]), 2)
        tarih_farki_saat = abs((pd.to_datetime(h["gecis_tarihi"]) - pd.to_datetime(b["gecis_tarihi"])).total_seconds()) / 3600

        ortak = {**temel, "hgs_tutar": h["tutar"], "banka_tutar": b["tutar"],
                 "hgs_tarih": h["gecis_tarihi"], "banka_tarih": b["gecis_tarihi"]}

        if tutar_farki > tutar_toleransi:
            sonuclar.append({**ortak, "durum": "UYUSMUYOR", "hata_tipi": "TUTAR_FARKI",
                              "detay": f"HGS: {h['tutar']} TL, Banka: {b['tutar']} TL (fark: {tutar_farki} TL)",
                              "tutar_farki_tl": tutar_farki})
        elif tarih_farki_saat > tarih_toleransi_saat:
            sonuclar.append({**ortak, "durum": "UYUSMUYOR", "hata_tipi": "GECIKMELI_BILDIRIM",
                              "detay": f"Fark: {tarih_farki_saat:.1f} saat"})
        else:
            sonuclar.append({**ortak, "durum": "UYUSTU", "hata_tipi": "-", "detay": "-"})

    return pd.DataFrame(sonuclar)


def esnek_mutabakat_yap(hgs: pd.DataFrame, banka: pd.DataFrame,
                         tutar_toleransi: float = TUTAR_TOLERANS,
                         tarih_toleransi_saat: float = TARIH_TOLERANS_SAAT) -> pd.DataFrame:
    """
    İşlem ID'nin iki sistemde de ortak/güvenilir olmadığı gerçek dünya senaryoları için:
    plaka + geçiş tarihi + tutar üzerinden en yakın eşleşmeyi bulan yaklaşık mutabakat motoru.
    Her HGS kaydı için aynı plakaya sahip, henüz kullanılmamış en yakın tarihli banka kaydı aranır.
    """
    hgs = hgs.copy()
    banka = banka.copy()
    hgs["gecis_tarihi"] = pd.to_datetime(hgs["gecis_tarihi"])
    banka["gecis_tarihi"] = pd.to_datetime(banka["gecis_tarihi"])

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
                 "hgs_tutar": h["tutar"], "banka_tutar": None,
                 "hgs_tarih": h["gecis_tarihi"].strftime("%Y-%m-%d %H:%M"), "banka_tarih": None, "tutar_farki_tl": 0.0}

        if not adaylar:
            sonuclar.append({**temel, "durum": "UYUSMUYOR", "hata_tipi": "EKSIK_KAYIT",
                              "detay": f"'{h['plaka']}' plakasına ait kayıt bankada bulunamadı"})
            continue

        # Aynı plakadaki adaylar arasından tarihçe en yakın olanı seç
        en_yakin_idx = min(adaylar, key=lambda idx: abs((banka.loc[idx, "gecis_tarihi"] - h["gecis_tarihi"]).total_seconds()))
        b = banka.loc[en_yakin_idx]
        banka_kullanildi[en_yakin_idx] = True

        tutar_farki = round(abs(h["tutar"] - b["tutar"]), 2)
        tarih_farki_saat = abs((h["gecis_tarihi"] - b["gecis_tarihi"]).total_seconds()) / 3600

        ortak = {**temel, "banka_tutar": b["tutar"], "banka_tarih": b["gecis_tarihi"].strftime("%Y-%m-%d %H:%M")}

        if tutar_farki > tutar_toleransi:
            sonuclar.append({**ortak, "durum": "UYUSMUYOR", "hata_tipi": "TUTAR_FARKI",
                              "detay": f"HGS: {h['tutar']} TL, Banka: {b['tutar']} TL (fark: {tutar_farki} TL) — plaka+tarih ile eşleştirildi",
                              "tutar_farki_tl": tutar_farki})
        elif tarih_farki_saat > tarih_toleransi_saat:
            sonuclar.append({**ortak, "durum": "UYUSMUYOR", "hata_tipi": "GECIKMELI_BILDIRIM",
                              "detay": f"Fark: {tarih_farki_saat:.1f} saat — plaka+tarih ile eşleştirildi"})
        else:
            sonuclar.append({**ortak, "durum": "UYUSTU", "hata_tipi": "-", "detay": "Plaka+tarih ile eşleştirildi"})

    # Bankada kalıp hiç kullanılmayan kayıtlar: HGS'de karşılığı bulunamamış demektir
    for idx, kullanildi in enumerate(banka_kullanildi):
        if not kullanildi:
            b = banka.loc[idx]
            sonuclar.append({
                "islem_id": b.get("islem_id", f"BANKA-{idx}"), "operator": b.get("operator", "Bilinmiyor"),
                "gecis_noktasi": b.get("gecis_noktasi", "Bilinmiyor"),
                "hgs_tutar": None, "banka_tutar": b["tutar"], "hgs_tarih": None,
                "banka_tarih": b["gecis_tarihi"].strftime("%Y-%m-%d %H:%M"),
                "tutar_farki_tl": 0.0, "durum": "UYUSMUYOR", "hata_tipi": "HGS_TARAFINDA_YOK",
                "detay": f"'{b['plaka']}' plakasına ait bu kayda HGS tarafında karşılık bulunamadı",
            })

    return pd.DataFrame(sonuclar)


def rozet_html(hata_tipi: str) -> str:
    renk = HATA_RENKLERI.get(hata_tipi, "#7A7A7A")
    yazi_renk = HATA_YAZI_RENKLERI.get(hata_tipi, "#FFFFFF")
    etiket = HATA_ETIKETLERI.get(hata_tipi, hata_tipi)
    return f'<span class="rozet" style="background-color:{renk}; color:{yazi_renk}">{etiket}</span>'


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


def ornek_veri_uret():
    """Kullanıcı kendi dosyası olmadan uygulamayı denemek isterse küçük bir örnek veri seti üretir."""
    import random
    from datetime import datetime, timedelta

    random.seed(7)
    baslangic = datetime(2026, 9, 1)
    noktalar = ["Kavacık G.", "Zincirlikuyu G.", "Fatih SM G.", "TEM Otoyol G."]
    operatorler = ["HGS-A", "HGS-B", "HGS-C"]

    hgs_kayitlar, banka_kayitlar = [], []
    for i in range(1, 121):
        islem_id = f"TX{i:05d}"
        tarih = baslangic + timedelta(days=random.randint(0, 9), hours=random.randint(0, 23))
        tutar = round(random.choice([13.25, 17.50, 22.00, 35.75]), 2)
        kayit = {
            "islem_id": islem_id, "plaka": f"34 AB {1000+i}",
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


st.title("HGS Mutabakat Otomasyonu")
st.markdown('<div class="baslik-seridi"></div>', unsafe_allow_html=True)
st.caption("HGS ve banka tahsilat kayıtlarını yükle, otomatik eşleştirme ve hata sınıflandırması yap.")

if "ornek_veri_aktif" not in st.session_state:
    st.session_state.ornek_veri_aktif = False

with st.sidebar:
    st.header("Veri yükle")
    hgs_dosya = st.file_uploader("HGS kayıtları (CSV)", type="csv", key="hgs")
    banka_dosya = st.file_uploader("Banka kayıtları (CSV)", type="csv", key="banka")
    st.caption("Beklenen kolonlar: islem_id, plaka, gecis_tarihi, tutar, gecis_noktasi, operator")

    if st.button("🎲 Örnek veriyle dene"):
        st.session_state.ornek_veri_aktif = True
    if hgs_dosya or banka_dosya:
        st.session_state.ornek_veri_aktif = False

    st.divider()
    st.header("Eşleştirme yöntemi")
    eslestirme_yontemi = st.radio(
        "Kayıtlar hangi bilgiyle eşleştirilsin?",
        ["İşlem ID (birebir)", "Plaka + Tarih + Tutar (yaklaşık)"],
        help="İki sistemde ortak/güvenilir bir işlem ID yoksa 'yaklaşık' modu kullan — "
             "plaka ve en yakın geçiş zamanına göre eşleştirme yapar.",
    )

    st.divider()
    st.header("Eşik ayarları")
    tutar_toleransi = st.slider("Tutar farkı toleransı (TL)", 0.0, 10.0, 0.01, 0.5,
                                 help="Bu tutarın üzerindeki farklar 'uyuşmuyor' sayılır")
    tarih_toleransi = st.slider("Gecikme toleransı (saat)", 0, 24, 2, 1,
                                 help="Bu süreden uzun gecikmeler 'uyuşmuyor' sayılır")

if st.session_state.ornek_veri_aktif and not (hgs_dosya and banka_dosya):
    hgs_df, banka_df = ornek_veri_uret()
    st.info("Örnek veriyle çalışıyorsun. Kendi dosyalarını yüklemek için sol menüyü kullan.")
    veri_hazir = True
elif hgs_dosya and banka_dosya:
    hgs_df = pd.read_csv(hgs_dosya)
    banka_df = pd.read_csv(banka_dosya)
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
            f"Beklenen kolonlar eksik. HGS dosyasında eksik: {eksik_hgs or 'yok'} | "
            f"Banka dosyasında eksik: {eksik_banka or 'yok'}"
        )
    else:
        with st.spinner("Mutabakat yapılıyor..."):
            if eslestirme_yontemi.startswith("İşlem ID"):
                sonuc_df = mutabakat_yap(hgs_df, banka_df, tutar_toleransi, tarih_toleransi)
            else:
                sonuc_df = esnek_mutabakat_yap(hgs_df, banka_df, tutar_toleransi, tarih_toleransi)

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

        sekme1, sekme2, sekme3 = st.tabs(["📊 Genel bakış", "📈 Zaman trendi", "🏷️ Operatör / nokta kırılımı"])

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
                            <th style="text-align:left; padding:8px 10px; border-bottom:2px solid #1A1A1A; white-space:nowrap;">Operatör</th>
                            <th style="text-align:left; padding:8px 10px; border-bottom:2px solid #1A1A1A; white-space:nowrap;">Geçiş noktası</th>
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
                    st.markdown(f"**Operatör:** {detay['operator']} — **Nokta:** {detay['gecis_noktasi']}")
                with d2:
                    if pd.notna(detay.get("hgs_tutar")):
                        st.markdown(f"**HGS tutar / tarih:** {detay['hgs_tutar']} TL — {detay['hgs_tarih']}")
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
            st.subheader("Operatör bazında uyuşmazlık")
            op_kirilim = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"]["operator"].value_counts()
            if len(op_kirilim) > 0:
                st.bar_chart(op_kirilim, color="#1A1A1A")
            else:
                st.info("Operatör bilgisi bulunamadı.")

            st.subheader("Geçiş noktası bazında uyuşmazlık")
            nokta_kirilim = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"]["gecis_noktasi"].value_counts()
            if len(nokta_kirilim) > 0:
                st.bar_chart(nokta_kirilim, color="#F5B301")
            else:
                st.info("Geçiş noktası bilgisi bulunamadı.")

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
    st.info("Devam etmek için sol menüden hem HGS hem de banka kayıtları CSV dosyasını yükle, ya da 'Örnek veriyle dene' butonuna tıkla.")