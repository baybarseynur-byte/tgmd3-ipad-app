import streamlit as st
import os
import sys

# =============================================================================
# 1. GÜVENLİ BAŞLANGIÇ (BEYAZ EKRANI ÖNLER)
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO", layout="wide", page_icon="✅")

# Kütüphane Kontrol Bloğu
try:
    import pandas as pd
    import numpy as np
    import matplotlib.pyplot as plt
    from fpdf import FPDF
    import hashlib
    import tempfile
    from datetime import date
except ImportError as e:
    st.error(f"⚠️ KRİTİK EKSİK: Sistemde şu kütüphane bulunamadı: {e.name}")
    st.info("Lütfen terminale şu komutu yazarak eksikleri yükleyin:")
    st.code("pip install pandas numpy matplotlib fpdf openpyxl", language="bash")
    st.stop() # Uygulamayı burada durdur ki çökmesin

# =============================================================================
# 2. AYARLAR
# =============================================================================
DB_FILE = "tgmd3_sistem_v4.xlsx"

# TGMD-3 Protokolü
TGMD3_PROTOCOL = {
    "LOKOMOTOR": {
        "Koşu": ["1. Kollar bükülü", "2. Ayaklar havada", "3. Ayak ucu basma", "4. Destek bacağı 90°"],
        "Galop": ["1. Kollar bükülü", "2. İki ayak havada", "3. Ritmik yapı", "4. Ayak takibi"],
        "Sek Sek": ["1. Salınım ayağı", "2. Salınım vücuda yakın", "3. Kollar bükülü", "4. 3 kez ardışık"],
        "Atlama": ["1. Ritmik adım", "2. Kollar çapraz", "3. İniş dengesi"],
        "Uzun Atlama": ["1. Hazırlık çökmesi", "2. Kollar yukarı", "3. Çift ayak iniş", "4. Denge"],
        "Kayma": ["1. Yan duruş", "2. Ayak takibi", "3. Ritmik kayma", "4. Yön değişimi"]
    },
    "NESNE_KONTROL": {
        "Sopa Vuruş": ["1. Tutuş", "2. Yan duruş", "3. Rotasyon", "4. İsabet", "5. Takip"],
        "Forehand": ["1. Geriye alma", "2. Adımlama", "3. Temas", "4. Raket takibi"],
        "Top Sürme": ["1. Bel hizası", "2. Parmak ucu", "3. Top kontrolü"],
        "Yakalama": ["1. Hazırlık", "2. Uzanma", "3. Elle kavrama"],
        "Ayak Vuruş": ["1. Yaklaşma", "2. Destek ayağı", "3. Vuruş", "4. Takip"],
        "Fırlatma": ["1. Geriye alma", "2. Zıt ayak", "3. Rotasyon", "4. Takip"],
        "Yuvarlama": ["1. Kol salınımı", "2. Diz bükme", "3. Zemin teması", "4. Takip"]
    }
}

MAX_PUANLAR = {}
for grup in TGMD3_PROTOCOL:
    for test, maddeler in TGMD3_PROTOCOL[grup].items():
        MAX_PUANLAR[test] = len(maddeler) * 2

# =============================================================================
# 3. FONKSİYONLAR
# =============================================================================
def veri_yukle():
    if not os.path.exists(DB_FILE): return pd.DataFrame()
    try:
        df = pd.read_excel(DB_FILE)
        # Veri temizliği (NaN hatası önleyici)
        for c in ["Ad", "Soyad", "ID"]:
            if c in df.columns: df[c] = df[c].astype(str).replace("nan", "")
        for c in df.columns:
            if "Puan" in c or c == "Toplam":
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except Exception as e:
        st.error(f"Veritabanı okuma hatası: {e}")
        return pd.DataFrame()

def veri_kaydet(yeni_veri):
    try:
        df = veri_yukle()
        yeni_df = pd.DataFrame([yeni_veri])
        
        if not df.empty:
            mask = (df["ID"] == yeni_veri["ID"]) & (df["Tarih"] == yeni_veri["Tarih"])
            df = df[~mask]
        
        son_df = pd.concat([df, yeni_df], ignore_index=True)
        
        with pd.ExcelWriter(DB_FILE, engine="openpyxl") as w:
            son_df.to_excel(w, index=False)
        return True
    except Exception as e:
        st.error(f"Kayıt hatası: {e}")
        return False

# GRAFİK ÇİZİCİ (Try-Except bloklu)
def grafik_ciz(isim, puanlar):
    try:
        labels = list(MAX_PUANLAR.keys())
        max_vals = list(MAX_PUANLAR.values())
        student_vals = [puanlar.get(f"{l}_Puan", 0) for l in labels]
        
        fig, ax = plt.subplots(figsize=(10, 8))
        y_pos = np.arange(len(labels))
        
        # Barlar
        ax.barh(y_pos, max_vals, color='#ecf0f1', label='Maksimum', height=0.7)
        colors = ['#e74c3c' if (s/m if m>0 else 0)<0.5 else '#2ecc71' for s,m in zip(student_vals, max_vals)]
        ax.barh(y_pos, student_vals, color=colors, label='Öğrenci', height=0.5)
        
        # Süsleme
        ax.set_yticks(y_pos)
        ax.set_yticklabels(labels, fontsize=10, fontweight="bold")
        ax.invert_yaxis()
        ax.set_title(f"{isim} - Gelişim Grafiği")
        
        # Etiketler
        for i, (s, m) in enumerate(zip(student_vals, max_vals)):
            ax.text(0.5, i, f"{int(s)} / {int(m)}", va='center', fontweight='bold')
            
        plt.tight_layout()
        return fig
    except Exception as e:
        st.warning(f"Grafik oluşturulamadı: {e}")
        return plt.figure()

