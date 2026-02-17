import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import hashlib
from datetime import date
import matplotlib.pyplot as plt
from fpdf import FPDF

# =============================================================================
# 1. AYARLAR VE PROTOKOL
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO: Güvenli Kayıt", layout="wide", page_icon="🛡️")

FILE_NAME = "tgmd3_secure_db.xlsx"

# PROTOKOL (Dokunulmaz)
PROTOCOL = {
    "LOKOMOTOR": {
        "Koşu": ["1. Kol-bacak çapraz hareket", "2. Ayakların yerden kesilmesi", "3. Ayak ucuyla basma", "4. Havadaki ayak 90 derece bükülü"],
        "Galop": ["1. Kollar bükülü", "2. Kısa süre iki ayak havada", "3. Ritmik galop", "4. Adım takibi"],
        "Sek Sek": ["1. Ayak salınımı", "2. Ayak vücuda yakın", "3. Kollar bükülü", "4. 4 kez sıçrama (destek)", "5. 3 kez sıçrama (diğer)"],
        "Atlama": ["1. İniş dengesi", "2. Kollar çapraz", "3. 4 ardışık tekrar"],
        "Uzun Atlama": ["1. Dizler bükülü hazırlık", "2. Kolları yukarı kaldırma", "3. Çift ayak iniş", "4. Kollar aşağı itiş"],
        "Kayma": ["1. Yan dönme", "2. Ayak takibi", "3. Sağa 4 adım", "4. Sola 4 adım"]
    },
    "NESNE_KONTROL": {
        "Sopa Vuruş": ["1. Tutuş", "2. Yan duruş", "3. Rotasyon", "4. Ağırlık aktarımı", "5. İsabetli vuruş"],
        "Forehand": ["1. Geriye salınım", "2. Adım atma", "3. Duvara vuruş", "4. Raket takibi"],
        "Top Sürme": ["1. Bel hizası", "2. Parmak ucu", "3. 4 kez sürme"],
        "Yakalama": ["1. Hazırlık", "2. Uzanma", "3. Sadece ellerle"],
        "Ayak Vuruş": ["1. Yaklaşma", "2. Uzun adım/sıçrama", "3. Destek ayağı konumu", "4. Ayak üstü vuruş"],
        "Fırlatma": ["1. Hazırlık", "2. Rotasyon", "3. Ağırlık aktarımı", "4. Kol takibi"],
        "Yuvarlama": ["1. Geriye salınım", "2. Çapraz ayak önde", "3. Duvara çarpma", "4. Kol takibi"]
    }
}

# Max Puanlar ve Sütun Listesi
MAX_SCORES = {}
ALL_COLUMNS = ['ID', 'Ad', 'Soyad', 'Cinsiyet', 'DogumTarihi', 'YasGrubu', 'SonIslemTarihi']

# Her madde için ayrı sütun oluşturuyoruz ki veri kaybı olmasın (Granüler Kayıt)
ITEM_COLUMNS = [] 

for domain in PROTOCOL:
    for test, items in PROTOCOL[domain].items():
        MAX_SCORES[test] = len(items) * 2
        ALL_COLUMNS.append(f"{test}_Toplam")
        # Madde bazlı sütunlar (Örn: L_Koşu_0, L_Koşu_1...)
        prefix = "L" if domain == "LOKOMOTOR" else "N"
        for i in range(len(items)):
            ITEM_COLUMNS.append(f"{prefix}_{test}_{i}")

FULL_DB_COLUMNS = ALL_COLUMNS + ITEM_COLUMNS

# =============================================================================
# 2. VERİTABANI MOTORU
# =============================================================================
def generate_universal_id(ad, soyad, dogum_tarihi):
    """Ad+Soyad+DT -> Benzersiz ID"""
    raw_str = f"{ad.strip().upper()}{soyad.strip().upper()}{str(dogum_tarihi)}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()[:12]

def load_db():
    if not os.path.exists(FILE_NAME):
        return pd.DataFrame(columns=FULL_DB_COLUMNS)
    try:
        df = pd.read_excel(FILE_NAME)
        # Eksik sütunları tamamla
        for col in FULL_DB_COLUMNS:
            if col not in df.columns:
                df[col] = 0 if col in ITEM_COLUMNS or "Toplam" in col else ""
        
        # Tipleri düzelt
        str_cols = ['ID', 'Ad', 'Soyad', 'Cinsiyet', 'YasGrubu']
        for c in str_cols:
            if c in df.columns: df[c] = df[c].astype(str).replace("nan", "")
            
        return df
    except:
        return pd.DataFrame(columns=FULL_DB_COLUMNS)

