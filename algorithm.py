import heapq
import math
import itertools  # Eşitlik bozucu sayaç için ekledik


def _kus_ucusu_mesafe(lat1, lon1, lat2, lon2):
    """Haversine formülü ile iki koordinat arası kuş uçuşu mesafeyi (km) hesaplar."""
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1))
        * math.cos(math.radians(lat2))
        * math.sin(dlon / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


def a_star_rotasi_bul(
    baslangic_koordinati,
    hedef_koordinati,
    istasyonlar_df,
    max_yakit,
    tuketim,
    esik_litre=3.0,
    min_durak_mesafesi=40.0,
):
    guvenli_menzil = (max_yakit - esik_litre) / tuketim
    ziyaret_edilenler = set()

    # EŞİTLİK BOZUCU SAYAÇ (Tie-breaker)
    sayac = itertools.count()

    baslangic_mesafe = _kus_ucusu_mesafe(
        baslangic_koordinati[0],
        baslangic_koordinati[1],
        hedef_koordinati[0],
        hedef_koordinati[1],
    )

    # Kuyruk: (f_skoru, g_maliyeti, SAYAÇ, mevcut_id, mevcut_duraklar_listesi)
    # next(sayac) her defasında benzersiz bir numara üretir
    kuyruk = [(baslangic_mesafe, 0, next(sayac), "start", [])]

    while kuyruk:
        # Kuyruktan veri çekerken sayacı (_) ile yoksayıyoruz çünkü sadece sıralama için lazımdı
        f_skor, g_maliyet, _, anlik_id, mevcut_duraklar = heapq.heappop(kuyruk)

        # Hedefe ulaştıysak hesaplamayı bitir
        if anlik_id == "end":
            return mevcut_duraklar

        if anlik_id in ziyaret_edilenler:
            continue
        ziyaret_edilenler.add(anlik_id)

        # Anlık konumu belirle
        if anlik_id == "start":
            anlik_lat, anlik_lon = baslangic_koordinati[0], baslangic_koordinati[1]
        else:
            anlik_lat, anlik_lon = (
                mevcut_duraklar[-1]["lat"],
                mevcut_duraklar[-1]["lon"],
            )

        # 1. İHTİMAL: Buradan doğrudan hedefe GÜVENLİ menzil yetiyor mu?
        hedefe_uzaklik = (
            _kus_ucusu_mesafe(
                anlik_lat, anlik_lon, hedef_koordinati[0], hedef_koordinati[1]
            )
            * 1.2
        )

        if hedefe_uzaklik <= guvenli_menzil:
            yeni_g = g_maliyet + hedefe_uzaklik
            heapq.heappush(
                kuyruk, (yeni_g, yeni_g, next(sayac), "end", mevcut_duraklar)
            )

        # 2. İHTİMAL: Hedefe yetmiyorsa, menzil içindeki diğer mantıklı istasyonlara zıpla
        for _, row in istasyonlar_df.iterrows():
            ist_id = row["id"]

            if ist_id in ziyaret_edilenler:
                continue

            mesafe = (
                _kus_ucusu_mesafe(anlik_lat, anlik_lon, row["lat"], row["lon"]) * 1.2
            )

            if min_durak_mesafesi <= mesafe <= guvenli_menzil:
                yeni_g = g_maliyet + mesafe
                h_skor = _kus_ucusu_mesafe(
                    row["lat"], row["lon"], hedef_koordinati[0], hedef_koordinati[1]
                )
                f_skor = yeni_g + h_skor

                yeni_durak = {
                    "id": ist_id,
                    "ad": row.get("istasyon_adi", "Bilinmeyen İstasyon"),
                    "lat": row["lat"],
                    "lon": row["lon"],
                    "marka": row.get("brand", "Bilinmiyor"),
                }

                # next(sayac) ile eşsiz numarayı ekliyoruz
                heapq.heappush(
                    kuyruk,
                    (
                        f_skor,
                        yeni_g,
                        next(sayac),
                        ist_id,
                        mevcut_duraklar + [yeni_durak],
                    ),
                )

    return None
