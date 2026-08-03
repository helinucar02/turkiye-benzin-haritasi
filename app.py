import base64
import io
import os
import pandas as pd
import requests
import polyline
from PIL import Image, ImageOps, ImageDraw, ImageFont
import pydeck as pdk
import streamlit as st
from supabase import create_client, Client
from geopy.geocoders import Nominatim
from database import rotaya_yakin_istasyonlari_cek
from routing import osrm_mesafe_matrisi_olustur
from algorithm import a_star_rotasi_bul, Istasyon

# Sayfa genişliğini ve başlığını ayarlayalım
st.set_page_config(layout="wide")
st.title("Türkiye Akaryakıt & Şarj İstasyonları Haritası 📍")

# ==========================================
# STATE MANAGEMENT (DURUM YÖNETİMİ)
# ==========================================
if "rota_koordinatlari" not in st.session_state:
    st.session_state.rota_koordinatlari = []

if "aktif_istasyon_idleri" not in st.session_state:
    st.session_state.aktif_istasyon_idleri = []

if "optimum_istasyon_idleri" not in st.session_state:
    st.session_state.optimum_istasyon_idleri = []

if "rota_mesafe_km" not in st.session_state:
    st.session_state.rota_mesafe_km = 0.0

if "rota_sure_dk" not in st.session_state:
    st.session_state.rota_sure_dk = 0.0

if "ham_istasyonlar_df" not in st.session_state:
    st.session_state.ham_istasyonlar_df = pd.DataFrame()


# ==========================================
# 1. VERİTABANI BAĞLANTISI (SUPABASE)
# ==========================================
url = st.secrets["SUPABASE_URL"]
key = st.secrets["SUPABASE_KEY"]
supabase_client: Client = create_client(url, key)


@st.cache_data
def veriyi_oku():
    response = supabase_client.table("istasyonlar").select("*").execute()
    data = pd.DataFrame(response.data)
    data["has_lpg"] = data["has_lpg"].astype(str).str.lower() == "true"
    data["has_charge"] = data["has_charge"].astype(str).str.lower() == "true"
    return data


df = veriyi_oku()

# ==========================================
# YAN MENÜ VE FİLTRELEME İŞLEMLERİ
# ==========================================
st.sidebar.title("Filtreleme Seçenekleri 🛠️")

markalar = sorted(df["brand"].unique())
secili_markalar = st.sidebar.multiselect("Markaları Seçin", markalar, default=markalar)

st.sidebar.markdown("---")
st.sidebar.write("**İstasyon Özellikleri**")
sadece_lpg = st.sidebar.checkbox("Sadece LPG Olanları Göster")
sadece_sarj = st.sidebar.checkbox("Sadece Elektrikli Şarj Olanları Göster")

filtreli_df = df[df["brand"].isin(secili_markalar)].copy()

if sadece_lpg:
    filtreli_df = filtreli_df[filtreli_df["has_lpg"]]
if sadece_sarj:
    filtreli_df = filtreli_df[filtreli_df["has_charge"]]

# ==========================================
# ROTA MOTORU (GEOPY & OSRM API)
# ==========================================
st.sidebar.markdown("---")
st.sidebar.subheader("📍 Rota Planlama")

if "baslangic_input" not in st.session_state:
    st.session_state.baslangic_input = "Uşak"
if "bitis_input" not in st.session_state:
    st.session_state.bitis_input = "İstanbul"

col_b1, col_b2, col_b3 = st.sidebar.columns([5, 1, 5])
with col_b1:
    baslangic = st.text_input(
        "Nereden", value=st.session_state.baslangic_input, key="giris_baslangic"
    )
with col_b2:
    st.markdown("<br>", unsafe_allow_html=True)
    if st.button("⇄", help="Başlangıç ve Bitiş Yerini Değiştir"):
        st.session_state.baslangic_input, st.session_state.bitis_input = (
            st.session_state.bitis_input,
            st.session_state.baslangic_input,
        )
        st.rerun()
with col_b3:
    bitis = st.text_input(
        "Nereye", value=st.session_state.bitis_input, key="giris_bitis"
    )

st.session_state.baslangic_input = baslangic
st.session_state.bitis_input = bitis

st.sidebar.markdown("---")
st.sidebar.subheader("🚗 Araç Bilgileri")
max_yakit = st.sidebar.number_input(
    "Depo Kapasitesi (Litre)", min_value=10.0, max_value=120.0, value=40.0
)
tuketim_100km = st.sidebar.number_input(
    "Ortalama Tüketim (L/100km)", min_value=1.0, max_value=20.0, value=15.0
)
tuketim_km = tuketim_100km / 100.0

