import streamlit as st
import pandas as pd
import numpy as np
import os
import hashlib
import tempfile
from datetime import date
import matplotlib.pyplot as plt
from matplotlib import cm
from math import pi
from fpdf import FPDF

# =============================================================================
# 1. AYARLAR VE PROTOKOL
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO", layout="wide", page_icon="🧬")

# DOSYA ADINI DEĞİŞTİRDİK - ESKİ HATALI DOSYADAN KURTULMAK İÇİN
DB_FILE = "tgmd3_veritabani_v2.xlsx"

TGMD3_PROTOCOL = {
    "LOKOMOTOR": {
        "Koşu (Run)": ["1. Kol-bacak çapraz hareket", "2. Ayakların yerden kesilmesi", "3. Ayak ucuyla basma", "4. Havadaki ayak 90 derece bükülü"],
        "Galop (Gallop)": ["1. Kollar bükülü", "2. Kısa süre iki ayak havada", "3. Ritmik galop", "4. Adım takibi"],
        "Sek Sek (Hop)": ["1. Ayak salınımı", "2. Ayak vücuda yakın", "3. Kollar bükülü", "4. 4 kez sıçrama (destek)", "5. 3 kez sıçrama (diğer)"],
        "Atlama (Skip)": ["1. İniş dengesi", "2. Kollar çapraz", "3. 4 ardışık tekrar"],
        "Durarak Uzun Atlama (H. Jump)": ["1. Dizler bükülü hazırlık", "2. Kolları yukarı kaldırma", "3. Çift ayak iniş", "4. Kollar aşağı itiş"],
        "Kayma (Slide)": ["1. Yan dönme", "2. Ayak takibi", "3. Sağa 4 adım", "4. Sola 4 adım"]
    },
    "NESNE_KONTROL": {
        "Topa Sopayla Vuruş (Bat)": ["1. Tutuş", "2. Yan duruş", "3. Rotasyon", "4. Ağırlık aktarımı", "5. İsabetli vuruş"],
        "Forehand Vuruş": ["1. Geriye salınım", "2. Adım atma", "3. Duvara vuruş", "4. Raket takibi"],
        "Top Sürme (Dribble)": ["1. Bel hizası", "2. Parmak ucu", "3. 4 kez sürme"],
        "Yakalama (Catch)": ["1. Hazırlık", "2. Uzanma", "3. Sadece ellerle"],
        "Ayakla Vuruş (Kick)": ["1. Yaklaşma", "2. Uzun adım/sıçrama", "3. Destek ayağı konumu", "4. Ayak üstü vuruş"],
        "Top Fırlatma (Throw)": ["1. Hazırlık", "2. Rotasyon", "3. Ağırlık aktarımı", "4. Kol takibi"],
        "Duvara Çarptırma (Rolling)": ["1. Geriye salınım", "2. Çapraz ayak önde", "3. Duvara çarpma", "4. Kol takibi"],
    }
}

# Veritabanında olması gereken zorunlu sütunlar listesi
ZORUNLU_SUTUNLAR = [
    "OgrenciID", "TestTarihi", "Ad", "Soyad", "Cinsiyet", "DogumTarihi", 
    "Yas_Ay", "Yas_Grup_3Ay", 
    "Lokomotor_Puan", "Nesne_Puan", "Kaba_Motor_Puan"
]
# Test alt başlıkları için sütunları da ekleyelim
for ana_baslik in TGMD3_PROTOCOL:
    for test in TGMD3_PROTOCOL[ana_baslik]:
        ZORUNLU_SUTUNLAR.append(f"{test}_Toplam")

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

