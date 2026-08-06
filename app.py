import base64
import io
import os
import pandas as pd
from PIL import Image, ImageOps, ImageDraw, ImageFont
import pydeck as pdk
import streamlit as st
from supabase import create_client, Client
from geopy.geocoders import Nominatim
from database import rotaya_yakin_istasyonlari_cek
from routing import osrm_mesafe_matrisi_olustur
from algorithm import a_star_rotasi_bul
from services.api_service import koordinat_bul, gercek_rota_ciz
from components.visuals import optimum_logo_hazirla
from components.map_renderer import haritayi_ciz

# Sayfa genişliğini ve başlığını ayarlayalım
st.set_page_config(layout="wide")
st.title("Türkiye Akaryakıt & Şarj İstasyonları Haritası 📍")

# ==========================================
# STATE MANAGEMENT (DURUM YÖNETİMİ & HAFIZA)
# ==========================================

# --- 1. YENİ DİNAMİK MİMARİ (AGILE) DEĞİŞKENLERİ ---
if "arac_mevcut_yakit" not in st.session_state:
    st.session_state.arac_mevcut_yakit = 0.0
if "arac_mevcut_konum" not in st.session_state:
    st.session_state.arac_mevcut_konum = None
if "adim_sayaci" not in st.session_state:
    st.session_state.adim_sayaci = 0
if "onaylanan_duraklar" not in st.session_state:
    st.session_state.onaylanan_duraklar = []
if "nihai_rota_koordinatlari" not in st.session_state:
    st.session_state.nihai_rota_koordinatlari = []
if "koridor_istasyonlari_df" not in st.session_state:
    st.session_state.koridor_istasyonlari_df = None

# --- 2. GÖRSEL ARAYÜZ (UI) DEĞİŞKENLERİ (Aşağıdaki kodların çökmemesi için) ---
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

# 1. State'leri başlangıçta güvenle tanımlıyoruz
if "giris_baslangic" not in st.session_state:
    st.session_state.giris_baslangic = ""
if "giris_bitis" not in st.session_state:
    st.session_state.giris_bitis = ""


# 2. Takas işlemini gerçekleştirecek Callback Fonksiyonu
def sehirleri_degistir():
    gecici = st.session_state.giris_baslangic
    st.session_state.giris_baslangic = st.session_state.giris_bitis
    st.session_state.giris_bitis = gecici


col_b1, col_b2, col_b3 = st.sidebar.columns([5, 1, 5])
with col_b1:
    baslangic = st.text_input("Nereden", key="giris_baslangic")

with col_b2:
    st.markdown("<br>", unsafe_allow_html=True)
    # on_click parametresi ile callback fonksiyonunu bağlıyoruz.
    # Bu sayede Streamlit hata vermeden önce arkada takas gerçekleşir.
    st.button(
        "⇄", help="Başlangıç ve Bitiş Yerini Değiştir", on_click=sehirleri_degistir
    )

with col_b3:
    bitis = st.text_input("Nereye", key="giris_bitis")
st.sidebar.markdown("---")
st.sidebar.subheader("🚗 Araç ve Yakıt Bilgileri")

# ÖNCE DEĞİŞKENLERİ TANIMLIYORUZ
max_yakit = st.sidebar.number_input(
    "Aracın Maksimum Depo Hacmi (Litre)", min_value=10.0, max_value=120.0, value=50.0
)
tuketim_100km = st.sidebar.number_input(
    "Ortalama Tüketim (L/100km)", min_value=1.0, max_value=10.0, value=7.0
)
tuketim_km = tuketim_100km / 100.0
st.sidebar.markdown("---")
st.sidebar.subheader("⛽ Dinamik Yolculuk Ayarları")

# Slider yerine Number Input (Artan/Azalan Kutu) kullanıyoruz
baslangic_yakiti = st.sidebar.number_input(
    "Şu An Depoda Kalan Gerçek Yakıt (Litre)",
    min_value=1.0,
    max_value=float(max_yakit),
    value=float(max_yakit),
    step=5.0,
)

esik_litre = st.sidebar.number_input(
    "Güvenlik Eşiği (Depoda bırakılacak min. yakıt)",
    min_value=1.0,
    max_value=10.0,
    value=3.0,
    step=2.0,
    help="Araç bu litrenin altına düşmeden önce mutlaka istasyona yönlendirilir.",
)

st.sidebar.markdown("---")
st.sidebar.subheader("🤖 Planlama Modu")

