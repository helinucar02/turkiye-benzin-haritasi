import pandas as pd
import json


def rotaya_yakin_istasyonlari_cek(
    supabase_client, osrm_koordinatlari, tampon_metre=3000
):
    # 1. OSRM'den gelen koordinat listesini PostGIS'in anlayacağı GeoJSON formatına çeviriyoruz
    rota_geojson_sozlugu = {
        "type": "LineString",
        "coordinates": osrm_koordinatlari,  # Format: [[lon1, lat1], [lon2, lat2], ...]
    }

    # Sözlüğü metne (String) dönüştürüyoruz çünkü SQL fonksiyonumuz "text" bekliyor
    rota_geojson_metni = json.dumps(rota_geojson_sozlugu)

    # 2. Supabase içindeki kaydettiğimiz SQL fonksiyonunu (RPC) uzaktan tetikliyoruz
    cevap = supabase_client.rpc(
        "rotaya_yakin_istasyonlari_getir",
        {"rota_geojson": rota_geojson_metni, "tampon_metre": tampon_metre},
    ).execute()

    # 3. Gelen JSON formatındaki süzülmüş istasyonları, projenle uyumlu olması için DataFrame'e çeviriyoruz
    filtrelenmis_df = pd.DataFrame(cevap.data)

    return filtrelenmis_df