def save_to_db(data_dict):
    """Var olan kaydı bulur, sadece değişenleri günceller."""
    df = load_db()
    student_id = data_dict["ID"]
    
    if not df.empty and student_id in df["ID"].values:
        # GÜNCELLEME MODU
        idx = df[df["ID"] == student_id].index[0]
        for key, val in data_dict.items():
            df.at[idx, key] = val
    else:
        # YENİ KAYIT MODU
        new_row = pd.DataFrame([data_dict])
        df = pd.concat([df, new_row], ignore_index=True)
    
    # NaN temizliği
    df = df.fillna(0)
    
    with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return True

def calculate_age_group(birth_date):
    today = date.today()
    if isinstance(birth_date, str):
        b_date = pd.to_datetime(birth_date).date()
    else:
        b_date = birth_date
        
    diff_days = (today - b_date).days
    age_months = int(diff_days / 30.44)
    quarter = (age_months // 3) * 3
    return f"{quarter}-{quarter+2} Ay"

# =============================================================================
# 3. İSTATİSTİK
# =============================================================================
def get_stats(student_row, full_df):
    group_df = full_df[
        (full_df['Cinsiyet'] == student_row['Cinsiyet']) & 
        (full_df['YasGrubu'] == student_row['YasGrubu'])
    ]
    
    results = []
    for test, max_score in MAX_SCORES.items():
        col = f"{test}_Toplam"
        puan = float(student_row.get(col, 0))
        
        if len(group_df) > 1:
            ort = group_df[col].mean()
            ss = group_df[col].std(ddof=1)
            z = (puan - ort) / ss if ss > 0 else 0
        else:
            ort, ss, z = puan, 0, 0
            
        if z >= 1: yorum = "İleri"
        elif z <= -1: yorum = "Geliştirilmeli"
        else: yorum = "Normal"
        if len(group_df) < 2: yorum = "Veri Yetersiz"
        
        results.append({
            "Alt Test": test, "Puan": puan, "Max": max_score,
            "Ort": round(ort,2), "SS": round(ss,2), "Z": round(z,2), "Durum": yorum
        })
    return pd.DataFrame(results)

# =============================================================================
# 4. ARAYÜZ
# =============================================================================
st.sidebar.title("TGMD-3 Kontrol")
menu = st.sidebar.radio("Menü", ["Veri Girişi", "Gelişim Raporu", "Excel İndir"])

if menu == "Veri Girişi":
    st.header("📝 Güvenli Veri Girişi")
    st.info("Sistem, öğrenciyi tanıdığında eski puanlarını otomatik yükler. Veri kaybı yaşanmaz.")
    
    # 1. KİMLİK BİLGİLERİ
    with st.container():
        c1, c2, c3, c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper()
        soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("Doğum Tarihi", date(2018, 1, 1))
        cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)
    
    # 2. VERİTABANI KONTROLÜ (OTOMATİK)
    active_id = None
    existing_data = {}
    
    if ad and soyad:
        active_id = generate_universal_id(ad, soyad, dt)
        df = load_db()
        
        if not df.empty and active_id in df["ID"].values:
            existing_data = df[df["ID"] == active_id].iloc[0].to_dict()
            st.success(f"📂 Kayıt Bulundu: {ad} {soyad}. Eski puanlar yüklendi, düzenleyebilirsiniz.")
        else:
            st.warning("🆕 Yeni Kayıt. Tüm puanlar 0 olarak başlatılıyor.")

        st.divider()
        
        # 3. TEST GİRİŞ FORMU (ESKİ VERİLERLE DOLDURULMUŞ)
        form_data = {}
        toplamlar = {}
        
        col_l, col_n = st.columns(2)
        
        # LOKOMOTOR
        with col_l:
            st.subheader("🏃 LOKOMOTOR")
            for test, items in PROTOCOL["LOKOMOTOR"].items():
                test_total = 0
                with st.expander(test):
                    for i, item in enumerate(items):
                        key_name = f"L_{test}_{i}"
                        # Varsa eski değeri al, yoksa 0
                        default_val = int(existing_data.get(key_name, 0))
                        
                        # Radio butonu eski değerle başlar!
                        val = st.radio(
                            f"{item}", 
                            [0, 1, 2], 
                            index=default_val, 
                            key=f"radio_{key_name}_{active_id}", # ID ekledik ki çakışmasın
                            horizontal=True
                        )
                        form_data[key_name] = val
                        test_total += val
                    
                    st.caption(f"Bu Test Toplamı: {test_total}")
                    toplamlar[f"{test}_Toplam"] = test_total

        # NESNE KONTROL
        with col_n:
            st.subheader("🏀 NESNE KONTROL")
            for test, items in PROTOCOL["NESNE_KONTROL"].items():
                test_total = 0
                with st.expander(test):
                    for i, item in enumerate(items):
                        key_name = f"N_{test}_{i}"
                        default_val = int(existing_data.get(key_name, 0))
                        
                        val = st.radio(
                            f"{item}", 
                            [0, 1, 2], 
                            index=default_val, 
                            key=f"radio_{key_name}_{active_id}",
                            horizontal=True
                        )
                        form_data[key_name] = val
                        test_total += val
                        
                    st.caption(f"Bu Test Toplamı: {test_total}")
                    toplamlar[f"{test}_Toplam"] = test_total
        
        # 4. KAYDET BUTONU
        if st.button("💾 VERİLERİ GÜNCELLE / KAYDET", type="primary"):
            final_record = {
                "ID": active_id,
                "Ad": ad, "Soyad": soyad, 
                "DogumTarihi": str(dt),
                "Cinsiyet": cinsiyet,
                "YasGrubu": calculate_age_group(dt),
                "SonIslemTarihi": str(date.today())
            }
            # Skorları birleştir
            final_record.update(form_data) # Madde puanları
            final_record.update(toplamlar) # Toplam puanlar
            
            if save_to_db(final_record):
                st.success("✅ Veriler başarıyla veritabanına işlendi!")
                st.balloons()
    else:
        st.info("Lütfen veri girişi yapmak için yukarıdaki kimlik bilgilerini doldurun.")

