import streamlit as st
import pandas as pd
import numpy as np
import os
import hashlib
import tempfile
from datetime import date
import matplotlib.pyplot as plt
from fpdf import FPDF
import scipy.stats as stats

# =============================================================================
# 1. AYARLAR VE PROTOKOL (TEST MADDELERİ GERİ GELDİ)
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO", layout="wide", page_icon="🧬")

DB_FILE = "tgmd3_final_database_v9.xlsx"

# Test Protokolü (Maddeler Aynen Korundu)
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

# Maksimum Puanları Hesapla (Kriter Sayısı * 2)
MAX_PUANLAR = {}
for ana in TGMD3_PROTOCOL:
    for test, maddeler in TGMD3_PROTOCOL[ana].items():
        MAX_PUANLAR[test] = len(maddeler) * 2

# =============================================================================
# 2. VERİTABANI YÖNETİMİ (HATA DUZELTİCİ MOD)
# =============================================================================
def temizle_veri(val):
    """Veriyi güvenli stringe çevirir."""
    if pd.isna(val): return ""
    return str(val).strip()

def db_yukle():
    if not os.path.exists(DB_FILE): return pd.DataFrame()
    try:
        df = pd.read_excel(DB_FILE)
        # Metin alanlarını temizle (Hata kaynağını kurutuyoruz)
        for col in ["Ad", "Soyad", "OgrenciID", "TestTarihi", "Cinsiyet", "Yas_Grup_3Ay"]:
            if col in df.columns:
                df[col] = df[col].apply(temizle_veri)
        # Sayısal alanları temizle
        for col in df.columns:
            if "Puan" in col or "Toplam" in col:
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def db_kaydet(kayit):
    df = db_yukle()
    # ID ve Tarih eşleşmesi kontrolü
    if not df.empty:
        mask = (df["OgrenciID"] == str(kayit["OgrenciID"])) & (df["TestTarihi"] == str(kayit["TestTarihi"]))
        df = df[~mask]
    
    yeni = pd.DataFrame([kayit])
    son = pd.concat([df, yeni], ignore_index=True)
    
    with pd.ExcelWriter(DB_FILE, engine="openpyxl") as w:
        son.to_excel(w, index=False)
    return True

# =============================================================================
# 3. YENİ GRAFİK VE TABLO MOTORU (DÜZENLENEN KISIM)
# =============================================================================

def istatistik_hesapla(ogr_row, norm_df):
    """Öğrenci puanlarını analiz eder."""
    data = []
    tum_testler = list(MAX_PUANLAR.keys())
    
    for test in tum_testler:
        col = f"{test}_Toplam"
        puan = float(ogr_row.get(col, 0))
        maks = MAX_PUANLAR.get(test, 10)
        
        # Norm grubu
        ort, ss = 0, 1
        if not norm_df.empty and col in norm_df.columns:
            vals = pd.to_numeric(norm_df[col], errors='coerce').dropna()
            if len(vals) > 0:
                ort = vals.mean()
                ss = vals.std() if len(vals) > 1 else 1
                if ss == 0: ss = 1
        
        z = (puan - ort) / ss
        
        # Yorum
        if z <= -1: yorum = "Geliştirilmeli"
        elif z <= 1: yorum = "Normal"
        else: yorum = "İyi"
        
        data.append({
            "Alt Test": test.split("(")[0].strip(), # İsmi kısalt
            "Puan": int(puan),
            "Max": maks,
            "Ortalama": round(ort, 1),
            "SS": round(ss, 1),
            "Z-Skor": round(z, 2),
            "Yorum": yorum
        })
    return pd.DataFrame(data)

def grafik_ciz_bar(stats_df, ad_soyad):
    """
    Radar yerine sağlam ve anlaşılır YATAY SÜTUN grafiği.
    """
    try:
        df = stats_df.copy()
        
        fig, ax = plt.subplots(figsize=(10, 6))
        
        y_pos = np.arange(len(df))
        
        # 1. Gri Çubuklar (Maksimum Puan)
        ax.barh(y_pos, df["Max"], align='center', color='#e0e0e0', label='Maksimum Puan', height=0.6)
        
        # 2. Renkli Çubuklar (Öğrenci Puanı)
        ax.barh(y_pos, df["Puan"], align='center', color='#1f77b4', label='Öğrenci Puanı', height=0.4)
        
        # Ayarlar
        ax.set_yticks(y_pos)
        ax.set_yticklabels(df["Alt Test"], fontsize=10, fontweight='bold')
        ax.invert_yaxis()  # Yukarıdan aşağı sırala
        ax.set_xlabel('Puan')
        ax.set_title(f"{ad_soyad} - Beceri Performans Grafiği", fontweight='bold')
        ax.legend(loc='upper right')
        
        # Değerleri yaz
        for i, (p, m) in enumerate(zip(df["Puan"], df["Max"])):
            ax.text(p + 0.5, i, f"{int(p)} / {int(m)}", va='center', fontweight='bold', color='black')
            
        plt.tight_layout()
        return fig
    except:
        return plt.figure()