planlama_modu = st.sidebar.radio(
    "Rota nasıl planlansın?",
    ("Kendim Seçeceğim (İnteraktif Adım Adım)", "Yapay Zeka Otomatik Planlasın"),
    help="Yapay zeka modu, menzil ve mesafe maliyetlerini hesaplayarak tüm durakları tek seferde bulur.",
)

rota_hesapla = st.sidebar.button("Yolculuğu Başlat")

if rota_hesapla:
    st.session_state.arac_mevcut_yakit = baslangic_yakiti
    st.session_state.onaylanan_duraklar = []

    st.spinner("Güzergah ve istasyon verileri analiz ediliyor...")

    # 1. Koordinatları Bul
    koordinat_1 = koordinat_bul(st.session_state.giris_baslangic)
    st.session_state.krd_baslangic = koordinat_1
    koordinat_2 = koordinat_bul(st.session_state.giris_bitis)
    st.session_state.krd_hedef = koordinat_2

    if koordinat_1 and koordinat_2:
        st.session_state.arac_mevcut_konum = koordinat_1

        # OSRM'den Ana Koridoru Çek
        ham_rota, ham_mesafe, ham_sure = gercek_rota_ciz([koordinat_1, koordinat_2])

        if ham_rota:
            # Koridor istasyonlarını Supabase'den çek
            st.session_state.koridor_istasyonlari_df = rotaya_yakin_istasyonlari_cek(
                supabase_client, ham_rota, tampon_metre=1500
            )

            kullanilabilir_menzil_km = (baslangic_yakiti - esik_litre) / tuketim_km

            # ==========================================
            # HİBRİT KARAR MEKANİZMASI (AI vs MANUEL)
            # ==========================================
            if planlama_modu == "Yapay Zeka Otomatik Planlasın":
                st.info(
                    "🤖 Yapay zeka tüm rota boyunca en optimal durakları hesaplıyor, lütfen bekleyin..."
                )

                # algorithm.py içindeki A* fonksiyonunu çağırıyoruz
                # (Fonksiyonunun parametrelerini kendi algorithm.py dosyandaki yapıya göre ayarlayabilirsin)
                optimal_duraklar = a_star_rotasi_bul(
                    koordinat_1,
                    koordinat_2,
                    st.session_state.koridor_istasyonlari_df,
                    baslangic_yakiti,
                    tuketim_km,
                )

                if optimal_duraklar:
                    st.session_state.onaylanan_duraklar = optimal_duraklar

                    # OSRM ile nihai AI rotasını tek seferde çiziyoruz
                    rota_zinciri = (
                        [koordinat_1]
                        + [(d["lat"], d["lon"]) for d in optimal_duraklar]
                        + [koordinat_2]
                    )
                    ai_rota, ai_mesafe, ai_sure = gercek_rota_ciz(rota_zinciri)

                    st.session_state.rota_koordinatlari = ai_rota
                    st.session_state.rota_mesafe_km = ai_mesafe
                    st.session_state.rota_sure_dk = ai_sure

                    # Adım sayacını 0'da bırakıyoruz ki interaktif menü çıkmasın, doğrudan harita yüklensin
                    st.session_state.adim_sayaci = 0
                    st.success(
                        "🎉 Yapay Zeka rotayı ve durakları kusursuz şekilde planladı!"
                    )
                else:
                    st.error(
                        "Algoritma bu yakıt menziliyle hedefe ulaşacak kesintisiz bir istasyon zinciri bulamadı."
                    )

            else:
                # Kullanıcının kendisinin seçeceği İnteraktif Mod
                st.session_state.adim_sayaci = 1
                st.success(
                    "Koridor verileri çekildi! Lütfen haritanın altından ilk durağınızı seçin."
                )
        else:
            st.error("Rota çizimi alınamadı.")
    else:
        st.error("Girilen şehirlerin koordinatları bulunamadı.")

