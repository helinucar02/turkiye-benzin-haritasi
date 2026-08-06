# ⛽ Türkiye Benzin İstasyonları Haritası

Bu proje, Türkiye genelindeki farklı akaryakıt markalarının konum verilerini temizleyerek interaktif bir harita üzerinde görselleştirir.

## 🚀 Nasıl Çalıştırılır?

1. Bağımlılıkları yükleyin:
   ```bash
   pip install -r requirements.txt


   A. Çift Modlu Sistem (Human-in-the-loop vs. Auto-Pilot)
Gerçek bir üründe kullanıcıya iki seçenek sunulur:

Kendim Seçeceğim (Manuel Mod): Şu anki yaptığımız sistem. Greedy algoritma çalışır, menzil içindeki durakları gösterir, son kararı kullanıcı (insan) verir.

Yapay Zeka Belirlesin (A Auto-Pilot):* Kullanıcı "Bana en iyi rotayı çiz" der. A* algoritması devreye girer. Başlangıçtan hedefe kadar, aracın yakıt tüketimi, istasyonların mesafesi ve menzil kısıtlarını hesaplayarak, hiç kullanıcıya sormadan kusursuz istasyon zincirini (Durak 1 -> Durak 2 -> Hedef) tek seferde bulur ve ekrana çizer.

B. A* Algoritmasının "Maliyet Fonksiyonunu" (Cost Function) Akıllandırmak
Sadece mesafe bazlı bir A* profesyonel değildir. Bir AI mühendisi algorithm.py dosyasındaki A* maliyet fonksiyonunu (Heuristic) şu verilerle beslerdi:

Yakıt Fiyatı Optimizasyonu: "Menzil yetiyor ama 20 km ilerideki istasyonda benzin 2 TL daha ucuz, A* orayı seçsin."

İstasyon Puanları (Rating): Tuvaleti temiz, restoranı olan yüksek puanlı istasyonlara algoritmada "daha az maliyetli" (cazip) muamelesi yapılırdı.

Şarj Süresi (Elektrikli Araçlar İçin): Sadece yol mesafesi değil, istasyondaki şarj cihazının hızı (kW) da algoritmaya süre maliyeti olarak eklenirdi.

C. Prediktif (Tahminsel) Menzil Modeli
Şu an menzili (Yakıt / Tüketim) gibi basit bir matematikle hesaplıyoruz. Bir AI mühendisi buraya bir Makine Öğrenmesi (Machine Learning) modeli entegre ederdi. Rakım değişikliği (yokuş çıkmak), trafik yoğunluğu ve hava durumu (klima kullanımı) gibi parametrelere göre tüketimi dinamik tahmin eder, A* algoritmasının menzil sınırını buna göre daraltıp genişletirdi.

🔥 Ürünümüzü "Gerçek Profesyonel" Seviyeye Çıkarma Planı
Madem gerçek bir ürün yapıyoruz, o halde A* algoritmamızı (algorithm.py) yeniden sahneye çağırmalıyız!

Yan menüye (Sidebar) bir "Yapay Zeka (A) ile Otomatik Planla"* butonu (Toggle) ekleyelim.

Eğer kullanıcı bunu açarsa; sistem durak seçimi için adım adım onay beklemesin, senin yazdığın A* algoritmasını çalıştırıp en ideal istasyon noktalarını arka arkaya bulsun ve rotayı tek seferde çizsin.

Kapalıysa, şu anki "Etkileşimli (Greedy)" modda çalışsın.