import pandas as pd
import json

df_alpet = pd.read_json("data/raw/benzinistasyonu/alpet.json", encoding="utf-8")
df_alpet_temiz = df_alpet[["Name", "Enlem", "Boylam"]].copy()
df_alpet_temiz = df_alpet_temiz.rename(
    columns={"Name": "istasyon_adi", "Enlem": "lat", "Boylam": "lon"}
)
# Hangi markaya ait olduğunu takip edebilmek için yeni bir sütun ekleyelim
df_alpet_temiz["brand"] = "Alpet"


df_aytemiz = pd.read_json("data/raw/benzinistasyonu/aytemiz.json", encoding="utf-8")
df_aytemiz_temiz = df_aytemiz[["Title", "Lat", "Lon"]].copy()
df_aytemiz_temiz = df_aytemiz_temiz.rename(
    columns={"Title": "istasyon_adi", "Lat": "lat", "Lon": "lon"}
)
df_aytemiz_temiz["brand"] = "Aytemiz"

df_kadoil = pd.read_json("data/raw/benzinistasyonu/kadoil.json", encoding="utf-8")
df_kadoil_temiz = df_kadoil[["name", "lat", "lng"]].copy()
df_kadoil_temiz = df_kadoil_temiz.rename(
    columns={"name": "istasyon_adi", "lat": "lat", "lng": "lon"}
)
df_kadoil_temiz["brand"] = "Kadoil"

df_opet = pd.read_json("data/raw/benzinistasyonu/opet.json", encoding="utf-8")
df_opet_temiz = df_opet[["name", "latitude", "longitude"]].copy()
df_opet_temiz = df_opet_temiz.rename(
    columns={"name": "istasyon_adi", "latitude": "lat", "longitude": "lon"}
)
df_opet_temiz["brand"] = "Opet"

# --- 5. Petrol Ofisi (Kesin Çalışan Düzen) ---
# Dosyayı düz bir şekilde okuyoruz
df_po_raw = pd.read_json("data/raw/benzinistasyonu/petrol_ofisi.json", encoding="utf-8")

# Tablonun ilk hücresindeki ("Values" sütununun altındaki) listeyi alıp doğrudan DataFrame yapıyoruz
df_petrol_ofisi = pd.DataFrame(df_po_raw["Values"].iloc[0])

# Burası senin yazdığın o harika ve alıştığın kod düzeniyle tamamen aynı!
df_petrol_ofisi_temiz = df_petrol_ofisi[["StationName", "Latitude", "Longitude"]].copy()
df_petrol_ofisi_temiz = df_petrol_ofisi_temiz.rename(
    columns={"StationName": "istasyon_adi", "Latitude": "lat", "Longitude": "lon"}
)
df_petrol_ofisi_temiz["brand"] = "Petrol Ofisi"


df_shell = pd.read_json("data/raw/benzinistasyonu/shell.json", encoding="utf-8")
df_shell_temiz = df_shell[["name", "lat", "lng"]].copy()
df_shell_temiz = df_shell_temiz.rename(
    columns={"name": "istasyon_adi", "lat": "lat", "lng": "lon"}
)
df_shell_temiz["brand"] = "Shell"

df_soil = pd.read_json("data/raw/benzinistasyonu/soil_stations.json", encoding="utf-8")
df_soil_temiz = df_soil[["title", "lat", "lng"]].copy()
df_soil_temiz = df_soil_temiz.rename(
    columns={"title": "istasyon_adi", "lat": "lat", "lng": "lon"}
)
df_soil_temiz["brand"] = "Soil"

df_total = pd.read_json(
    "data/raw/benzinistasyonu/total_stations.json", encoding="utf-8"
)
df_total_temiz = df_total[["name", "lat", "lon"]].copy()
df_total_temiz = df_total_temiz.rename(
    columns={"name": "istasyon_adi", "lat": "lat", "lon": "lon"}
)
df_total_temiz["brand"] = "Total"

df_turkpetrol = pd.read_json(
    "data/raw/benzinistasyonu/turkiye_petrolleri.json", encoding="utf-8"
)
df_turkpetrol_temiz = df_turkpetrol[["StationName", "Lat", "Lng"]].copy()
df_turkpetrol_temiz = df_turkpetrol_temiz.rename(
    columns={"StationName": "istasyon_adi", "Lat": "lat", "Lng": "lon"}
)
df_turkpetrol_temiz["brand"] = "Turkiye Petrolleri"


tum_istasyonlar = pd.concat(
    [
        df_alpet_temiz,
        df_aytemiz_temiz,
        df_kadoil_temiz,
        df_opet_temiz,
        df_petrol_ofisi_temiz,
        df_shell_temiz,
        df_soil_temiz,
        df_total_temiz,
        df_turkpetrol_temiz,
    ],
    ignore_index=True,
)
tum_istasyonlar = tum_istasyonlar[
    (tum_istasyonlar["lat"] >= 36)
    & (tum_istasyonlar["lat"] <= 42)
    & (tum_istasyonlar["lon"] >= 26)
    & (tum_istasyonlar["lon"] <= 45)
]

# Boş koordinat satırları varsa onları da temizleyelim
tum_istasyonlar = tum_istasyonlar.dropna(subset=["lat", "lon"])

# --- KAYDETME ADIMI ---
# Temizlediğimiz bu tek veri setini CSV dosyası olarak klasörümüze kaydedelim
tum_istasyonlar.to_csv(
    "data/processed/temiz_istasyonlar.csv", index=False, encoding="utf-8"
)
print(
    f"Başarılı! Toplam {len(tum_istasyonlar)} adet istasyon temizlendi ve 'temiz_istasyonlar.csv' olarak kaydedildi."
)
