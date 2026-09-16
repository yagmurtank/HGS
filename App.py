"""
HGS Mutabakat Otomasyonu - Streamlit Arayüzü
Çalıştırmak için: streamlit run app.py
"""

import streamlit as st
import pandas as pd

st.set_page_config(page_title="HGS Mutabakat Otomasyonu", layout="wide")

TUTAR_TOLERANS = 0.01
TARIH_TOLERANS_SAAT = 2


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
                              "detay": f"HGS: {h['tutar']} TL, Banka: {b['tutar']} TL (fark: {tutar_farki} TL)"})
        elif tarih_farki_saat > TARIH_TOLERANS_SAAT:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "GECIKMELI_BILDIRIM",
                              "detay": f"Fark: {tarih_farki_saat:.1f} saat"})
        else:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSTU", "hata_tipi": "-", "detay": "-"})

    return pd.DataFrame(sonuclar)


st.title("HGS Mutabakat Otomasyonu")
st.caption("HGS ve banka tahsilat kayıtlarını yükle, otomatik eşleştirme ve hata sınıflandırması yap.")

col1, col2 = st.columns(2)
with col1:
    hgs_dosya = st.file_uploader("HGS kayıtları (CSV)", type="csv", key="hgs")
with col2:
    banka_dosya = st.file_uploader("Banka kayıtları (CSV)", type="csv", key="banka")

st.divider()

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
            st.bar_chart(hata_dagilimi)
        else:
            st.info("Hiç uyuşmazlık bulunamadı.")

        st.subheader("Uyuşmayan kayıtlar")
        st.dataframe(
            sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"].reset_index(drop=True),
            use_container_width=True,
        )

        csv_cikti = sonuc_df.to_csv(index=False).encode("utf-8-sig")
        st.download_button(
            "Mutabakat sonuçlarını indir (CSV)",
            data=csv_cikti,
            file_name="mutabakat_sonuclari.csv",
            mime="text/csv",
        )

        with st.expander("Tüm kayıtları gör"):
            st.dataframe(sonuc_df, use_container_width=True)
else:
    st.info("Devam etmek için hem HGS hem de banka kayıtları CSV dosyasını yükle.")
    st.caption("Beklenen kolonlar: islem_id, plaka, gecis_tarihi, tutar, gecis_noktasi, operator")