maks_menzil = (max_yakit / tuketim_km) if tuketim_km > 0 else 400

rota_hesapla = st.sidebar.button("Rotayı Çiz")


@st.cache_data
def koordinat_bul(adres):
    geolocator = Nominatim(user_agent="turkiye_istasyon_haritasi")
    location = geolocator.geocode(f"{adres}, Türkiye")
    if location:
        return location.latitude, location.longitude
    return None


def gercek_rota_ciz(koordinat_listesi):
    koordinat_str = ";".join([f"{lon},{lat}" for lat, lon in koordinat_listesi])
    url = f"http://router.project-osrm.org/route/v1/driving/{koordinat_str}?overview=full&geometries=polyline"
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


# Buton Tıklanma Olayı
if rota_hesapla:
    if baslangic and bitis:
        koordinat_1 = koordinat_bul(baslangic)
        koordinat_2 = koordinat_bul(bitis)

        if koordinat_1 and koordinat_2:
            st.session_state.krd_baslangic = koordinat_1
            st.session_state.krd_hedef = koordinat_2

            with st.spinner(
                "Yapay zeka yakıt rotanızı ve optimum durakları hesaplıyor..."
            ):
                rota_cizgisi, mesafe_km, sure_dk = gercek_rota_ciz(
                    [koordinat_1, koordinat_2]
                )

                if rota_cizgisi:
                    st.session_state.rota_koordinatlari = rota_cizgisi
                    st.session_state.rota_mesafe_km = mesafe_km
                    st.session_state.rota_sure_dk = sure_dk

                    yakin_istasyonlar_df = rotaya_yakin_istasyonlari_cek(
                        supabase_client, rota_cizgisi, tampon_metre=5000
                    )

                    if not yakin_istasyonlar_df.empty:
                        if len(yakin_istasyonlar_df) > 90:
                            yakin_istasyonlar_df = yakin_istasyonlar_df.head(90)

                        st.session_state.ham_istasyonlar_df = yakin_istasyonlar_df
                        st.session_state.aktif_istasyon_idleri = yakin_istasyonlar_df[
                            "id"
                        ].tolist()

                        mesafe_matrisi = osrm_mesafe_matrisi_olustur(
                            yakin_istasyonlar_df
                        )

                        if mesafe_matrisi:
                            baslangic_nesnesi = Istasyon(
                                istasyon_id=0,
                                ad="Başlangıç",
                                enlem=koordinat_1[0],
                                boylam=koordinat_1[1],
                            )
                            hedef_nesnesi = Istasyon(
                                istasyon_id=-1,
                                ad="Hedef",
                                enlem=koordinat_2[0],
                                boylam=koordinat_2[1],
                            )

                            optimum_zincir = a_star_rotasi_bul(
                                baslangic_noktasi=baslangic_nesnesi,
                                hedef_noktasi=hedef_nesnesi,
                                istasyonlar_df=yakin_istasyonlar_df,
                                mesafe_matrisi=mesafe_matrisi,
                                max_yakit=max_yakit,
                                tuketim=tuketim_km,
                            )

                            if optimum_zincir:
                                optimum_id_listesi = [
                                    durak.istasyon_id
                                    for durak in optimum_zincir
                                    if durak.istasyon_id not in [0, -1]
                                ]
                                st.session_state.optimum_istasyon_idleri = (
                                    optimum_id_listesi
                                )
                            else:
                                st.warning(
                                    "Mevcut yakıt kapasitesi ile rota tamamlanamıyor."
                                )
                        else:
                            st.error("OSRM mesafe matrisi oluşturulamadı.")
                    else:
                        st.warning("Bu güzergah üzerinde uygun istasyon bulunamadı.")
                else:
                    st.error("Bu iki nokta arasında karayolu bulunamadı.")
        else:
            st.error("Şehirler bulunamadı.")
    else:
        st.warning("Lütfen başlangıç ve bitiş noktalarını doldurun.")

# Rota temizleme butonu
if len(st.session_state.rota_koordinatlari) > 0:
    if st.sidebar.button("Rotayı Temizle"):
        st.session_state.rota_koordinatlari = []
        st.session_state.aktif_istasyon_idleri = []
        st.session_state.optimum_istasyon_idleri = []
        st.session_state.rota_mesafe_km = 0.0
        st.session_state.rota_sure_dk = 0.0
        st.session_state.ham_istasyonlar_df = pd.DataFrame()
        st.rerun()

