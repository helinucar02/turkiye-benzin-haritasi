import os
import io
import base64
from PIL import Image, ImageDraw, ImageFont
import streamlit as st


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