# Rota temizleme butonu
if (
    len(st.session_state.rota_koordinatlari) > 0
    or len(st.session_state.onaylanan_duraklar) > 0
):
    if st.sidebar.button("Rotayı Temizle"):
        st.session_state.rota_koordinatlari = []
        st.session_state.aktif_istasyon_idleri = []
        st.session_state.optimum_istasyon_idleri = []
        st.session_state.onaylanan_duraklar = (
            []
        )  # <-- İkonların kalmasını önleyen temizlik!
        st.session_state.adim_sayaci = 0  # <-- Interaktif döngüyü de sıfırlar
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

                    uygun_adaylar = []
                    for _, row in bolge_adaylari.iterrows():
                        aday_kord = (row["lat"], row["lon"])
                        if onceki_nokta:
                            mesafe_hesap = (
                                (
                                    (aday_kord[0] - onceki_nokta[0]) ** 2
                                    + (aday_kord[1] - onceki_nokta[1]) ** 2
                                )
                                ** 0.5
                                * 111
                                * 1.2
                            )
                            if mesafe_hesap <= kullanilabilir_menzil_km:
                                uygun_adaylar.append(row)

                    if not uygun_adaylar:
                        uygun_adaylar = [row for _, row in bolge_adaylari.iterrows()]

                    secenekler_dict = {}
                    for row in uygun_adaylar:
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
haritayi_ciz(st.session_state.rota_koordinatlari, st.session_state.onaylanan_duraklar)
# ==========================================
# ETKİLEŞİMLİ DURAK SEÇİM ARAYÜZÜ (STATE 1 ve Sonrası)
# ==========================================

if st.session_state.adim_sayaci > 0:
    st.markdown("---")

    # 1. EĞER GEÇMİŞTE DURAKLAR ONAYLANDDIYSA, BİR "YOLCULUK GÜNLÜĞÜ" (LOG TABLOSU) GÖSTERELİM
    if st.session_state.onaylanan_duraklar:
        st.markdown("#### 📋 Geçmiş Durak ve İkmal Geçmişiniz")
        log_verisi = []
        for idx, durak in enumerate(st.session_state.onaylanan_duraklar, 1):
            log_verisi.append(
                {
                    "Adım": f"Durak {idx}",
                    "İstasyon Adı": durak["ad"],
                    "Marka": durak.get("marka", "Bilinmiyor"),
                    "Uzaklık (km)": int(durak["mesafe"]),
                    "Alınan Yakıt (L)": durak.get("alinan_yakit", 0.0),
                    "Ayrılış Yakıtı": f"{durak.get('ayrilis_yakiti', 0.0):.1f} L",  # İstasyondan çıkarkenki yakıt
                }
            )
        st.table(log_verisi)
        st.markdown("---")

    st.subheader(f"📍 {st.session_state.adim_sayaci}. Durak Seçimi ve Yakıt İkmali")

    # 2. Dinamik Güvenli Menzil Hesabı
    mevcut_yakit = st.session_state.arac_mevcut_yakit
    kullanilabilir_yakit = mevcut_yakit - esik_litre

    # Hedef koordinatını hafızadan veya fonksiyondan alalım
    hedef_konum = (
        koordinat_bul(bitis)
        if "bitis" in locals() and bitis
        else koordinat_bul("İstanbul")
    )
    mevcut_konum = st.session_state.arac_mevcut_konum

    from geopy.distance import geodesic

    # Mevcut konumdan hedefe kalan toplam mesafe (km)
    mevcut_hedef_mesafe = geodesic(mevcut_konum, hedef_konum).km * 1.2

    if kullanilabilir_yakit <= 0:
        st.error("Mevcut yakıtınız güvenlik eşiğinin altında! Yola devam edilemez.")
    else:
        guvenli_menzil_km = kullanilabilir_yakit / tuketim_km
        st.info(
            f"Mevcut Yakıtla Güvenli Gidilebilecek Maksimum Mesafe: **{int(guvenli_menzil_km)} km** | Hedefe Kalan Yol: **{int(mevcut_hedef_mesafe)} km**"
        )

        # KRİTİK KONTROL: Eğer güvenli menzil, hedefe kalan yoldan büyükse durmaya gerek yok!
        if guvenli_menzil_km >= mevcut_hedef_mesafe:
            st.success(
                "🎉 Harika haber! Mevcut yakıtınız ve menziliniz Hedefe tek başına ulaşmaya fazlasıyla yetiyor. Ek bir durağa ihtiyacınız yok!"
            )

        else:
            # Menzil yetmiyorsa, sadece hedefe doğru olan ve menzil içindeki istasyonları filtrele
            adaylar = []
            for index, row in st.session_state.koridor_istasyonlari_df.iterrows():
                istasyon_konum = (row["lat"], row["lon"])

                mesafe_duraga = geodesic(mevcut_konum, istasyon_konum).km * 1.2
                mesafe_istasyondan_hedefe = (
                    geodesic(istasyon_konum, hedef_konum).km * 1.2
                )

                # Sıkı Filtreleme: Menzil içinde olacak, 10 km'den uzak olacak ve HEDEFE YAKLAŞTiracak
                if (
                    10 < mesafe_duraga <= guvenli_menzil_km
                    and mesafe_istasyondan_hedefe < mevcut_hedef_mesafe
                ):
                    adaylar.append(
                        {
                            "id": row["id"],
                            "ad": row["istasyon_adi"],
                            "marka": row["brand"],
                            "mesafe": mesafe_duraga,
                            "lat": row["lat"],
                            "lon": row["lon"],
                        }
                    )

            if adaylar:
                adaylar = sorted(adaylar, key=lambda x: x["mesafe"], reverse=True)
                secenekler = {
                    f"{a['ad']} - {a['marka']} (~{int(a['mesafe'])} km ileride)": a
                    for a in adaylar
                }

                secilen_etiket = st.selectbox(
                    "Bu menzil içindeki ideal duraklardan birini seçin:",
                    list(secenekler.keys()),
                )
                secilen_istasyon = secenekler[secilen_etiket]

                tahmini_kalan_yakit = mevcut_yakit - (
                    secilen_istasyon["mesafe"] * tuketim_km
                )
                maksimum_alinabilecek = float(max_yakit - tahmini_kalan_yakit)
                if maksimum_alinabilecek < 0:
                    maksimum_alinabilecek = 0.0

                st.markdown("##### ⛽ İkmal Detayları")
                alinan_yakit = st.number_input(
                    "Bu istasyonda kaç litre yakıt alacaksınız?",
                    min_value=0.0,
                    max_value=max(5.0, maksimum_alinabilecek),
                    value=maksimum_alinabilecek,
                )

                if st.button("Durağı Onayla ve Sonraki Adıma Geç"):
                    secilen_istasyon["alinan_alinan"] = (
                        alinan_yakit if "alinan_yakit" in locals() else alinan_yakit
                    )
                    secilen_istasyon["alinan_yakit"] = alinan_yakit
                    harcanan_yakit = secilen_istasyon["mesafe"] * tuketim_km
                    varis_yakiti = mevcut_yakit - harcanan_yakit
                    yeni_yakit = varis_yakiti + alinan_yakit
                    if yeni_yakit > max_yakit:
                        yeni_yakit = max_yakit

                    secilen_istasyon["varis_yakiti"] = varis_yakiti
                    secilen_istasyon["ayrilis_yakiti"] = yeni_yakit

                    st.session_state.onaylanan_duraklar.append(secilen_istasyon)
                    st.session_state.arac_mevcut_konum = (
                        secilen_istasyon["lat"],
                        secilen_istasyon["lon"],
                    )
                    st.session_state.arac_mevcut_yakit = yeni_yakit
                    st.session_state.adim_sayaci += 1
                    st.rerun()
            else:
                st.warning(
                    "Menziliniz içinde hedefe doğru uygun istasyon kalmadı. Doğrudan hedefe ulaşabilirsiniz!"
                )
                # Ortak Yolculuk Tamamlama Fonksiyonu veya Bloğu
