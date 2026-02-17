import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import hashlib
from datetime import date
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from fpdf import FPDF

# =============================================================================
# 1. AYARLAR VE PROTOKOL
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO: Boylamsal Takip", layout="wide", page_icon="📈")

FILE_NAME = "tgmd3_longitudinal_db.xlsx"

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

# Sütun İsimleri ve Puan Hesaplamaları
MAX_SCORES = {}
# Temel Kimlik Bilgileri
BASE_COLUMNS = [
    'TestID',       # HER TEST OTURUMU İÇİN BENZERSİZ
    'OgrenciID',    # ÖĞRENCİ İÇİN SABİT (BOYLAMSAL TAKİP İÇİN)
    'Ad', 'Soyad', 'Cinsiyet', 'DogumTarihi', 
    'TestTarihi', 'TestYeri', 'TercihEl', 'TercihAyak', 
    'YasGrubu', 'YasAy', 'SonIslemTarihi'
]
ITEM_COLUMNS = []

for domain in PROTOCOL:
    for test, items in PROTOCOL[domain].items():
        MAX_SCORES[test] = len(items) * 2
        prefix = "L" if domain == "LOKOMOTOR" else "N"
        for i in range(len(items)):
            ITEM_COLUMNS.append(f"{prefix}_{test}_{i}")

SCORE_COLUMNS = [f"{test}_Toplam" for domain in PROTOCOL for test in PROTOCOL[domain]]
FULL_DB_COLUMNS = BASE_COLUMNS + SCORE_COLUMNS + ITEM_COLUMNS

# =============================================================================
# 2. VERİTABANI MOTORU (BOYLAMSAL YAPI)
# =============================================================================
def generate_student_id(ad, soyad, dogum_tarihi):
    """Öğrenciyi tanımlayan sabit ID (Değişmez)"""
    clean_ad = ad.strip().upper().replace('İ','I').replace('Ğ','G').replace('Ü','U').replace('Ş','S').replace('Ö','O').replace('Ç','C')
    clean_soyad = soyad.strip().upper().replace('İ','I').replace('Ğ','G').replace('Ü','U').replace('Ş','S').replace('Ö','O').replace('Ç','C')
    raw_str = f"{clean_ad}{clean_soyad}{str(dogum_tarihi)}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()[:10]

def generate_test_id(student_id, test_date):
    """Her test oturumu için benzersiz ID (ÖğrenciID + Tarih)"""
    raw_str = f"{student_id}{str(test_date)}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()[:12]

def load_db():
    if not os.path.exists(FILE_NAME):
        return pd.DataFrame(columns=FULL_DB_COLUMNS)
    try:
        df = pd.read_excel(FILE_NAME)
        # Eksik sütun tamamlama
        for col in FULL_DB_COLUMNS:
            if col not in df.columns:
                if col in BASE_COLUMNS: df[col] = ""
                else: df[col] = 0
        
        # Tarih formatlarını düzelt
        df['TestTarihi'] = pd.to_datetime(df['TestTarihi']).dt.date
        df['DogumTarihi'] = pd.to_datetime(df['DogumTarihi']).dt.date
        
        # String temizliği
        str_cols = ['TestID', 'OgrenciID', 'Ad', 'Soyad', 'Cinsiyet', 'YasGrubu']
        for c in str_cols:
            if c in df.columns: df[c] = df[c].astype(str).replace("nan", "")
            
        return df
    except:
        return pd.DataFrame(columns=FULL_DB_COLUMNS)

