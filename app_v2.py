"""
HGS Mutabakat Otomasyonu - Streamlit Arayüzü (v2)
Çalıştırmak için: streamlit run app.py

Yenilikler:
- Hata tipine ve duruma göre filtreleme
- İşlem bazında detay görünümü
- Renkli durum rozetleri, daha temiz kart tasarımı
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="HGS Mutabakat Otomasyonu", layout="wide", page_icon="🚗")

TUTAR_TOLERANS = 0.01
TARIH_TOLERANS_SAAT = 2

HATA_RENKLERI = {
    "TUTAR_FARKI": "#D85A30",
    "GECIKMELI_BILDIRIM": "#BA7517",
    "EKSIK_KAYIT": "#993C1D",
    "MUKERRER_KAYIT": "#993556",
    "HGS_TARAFINDA_YOK": "#5F5E5A",
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
        border-radius: 12px;
        font-size: 12.5px;
        font-weight: 600;
        color: white;
    }
    .kart {
        border: 1px solid rgba(128,128,128,0.25);
        border-radius: 10px;
        padding: 16px 20px;
        margin-bottom: 8px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def mutabakat_yap(hgs: pd.DataFrame, banka: pd.DataFrame) -> pd.DataFrame:
    sonuclar = []

    mukerrer_idler = banka["islem_id"].value_counts()
    mukerrer_idler = set(mukerrer_idler[mukerrer_idler > 1].index)

    banka_gruplu = banka.groupby("islem_id")
    tum_idler = set(hgs["islem_id"]) | set(banka["islem_id"])

    for islem_id in sorted(tum_idler):
        hgs_satir = hgs[hgs["islem_id"] == islem_id]
        banka_var_mi = islem_id in banka_gruplu.groups

        if len(hgs_satir) == 0 and banka_var_mi:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "HGS_TARAFINDA_YOK",
                              "detay": "Kayıt bankada var, HGS'de yok"})
            continue

        if len(hgs_satir) > 0 and not banka_var_mi:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "EKSIK_KAYIT",
                              "detay": "HGS'de var, bankaya hiç düşmemiş"})
            continue

        if islem_id in mukerrer_idler:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "MUKERRER_KAYIT",
                              "detay": f"Bankada {len(banka_gruplu.get_group(islem_id))} kez tekrar etmiş"})
            continue

        h = hgs_satir.iloc[0]
        b = banka_gruplu.get_group(islem_id).iloc[0]

        tutar_farki = round(abs(h["tutar"] - b["tutar"]), 2)
        tarih_farki_saat = abs((pd.to_datetime(h["gecis_tarihi"]) - pd.to_datetime(b["gecis_tarihi"])).total_seconds()) / 3600

        if tutar_farki > TUTAR_TOLERANS:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "TUTAR_FARKI",
                              "detay": f"HGS: {h['tutar']} TL, Banka: {b['tutar']} TL (fark: {tutar_farki} TL)",
                              "hgs_tutar": h["tutar"], "banka_tutar": b["tutar"],
                              "hgs_tarih": h["gecis_tarihi"], "banka_tarih": b["gecis_tarihi"]})
            continue
        elif tarih_farki_saat > TARIH_TOLERANS_SAAT:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "GECIKMELI_BILDIRIM",
                              "detay": f"Fark: {tarih_farki_saat:.1f} saat",
                              "hgs_tutar": h["tutar"], "banka_tutar": b["tutar"],
                              "hgs_tarih": h["gecis_tarihi"], "banka_tarih": b["gecis_tarihi"]})
            continue
        else:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSTU", "hata_tipi": "-", "detay": "-",
                              "hgs_tutar": h["tutar"], "banka_tutar": b["tutar"],
                              "hgs_tarih": h["gecis_tarihi"], "banka_tarih": b["gecis_tarihi"]})

    return pd.DataFrame(sonuclar)


def rozet_html(hata_tipi: str) -> str:
    renk = HATA_RENKLERI.get(hata_tipi, "#5F5E5A")
    etiket = HATA_ETIKETLERI.get(hata_tipi, hata_tipi)
    return f'<span class="rozet" style="background-color:{renk}">{etiket}</span>'


st.title("HGS Mutabakat Otomasyonu")
st.caption("HGS ve banka tahsilat kayıtlarını yükle, otomatik eşleştirme ve hata sınıflandırması yap.")

with st.sidebar:
    st.header("Veri yükle")
    hgs_dosya = st.file_uploader("HGS kayıtları (CSV)", type="csv", key="hgs")
    banka_dosya = st.file_uploader("Banka kayıtları (CSV)", type="csv", key="banka")
    st.caption("Beklenen kolonlar: islem_id, plaka, gecis_tarihi, tutar, gecis_noktasi, operator")

if hgs_dosya and banka_dosya:
    hgs_df = pd.read_csv(hgs_dosya)
    banka_df = pd.read_csv(banka_dosya)

    gerekli_kolonlar = {"islem_id", "gecis_tarihi", "tutar"}
    eksik_hgs = gerekli_kolonlar - set(hgs_df.columns)
    eksik_banka = gerekli_kolonlar - set(banka_df.columns)

    if eksik_hgs or eksik_banka:
        st.error(
            f"Beklenen kolonlar eksik. HGS dosyasında eksik: {eksik_hgs or 'yok'} | "
            f"Banka dosyasında eksik: {eksik_banka or 'yok'}"
        )
    else:
        with st.spinner("Mutabakat yapılıyor..."):
            sonuc_df = mutabakat_yap(hgs_df, banka_df)

        toplam = len(sonuc_df)
        uyusan = int((sonuc_df["durum"] == "UYUSTU").sum())
        uyusmayan = toplam - uyusan

        m1, m2, m3 = st.columns(3)
        m1.metric("Toplam işlem", toplam)
        m2.metric("Uyuşan kayıt", uyusan, f"%{uyusan/toplam*100:.1f}")
        m3.metric("Uyuşmayan kayıt", uyusmayan, f"%{uyusmayan/toplam*100:.1f}", delta_color="inverse")

        st.subheader("Hata tipi dağılımı")
        hata_dagilimi = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"]["hata_tipi"].value_counts()
        if len(hata_dagilimi) > 0:
            hata_dagilimi_okunabilir = hata_dagilimi.rename(index=HATA_ETIKETLERI)
            st.bar_chart(hata_dagilimi_okunabilir)
        else:
            st.info("Hiç uyuşmazlık bulunamadı.")

        st.divider()
        st.subheader("Uyuşmayan kayıtlar")

        uyusmayan_df = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"].reset_index(drop=True)

        # --- Filtreleme ---
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
            filtreli_df = filtreli_df[
                filtreli_df["islem_id"].str.contains(arama, case=False, na=False)
            ]

        st.caption(f"{len(filtreli_df)} / {len(uyusmayan_df)} uyuşmayan kayıt gösteriliyor")

        # Görsel tablo: rozet olarak hata tipi
        goruntu_df = filtreli_df.copy()
        if len(goruntu_df) > 0:
            goruntu_df["hata_tipi_rozet"] = goruntu_df["hata_tipi"].map(
                lambda x: HATA_ETIKETLERI.get(x, x)
            )
            st.dataframe(
                goruntu_df[["islem_id", "hata_tipi_rozet", "detay"]].rename(
                    columns={"hata_tipi_rozet": "hata tipi"}
                ),
                use_container_width=True,
                hide_index=True,
            )
        else:
            st.info("Filtreye uyan kayıt bulunamadı.")

        # --- İşlem detay görünümü ---
        st.divider()
        st.subheader("İşlem detayı")

        if len(filtreli_df) > 0:
            secili_islem = st.selectbox("İncelemek istediğin işlem ID'sini seç", filtreli_df["islem_id"])
            detay = sonuc_df[sonuc_df["islem_id"] == secili_islem].iloc[0]

            st.markdown(f"<div class='kart'>", unsafe_allow_html=True)
            d1, d2 = st.columns(2)
            with d1:
                st.markdown(f"**İşlem ID:** {detay['islem_id']}")
                st.markdown(f"**Durum:** {rozet_html(detay['hata_tipi']) if detay['durum']=='UYUSMUYOR' else '✅ Uyuştu'}", unsafe_allow_html=True)
            with d2:
                if "hgs_tutar" in detay and pd.notna(detay.get("hgs_tutar")):
                    st.markdown(f"**HGS tutar / tarih:** {detay['hgs_tutar']} TL — {detay['hgs_tarih']}")
                    st.markdown(f"**Banka tutar / tarih:** {detay['banka_tutar']} TL — {detay['banka_tarih']}")
            st.markdown(f"**Açıklama:** {detay['detay']}")
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            st.caption("Detay görmek için önce filtreye uyan bir kayıt olmalı.")

        st.divider()
        csv_cikti = sonuc_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Tüm mutabakat sonuçlarını indir (CSV)",
            data=csv_cikti,
            file_name="mutabakat_sonuclari.csv",
            mime="text/csv",
        )

        with st.expander("Tüm kayıtları gör (uyuşan dahil)"):
            st.dataframe(sonuc_df, use_container_width=True, hide_index=True)
else:
    st.info("Devam etmek için sol menüden hem HGS hem de banka kayıtları CSV dosyasını yükle.")