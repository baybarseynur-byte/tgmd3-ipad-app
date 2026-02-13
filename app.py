import streamlit as st
import pandas as pd
import numpy as np
import os
import hashlib
import tempfile
from datetime import date
from io import BytesIO
import matplotlib.pyplot as plt
from matplotlib import cm
from math import pi
from fpdf import FPDF

# =============================================================================
# 1. AYARLAR VE PROTOKOL
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO (Görsel Rapor)", layout="wide", page_icon="🧬")

DB_FILE = "tgmd3_database_pro.xlsx"

TGMD3_PROTOCOL = {
    "LOKOMOTOR": {
        "Koşu (Run)": ["1. Kol-bacak çapraz hareket-dirsekler bükülü", "2. Ayakların yerden kesilmesi", "3. Ayak ucuyla basma", "4. Havadaki ayak 90 derece bükülü"],
        "Galop (Gallop)": ["1. Kollar sıçramada bel hizasında bükülü", "2. Kısa süre iki ayak da havada", "3. Arka arkaya 4 galopta ritmi sürdürme", "4. İlk adımın yanına yada gerisine ikinci adım"],
        "Sek Sek (Hop)": ["1. Havadaki ayağın güç almak için salınımı", "2. Havadaki ayak vücuda yakın", "3. Kollar bükülü güç almak için salınım", "4. Arka arkaya 4 kez sıçrama-iniş (destek ayağı)", "5. Arka arkaya 3 kez sıçrama-iniş (diğer ayak)"],
        "Atlama (Skip)": ["1. İleriye doğru atlama yapan ayağın üzerine inme", "2. Kollar güç üretmek için bükülü ve bacaklarla çapraz durumda", "3. Hareketin birbirini takip eden dört tane ardışık tekrarını yapabilme"],
        "Durarak Uzun Atlama (H. Jump)": ["1. Harekete hazırlık için dizler bükülü ve kollar bükülü", "2. Atlama anında Kolları hızlı ve güçlü bir şekilde başın üstüne kaldırma", "3. İki ayakla sıçrama ve iniş", "4. Kollar iniş boyunca aşağı doğru itiş yapar"],
        "Kayma (Slide)": ["1. Beden yan dönerek gidiş yönünde", "2. Arkadan gelen ayak ilkinin yerine konur", "3. Sağa kaymada en az 4 adım", "4. Sola kaymada en az 4 adım"]
    },
    "NESNE_KONTROL": {
        "Topa Sopayla Vuruş (Bat)": ["1. Sopayı tutuşta baskın el üstte, diğeri altta", "2. Baskın olmayan taraf vuruş yönünde, ayaklar paralel duruş", "3. Salınım sırasında omuz ve kalça rotasyonu", "4. Ağırlığı gerideki ayaktan öndekine aktarma", "5. Topa vurma ve topun net bir şekilde ileriye gitmesi"],
        "Forehand Vuruş": ["1. Çocuğun top yerden gelirken geriye salınımı", "2. Baskın olmayan ayakla adım atma", "3. Topu duvara doğru vurma", "4. Topu yere bırakan omuza doğru raketin takibi"],
        "Top Sürme (Dribble)": ["1. Topun bel hizasında değmesi", "2. Topun parmak uçlarıyla itilmesi", "3. Hareket formunun bozmadan ard arda 4 kez topu sürme ve topu tutma"],
        "Yakalama (Catch)": ["1. Kollar önde ve bükülü hazırlanma", "2. Topa yetişmek için kolu uzatma", "3. Topu sadece ellerle yakalama"],
        "Ayakla Vuruş (Kick)": ["1. Topa hızlı yaklaşma", "2. Topa temas etmeden önce uzun bir adım ya da sıçrama", "3. Yerdeki ayak topun yanında ya da gerisinde", "4. Topa ayamın üst kısmıyla ya da ucuyla vurma"],
        "Top Fırlatma (Throw)": ["1. Hazırlık için el ve kollar aşağıda", "2. Kalça-omuz rotasyonu ile topu tutan kolun geri hareketi", "3. Ağırlık atış yapan kolun çaprazındaki ayakta", "4. Top elden çıkınca kolun çapraz yönde hareketi"],
        "Duvara Çarptırma (Rolling)": ["1. Topu tutan kolun gövde arkasına salınımı", "2. Atış anında topu tutan kolun çapraz ayağı önde", "3. Topun direk olarak duvara çarptırılması", "4. Topu atan elin atışı göğüs seviyesine kadar takip etmesi"],
    }
}

# =============================================================================
# 🔒 GÜVENLİK (ŞİFRE KONTROLÜ)
# =============================================================================
def sifre_kontrol():
    """Kullanıcı doğru şifreyi girene kadar uygulamayı durdurur."""
    
    if "sifre_dogru" not in st.session_state:
        st.session_state["sifre_dogru"] = False

    if st.session_state["sifre_dogru"]:
        return True

    st.markdown("## 🔒 Giriş Yapınız")
    st.info("Erişim için şifre gereklidir.")
    
    girilen_sifre = st.text_input("Şifre:", type="password")

    if st.button("Giriş Yap"):
        # Şifreyi st.secrets'tan veya hardcoded olarak kontrol et
        # Eğer secrets ayarlanmadıysa 'Sporcu2024' varsayılan olur (Test için)
        try:
            dogru_sifre = st.secrets["giris_sifresi"]
        except:
            dogru_sifre = "Sporcu2024" # Secrets dosyası yoksa yedek şifre

        if girilen_sifre == dogru_sifre:
            st.session_state["sifre_dogru"] = True
            st.rerun()
        else:
            st.error("Hatalı şifre! Lütfen tekrar deneyiniz.")
    
    return False