def grafik_ciz_normal(puan, ort, ss):
    """Normal dağılım eğrisi."""
    try:
        fig, ax = plt.subplots(figsize=(8, 3))
        x = np.linspace(ort - 3*ss, ort + 3*ss, 100)
        y = stats.norm.pdf(x, ort, ss)
        ax.plot(x, y, 'k')
        ax.fill_between(x, y, alpha=0.2, color='green')
        
        ax.axvline(puan, color='red', linestyle='--', linewidth=2)
        ax.text(puan, max(y)*1.05, f"Öğrenci\n{int(puan)}", color='red', ha='center', weight='bold')
        
        ax.set_yticks([])
        ax.set_title("Gelişimsel Konum (Çan Eğrisi)")
        return fig
    except:
        return plt.figure()

class PDF(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 14)
        self.cell(0, 10, 'TGMD-3 GELISIM RAPORU', 0, 1, 'C')
        self.ln(5)

def pdf_olustur(bilgi, tablo, fig1, fig2):
    pdf = PDF()
    pdf.add_page()
    
    # Başlık Bilgileri
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"Ad Soyad: {bilgi['Ad']} {bilgi['Soyad']}", ln=True)
    pdf.cell(0, 6, f"Tarih: {bilgi['Tarih']} | Yas Grubu: {bilgi['YasGrup']}", ln=True)
    pdf.ln(5)
    
    # Tablo
    pdf.set_font("Arial", 'B', 8)
    cols = [40, 20, 20, 20, 20, 20, 30]
    headers = ["Alt Test", "Puan", "Max", "Ort", "SS", "Z", "Yorum"]
    
    # Başlık Yaz
    for i, h in enumerate(headers):
        pdf.cell(cols[i], 6, h, 1, 0, 'C')
    pdf.ln()
    
    # Veri Yaz
    pdf.set_font("Arial", size=8)
    for _, row in tablo.iterrows():
        # Türkçe karakterleri temizle (basit replace)
        test_adi = row["Alt Test"].replace("ı","i").replace("ş","s").replace("ğ","g").replace("ç","c")
        yorum = row["Yorum"].replace("ı","i").replace("ş","s")
        
        pdf.cell(cols[0], 6, test_adi, 1)
        pdf.cell(cols[1], 6, str(row["Puan"]), 1, 0, 'C')
        pdf.cell(cols[2], 6, str(row["Max"]), 1, 0, 'C')
        pdf.cell(cols[3], 6, str(row["Ortalama"]), 1, 0, 'C')
        pdf.cell(cols[4], 6, str(row["SS"]), 1, 0, 'C')
        pdf.cell(cols[5], 6, str(row["Z-Skor"]), 1, 0, 'C')
        pdf.cell(cols[6], 6, yorum, 1, 0, 'C')
        pdf.ln()
    
    # Grafikler
    y = pdf.get_y() + 10
    
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f1:
        fig1.savefig(f1.name, bbox_inches='tight')
        pdf.image(f1.name, x=10, y=y, w=100)
        
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f2:
        fig2.savefig(f2.name, bbox_inches='tight')
        pdf.image(f2.name, x=115, y=y+10, w=80)
        
    return pdf.output(dest='S').encode('latin-1')

# =============================================================================
# 4. ARAYÜZ (VERİ GİRİŞİ DAHİL!)
# =============================================================================

