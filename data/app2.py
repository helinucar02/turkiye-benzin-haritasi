from keplergl import KeplerGl
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Sayfa genişliği ve başlık
st.set_page_config(layout="wide", page_title="Kepler.gl İstasyon Haritası")
st.title("Türkiye Akaryakıt & Şarj İstasyonları - Kepler.gl 🚀")


# 1. Veriyi Oku
@st.cache_data
def veriyi_oku():
    data = pd.read_csv("data/processed/temiz_istasyon_verileri.csv")
    data["has_lpg"] = data["has_lpg"].astype(str).str.lower() == "true"
    data["has_charge"] = data["has_charge"].astype(str).str.lower() == "true"
    return data


df = veriyi_oku()

# Yan Menü Filtreleri
st.sidebar.title("Kepler Filtreleri 🛠️")
markalar = sorted(df["brand"].unique())
secili_markalar = st.sidebar.multiselect("Markaları Seçin", markalar, default=markalar)

sadece_lpg = st.sidebar.checkbox("Sadece LPG Olanları Göster")
sadece_sarj = st.sidebar.checkbox("Sadece Elektrikli Şarj Olanları Göster")

# Filtreleme Mantığı
filtreli_df = df[df["brand"].isin(secili_markalar)].copy()
if sadece_lpg:
    filtreli_df = filtreli_df[filtreli_df["has_lpg"]]
if sadece_sarj:
    filtreli_df = filtreli_df[filtreli_df["has_charge"]]

st.success(f"🎉 Kepler haritasında toplam **{len(filtreli_df)}** istasyon aktif.")

# 2. Kepler.gl Haritası Oluşturma (Aydınlık Tema ve Türkiye Konumu)
aydinlik_config = {
    "version": "v1",
    "config": {
        "mapState": {
            "latitude": 39.0,
            "longitude": 35.0,
            "zoom": 5.5,
            "pitch": 0,
            "bearing": 0,
        },
    },
}

# Haritayı aydınlık config ile oluşturuyoruz
harita = KeplerGl(height=650, data={"Istasyonlar": filtreli_df}, config=aydinlik_config)

# 3. Streamlit İçine Gömme
html_harita = harita._repr_html_()
components.html(html_harita, height=680)