# Şifre kontrolünü çalıştır
if not sifre_kontrol():
    st.stop()

# =============================================================================
# 2. YARDIMCI FONKSİYONLAR
# =============================================================================

def yas_hesapla_ay(dogum_tarihi, test_tarihi):
    try:
        d1 = pd.to_datetime(dogum_tarihi)
        d2 = pd.to_datetime(test_tarihi)
        return int((d2.year - d1.year) * 12 + (d2.month - d1.month))
    except: return 0

def yas_araligi_bul(ay):
    baslangic = (ay // 3) * 3
    return f"{baslangic}-{baslangic+2} Ay"

def id_uret(ad, soyad, dogum, kaynak="LOC"):
    raw = f"{ad}{soyad}{dogum}".lower().replace(" ", "")
    hash_code = hashlib.md5(raw.encode()).hexdigest()[:8].upper()
    return f"{kaynak}_{hash_code}"

def z_skor_yorumla(z_score):
    if z_score is None or pd.isna(z_score): return "Yetersiz Veri"
    if z_score <= -2.0: return "Cok Zayif (Gecikme)"
    elif -2.0 < z_score <= -1.0: return "Zayif"
    elif -1.0 < z_score <= 1.0: return "Normal"
    elif 1.0 < z_score <= 2.0: return "Iyi"
    else: return "Ustun"

def tr_chars(text):
    return str(text).replace("ğ","g").replace("Ğ","G")\
                    .replace("ş","s").replace("Ş","S")\
                    .replace("ı","i").replace("İ","I")\
                    .replace("ü","u").replace("Ü","U")\
                    .replace("ö","o").replace("Ö","O")\
                    .replace("ç","c").replace("Ç","C")

def veritabani_yukle():
    if not os.path.exists(DB_FILE): return pd.DataFrame()
    try:
        df = pd.read_excel(DB_FILE)
        cols_to_str = ["OgrenciID", "TestTarihi"]
        for col in cols_to_str:
            if col in df.columns: df[col] = df[col].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

# -----------------------------------------------------------------------------
# 🔥 ÖNEMLİ GÜNCELLEME: VERİ BİRLEŞTİRME (MERGE) FONKSİYONU
# -----------------------------------------------------------------------------
def veritabani_kaydet(yeni_veriler_sozluk, ogrenci_id, test_tarihi):
    """
    Var olan kaydı bulur, sadece yeni girilen alanları günceller ve puanları yeniden hesaplar.
    """
    mevcut_df = veritabani_yukle()
    test_tarihi_str = str(test_tarihi)
    
    # Yeni veri için DataFrame oluştur
    mask = (mevcut_df["OgrenciID"] == ogrenci_id) & (mevcut_df["TestTarihi"] == test_tarihi_str)
    
    if mevcut_df.empty or not mask.any():
        # Yeni satır ekle
        yeni_df = pd.DataFrame([yeni_veriler_sozluk])
        son_df = pd.concat([mevcut_df, yeni_df], ignore_index=True)
    else:
        # Kayıt varsa: Mevcut satırı güncelle
        idx = mevcut_df[mask].index[0]
        
        # Yeni değerleri işle
        for key, value in yeni_veriler_sozluk.items():
            mevcut_df.at[idx, key] = value
            
        # --- OTOMATİK PUAN HESAPLAMA ---
        cols = mevcut_df.columns
        
        # Lokomotor Toplam
        loko_sum = 0
        for main_key in TGMD3_PROTOCOL["LOKOMOTOR"].keys():
            col_name = f"{main_key}_Toplam"
            if col_name in cols:
                loko_sum += pd.to_numeric(mevcut_df.at[idx, col_name], errors='coerce') or 0
        
        # Nesne Kontrol Toplam
        nesne_sum = 0
        for main_key in TGMD3_PROTOCOL["NESNE_KONTROL"].keys():
            col_name = f"{main_key}_Toplam"
            if col_name in cols:
                nesne_sum += pd.to_numeric(mevcut_df.at[idx, col_name], errors='coerce') or 0
        
        # Ana puanları güncelle
        mevcut_df.at[idx, "Lokomotor_Puan"] = loko_sum
        mevcut_df.at[idx, "Nesne_Puan"] = nesne_sum
        mevcut_df.at[idx, "Kaba_Motor_Puan"] = loko_sum + nesne_sum
        
        son_df = mevcut_df

    with pd.ExcelWriter(DB_FILE, engine="openpyxl") as w:
        son_df.to_excel(w, index=False)
    
    return son_df

# =============================================================================
# 3. PDF OLUŞTURMA
# =============================================================================
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'TGMD-3 GELISIMSEL TAKIP RAPORU', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

def create_full_report(ogrenci_bilgi, fig_radar, fig_line, gecmis_df, df_ana):
    pdf = PDFReport()
    
    # SAYFA 1: KAPAK ve GENEL GRAFİKLER
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, tr_chars(f"Öğrenci: {ogrenci_bilgi['Ad']} {ogrenci_bilgi['Soyad']}"), ln=True, align='C