# --- KRİTİK DÜZELTME: SAĞLAM VERİTABANI YÜKLEME ---
def veritabani_yukle():
    """
    Excel dosyasını yükler. Dosya yoksa veya BOZUKSA (sütunlar eksikse),
    hata vermek yerine boş ve düzgün formatlı bir DataFrame döndürür.
    """
    # 1. Dosya hiç yoksa temiz bir tablo oluştur
    if not os.path.exists(DB_FILE):
        return pd.DataFrame(columns=ZORUNLU_SUTUNLAR)
    
    try:
        df = pd.read_excel(DB_FILE)
        
        # 2. Dosya var ama içi boşsa veya OgrenciID sütunu yoksa (BOZUKSA)
        if df.empty or "OgrenciID" not in df.columns:
            return pd.DataFrame(columns=ZORUNLU_SUTUNLAR)
            
        # 3. Veri tiplerini garantiye al (String hatasını önlemek için)
        df["OgrenciID"] = df["OgrenciID"].astype(str).str.strip()
        df["TestTarihi"] = df["TestTarihi"].astype(str).str.strip()
        
        # Eksik sütun varsa tamamla (pandas ile birleştirme hatası olmasın diye)
        for col in ZORUNLU_SUTUNLAR:
            if col not in df.columns:
                df[col] = 0
                
        return df
    except Exception as e:
        # Okuma sırasında ne hata olursa olsun, programın çökmemesi için boş dön
        return pd.DataFrame(columns=ZORUNLU_SUTUNLAR)

# --- KRİTİK DÜZELTME: SAĞLAM KAYDETME ---
def veritabani_kaydet(yeni_df_satir, ogrenci_id, test_tarihi):
    mevcut_df = veritabani_yukle()
    
    # Tipleri string yapıp temizle
    ogrenci_id = str(ogrenci_id).strip()
    test_tarihi = str(test_tarihi).strip()
    
    if not mevcut_df.empty:
        # Eski kaydı sil (güncelleme mantığı)
        # Sütunlar veritabani_yukle sayesinde kesinlikle var, KeyError VERMEZ.
        mask = ~((mevcut_df["OgrenciID"] == ogrenci_id) & (mevcut_df["TestTarihi"] == test_tarihi))
        mevcut_df = mevcut_df[mask]
        
    # Yeni satırı ekle
    son_df = pd.concat([mevcut_df, yeni_df_satir], ignore_index=True)
    
    # Dosyaya yaz
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
    pdf.add_page()
    pdf.set_font("Arial", 'B', 14)
    pdf.cell(0, 10, tr_chars(f"Öğrenci: {ogrenci_bilgi['Ad']} {ogrenci_bilgi['Soyad']}"), ln=True, align='C')
    
    # Grafikleri dosyaya kaydetip PDF'e ekle
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_radar, \
         tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_line:
        
        fig_radar.savefig(tmp_radar.name, format="png", bbox_inches='tight')
        fig_line.savefig(tmp_line.name, format="png", bbox_inches='tight')
        
        pdf.image(tmp_radar.name, x=60, y=50, w=90)
        pdf.image(tmp_line.name, x=30, y=150, w=150)
    
    try:
        os.remove(tmp_radar.name)
        os.remove(tmp_line.name)
    except: pass
    
    return pdf.output(dest='S').encode('latin-1')

# =============================================================================
# 4. ARAYÜZ
# =============================================================================
st.sidebar.markdown("### ⚠️ Acil Durum")
if st.sidebar.button("🗑️ Veritabanını Sıfırla (Hata Alırsan Bas)"):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        st.success("Veritabanı silindi! Temiz sayfa açıldı.")
        st.rerun()

menu = st.sidebar.radio("MENÜ", ["1. Test Girişi", "2. Veri Import", "3. Gelişimsel Rapor", "4. Araştırmacı Verisi"])
df_ana = veritabani_yukle()

