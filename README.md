[README.md](https://github.com/user-attachments/files/32287464/README.md)
# HGS Mutabakat Otomasyonu

HGS geçiş kayıtları ile banka tahsilat kayıtları arasındaki mutabakat sürecini otomatikleştiren, hata tiplerini sınıflandıran ve interaktif bir arayüzle sunan bir prototip.

**Canlı demo:** [ctaz29ijjbplqgrmb5apya.streamlit.app](https://ctaz29ijjbplqgrmb5apya.streamlit.app)

## Proje hakkında

Bankacılıkta nakit yönetimi / uygulama geliştirme stajı kapsamında, HGS mutabakatının şu an büyük ölçüde manuel (Excel bazlı) yürütülen bir süreç olduğu gözleminden yola çıkılarak geliştirilmiştir. Amaç, uyuşmazlıkları otomatik tespit edip sınıflandıran, gerçek veri gerektirmeyen (dummy veriyle çalışan) bir prototip ortaya koymak.

> **Not:** Bu proje gerçek banka verisi kullanmaz. Tüm veriler `veri_uret.py` ile üretilen sahte (dummy) kayıtlardır, yalnızca yöntemi göstermek amacıyla hazırlanmıştır.

## Özellikler

- **Otomatik eşleştirme:** İki kaynaktan gelen kayıtları eşleştirip 5 farklı uyuşmazlık tipini otomatik sınıflandırır (tutar farkı, gecikmeli bildirim, eksik kayıt, mükerrer kayıt, karşılıksız kayıt)
- **İki eşleştirme yöntemi:**
  - *İşlem ID ile* — iki sistemde ortak bir işlem numarası varsa birebir eşleştirme
  - *Plaka + Tarih + Tutar ile* — ortak bir ID olmadığı gerçek dünya senaryoları için yaklaşık eşleştirme
- **Ayarlanabilir eşik değerleri:** Tutar farkı ve gecikme toleransını arayüzden slider ile değiştirebilme
- **Analiz görünümleri:** Genel bakış, zaman bazlı trend, operatör/geçiş noktası kırılımı
- **Parasal etki özeti:** Toplam tutar farkının TL karşılığı
- **Dışa aktarma:** CSV ve çok sekmeli Excel (özet + detay) raporu
- **Örnek veriyle deneme:** Dosya yüklemeden, tek tıkla demo veri ile test

## Kullanılan teknolojiler

- Python, pandas (veri işleme ve eşleştirme mantığı)
- Streamlit (arayüz)
- openpyxl (Excel rapor üretimi)

## Kurulum ve çalıştırma

```bash
pip install -r requirements.txt
streamlit run app_v3.py
```

Uygulama açıldığında sol menüden örnek veri butonuna tıklayarak ya da kendi CSV dosyalarını (`islem_id, plaka, gecis_tarihi, tutar, gecis_noktasi, operator` kolonlarını içeren) yükleyerek deneyebilirsin.

## Dosya yapısı

```
├── app_v3.py              # Streamlit arayüzü ve mutabakat motoru
├── veri_uret.py            # Dummy HGS/banka veri üretici
├── requirements.txt        # Python bağımlılıkları
└── .streamlit/config.toml  # Arayüz tema ayarları
```

## Geliştirme fikirleri (yapılabilecekler)

- PDF formatında yönetici özeti raporu
- Mükerrer kayıt tespitinin esnek eşleştirme modunda da tam desteklenmesi
- Gerçek veri kaynaklarıyla (API/veritabanı) entegrasyon

---
*Bu proje bir staj çalışması kapsamında, öğrenme ve prototipleme amacıyla hazırlanmıştır.*