def save_to_db(data_dict):
    """
    Mantık:
    - Eğer aynı TestID (Öğrenci + Tarih) varsa -> GÜNCELLE (Edit)
    - Eğer TestID yoksa -> YENİ SATIR EKLE (New Measurement)
    """
    df = load_db()
    test_id = data_dict["TestID"]
    
    # Tarihleri string olarak sakla (Excel uyumu için)
    data_dict["TestTarihi"] = str(data_dict["TestTarihi"])
    data_dict["DogumTarihi"] = str(data_dict["DogumTarihi"])
    
    if not df.empty and test_id in df["TestID"].values:
        # Mevcut testi güncelle
        idx = df[df["TestID"] == test_id].index[0]
        for key, val in data_dict.items():
            df.at[idx, key] = val
    else:
        # Yeni test ekle
        new_row = pd.DataFrame([data_dict])
        df = pd.concat([df, new_row], ignore_index=True)
    
    df = df.fillna(0)
    with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return True

def delete_test(test_id):
    df = load_db()
    if not df.empty and test_id in df["TestID"].values:
        df = df[df["TestID"] != test_id]
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return True
    return False

def calculate_age_group(birth_date, test_date):
    if isinstance(birth_date, str): b_date = pd.to_datetime(birth_date).date()
    else: b_date = birth_date
    if isinstance(test_date, str): t_date = pd.to_datetime(test_date).date()
    else: t_date = test_date
        
    diff_days = (t_date - b_date).days
    age_months = int(diff_days / 30.44)
    quarter = (age_months // 3) * 3
    return age_months, f"{quarter}-{quarter+2} Ay"

# =============================================================================
# 3. İSTATİSTİK VE ANALİZ
# =============================================================================
def get_norm_stats(student_row, full_df):
    """Norm değerlerini hesaplar (O anki yaş grubuna göre)"""
    # Filtre: Aynı Cinsiyet + Aynı Yaş Grubu (Farklı öğrencilerin verileri)
    # Kendisinin diğer testlerini de norm grubuna katmamak için OgrenciID hariç tutulabilir ama 
    # popülasyon küçükse katılması daha iyidir. Şimdilik katıyoruz.
    
    group_df = full_df[
        (full_df['Cinsiyet'] == student_row['Cinsiyet']) & 
        (full_df['YasGrubu'] == student_row['YasGrubu'])
    ]
    
    stats = []
    for test, max_score in MAX_SCORES.items():
        col = f"{test}_Toplam"
        puan = float(student_row.get(col, 0))
        
        if len(group_df) > 1:
            ort = group_df[col].mean()
            ss = group_df[col].std(ddof=1)
            z = (puan - ort) / ss if ss > 0 else 0
        else:
            ort, ss, z = puan, 0, 0
            
        if z >= 1: durum = "İleri"
        elif z <= -1: durum = "Geliştirilmeli"
        else: durum = "Normal"
        if len(group_df) < 2: durum = "Veri Yetersiz"
        
        stats.append({
            "Test": test, "Puan": puan, "Max": max_score,
            "Ort": round(ort,2), "SS": round(ss,2), "Z": round(z,2), "Durum": durum
        })
    return pd.DataFrame(stats)

# =============================================================================
# 4. ARAYÜZ
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Test Girişi (Yeni/Eski)", "2. Veri Düzenle/Sil", "3. Gelişim Raporu", "4. Araştırma Çıktısı (Excel)"])

# --- MODÜL 1: TEST GİRİŞİ ---
if menu == "1. Test Girişi (Yeni/Eski)":
    st.header("⏱ Test Oturumu Girişi")
    st.info("Aynı öğrenciye farklı tarihlerde yapılan testler ayrı ayrı kaydedilir.")

    # 1. KİMLİK
    with st.expander("Öğrenci ve Tarih Bilgisi", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper()
        soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("Doğum Tarihi", date(2018, 1, 1))
        cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)
        
        st.divider()
        c5, c6, c7, c8 = st.columns(4)
        # BURASI ÖNEMLİ: Test tarihi değiştikçe yeni kayıt oluşur!
        test_tarihi = c5.date_input("Test Tarihi (Bugün veya Geçmiş)", date.today())
        test_yeri = c6.text_input("Test Yeri").upper()
        el = c7.selectbox("Tercih Edilen El", ["Sağ", "Sol", "Belirsiz"])
        ayak = c8.selectbox("Tercih Edilen Ayak", ["Sağ", "Sol", "Belirsiz"])

    # 2. OTOMATİK KONTROL
    ogrenci_id = None
    test_id = None
    existing_data = {}
    
    if ad and soyad:
        ogrenci_id = generate_student_id(ad, soyad, dt)
        test_id = generate_test_id(ogrenci_id, test_tarihi)
        
        df = load_db()
        
        # Durum Analizi
        # A. Bu öğrencinin bu tarihte testi var mı?
        is_update = False
        if not df.empty and test_id in df["TestID"].values:
            st.warning(f"⚠️ {ad} {soyad} için {test_tarihi} tarihinde zaten bir kayıt var. Yapacağınız değişiklikler bu kaydı güncelleyecek.")
            existing_data = df[df["TestID"] == test_id].iloc[0].to_dict()
            is_update = True
        # B. Öğrenci var ama tarih farklı (YENİ ÖLÇÜM)
        elif not df.empty and ogrenci_id in df["OgrenciID"].values:
            st.success(f"📈 {ad} {soyad} sistemde kayıtlı. {test_tarihi} tarihli YENİ BİR ÖLÇÜM ekliyorsunuz.")
            # Kolaylık olsun diye önceki tercihlerini (el/ayak) getirebiliriz ama puanları sıfır olmalı
            prev_rec = df[df["OgrenciID"] == ogrenci_id].iloc[-1]
            existing_data = {"TercihEl": prev_rec["TercihEl"], "TercihAyak": prev_rec["TercihAyak"], "TestYeri": prev_rec["TestYeri"]}
        else:
            st.info("🆕 Sistemde bulunmayan yeni bir öğrenci.")

        # 3. TEST FORMU
        st.markdown("---")
        form_data = {}
        toplamlar = {}
        col_l, col_n = st.columns(2)
        
        with col_l:
            st.subheader("🏃 LOKOMOTOR")
            for test, items in PROTOCOL["LOKOMOTOR"].items():
                t_total = 0
                with st.expander(test):
                    for i, item in enumerate(items):
                        key = f"L_{test}_{i}"
                        val = st.radio(item, [0, 1, 2], index=int(existing_data.get(key, 0)), key=f"{test_id}_{key}", horizontal=True)
                        form_data[key] = val
                        t_total += val
                    toplamlar[f"{test}_Toplam"] = t_total
                    st.caption(f"Skor: {t_total}")

        with col_n:
            st.subheader("🏀 NESNE KONTROL")
            for test, items in PROTOCOL["NESNE_KONTROL"].items():
                t_total = 0
                with st.expander(test):
                    for i, item in enumerate(items):
                        key = f"N_{test}_{i}"
                        val = st.radio(item, [0, 1, 2], index=int(existing_data.get(key, 0)), key=f"{test_id}_{key}", horizontal=True)
                        form_data[key] = val
                        t_total += val
                    toplamlar[f"{test}_Toplam"] = t_total
                    st.caption(f"Skor: {t_total}")
        
        # KAYDET
        btn_text = "GÜNCELLE" if is_update else "YENİ ÖLÇÜM KAYDET"
        if st.button(f"💾 {btn_text}", type="primary"):
            yas_ay, yas_grup = calculate_age_group(dt, test_tarihi)
            
            record = {
                "TestID": test_id,
                "OgrenciID": ogrenci_id,
                "Ad": ad, "Soyad": soyad, "DogumTarihi": dt, "Cinsiyet": cinsiyet,
                "TestTarihi": test_tarihi, "TestYeri": test_yeri,
                "TercihEl": el, "TercihAyak": ayak,
                "YasAy": yas_ay, "YasGrubu": yas_grup,
                "SonIslemTarihi": str(date.today())
            }
            record.update(form_data)
            record.update(toplamlar)
            
            save_to_db(record)
            st.success("İşlem Başarılı!")
            st.rerun()

# --- MODÜL 2: DÜZENLE / SİL ---
elif menu == "2. Veri Düzenle/Sil":
    st.header("🛠 Kayıt Yönetimi")
    df = load_db()
    if not df.empty:
        # Önce Öğrenci Seç
        df['AdSoyad'] = df['Ad'] + " " + df['Soyad']
        students = df['AdSoyad'].unique()
        selected_student = st.selectbox("Öğrenci Seç:", students)
        
        # Sonra O Öğrencinin Testlerini Listele
        student_tests = df[df['AdSoyad'] == selected_student]
        # Gösterim: Tarih - Yaş Grubu - Toplam Puanlar
        student_tests['Gosterim'] = student_tests.apply(
            lambda x: f"{x['TestTarihi']} | {x['YasGrubu']} | Loko:{sum([x[f'{t}_Toplam'] for t in PROTOCOL['LOKOMOTOR']])} Nesne:{sum([x[f'{t}_Toplam'] for t in PROTOCOL['NESNE_KONTROL']])}", 
            axis=1
        )
        
        selected_test_display = st.selectbox("Düzenlenecek Test Oturumu:", student_tests['Gosterim'].unique())
        
        if selected_test_display:
            target_test = student_tests[student_tests['Gosterim'] == selected_test_display].iloc[0]
            target_id = target_test['TestID']
            
            st.info("Bu testin içeriğini değiştirmek için 'Test Girişi' menüsüne gidip aynı tarihi seçebilirsiniz. Silmek için aşağıyı kullanın.")
            
            if st.button("🗑 BU TEST OTURUMUNU SİL", type="primary"):
                delete_test(target_id)
                st.success("Test kaydı silindi.")
                st.rerun()
    else:
        st.warning("Veri yok.")

# --- MODÜL 3: GELİŞİM RAPORU ---
elif menu == "3. Gelişim Raporu":
    st.header("📈 Gelişimsel Takip Raporu")
    df = load_db()
    
    if not df.empty:
        # Öğrenci Seçimi
        df['AdSoyad'] = df['Ad'] + " " + df['Soyad']
        student_list = df['AdSoyad'].unique()
        choice = st.selectbox("Öğrenci:", student_list)
        
        if choice:
            # Öğrencinin tüm verilerini çek ve tarihe göre sırala
            sub_df = df[df['AdSoyad'] == choice].sort_values(by='TestTarihi')
            
            # --- SEÇENEK 1: TEKİL RAPOR (En son veya seçilen) ---
            st.subheader(f"1. Detaylı Performans Analizi")
            test_dates = sub_df['TestTarihi'].tolist()
            selected_date = st.selectbox("Hangi Tarihli Rapor?", test_dates, index=len(test_dates)-1)
            
            current_row = sub_df[sub_df['TestTarihi'] == selected_date].iloc[0]
            stats = get_norm_stats(current_row, df)
            
            # Tablo
            st.write(f"**Test Tarihi:** {selected_date} | **Yaş Grubu:** {current_row['YasGrubu']}")
            st.dataframe(stats, hide_index=True)
            
            # --- SEÇENEK 2: GELİŞİM GRAFİĞİ (Eğer birden fazla test varsa) ---
            if len(sub_df) > 1:
                st.markdown("---")
                st.subheader("2. Zaman İçindeki Gelişim")
                
                # Veriyi hazırla
                dates = sub_df['TestTarihi'].tolist()
                
                # Loko ve Nesne Toplamlarını Hesapla
                loko_totals = []
                nesne_totals = []
                
                for _, row in sub_df.iterrows():
                    l = sum([row[f"{t}_Toplam"] for t in PROTOCOL['LOKOMOTOR']])
                    n = sum([row[f"{t}_Toplam"] for t in PROTOCOL['NESNE_KONTROL']])
                    loko_totals.append(l)
                    nesne_totals.append(n)
                
                # Grafik Çiz
                fig, ax = plt.subplots(figsize=(10, 5))
                ax.plot(dates, loko_totals, marker='o', label='Lokomotor Toplam', linewidth=2)
                ax.plot(dates, nesne_totals, marker='s', label='Nesne Kontrol Toplam', linewidth=2)
                
                # Tarih formatı
                # ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
                # ax.xaxis.set_major_locator(mdates.DayLocator(interval=1))
                plt.xticks(rotation=45)
                
                ax.set_title("Gelişim Eğrisi")
                ax.set_ylabel("Toplam Puan")
                ax.grid(True, linestyle='--', alpha=0.6)
                ax.legend()
                
                st.pyplot(fig)
                
                st.info(f"Öğrencinin {len(dates)} farklı ölçümü bulunmaktadır. Gelişim grafiği yukarıdaki gibidir.")

            # PDF ÇIKTISI
            if st.button("📄 Raporu PDF Olarak İndir"):
                pdf = FPDF()
                pdf.add_page()
                tr = str.maketrans("ğĞıİşŞüÜöÖçÇ", "gGiIsSuUoOcC")
                
                # Başlık
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, "TGMD-3 GELISIM RAPORU", ln=True, align="C")
                
                # Bilgiler
                pdf.set_font("Arial", size=11)
                pdf.cell(0, 7, f"Ogrenci: {choice}".translate(tr), ln=True)
                pdf.cell(0, 7, f"Rapor Tarihi: {selected_date}".translate(tr), ln=True)
                pdf.ln(5)
                
                # Tablo
                pdf.set_font("Arial", "B", 10)
                headers = ["Test", "Puan", "Max", "Ort", "SS", "Z", "Durum"]
                w = [35, 15, 15, 15, 15, 20, 40]
                for i, h in enumerate(headers): pdf.cell(w[i], 7, h, 1)
                pdf.ln()
                
                pdf.set_font("Arial", size=10)
                for _, r in stats.iterrows():
                    pdf.cell(w[0], 7, r['Test'].translate(tr), 1)
                    pdf.cell(w[1], 7, str(r['Puan']), 1)
                    pdf.cell(w[2], 7, str(r['Max']), 1)
                    pdf.cell(w[3], 7, str(r['Ort']), 1)
                    pdf.cell(w[4], 7, str(r['SS']), 1)
                    pdf.cell(w[5], 7, str(r['Z']), 1)
                    pdf.cell(w[6], 7, r['Durum'].translate(tr), 1)
                    pdf.ln()
                
                # Gelişim Notu
                if len(sub_df) > 1:
                    pdf.ln(10)
                    pdf.set_font("Arial", "B", 11)
                    pdf.cell(0, 10, f"GELISIM TAKIBI ({len(sub_df)} OLCUM)", ln=True)
                    pdf.set_font("Arial", size=10)
                    for i, d in enumerate(dates):
                         pdf.cell(0, 7, f"{i+1}. Olcum ({d}): Loko={loko_totals[i]} | Nesne={nesne_totals[i]}", ln=True)

                out = pdf.output(dest='S').encode('latin-1')
                st.download_button("İndir", out, "gelisim_raporu.pdf", "application/pdf")

# --- MODÜL 4: ARAŞTIRMA ÇIKTISI ---
elif menu == "4. Araştırma Çıktısı (Excel)":
    st.header("💾 SPSS / Excel Çıktısı")
    st.markdown("""
    Bu çıktı **'Long Format'** (Uzun Format) yapısındadır. 
    Her satır bir test oturumunu temsil eder. Tekrarlı ölçüm analizleri (Repeated Measures ANOVA vb.) için uygundur.
    """)
    
    df = load_db()
    if not df.empty:
        st.dataframe(df.head())
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("📥 Veriyi İndir (.xlsx)", buffer.getvalue(), "tgmd3_research_data.xlsx")
    else:
        st.warning("Henüz veri yok.")