if st.button("🏁 Yolculuğu Tamamla ve Rotayı Onayla", key="ortak_bitir_butonu"):
    # 1. Koordinat zincirini oluşturuyoruz: Başlangıç -> Duraklar -> Hedef
    rota_zinciri = [st.session_state.krd_baslangic]

    for durak in st.session_state.onaylanan_duraklar:
        rota_zinciri.append((durak["lat"], durak["lon"]))

    rota_zinciri.append(st.session_state.krd_hedef)

    # 2. OSRM motoruna tüm zinciri gönderip tek parça kusursuz mavi rotayı alıyoruz
    with st.spinner("Tüm durakları içeren nihai rota harita için çiziliyor..."):
        nihai_cizgi, toplam_mesafe, toplam_sure = gercek_rota_ciz(rota_zinciri)

        if nihai_cizgi:
            # Haritanın okuyacağı state değişkenlerine mühürlüyoruz
            st.session_state.rota_koordinatlari = nihai_cizgi
            st.session_state.rota_mesafe_km = toplam_mesafe
            st.session_state.rota_sure_dk = toplam_sure

            # Seçilen durakların ID'lerini haritada pin olarak göstermek için kaydediyoruz
            st.session_state.optimum_istasyon_idleri = [
                d["id"] for d in st.session_state.onaylanan_duraklar
            ]

            # Döngüyü başa sar ve interaktif modu kapatıp harita gösterimine geç
            st.session_state.adim_sayaci = 0
            st.success("Rota başarıyla oluşturuldu ve haritaya işlendi!")
            st.rerun()
        else:
            st.error("Nihai rota OSRM üzerinden çizilemedi.")
