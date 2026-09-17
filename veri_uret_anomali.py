"""
Anomali tespiti sekmesini test etmek için özel hazırlanmış veri seti.
İçinde kasıtlı olarak:
- 3 adet aşırı yüksek tutarlı işlem (tutar anomalisi tetiklemek için)
- 1 plaka aynı gün 9 kez geçiş yapıyor (sık geçiş anomalisi tetiklemek için)
- Geri kalan ~40 kayıt tamamen normal (gürültü/kontrol grubu)
"""

import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(99)

hgs_kayitlar = []
banka_kayitlar = []

noktalar = ["Kavacık G.", "Zincirlikuyu G.", "TEM Otoyol G."]
operatorler = ["HGS-A", "HGS-B", "HGS-C"]
gun = datetime(2026, 9, 10)

islem_no = 1

def kayit_ekle(plaka, saat, tutar, gecis_noktasi=None, operator=None):
    global islem_no
    islem_id = f"TX{islem_no:04d}"
    islem_no += 1
    tarih = (gun + timedelta(hours=saat)).strftime("%Y-%m-%d %H:%M")
    kayit = {
        "islem_id": islem_id, "plaka": plaka, "gecis_tarihi": tarih, "tutar": tutar,
        "gecis_noktasi": gecis_noktasi or random.choice(noktalar),
        "operator": operator or random.choice(operatorler),
    }
    hgs_kayitlar.append(kayit)
    banka_kayitlar.append(dict(kayit))  # mutabakat açısından hepsi uyuşsun, odak anomalide olsun

# --- 1) Normal kayıtlar (kontrol grubu) - tutar 15-40 TL arası ---
for i in range(40):
    plaka = f"34 NR {2000+i}"
    saat = random.randint(6, 22)
    tutar = round(random.choice([15.0, 17.5, 22.0, 28.0, 35.0, 40.0]), 2)
    kayit_ekle(plaka, saat, tutar)

# --- 2) Tutar anomalisi: aşırı yüksek 3 işlem ---
kayit_ekle("34 ANM 001", 9, 850.0)
kayit_ekle("34 ANM 002", 14, 920.0)
kayit_ekle("06 ANM 003", 20, 1100.0)

# --- 3) Sık geçiş anomalisi: aynı plaka aynı gün 9 kez ---
for saat in [7, 7, 9, 11, 13, 15, 17, 19, 21]:
    kayit_ekle("34 SIK 999", saat, 20.0, gecis_noktasi="Kavacık G.", operator="HGS-B")

hgs_df = pd.DataFrame(hgs_kayitlar)
banka_df = pd.DataFrame(banka_kayitlar)

hgs_df.to_csv("hgs_test_anomali.csv", index=False)
banka_df.to_csv("banka_test_anomali.csv", index=False)

print(f"Toplam kayıt: {len(hgs_df)}")
print("Dosyalar oluşturuldu: hgs_test_anomali.csv, banka_test_anomali.csv")
print("\nBeklenen anomaliler:")
print("- 3 tutar anomalisi (850, 920, 1100 TL'lik işlemler)")
print("- 1 sık geçiş anomalisi ('34 SIK 999' plakası, 2026-09-10'da 9 geçiş)")
