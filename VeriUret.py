"""
HGS Mutabakatı - Dummy Veri Üretici
Gerçek veri kullanmadan, gerçekçi senaryolarla HGS ve Banka tarafı
işlem kayıtları üretir. Kasıtlı olarak bazı kayıtlarda uyuşmazlık
(tutar farkı, eksik kayıt, mükerrer kayıt, tarih kayması) bırakılır.
"""

import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

N_ISLEM = 500  # toplam işlem sayısı
BASLANGIC_TARIH = datetime(2026, 8, 1)

GECIS_NOKTALARI = ["Kavacık G.", "Zincirlikuyu G.", "Fatih SM G.", "15 Temmuz Köprüsü", "Avrasya Tüneli", "TEM Otoyol G."]
OPERATORLER = ["HGS-A", "HGS-B", "HGS-C"]

def rastgele_plaka():
    il = random.randint(1, 81)
    harf = ''.join(random.choices("ABCDEFGHIJKLMNOPRSTUVYZ", k=2))
    sayi = random.randint(100, 9999)
    return f"{il:02d} {harf} {sayi}"

def uret():
    hgs_kayitlar = []
    banka_kayitlar = []

    for i in range(1, N_ISLEM + 1):
        islem_id = f"TX{i:05d}"
        plaka = rastgele_plaka()
        tarih = BASLANGIC_TARIH + timedelta(days=random.randint(0, 29), hours=random.randint(0, 23), minutes=random.randint(0, 59))
        tutar = round(random.choice([13.25, 17.50, 22.00, 35.75, 44.00, 8.50]), 2)
        nokta = random.choice(GECIS_NOKTALARI)
        operator = random.choice(OPERATORLER)

        hgs_kayit = {
            "islem_id": islem_id,
            "plaka": plaka,
            "gecis_tarihi": tarih.strftime("%Y-%m-%d %H:%M"),
            "tutar": tutar,
            "gecis_noktasi": nokta,
            "operator": operator,
        }

        # Varsayılan: banka tarafı da aynı kayda sahip
        banka_kayit = dict(hgs_kayit)

        # Hata senaryosu oranları: tutar farkı en sık, gecikmeli bildirim ikinci sık
        # (bankada gözlemlenen gerçek dağılıma yakınlaştırıldı)
        senaryo = random.random()
        if senaryo < 0.08:
            # tutar farkı (en sık görülen hata tipi)
            banka_kayit["tutar"] = round(tutar + random.choice([-5.0, -2.5, 1.5, 3.0]), 2)
        elif senaryo < 0.13:
            # gecikmeli bildirim (ikinci en sık hata tipi)
            gecikme = timedelta(hours=random.randint(6, 48))
            banka_kayit["gecis_tarihi"] = (tarih + gecikme).strftime("%Y-%m-%d %H:%M")
        elif senaryo < 0.15:
            # eksik kayıt: banka tarafında hiç yok
            banka_kayit = None
        elif senaryo < 0.17:
            # mükerrer kayıt: banka tarafında iki kez düşmüş
            banka_kayitlar.append(dict(hgs_kayit))  # ekstra kopya

        hgs_kayitlar.append(hgs_kayit)
        if banka_kayit is not None:
            banka_kayitlar.append(banka_kayit)

    # Ayrıca banka tarafında HGS'de olmayan birkaç "yabancı" kayıt (örn. sistem hatası) ekleyelim
    for j in range(6):
        tarih = BASLANGIC_TARIH + timedelta(days=random.randint(0, 29))
        banka_kayitlar.append({
            "islem_id": f"TXX{j:03d}",
            "plaka": rastgele_plaka(),
            "gecis_tarihi": tarih.strftime("%Y-%m-%d %H:%M"),
            "tutar": round(random.choice([13.25, 22.00]), 2),
            "gecis_noktasi": random.choice(GECIS_NOKTALARI),
            "operator": random.choice(OPERATORLER),
        })

    return pd.DataFrame(hgs_kayitlar), pd.DataFrame(banka_kayitlar)

if __name__ == "__main__":
    hgs_df, banka_df = uret()
    hgs_df.to_csv("hgs_kayitlari.csv", index=False)
    banka_df.to_csv("banka_kayitlari.csv", index=False)
    print(f"HGS kayıt sayısı: {len(hgs_df)}")
    print(f"Banka kayıt sayısı: {len(banka_df)}")
    print("Dosyalar oluşturuldu: hgs_kayitlari.csv, banka_kayitlari.csv")