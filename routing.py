import requests


def osrm_mesafe_matrisi_olustur(istasyonlar_df):
    """
    Supabase'den gelen istasyonların birbirleri arasındaki
    gerçek yol mesafelerini (metre cinsinden) hesaplar ve bir Sözlük (Dictionary) döndürür.
    """

    # 1. Koordinatları OSRM'nin istediği "boylam,enlem;boylam,enlem" formatına çeviriyoruz
    # Aynı zamanda hangi sıranın hangi istasyon_id'ye ait olduğunu kaydediyoruz
    koordinat_metni_listesi = []
    id_siralamasi = []

    for index, satir in istasyonlar_df.iterrows():
        koordinat_metni_listesi.append(f"{satir['lon']},{satir['lat']}")
        id_siralamasi.append(satir["id"])

    koordinat_string = ";".join(koordinat_metni_listesi)

    # 2. OSRM Table API'sine tek ve devasa bir istek atıyoruz
    # annotations=distance parametresi ile bize süre değil, "mesafe" (metre) vermesini istiyoruz
    url = f"http://router.project-osrm.org/table/v1/driving/{koordinat_string}?annotations=distance"

    cevap = requests.get(url)
    veri = cevap.json()

    mesafe_matrisi = {}

    # Eğer OSRM'den başarılı yanıt geldiyse tabloyu sözlüğe (Dictionary) çeviriyoruz
    if veri.get("code") == "Ok":
        osrm_mesafeler = veri["distances"]  # 2 boyutlu liste [45][45]

        istasyon_sayisi = len(id_siralamasi)

        # 3. İki boyutlu listeyi, süper hızlı okuyacağımız Dictionary (Hash Map) formatına dönüştürüyoruz
        for i in range(istasyon_sayisi):
            for j in range(istasyon_sayisi):
                kaynak_id = id_siralamasi[i]
                hedef_id = id_siralamasi[j]

                # Kendisinden kendisine olan mesafe 0'dır, matrise ekliyoruz
                mesafe_matrisi[(kaynak_id, hedef_id)] = osrm_mesafeler[i][j]

        return mesafe_matrisi
    else:
        return None  # Bir hata oluşursa None döndür
