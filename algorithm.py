import heapq
from geopy.distance import geodesic


class Istasyon:
    def __init__(self, istasyon_id, ad, enlem, boylam):
        self.istasyon_id = istasyon_id
        self.ad = ad
        self.enlem = enlem
        self.boylam = boylam


class AracDurumu:
    def __init__(
        self, mevcut_istasyon, kalan_yakit, kat_edilen_mesafe, istasyon_zinciri
    ):
        self.mevcut_istasyon = mevcut_istasyon
        self.kalan_yakit = kalan_yakit
        self.kat_edilen_mesafe = kat_edilen_mesafe
        self.istasyon_zinciri = istasyon_zinciri

    # heapq modülünün sıralama yapabilmesi için
    def __lt__(self, diger):
        return self.kat_edilen_mesafe < diger.kat_edilen_mesafe


def kus_ucusu_mesafe(istasyon1, istasyon2):
    # Geopy ile offline (çevrimdışı) kuş uçuşu mesafe hesaplama
    return geodesic(
        (istasyon1.enlem, istasyon1.boylam), (istasyon2.enlem, istasyon2.boylam)
    ).km


def a_star_rotasi_bul(
    baslangic_noktasi, hedef_noktasi, istasyonlar_df, mesafe_matrisi, max_yakit, tuketim
):
    oncelikli_kuyruk = []
    ziyaret_edilenler = set()

    baslangic_durumu = AracDurumu(
        mevcut_istasyon=baslangic_noktasi,
        kalan_yakit=max_yakit,
        kat_edilen_mesafe=0,
        istasyon_zinciri=[baslangic_noktasi],
    )

    heapq.heappush(oncelikli_kuyruk, (0, baslangic_durumu))

    # Döngüde hızlı kullanmak için DataFrame'deki istasyonları bir listeye çeviriyoruz
    aday_istasyonlar = []
    for index, satir in istasyonlar_df.iterrows():
        aday_istasyonlar.append(
            Istasyon(satir["id"], satir["istasyon_adi"], satir["lat"], satir["lon"])
        )

    # Nihai hedefi de gidilecek bir durak olarak listeye ekliyoruz
    aday_istasyonlar.append(hedef_noktasi)

    while oncelikli_kuyruk:
        guncel_puan, guncel_durum = heapq.heappop(oncelikli_kuyruk)
        mevcut_ist = guncel_durum.mevcut_istasyon

        # Hedefe ulaştıysak mutlu son! Zinciri gönder
        if mevcut_ist.istasyon_id == hedef_noktasi.istasyon_id:
            return guncel_durum.istasyon_zinciri

        if mevcut_ist.istasyon_id in ziyaret_edilenler:
            continue

        ziyaret_edilenler.add(mevcut_ist.istasyon_id)

        # Etraftaki diğer istasyonları kontrol et
        for aday_ist in aday_istasyonlar:
            if (
                aday_ist.istasyon_id == mevcut_ist.istasyon_id
                or aday_ist.istasyon_id in ziyaret_edilenler
            ):
                continue

            # OSRM Matrisinden mesafeyi çek. Eğer matriste yoksa (Örn: Başlangıç noktası) kuş uçuşu kullan.
            if (
                mesafe_matrisi
                and (mevcut_ist.istasyon_id, aday_ist.istasyon_id) in mesafe_matrisi
            ):
                mesafe_km = (
                    mesafe_matrisi[(mevcut_ist.istasyon_id, aday_ist.istasyon_id)]
                    / 1000.0
                )
            else:
                mesafe_km = kus_ucusu_mesafe(mevcut_ist, aday_ist)

            harcanacak_yakit = mesafe_km * tuketim

            # YAKIT KONTROLÜ (Budama)
            if guncel_durum.kalan_yakit < harcanacak_yakit:
                continue

            yeni_zincir = list(guncel_durum.istasyon_zinciri)
            yeni_zincir.append(aday_ist)

            # Eğer vardığımız yer istasyonsa depoyu fulle, eğer son hedefse yakıt alma
            yeni_yakit = (
                guncel_durum.kalan_yakit - harcanacak_yakit
                if aday_ist.istasyon_id == hedef_noktasi.istasyon_id
                else max_yakit
            )

            yeni_durum = AracDurumu(
                mevcut_istasyon=aday_ist,
                kalan_yakit=yeni_yakit,
                kat_edilen_mesafe=guncel_durum.kat_edilen_mesafe + mesafe_km,
                istasyon_zinciri=yeni_zincir,
            )

            # f(n) = g(n) + h(n)
            g_puani = yeni_durum.kat_edilen_mesafe
            h_puani = kus_ucusu_mesafe(aday_ist, hedef_noktasi)
            f_puani = g_puani + h_puani

            heapq.heappush(oncelikli_kuyruk, (f_puani, yeni_durum))

    return None  # Hedefe ulaşılmazsa
