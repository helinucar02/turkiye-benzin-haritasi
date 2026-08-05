import requests
import polyline
import streamlit as st
from geopy.geocoders import Nominatim


@st.cache_data
def koordinat_bul(yer_adi):
    """
    Nominatim API kullanarak bir yerin (il/ilçe) coğrafi koordinatlarını
    profesyonel ve filtrelenmiş olarak bulur.
    """
    geolocator = Nominatim(user_agent="turkiye_benzin_haritasi_app_v2")

    try:
        sorgu = f"{yer_adi}, Turkey"
        location = geolocator.geocode(sorgu, timeout=10)

        if location:
            return (location.latitude, location.longitude)
        return None
    except Exception as e:
        print(f"Koordinat bulma hatası: {e}")
        return None


def gercek_rota_ciz(koordinat_listesi):
    """
    OSRM API kullanarak verilen koordinat listesinden gerçek yol rotasını çizer.
    """
    koordinat_str = ";".join([f"{lon},{lat}" for lat, lon in koordinat_listesi])
    url = f"http://router.project-osrm.org/route/v1/driving/{koordinat_str}?overview=full&geometries=polyline"

    try:
        response = requests.get(url).json()
        if response.get("code") == "Ok":
            rota_bilgisi = response["routes"][0]
            sifreli_rota = rota_bilgisi["geometry"]
            mesafe_m = rota_bilgisi["distance"]
            sure_s = rota_bilgisi["duration"]

            cozulmus_koordinatlar = polyline.decode(sifreli_rota)
            pydeck_koordinatlari = [[lon, lat] for lat, lon in cozulmus_koordinatlar]

            return pydeck_koordinatlari, mesafe_m / 1000.0, sure_s / 60.0
        else:
            return None, 0, 0
    except Exception as e:
        print(f"Rota çizim hatası: {e}")
        return None, 0, 0