elif menu == "Gelişim Raporu":
    st.header("📊 Öğrenci Raporu")
    df = load_db()
    
    if not df.empty:
        df['Gosterim'] = df['Ad'] + " " + df['Soyad'] + " (" + df['YasGrubu'] + ")"
        secim = st.selectbox("Öğrenci Seçiniz:", df['Gosterim'].unique())
        
        if secim:
            row = df[df['Gosterim'] == secim].iloc[0]
            stats = get_stats(row, df)
            
            st.subheader(f"Analiz: {row['Ad']} {row['Soyad']}")
            st.dataframe(stats, hide_index=True)
            
            # Grafik
            fig, ax = plt.subplots(figsize=(10, 5))
            x = np.arange(len(stats['Alt Test']))
            width = 0.35
            
            ax.bar(x - width/2, stats['Max'], width, label='Maksimum', color='#e0e0e0')
            ax.bar(x + width/2, stats['Puan'], width, label='Öğrenci', color='#2196F3')
            
            ax.set_xticks(x)
            ax.set_xticklabels(stats['Alt Test'], rotation=45)
            ax.legend()
            st.pyplot(fig)
            
            # PDF
            if st.button("📄 PDF İndir"):
                pdf = FPDF()
                pdf.add_page()
                # Türkçe karakter haritası
                tr = str.maketrans("ğĞıİşŞüÜöÖçÇ", "gGiIsSuUoOcC")
                
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, "TGMD-3 OZEL RAPOR", ln=True, align="C")
                
                pdf.set_font("Arial", size=11)
                pdf.cell(0, 7, f"Ad: {row['Ad']} {row['Soyad']}".translate(tr), ln=True)
                pdf.cell(0, 7, f"Grup: {row['Cinsiyet']} / {row['YasGrubu']}".translate(tr), ln=True)
                pdf.ln(5)
                
                # Tablo Başlık
                pdf.set_font("Arial", "B", 10)
                cols = ["Test", "Puan", "Max", "Ort", "SS", "Z-Skor", "Durum"]
                ws = [35, 15, 15, 15, 15, 20, 40]
                for i, c in enumerate(cols): pdf.cell(ws[i], 7, c, 1)
                pdf.ln()
                
                # Tablo Veri
                pdf.set_font("Arial", size=10)
                for _, r in stats.iterrows():
                    pdf.cell(ws[0], 7, r['Alt Test'].translate(tr), 1)
                    pdf.cell(ws[1], 7, str(r['Puan']), 1)
                    pdf.cell(ws[2], 7, str(r['Max']), 1)
                    pdf.cell(ws[3], 7, str(r['Ort']), 1)
                    pdf.cell(ws[4], 7, str(r['SS']), 1)
                    pdf.cell(ws[5], 7, str(r['Z']), 1)
                    pdf.cell(ws[6], 7, r['Durum'].translate(tr), 1)
                    pdf.ln()
                
                out = pdf.output(dest='S').encode('latin-1')
                st.download_button("İndir", out, "rapor.pdf", "application/pdf")

elif menu == "Excel İndir":
    st.header("💾 Veritabanı Yedek")
    df = load_db()
    if not df.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("Excel İndir", buffer.getvalue(), "tgmd3_full_data.xlsx")
    else:
        st.warning("Veri yok.")