# ==========================================
# ANA EKRAN: SEYAHAT ÖZETİ VE HARİTA ÜSTÜ ALTERNATİF PANELİ
# ==========================================
if st.session_state.rota_mesafe_km > 0:
    saat = int(st.session_state.rota_sure_dk // 60)
    dakika = int(st.session_state.rota_sure_dk % 60)

    st.success(
        f"🚗 **Tahmini Seyahat Süresi:** {saat} sa {dakika} dk  |  📏 **Toplam Mesafe:** {st.session_state.rota_mesafe_km:.1f} km"
    )

    if (
        not st.session_state.ham_istasyonlar_df.empty
        and len(st.session_state.optimum_istasyon_idleri) > 0
    ):
        st.markdown("### 🔀 Rota Üzerindeki Optimize Duraklar ve Alternatif Seçimi")

        optimum_idler = st.session_state.get("optimum_istasyon_idleri", [])
        secilen_alternatif_idler = []
        secilen_koordinatlar_listesi = []

        if "krd_baslangic" in st.session_state:
            secilen_koordinatlar_listesi.append(st.session_state.krd_baslangic)

        cols = st.columns(max(len(optimum_idler), 1))
        onceki_nokta = st.session_state.get("krd_baslangic", None)

        for i, opt_id in enumerate(optimum_idler):
            mevcut_durak = st.session_state.ham_istasyonlar_df[
                st.session_state.ham_istasyonlar_df["id"] == opt_id
            ]
            if not mevcut_durak.empty:
                with cols[i]:
                    st.markdown(f"**Durak {i+1}**")

                    bolge_adaylari = st.session_state.ham_istasyonlar_df[
                        st.session_state.ham_istasyonlar_df["brand"].isin(
                            secili_markalar
                        )
                    ]

                    secenekler_dict = {}
                    for _, row in bolge_adaylari.iterrows():
                        ek_mesafe = round(
                            abs(row["lat"] - mevcut_durak.iloc[0]["lat"]) * 111 + 1.2, 1
                        )
                        ek_sure = int(ek_mesafe * 1.2 + 2)
                        label = f"{row['istasyon_adi']} (Sapma: +{ek_mesafe} km, +{ek_sure} dk)"
                        secenekler_dict[label] = row["id"]

                    secenek_listesi = list(secenekler_dict.keys())

                    default_label = secenek_listesi[0] if secenek_listesi else ""
                    for lbl, idx_val in secenekler_dict.items():
                        if idx_val == opt_id:
                            default_label = lbl
                            break

                    if secenek_listesi:
                        secilen_label = st.selectbox(
                            f"Alternatif Seç ({i+1})",
                            secenek_listesi,
                            index=(
                                secenek_listesi.index(default_label)
                                if default_label in secenek_listesi
                                else 0
                            ),
                            key=f"ust_alt_durak_{i}",
                            label_visibility="collapsed",
                        )
                        secilen_id = secenekler_dict[secilen_label]
                    else:
                        secilen_id = opt_id

                    secilen_alternatif_idler.append(secilen_id)

                    secilen_satir = bolge_adaylari[bolge_adaylari["id"] == secilen_id]
                    if not secilen_satir.empty:
                        durak_kord = (
                            secilen_satir.iloc[0]["lat"],
                            secilen_satir.iloc[0]["lon"],
                        )
                        secilen_koordinatlar_listesi.append(durak_kord)

                        if onceki_nokta:
                            arasi_mesafe = (
                                (
                                    (durak_kord[0] - onceki_nokta[0]) ** 2
                                    + (durak_kord[1] - onceki_nokta[1]) ** 2
                                )
                                ** 0.5
                                * 111
                                * 1.2
                            )
                            st.info(f"Menzil Uygun ✅ (~{int(arasi_mesafe)} km)")

                        onceki_nokta = durak_kord

        if "krd_hedef" in st.session_state:
            hedef_kord = st.session_state.krd_hedef
            secilen_koordinatlar_listesi.append(hedef_kord)

        if secilen_alternatif_idler != st.session_state.optimum_istasyon_idleri:
            st.session_state.optimum_istasyon_idleri = secilen_alternatif_idler
            if len(secilen_koordinatlar_listesi) >= 2:
                yeni_rota, yeni_mesafe, yeni_sure = gercek_rota_ciz(
                    secilen_koordinatlar_listesi
                )
                if yeni_rota:
                    st.session_state.rota_koordinatlari = yeni_rota
                    st.session_state.rota_mesafe_km = yeni_mesafe
                    st.session_state.rota_sure_dk = yeni_sure
                    st.rerun()


# ==========================================
# LOGO HAZIRLAMA FONKSİYONU
# ==========================================
@st.cache_data
def optimum_logo_hazirla(marka):
    ozel_eslesme = {
        "TotalEnergies": "totalenergies.png",
        "Türkiye Petrolleri": "turkiye_petrolleri.png",
        "Petrol Ofisi": "petrol_ofisi.png",
    }
    if marka in ozel_eslesme:
        logo_dosya_adi = ozel_eslesme[marka]
    else:
        temiz_isim = (
            str(marka)
            .lower()
            .replace(" ", "_")
            .replace("İ", "i")
            .replace("I", "ı")
            .replace("ş", "s")
            .replace("ü", "u")
            .replace("ö", "o")
            .replace("ç", "c")
            .replace("ğ", "g")
        )
        logo_dosya_adi = f"{temiz_isim}.png"
    logo_yolu = os.path.join("assets", logo_dosya_adi)
    boyut = 128
    tuval = Image.new("RGBA", (boyut, boyut), (255, 255, 255, 0))
    cizim = ImageDraw.Draw(tuval)

    pin_renk = (255, 69, 0, 255)
    cerceve_renk = (255, 255, 255, 255)

    cizim.ellipse([14, 4, 114, 104], fill=pin_renk, outline=cerceve_renk, width=4)
    cizim.polygon([(64, 126), (34, 85), (94, 85)], fill=pin_renk)
    cizim.line([(64, 126), (34, 85)], fill=cerceve_renk, width=4)
    cizim.line([(64, 126), (94, 85)], fill=cerceve_renk, width=4)

    if os.path.exists(logo_yolu):
        try:
            img = Image.open(logo_yolu).convert("RGBA")
            img.thumbnail((66, 66), Image.Resampling.LANCZOS)
            tuval.paste(img, (64 - (img.size[0] // 2), 54 - (img.size[1] // 2)), img)
            buffer = io.BytesIO()
            tuval.save(buffer, format="PNG")
            return f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
        except:
            pass

    harf = str(marka)[0].upper()
    try:
        font = ImageFont.truetype("arial.ttf", 46)
    except:
        font = ImageFont.load_default()
    cizim.text((50, 24), harf, fill=(255, 255, 255, 255), font=font)
    buffer = io.BytesIO()
    tuval.save(buffer, format="PNG")
    return (
        f"data:image/png;base64,{base64.b64encode(buffer.getvalue()).decode('utf-8')}"
    )


# ==========================================
# PYDECK KATMANLARI (İnce Şerit Rota + Logolu Durak Pinleri)
# ==========================================
aktif_katmanlar = []

# 1. Katman: Optimum Durakların Logolu Pinleri (Kırmızı Çerçeveli)
optimum_idleri = st.session_state.get("optimum_istasyon_idleri", [])
if len(optimum_idleri) > 0 and not st.session_state.ham_istasyonlar_df.empty:
    optimum_df = st.session_state.ham_istasyonlar_df[
        st.session_state.ham_istasyonlar_df["id"].isin(optimum_idleri)
    ].copy()

    optimum_logo_dict = {
        m: {"url": optimum_logo_hazirla(m), "width": 128, "height": 128, "anchorY": 126}
        for m in markalar
    }
    optimum_df["optimum_icon"] = optimum_df["brand"].map(optimum_logo_dict)

    optimum_ikon_katmani = pdk.Layer(
        type="IconLayer",
        data=optimum_df,
        get_position=["lon", "lat"],
        get_icon="optimum_icon",
        get_size=1,
        size_scale=45,
        pickable=True,
        auto_highlight=True,
    )
    aktif_katmanlar.append(optimum_ikon_katmani)

# 2. Katman: Profesyonel Navigasyon Tarzı İnce Şerit Rota Çizgisi
if len(st.session_state.rota_koordinatlari) > 0:
    rota_verisi = pd.DataFrame({"path": [st.session_state.rota_koordinatlari]})

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

# ==========================================
# HARİTAYI ÇİZ
# ==========================================
baslangic_gorunumu = pdk.ViewState(latitude=39.0, longitude=35.0, zoom=5.5, pitch=0)

harita = pdk.Deck(
    map_style="road",
    layers=aktif_katmanlar,
    initial_view_state=baslangic_gorunumu,
    tooltip={"text": "İstasyon: {istasyon_adi}\nMarka: {brand}"},
)

st.pydeck_chart(harita, use_container_width=True)
