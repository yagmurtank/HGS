"""
POS Kart İşlemleri mutabakat modunu test etmek için veri üretici.
Uygulamanın POS modunda beklediği HAM kolon isimleriyle (kart_no, islem_tarihi,
isyeri, pos_saglayici) üretir - uygulama bunları otomatik olarak kanonik
isimlere çevirir.

İçerik:
- ~150 normal işlem (bir kısmında kasıtlı mutabakat hataları: tutar farkı,
  gecikmeli bildirim, eksik kayıt, mükerrer kayıt)
- 3 aşırı yüksek tutarlı işlem (tutar anomalisi testi için)
- 1 kart no aynı gün 8 kez kullanılıyor (sık işlem anomalisi testi için)
"""

import pandas as pd
import random
from datetime import datetime, timedelta

random.seed(42)

isyerleri = ["Migros Kadıköy", "CarrefourSA Ataşehir", "Boyner Nişantaşı",
             "Opet Maslak", "A101 Beşiktaş", "Teknosa Levent"]
saglayicilar = ["POS-Param", "POS-PayTR", "POS-VakıfPOS"]
baslangic = datetime(2026, 9, 1)

pos_kayitlar = []
banka_kayitlar = []
islem_no = 1


def maskeli_kart():
    return f"{random.randint(4000,4999)} **** **** {random.randint(1000,9999)}"


def kayit_ekle(kart_no, saat_offset_gun, saat, tutar, isyeri=None, saglayici=None):
    global islem_no
    islem_id = f"POS{islem_no:04d}"
    islem_no += 1
    tarih = (baslangic + timedelta(days=saat_offset_gun, hours=saat)).strftime("%Y-%m-%d %H:%M")
    kayit = {
        "islem_id": islem_id, "kart_no": kart_no, "islem_tarihi": tarih, "tutar": tutar,
        "isyeri": isyeri or random.choice(isyerleri),
        "pos_saglayici": saglayici or random.choice(saglayicilar),
    }
    return kayit


# --- 1) Normal işlemler + mutabakat hataları (150 kayıt) ---
for i in range(150):
    kart = maskeli_kart()
    gun = random.randint(0, 13)
    saat = random.randint(8, 22)
    tutar = round(random.choice([24.90, 49.50, 89.00, 149.90, 199.90, 59.90]), 2)

    hgs_kayit = kayit_ekle(kart, gun, saat, tutar)
    banka_kayit = dict(hgs_kayit)

    senaryo = random.random()
    if senaryo < 0.08:
        # tutar farkı (en sık)
        banka_kayit["tutar"] = round(tutar + random.choice([-5.0, -2.5, 1.5, 3.0]), 2)
    elif senaryo < 0.13:
        # gecikmeli bildirim (ikinci en sık)
        gecikme = timedelta(hours=random.randint(3, 30))
        yeni_tarih = datetime.strptime(hgs_kayit["islem_tarihi"], "%Y-%m-%d %H:%M") + gecikme
        banka_kayit["islem_tarihi"] = yeni_tarih.strftime("%Y-%m-%d %H:%M")
    elif senaryo < 0.16:
        # eksik kayıt
        banka_kayit = None
    elif senaryo < 0.18:
        # mükerrer kayıt
        banka_kayitlar.append(dict(hgs_kayit))

    pos_kayitlar.append(hgs_kayit)
    if banka_kayit is not None:
        banka_kayitlar.append(banka_kayit)

# --- 2) Tutar anomalisi: 3 aşırı yüksek işlem ---
for tutar in [1250.0, 1580.0, 2100.0]:
    kayit = kayit_ekle(maskeli_kart(), random.randint(0, 13), random.randint(9, 20), tutar)
    pos_kayitlar.append(kayit)
    banka_kayitlar.append(dict(kayit))

# --- 3) Sık işlem anomalisi: aynı kart aynı gün 8 kez ---
sik_kart = "4999 **** **** 0001"
for saat in [8, 9, 10, 12, 14, 16, 18, 20]:
    kayit = kayit_ekle(sik_kart, 5, saat, 39.90, isyeri="A101 Beşiktaş", saglayici="POS-Param")
    pos_kayitlar.append(kayit)
    banka_kayitlar.append(dict(kayit))

pos_df = pd.DataFrame(pos_kayitlar)
banka_df = pd.DataFrame(banka_kayitlar)

pos_df.to_csv("pos_kayitlari.csv", index=False)
banka_df.to_csv("banka_hesap_hareketleri.csv", index=False)

print(f"POS kayıt sayısı: {len(pos_df)}")
print(f"Banka hesap hareketi sayısı: {len(banka_df)}")
print("\nDosyalar oluşturuldu: pos_kayitlari.csv, banka_hesap_hareketleri.csv")
print("\nBeklenen sonuçlar:")
print("- Mutabakat: tutar farkı + gecikmeli bildirim + eksik kayıt + mükerrer kayıt karışık")
print("- Tutar anomalisi: 3 kayıt (1250, 1580, 2100 TL)")
print("- Sık işlem anomalisi: '4999 **** **** 0001' kartı, 1 günde 8 işlem")
