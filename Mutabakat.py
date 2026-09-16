"""
HGS Mutabakat Otomasyonu
HGS tarafı ve Banka tarafı kayıtlarını islem_id üzerinden eşleştirir,
uyuşmazlıkları tespit edip kategorize eder ve özet bir rapor üretir.
"""

import pandas as pd

TUTAR_TOLERANS = 0.01  # kuruş bazında yuvarlama farkını görmezden gel
TARIH_TOLERANS_SAAT = 2  # bu saatten fazla fark varsa "gecikme" say

def yukle():
    hgs = pd.read_csv("hgs_kayitlari.csv", parse_dates=["gecis_tarihi"])
    banka = pd.read_csv("banka_kayitlari.csv", parse_dates=["gecis_tarihi"])
    return hgs, banka

def mutabakat_yap(hgs, banka):
    sonuclar = []

    # Mükerrer kayıtları tespit et (banka tarafında aynı islem_id birden fazla kez varsa)
    mukerrer_idler = banka["islem_id"].value_counts()
    mukerrer_idler = set(mukerrer_idler[mukerrer_idler > 1].index)

    banka_gruplu = banka.groupby("islem_id")

    tum_idler = set(hgs["islem_id"]) | set(banka["islem_id"])

    for islem_id in sorted(tum_idler):
        hgs_satir = hgs[hgs["islem_id"] == islem_id]
        banka_var_mi = islem_id in banka_gruplu.groups

        if len(hgs_satir) == 0 and banka_var_mi:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "HGS_TARAFINDA_YOK",
                              "detay": "Kayıt bankada var, HGS'de yok (yabancı/hatalı kayıt olabilir)"})
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
        tarih_farki_saat = abs((h["gecis_tarihi"] - b["gecis_tarihi"]).total_seconds()) / 3600

        if tutar_farki > TUTAR_TOLERANS:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "TUTAR_FARKI",
                              "detay": f"HGS: {h['tutar']} TL, Banka: {b['tutar']} TL (fark: {tutar_farki} TL)"})
        elif tarih_farki_saat > TARIH_TOLERANS_SAAT:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSMUYOR", "hata_tipi": "GECIKMELI_BILDIRIM",
                              "detay": f"Fark: {tarih_farki_saat:.1f} saat"})
        else:
            sonuclar.append({"islem_id": islem_id, "durum": "UYUSTU", "hata_tipi": "-", "detay": "-"})

    return pd.DataFrame(sonuclar)

def rapor_yazdir(sonuc_df):
    toplam = len(sonuc_df)
    uyusan = (sonuc_df["durum"] == "UYUSTU").sum()
    uyusmayan = toplam - uyusan

    print("=" * 55)
    print("HGS MUTABAKAT RAPORU")
    print("=" * 55)
    print(f"Toplam işlem incelendi : {toplam}")
    print(f"Uyuşan kayıt           : {uyusan}  (%{uyusan/toplam*100:.1f})")
    print(f"Uyuşmayan kayıt        : {uyusmayan}  (%{uyusmayan/toplam*100:.1f})")
    print("-" * 55)
    print("Hata tipi dağılımı:")
    hata_dagilimi = sonuc_df[sonuc_df["durum"] == "UYUSMUYOR"]["hata_tipi"].value_counts()
    for hata_tipi, adet in hata_dagilimi.items():
        print(f"  - {hata_tipi:<22}: {adet}")
    print("=" * 55)

if __name__ == "__main__":
    hgs, banka = yukle()
    sonuc = mutabakat_yap(hgs, banka)
    sonuc.to_csv("mutabakat_sonuclari.csv", index=False)
    rapor_yazdir(sonuc)
    print("\nDetaylı sonuçlar 'mutabakat_sonuclari.csv' dosyasına kaydedildi.")