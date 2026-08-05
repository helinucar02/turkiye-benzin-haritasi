import pydeck as pdk
import pandas as pd
import streamlit as st
from components.visuals import optimum_logo_hazirla


def haritayi_ciz(rota_koordinatlari, onaylanan_duraklar):
    """
    Kullanıcının rotasını ve onayladığı durakları Streamlit üzerinde haritaya çizer.
    """
    aktif_katmanlar = []

    # 1. Katman: Rota Çizgisi (PathLayer)
    if len(rota_koordinatlari) > 0:
        rota_verisi = pd.DataFrame({"path": [rota_koordinatlari]})

        rota_katmani_dis = pdk.Layer(
            type="PathLayer",
            data=rota_verisi,
            pickable=False,
            get_color=[20, 60, 140, 220],
            width_scale=1,
            width_min_pixels=5,
            get_path="path",
            get_width=2,
            joint_rounded=True,
            cap_rounded=True,
        )
        rota_katmani_ic = pdk.Layer(
            type="PathLayer",
            data=rota_verisi,
            pickable=True,
            get_color=[50, 130, 246, 255],
            width_scale=1,
            width_min_pixels=3,
            get_path="path",
            get_width=1,
            joint_rounded=True,
            cap_rounded=True,
        )
        aktif_katmanlar.extend([rota_katmani_dis, rota_katmani_ic])

    # 2. Katman: Onaylanan Durakların Logolu Pinleri (IconLayer)
    if onaylanan_duraklar:
        durak_pin_verileri = []
        for d in onaylanan_duraklar:
            marka_adi = d.get("marka", "Bilinmiyor")
            durak_pin_verileri.append(
                {
                    "lat": d["lat"],
                    "lon": d["lon"],
                    "ad": d["ad"],
                    "brand": marka_adi,
                    "optimum_icon": {
                        "url": optimum_logo_hazirla(marka_adi),
                        "width": 128,
                        "height": 128,
                        "anchorY": 126,
                    },
                }
            )

        durak_df = pd.DataFrame(durak_pin_verileri)

        durak_ikon_katmani = pdk.Layer(
            type="IconLayer",
            data=durak_df,
            get_position=["lon", "lat"],
            get_icon="optimum_icon",
            get_size=1,
            size_scale=45,
            pickable=True,
            auto_highlight=True,
        )
        aktif_katmanlar.append(durak_ikon_katmani)

    # Kamera Odaklanması (Auto-Zoom)
    if len(rota_koordinatlari) > 0:
        latler = [koordinat[0] for koordinat in rota_koordinatlari]
        lonlar = [koordinat[1] for koordinat in rota_koordinatlari]
        merkez_lat = sum(latler) / len(latler)
        merkez_lon = sum(lonlar) / len(lonlar)

        baslangic_gorunumu = pdk.ViewState(
            latitude=merkez_lat,
            longitude=merkez_lon,
            zoom=7.2,
            pitch=0,
        )
    else:
        baslangic_gorunumu = pdk.ViewState(
            latitude=39.0, longitude=35.0, zoom=5.5, pitch=0
        )

    harita = pdk.Deck(
        map_style="road",
        layers=aktif_katmanlar,
        initial_view_state=baslangic_gorunumu,
        tooltip={"text": "İstasyon: {ad}\nMarka: {brand}"},
    )

    st.pydeck_chart(harita, use_container_width=True)