# --- 1. TEST GİRİŞİ ---
if menu == "1. Test Girişi":
    st.header("📝 Test Giriş Ekranı")
    mod = st.radio("Kayıt Tipi:", ["Yeni Öğrenci", "Kayıtlı Öğrenci"], horizontal=True)
    d_ad, d_soyad, d_dt, d_cin = "", "", date(2018,1,1), "Kız"
    sabit_id = None
    
    if mod == "Kayıtlı Öğrenci" and not df_ana.empty:
        ozet = df_ana[["OgrenciID", "Ad", "Soyad"]].drop_duplicates("OgrenciID")
        ozet["Gosterim"] = ozet["Ad"] + " " + ozet["Soyad"] + " (" + ozet["OgrenciID"] + ")"
        secim = st.selectbox("Öğrenci Seç:", ozet["Gosterim"])
        if secim:
            sabit_id = secim.split("(")[-1].strip(")")
            row = df_ana[df_ana["OgrenciID"] == sabit_id].iloc[-1]
            d_ad, d_soyad = row["Ad"], row["Soyad"]
            try: d_dt = pd.to_datetime(row["DogumTarihi"]).date()
            except: pass
            d_cin = row["Cinsiyet"]

    with st.expander("Kimlik Bilgileri", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        ad = c1.text_input("Ad", d_ad).upper()
        soyad = c2.text_input("Soyad", d_soyad).upper()
        cin = c3.selectbox("Cinsiyet", ["Kız", "Erkek"], index=0 if d_cin=="Kız" else 1)
        dt = c4.date_input("Doğum Tarihi", d_dt)
        c5, c6, c7, c8 = st.columns(4)
        tt = c5.date_input("Test Tarihi", date.today())
        el = c6.selectbox("El", ["Sağ", "Sol"])
        ayak = c7.selectbox("Ayak", ["Sağ", "Sol"])
        yer = c8.text_input("Yer", "Spor Salonu")
        
        yas_ay = yas_hesapla_ay(dt, tt)
        final_id = sabit_id if sabit_id else id_uret(ad, soyad, str(dt))
        st.info(f"ID: {final_id} | Yaş: {yas_ay} Ay")

    if ad and soyad:
        with st.form("test_form"):
            ham = {}
            loko_top = nesne_top = 0
            st.info("A. LOKOMOTOR")
            for t_ad, kr in TGMD3_PROTOCOL["LOKOMOTOR"].items():
                with st.expander(t_ad):
                    sub = 0
                    for i, k in enumerate(kr):
                        st.write(k)
                        ca, cb = st.columns([1, 1])
                        d1 = ca.checkbox("D1", key=f"L_{t_ad}_{i}_1")
                        d2 = cb.checkbox("D2", key=f"L_{t_ad}_{i}_2")
                        p = int(d1)+int(d2)
                        sub += p
                        ham[f"{t_ad}_K{i+1}_D1"] = int(d1)
                        ham[f"{t_ad}_K{i+1}_D2"] = int(d2)
                        ham[f"{t_ad}_K{i+1}_Top"] = p
                    ham[f"{t_ad}_Toplam"] = sub
                    loko_top += sub
            
            st.warning("B. NESNE KONTROL")
            for t_ad, kr in TGMD3_PROTOCOL["NESNE_KONTROL"].items():
                with st.expander(t_ad):
                    sub = 0
                    for i, k in enumerate(kr):
                        st.write(k)
                        ca, cb = st.columns([1, 1])
                        d1 = ca.checkbox("D1", key=f"N_{t_ad}_{i}_1")
                        d2 = cb.checkbox("D2", key=f"N_{t_ad}_{i}_2")
                        p = int(d1)+int(d2)
                        sub += p
                        ham[f"{t_ad}_K{i+1}_D1"] = int(d1)
                        ham[f"{t_ad}_K{i+1}_D2"] = int(d2)
                        ham[f"{t_ad}_K{i+1}_Top"] = p
                    ham[f"{t_ad}_Toplam"] = sub
                    nesne_top += sub
            
            km_top = loko_top + nesne_top
            if st.form_submit_button("KAYDET"):
                kayit = {
                    "OgrenciID": str(final_id), "Ad": ad, "Soyad": soyad, "Cinsiyet": cin,
                    "DogumTarihi": str(dt), "TestTarihi": str(tt), "El": el, "Ayak": ayak, "Konum": yer,
                    "Yas_Ay": yas_ay, "Yas_Grup_3Ay": yas_araligi_bul(yas_ay), "Kaynak": "Local",
                    "Lokomotor_Puan": loko_top, "Nesne_Puan": nesne_top, "Kaba_Motor_Puan": km_top
                }
                kayit.update(ham)
                
                # DataFrame oluşturup kaydet (Tipleri düzgün tutmak için)
                yeni_df = pd.DataFrame([kayit])
                # Eksik sütunları 0 ile doldur
                for col in ZORUNLU_SUTUNLAR:
                    if col not in yeni_df.columns:
                        yeni_df[col] = 0
                        
                veritabani_kaydet(yeni_df, final_id, tt)
                st.success("✅ Veriler Başarıyla Kaydedildi!")

# --- 2. IMPORT ---
elif menu == "2. Veri Import":
    st.header("Excel Import")
    up = st.file_uploader("Dosya Seç", type=["xlsx"])
    if up:
        try:
            df = pd.read_excel(up)
            if {"Ad", "Soyad"}.issubset(df.columns):
                count = 0
                for _, r in df.iterrows():
                    ad, soy = str(r.get("Ad","-")).strip().upper(), str(r.get("Soyad","-")).strip().upper()
                    dt, tt = str(r.get("DogumTarihi", date.today())), str(r.get("TestTarihi", date.today()))
                    uid = id_uret(ad, soy, dt, "EXT")
                    d = r.to_dict()
                    d.update({"OgrenciID": uid, "Yas_Ay": yas_hesapla_ay(dt, tt)})
                    d["Yas_Grup_3Ay"] = yas_araligi_bul(d["Yas_Ay"])
                    
                    # Kayıt için DataFrame
                    temp_df = pd.DataFrame([d])
                    veritabani_kaydet(temp_df, uid, tt)
                    count += 1
                st.success(f"{count} Kayıt İçe Aktarıldı.")
        except Exception as e: st.error(f"Hata: {e}")

# --- 3. RAPOR ---
elif menu == "3. Gelişimsel Rapor":
    st.header("📊 Bireysel Gelişim ve Takip Raporu")
    df_ana = veritabani_yukle()
    
    if not df_ana.empty:
        ozet = df_ana[["OgrenciID", "Ad", "Soyad"]].drop_duplicates("OgrenciID")
        secenekler = [f"{r.Ad} {r.Soyad} ({r.OgrenciID})" for i,r in ozet.iterrows()]
        secim = st.selectbox("Öğrenci Seçiniz:", secenekler)
        
        if secim:
            sid = secim.split("(")[-1].strip(")")
            gecmis = df_ana[df_ana["OgrenciID"] == sid].sort_values("TestTarihi")
            ogr_info = df_ana[df_ana["OgrenciID"] == sid].iloc[-1]
            
            # GRAFİKLERİ HAZIRLA
            st.write(f"Toplam {len(gecmis)} test bulundu.")
            st.dataframe(gecmis[["TestTarihi", "Kaba_Motor_Puan", "Lokomotor_Puan", "Nesne_Puan"]])
            
            # Radar Grafik
            fig_radar, ax_radar = plt.subplots(figsize=(4, 4), subplot_kw=dict(polar=True))
            # (Basit radar çizimi)
            st.pyplot(fig_radar)

# --- 4. HAM VERİ ---
elif menu == "4. Araştırmacı Verisi":
    st.header("Ham Veri")
    df_ana = veritabani_yukle()
    if not df_ana.empty:
        st.dataframe(df_ana)
        with open(DB_FILE, "rb") as f:
            st.download_button("Excel İndir", f, file_name="tgmd3_tam_veri.xlsx")