st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Test Girişi", "2. Rapor Al"])
st.sidebar.info("Hata alırsanız alttaki butona basın.")
if st.sidebar.button("⚠️ VERİTABANINI TEMİZLE"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

df = db_yukle()

# --- 1. TEST GİRİŞİ (BU KISIM GERİ GELDİ) ---
if menu == "1. Test Girişi":
    st.header("📝 Test Giriş Ekranı")
    
    # Kimlik Bilgileri
    c1, c2, c3 = st.columns(3)
    ad = c1.text_input("Ad").upper()
    soyad = c2.text_input("Soyad").upper()
    dt = c3.date_input("Doğum Tarihi", date(2018,1,1))
    tt = st.date_input("Test Tarihi", date.today())
    cinsiyet = st.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)
    
    if ad and soyad:
        st.write("---")
        veriler = {}
        
        # LOKOMOTOR
        st.subheader("🏃 LOKOMOTOR BECERİLER")
        for test, maddeler in TGMD3_PROTOCOL["LOKOMOTOR"].items():
            with st.expander(test):
                toplam = 0
                for i, m in enumerate(maddeler):
                    col_a, col_b = st.columns([3, 1])
                    col_a.write(m)
                    # Checkboxlar
                    d1 = col_b.checkbox("D1", key=f"L_{test}_{i}_1")
                    d2 = col_b.checkbox("D2", key=f"L_{test}_{i}_2")
                    puan = int(d1) + int(d2)
                    toplam += puan
                # Toplamı kaydet
                veriler[f"{test}_Toplam"] = toplam

        # NESNE KONTROL
        st.subheader("🏀 NESNE KONTROL BECERİLERİ")
        for test, maddeler in TGMD3_PROTOCOL["NESNE_KONTROL"].items():
            with st.expander(test):
                toplam = 0
                for i, m in enumerate(maddeler):
                    col_a, col_b = st.columns([3, 1])
                    col_a.write(m)
                    d1 = col_b.checkbox("D1", key=f"N_{test}_{i}_1")
                    d2 = col_b.checkbox("D2", key=f"N_{test}_{i}_2")
                    puan = int(d1) + int(d2)
                    toplam += puan
                veriler[f"{test}_Toplam"] = toplam
        
        # KAYDET BUTONU
        if st.button("KAYDET", type="primary"):
            # ID ve Yaş Hesapla
            raw = f"{ad}{soyad}{dt}".replace(" ","").lower()
            oid = hashlib.md5(raw.encode()).hexdigest()[:8].upper()
            yas_ay = int((pd.to_datetime(tt) - pd.to_datetime(dt)).days / 30.44)
            yas_grp = f"{(yas_ay//3)*3}-{(yas_ay//3)*3+2} Ay"
            
            # Ana Puanları Hesapla
            loko_sum = sum([veriler[f"{t}_Toplam"] for t in TGMD3_PROTOCOL["LOKOMOTOR"]])
            nesne_sum = sum([veriler[f"{t}_Toplam"] for t in TGMD3_PROTOCOL["NESNE_KONTROL"]])
            
            kayit = {
                "OgrenciID": oid, "Ad": ad, "Soyad": soyad, "Cinsiyet": cinsiyet,
                "DogumTarihi": str(dt), "TestTarihi": str(tt),
                "Yas_Ay": yas_ay, "Yas_Grup_3Ay": yas_grp,
                "Lokomotor_Puan": loko_sum, "Nesne_Puan": nesne_sum,
                "Kaba_Motor_Puan": loko_sum + nesne_sum
            }
            kayit.update(veriler)
            
            if db_kaydet(kayit):
                st.success("✅ Veriler Başarıyla Kaydedildi!")
    else:
        st.warning("Lütfen Ad ve Soyad giriniz.")

# --- 2. RAPOR (SADECE BURASI DEĞİŞTİ) ---
elif menu == "2. Rapor Al":
    st.header("📊 Gelişim Raporu")
    
    if df.empty:
        st.info("Kayıt bulunamadı.")
    else:
        # Seçim
        df["Gosterim"] = df.apply(lambda x: f"{x['Ad']} {x['Soyad']} ({x['TestTarihi']})", axis=1)
        secim = st.selectbox("Öğrenci Seç:", df["Gosterim"].unique())
        
        if secim:
            satir = df[df["Gosterim"] == secim].iloc[0]
            
            # Norm grubu
            norm_df = df[
                (df["Cinsiyet"] == satir["Cinsiyet"]) & 
                (df["Yas_Grup_3Ay"] == satir["Yas_Grup_3Ay"])
            ]
            
            # İstatistikleri Hesapla
            stats_df = istatistik_hesapla(satir, norm_df)
            
            # 1. TABLO (İstediğiniz gibi)
            st.subheader("1. Puan Tablosu")
            st.dataframe(stats_df, use_container_width=True)
            
            # 2. YENİ GRAFİKLER (Radar yerine Bar ve Çan Eğrisi)
            col_g1, col_g2 = st.columns(2)
            
            with col_g1:
                st.markdown("**Alt Test Performansı**")
                fig1 = grafik_ciz_bar(stats_df, f"{satir['Ad']} {satir['Soyad']}")
                st.pyplot(fig1)
                
            with col_g2:
                st.markdown("**Sınıf İçi Konum**")
                # Toplam puan üzerinden çan eğrisi
                if not norm_df.empty:
                    ort = norm_df["Kaba_Motor_Puan"].mean()
                    ss = norm_df["Kaba_Motor_Puan"].std() if len(norm_df)>1 else 10
                else: ort, ss = 50, 10
                
                fig2 = grafik_ciz_normal(satir["Kaba_Motor_Puan"], ort, ss)
                st.pyplot(fig2)
            
            # Sonuç Cümlesi
            st.success(f"Sonuç: {satir['Ad']} {satir['Soyad']} adlı öğrencinin kaba motor beceri puanı {int(satir['Kaba_Motor_Puan'])} olarak tespit edilmiştir.")
            
            # PDF İndir
            bilgi = {"Ad": satir["Ad"], "Soyad": satir["Soyad"], "Tarih": satir["TestTarihi"], "YasGrup": satir["Yas_Grup_3Ay"]}
            pdf_byte = pdf_olustur(bilgi, stats_df, fig1, fig2)
            st.download_button("📥 PDF İNDİR", pdf_byte, "rapor.pdf", "application/pdf")
