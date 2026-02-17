import streamlit as st
import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import date
import tempfile

# =============================================================================
# 1. AYARLAR
# =============================================================================
st.set_page_config(page_title="TGMD-3 Rapor Sistemi", layout="wide", page_icon="📈")

# Dosya adını tamamen benzersiz yapıyoruz ki eski dosyalarla karışmasın
DB_FILE = "tgmd3_temiz_v2025.xlsx"

# TGMD-3 Protokolü ve Puanlama
MAX_PUANLAR = {
    # Lokomotor
    "Koşu": 8, "Galop": 8, "Sek Sek": 8, "Atlama": 6, "Uzun Atlama": 8, "Kayma": 8,
    # Nesne Kontrol
    "Sopa Vuruş": 10, "Forehand": 8, "Top Sürme": 6, "Yakalama": 6, "Ayak Vuruş": 8, "Fırlatma": 8, "Yuvarlama": 8
}

# =============================================================================
# 2. GÜVENLİ VERİTABANI İŞLEMLERİ (ÇÖKMEYEN YAPI)
# =============================================================================

def dosya_yukle():
    """Excel dosyasını yükler. Hata varsa boş tablo döner, asla çökmez."""
    if not os.path.exists(DB_FILE):
        return pd.DataFrame()
    
    try:
        df = pd.read_excel(DB_FILE)
        # Metin olması gerekenleri zorla metne çevir (NaN hatasını önler)
        for col in ["Ad", "Soyad", "Tarih", "ID"]:
            if col in df.columns:
                df[col] = df[col].astype(str).replace("nan", "").str.strip()
        
        # Sayı olması gerekenleri zorla sayıya çevir
        for col in df.columns:
            if "Puan" in col or col == "Toplam":
                df[col] = pd.to_numeric(df[col], errors='coerce').fillna(0)
        
        return df
    except Exception as e:
        st.error(f"Dosya okuma hatası oluştu ancak sistem çalışmaya devam ediyor. Hata: {e}")
        return pd.DataFrame() # Hata durumunda boş tablo dön

def kaydet(veri):
    """Veriyi Excel'e kaydeder."""
    try:
        df = dosya_yukle()
        yeni_df = pd.DataFrame([veri])
        
        if not df.empty:
            # Eski aynı kaydı temizle (Güncelleme mantığı)
            mask = (df["ID"] == str(veri["ID"])) & (df["Tarih"] == str(veri["Tarih"]))
            df = df[~mask]
            son_df = pd.concat([df, yeni_df], ignore_index=True)
        else:
            son_df = yeni_df
            
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as writer:
            son_df.to_excel(writer, index=False)
        return True
    except Exception as e:
        st.error(f"Kayıt sırasında hata: {e}")
        return False

# =============================================================================
# 3. GRAFİK (SÜTUN GRAFİĞİ)
# =============================================================================
def grafik_ciz(isim, puanlar):
    try:
        etiketler = list(MAX_PUANLAR.keys())
        max_degerler = list(MAX_PUANLAR.values())
        ogr_degerler = [puanlar.get(f"{k}_Puan", 0) for k in etiketler]

        fig, ax = plt.subplots(figsize=(10, 6))
        
        # Yatay çubuklar
        y_pos = np.arange(len(etiketler))
        
        # Gri Çubuk (Max Puan)
        ax.barh(y_pos, max_degerler, color='#ecf0f1', label='Maksimum Puan', height=0.7)
        
        # Mavi Çubuk (Öğrenci Puanı)
        ax.barh(y_pos, ogr_degerler, color='#3498db', label='Öğrenci Puanı', height=0.5)
        
        # Ayarlar
        ax.set_yticks(y_pos)
        ax.set_yticklabels(etiketler, fontsize=10, fontweight="bold")
        ax.invert_yaxis()
        ax.set_xlabel('Puan')
        ax.set_title(f"{isim} - Performans Grafiği", fontweight="bold")
        ax.legend()
        
        # Değerleri yaz
        for i, (v, m) in enumerate(zip(ogr_degerler, max_degerler)):
            ax.text(v + 0.1, i, f"{int(v)}/{m}", va='center', fontweight='bold', fontsize=9)
            
        # Çerçeve temizliği
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        plt.tight_layout()
        return fig
    except Exception as e:
        st.warning("Grafik oluşturulamadı.")
        return plt.figure()