# PDF ÇİZİCİ
def pdf_uret(bilgi, tablo_df, fig):
    try:
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 16)
        pdf.cell(0, 10, "TGMD-3 RAPORU", ln=True, align="C")
        pdf.ln(5)
        
        pdf.set_font("Arial", size=11)
        pdf.cell(0, 7, f"Ogrenci: {bilgi['Ad']} {bilgi['Soyad']}", ln=True)
        pdf.cell(0, 7, f"Tarih: {bilgi['Tarih']}", ln=True)
        pdf.cell(0, 7, f"Toplam: {bilgi['Toplam']}", ln=True)
        pdf.ln(5)
        
        # Tablo
        pdf.set_font("Arial", "B", 9)
        pdf.cell(60, 7, "Alt Test", 1)
        pdf.cell(30, 7, "Puan", 1)
        pdf.cell(30, 7, "Max", 1)
        pdf.cell(30, 7, "% Basari", 1)
        pdf.ln()
        
        pdf.set_font("Arial", size=9)
        for _, row in tablo_df.iterrows():
            ad = str(row['Alt Test']).replace("ş","s").replace("ç","c").replace("ğ","g").replace("ı","i").replace("ü","u").replace("ö","o")
            pdf.cell(60, 7, ad, 1)
            pdf.cell(30, 7, str(row['Puan']), 1)
            pdf.cell(30, 7, str(row['Max']), 1)
            pdf.cell(30, 7, f"%{row['Yuzde']}", 1)
            pdf.ln()
            
        # Grafik
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            fig.savefig(tmp.name, bbox_inches='tight')
            pdf.image(tmp.name, x=10, y=pdf.get_y()+10, w=180)
            
        return pdf.output(dest="S").encode("latin-1")
    except Exception as e:
        st.error(f"PDF Hatası: {e}")
        return b""

# =============================================================================
# 4. ARAYÜZ
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
st.sidebar.info("Eğer hata alırsanız 'Veritabanını Temizle' butonuna basın.")
if st.sidebar.button("⚠️ Veritabanını Temizle"):
    if os.path.exists(DB_FILE): os.remove(DB_FILE)
    st.rerun()

menu = st.sidebar.radio("MENÜ", ["Test Girişi", "Gelişim Raporu"])

if menu == "Test Girişi":
    st.header("📝 Veri Girişi")
    c1, c2, c3 = st.columns(3)
    ad = c1.text_input("Ad").upper()
    soyad = c2.text_input("Soyad").upper()
    tarih = c3.date_input("Tarih", date.today())
    
    if ad and soyad:
        puanlar = {}
        toplam = 0
        col1, col2 = st.columns(2)
        
        # Test döngüsü
        with col1:
            st.subheader("Lokomotor")
            for t, maddeler in TGMD3_PROTOCOL["LOKOMOTOR"].items():
                with st.expander(t):
                    sub = 0
                    for i, m in enumerate(maddeler):
                        st.write(m)
                        sub += int(st.checkbox("D1", key=f"L{t}{i}1")) + int(st.checkbox("D2", key=f"L{t}{i}2"))
                    puanlar[f"{t}_Puan"] = sub
                    toplam += sub
                    
        with col2:
            st.subheader("Nesne Kontrol")
            for t, maddeler in TGMD3_PROTOCOL["NESNE_KONTROL"].items():
                with st.expander(t):
                    sub = 0
                    for i, m in enumerate(maddeler):
                        st.write(m)
                        sub += int(st.checkbox("D1", key=f"N{t}{i}1")) + int(st.checkbox("D2", key=f"N{t}{i}2"))
                    puanlar[f"{t}_Puan"] = sub
                    toplam += sub
                    
        if st.button("KAYDET", type="primary"):
            oid = hashlib.md5(f"{ad}{soyad}".encode()).hexdigest()[:6]
            kayit = {"ID": oid, "Ad": ad, "Soyad": soyad, "Tarih": str(tarih), "Toplam": toplam}
            kayit.update(puanlar)
            if veri_kaydet(kayit):
                st.success("✅ Kayıt Başarılı!")

elif menu == "Gelişim Raporu":
    st.header("📊 Rapor Ekranı")
    df = veri_yukle()
    
    if not df.empty:
        df["Gosterim"] = df["Ad"] + " " + df["Soyad"] + " (" + df["Tarih"] + ")"
        secim = st.selectbox("Öğrenci Seç:", df["Gosterim"].unique())
        
        if secim:
            satir = df[df["Gosterim"] == secim].iloc[0]
            
            # Tablo verisi
            tdata = []
            for t, mx in MAX_PUANLAR.items():
                p = satir.get(f"{t}_Puan", 0)
                tdata.append({"Alt Test": t, "Puan": int(p), "Max": mx, "Yuzde": int((p/mx)*100)})
            tdf = pd.DataFrame(tdata)
            
            # Gösterim
            c1, c2 = st.columns([1, 2])
            c1.dataframe(tdf, hide_index=True)
            
            fig = grafik_ciz(f"{satir['Ad']} {satir['Soyad']}", satir)
            c2.pyplot(fig)
            
            # PDF
            pdf_data = pdf_uret({"Ad": satir["Ad"], "Soyad": satir["Soyad"], "Tarih": satir["Tarih"], "Toplam": satir["Toplam"]}, tdf, fig)
            if pdf_data:
                st.download_button("📥 PDF İndir", pdf_data, "rapor.pdf", "application/pdf")
    else:
        st.info("Kayıtlı veri yok.")