# =============================================================================
# 4. PDF RAPOR
# =============================================================================
def pdf_olustur(bilgi, tablo_df, fig):
    try:
        pdf = FPDF()
        pdf.add_page()
        
        # Başlık
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "TGMD-3 GELISIM RAPORU", ln=True, align='C')
        pdf.ln(5)
        
        # Bilgi
        pdf.set_font("Arial", size=12)
        pdf.cell(0, 8, f"Ad Soyad: {bilgi['Ad']} {bilgi['Soyad']}", ln=True)
        pdf.cell(0, 8, f"Tarih: {bilgi['Tarih']}", ln=True)
        pdf.cell(0, 8, f"Toplam Puan: {bilgi['Toplam']}", ln=True)
        pdf.ln(5)
        
        # Tablo Başlık
        pdf.set_font("Arial", 'B', 10)
        pdf.cell(70, 8, "Alt Test", 1)
        pdf.cell(30, 8, "Puan", 1)
        pdf.cell(30, 8, "Maksimum", 1)
        pdf.cell(30, 8, "Basari %", 1)
        pdf.ln()
        
        # Tablo İçerik
        pdf.set_font("Arial", size=10)
        for _, row in tablo_df.iterrows():
            # Türkçe karakterleri basitçe değiştir
            test_adi = str(row['Alt Test']).replace("ş","s").replace("ğ","g").replace("ç","c").replace("ı","i").replace("ü","u").replace("ö","o")
            pdf.cell(70, 8, test_adi, 1)
            pdf.cell(30, 8, str(row['Puan']), 1)
            pdf.cell(30, 8, str(row['Max']), 1)
            pdf.cell(30, 8, f"%{row['Basari']}", 1)
            pdf.ln()
            
        # Grafik
        pdf.ln(10)
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            fig.savefig(tmp.name, bbox_inches='tight')
            pdf.image(tmp.name, x=10, w=190)
            
        return pdf.output(dest='S').encode('latin-1')
    except Exception as e:
        return None

# =============================================================================
# 5. ARAYÜZ (GİRİŞ VE RAPOR)
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["Test Girişi", "Gelişim Raporu"])

# ACİL DURUM BUTONU
st.sidebar.markdown("---")
if st.sidebar.button("⚠️ SİSTEMİ SIFIRLA"):
    if os.path.exists(DB_FILE):
        os.remove(DB_FILE)
        st.sidebar.success("Sistem temizlendi! Sayfayı yenileyin.")
        st.rerun()

if menu == "Test Girişi":
    st.header("📝 Veri Girişi")
    
    c1, c2, c3 = st.columns(3)
    ad = c1.text_input("Ad").upper()
    soyad = c2.text_input("Soyad").upper()
    tarih = c3.date_input("Tarih", date.today())
    
    # Giriş Alanları
    puanlar = {}
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Lokomotor")
        keys = list(MAX_PUANLAR.keys())[:6] # İlk 6 tanesi lokomotor
        for k in keys:
            puanlar[f"{k}_Puan"] = st.number_input(f"{k} (Max: {MAX_PUANLAR[k]})", 0, MAX_PUANLAR[k])
            
    with col2:
        st.subheader("Nesne Kontrol")
        keys = list(MAX_PUANLAR.keys())[6:] # Geri kalanı nesne
        for k in keys:
            puanlar[f"{k}_Puan"] = st.number_input(f"{k} (Max: {MAX_PUANLAR[k]})", 0, MAX_PUANLAR[k])
            
    if st.button("KAYDET", type="primary"):
        if ad and soyad:
            toplam = sum(puanlar.values())
            # Basit bir ID oluştur
            oid = f"{ad[:2]}{soyad[:2]}{str(tarih).replace('-','')}"
            
            veri = {
                "ID": oid, "Ad": ad, "Soyad": soyad, "Tarih": str(tarih),
                "Toplam": toplam
            }
            veri.update(puanlar)
            
            if kaydet(veri):
                st.success("✅ Başarıyla Kaydedildi!")
        else:
            st.warning("Ad ve Soyad zorunludur.")

elif menu == "Gelişim Raporu":
    st.header("📊 Öğrenci Raporu")
    
    df = dosya_yukle()
    
    if df.empty:
        st.info("Kayıtlı veri bulunamadı.")
    else:
        # Seçim Listesi (Güvenli oluşturma)
        df["Etiket"] = df.apply(lambda x: f"{x['Ad']} {x['Soyad']} ({x['Tarih']})", axis=1)
        secim = st.selectbox("Öğrenci Seçiniz:", df["Etiket"].unique())
        
        if secim:
            satir = df[df["Etiket"] == secim].iloc[0]
            
            # Tablo Verisi Hazırla
            tablo_data = []
            for test, mx in MAX_PUANLAR.items():
                p = satir.get(f"{test}_Puan", 0)
                yuzde = int((p/mx)*100) if mx > 0 else 0
                tablo_data.append({
                    "Alt Test": test, "Puan": int(p), "Max": mx, "Basari": yuzde
                })
            tablo_df = pd.DataFrame(tablo_data)
            
            # Görselleştirme
            c1, c2 = st.columns([1, 2])
            
            with c1:
                st.subheader("📋 Puan Tablosu")
                st.dataframe(tablo_df, hide_index=True, use_container_width=True)
                st.metric("Toplam Puan", int(satir["Toplam"]))
                
            with c2:
                st.subheader("📈 Performans Grafiği")
                fig = grafik_ciz(f"{satir['Ad']} {satir['Soyad']}", satir)
                st.pyplot(fig)
                
            # PDF İndir
            st.divider()
            bilgi = {"Ad": satir["Ad"], "Soyad": satir["Soyad"], "Tarih": satir["Tarih"], "Toplam": int(satir["Toplam"])}
            pdf_data = pdf_olustur(bilgi, tablo_df, fig)
            
            if pdf_data:
                st.download_button("📥 PDF İNDİR", pdf_data, "rapor.pdf", "application/pdf")
            else:
                st.error("PDF oluşturulurken bir hata oluştu.")
