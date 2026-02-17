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
st.set_page_config(page_title="TGMD-3 PRO: Akıllı Takip", layout="wide", page_icon="🔍")

FILE_NAME = "tgmd3_longitudinal_db.xlsx"

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

MAX_SCORES = {}
BASE_COLUMNS = [
    'TestID', 'OgrenciID', 'Ad', 'Soyad', 'Cinsiyet', 'DogumTarihi', 
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
# 2. VERİTABANI MOTORU
# =============================================================================
def generate_student_id(ad, soyad, dogum_tarihi):
    clean_ad = ad.strip().upper().replace('İ','I').replace('Ğ','G').replace('Ü','U').replace('Ş','S').replace('Ö','O').replace('Ç','C')
    clean_soyad = soyad.strip().upper().replace('İ','I').replace('Ğ','G').replace('Ü','U').replace('Ş','S').replace('Ö','O').replace('Ç','C')
    raw_str = f"{clean_ad}{clean_soyad}{str(dogum_tarihi)}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()[:10]

def generate_test_id(student_id, test_date):
    raw_str = f"{student_id}{str(test_date)}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()[:12]

def load_db():
    if not os.path.exists(FILE_NAME):
        return pd.DataFrame(columns=FULL_DB_COLUMNS)
    try:
        df = pd.read_excel(FILE_NAME)
        # Eksik sütunları tamamla
        for col in FULL_DB_COLUMNS:
            if col not in df.columns:
                if col in BASE_COLUMNS: df[col] = ""
                else: df[col] = 0
        
        # Tarih formatlarını düzelt (String olarak tutuyoruz ki hata almasın)
        df['DogumTarihi'] = df['DogumTarihi'].astype(str)
        df['TestTarihi'] = df['TestTarihi'].astype(str)
        
        # Nan temizliği
        df = df.fillna(0)
        str_cols = ['TestID', 'OgrenciID', 'Ad', 'Soyad', 'Cinsiyet', 'YasGrubu', 'TestYeri', 'TercihEl', 'TercihAyak']
        for c in str_cols:
            if c in df.columns: df[c] = df[c].astype(str).replace("0", "").replace("nan", "")

        return df
    except:
        return pd.DataFrame(columns=FULL_DB_COLUMNS)

def save_to_db(data_dict):
    df = load_db()
    test_id = data_dict["TestID"]
    
    # Tarihleri string yap
    data_dict["TestTarihi"] = str(data_dict["TestTarihi"])
    data_dict["DogumTarihi"] = str(data_dict["DogumTarihi"])
    
    if not df.empty and test_id in df["TestID"].values:
        idx = df[df["TestID"] == test_id].index[0]
        for key, val in data_dict.items():
            df.at[idx, key] = val
    else:
        new_row = pd.DataFrame([data_dict])
        df = pd.concat([df, new_row], ignore_index=True)
    
    df = df.fillna(0)
    with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return True

def calculate_age_group(birth_date, test_date):
    if isinstance(birth_date, str): b_date = pd.to_datetime(birth_date).date()
    else: b_date = birth_date
    if isinstance(test_date, str): t_date = pd.to_datetime(test_date).date()
    else: t_date = test_date
        
    diff_days = (t_date - b_date).days
    age_months = int(diff_days / 30.44)
    quarter = (age_months // 3) * 3
    return age_months, f"{quarter}-{quarter+2} Ay"

def get_norm_stats(student_row, full_df):
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
# 3. ARAYÜZ TASARIMI
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Test ve Veri Girişi", "2. Gelişim Raporu", "3. Veri Yönetimi (Excel)"])

if menu == "1. Test ve Veri Girişi":
    st.header("⏱ Test Oturumu Girişi")
    
    # --- MOD SEÇİMİ: YENİ Mİ ESKİ Mİ? ---
    mode = st.radio("İşlem Türü Seçiniz:", ["📂 Kayıtlı Öğrenci Seç", "➕ Yeni Öğrenci Kaydı"], horizontal=True)
    
    # Değişkenleri başta tanımla
    ad, soyad, cinsiyet = "", "", "Kız"
    dt = date(2018, 1, 1)
    ogrenci_id = None
    
    # Veritabanını yükle
    df = load_db()
    
    if mode == "📂 Kayıtlı Öğrenci Seç":
        if df.empty:
            st.warning("Henüz kayıtlı öğrenci yok. Lütfen 'Yeni Öğrenci Kaydı' seçeneğini kullanın.")
        else:
            # BENZERSİZ ÖĞRENCİ LİSTESİ OLUŞTURMA
            # Ad, Soyad ve Doğum Tarihine göre tekilleştir
            unique_students = df[['OgrenciID', 'Ad', 'Soyad', 'DogumTarihi', 'Cinsiyet']].drop_duplicates(subset='OgrenciID')
            
            # Seçim Kutusunda Görünecek Etiket (İsim + DT karışıklığı önler)
            unique_students['Label'] = unique_students['Ad'] + " " + unique_students['Soyad'] + " (" + unique_students['DogumTarihi'] + ")"
            
            # Arama Kutusu (Selectbox searchable'dır)
            selected_label = st.selectbox(
                "Öğrenciyi Listeden Seçiniz veya İsmini Yazınız:", 
                unique_students['Label'].tolist(),
                index=None,
                placeholder="İsim yazmaya başlayın..."
            )
            
            if selected_label:
                # Seçilen öğrencinin bilgilerini al
                student_record = unique_students[unique_students['Label'] == selected_label].iloc[0]
                ad = student_record['Ad']
                soyad = student_record['Soyad']
                dt = pd.to_datetime(student_record['DogumTarihi']).date()
                cinsiyet = student_record['Cinsiyet']
                ogrenci_id = student_record['OgrenciID']
                
                st.success(f"✅ Seçildi: {ad} {soyad} | Doğum Tarihi: {dt}")

    else: # Yeni Öğrenci Modu
        c1, c2, c3, c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper()
        soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("Doğum Tarihi", date(2018, 1, 1))
        cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)
    
    # --- TEST DETAYLARI (HER İKİ DURUMDA DA GEREKLİ) ---
    if ad and soyad:
        st.divider()
        st.subheader("📝 Test Oturumu Bilgileri")
        
        c5, c6, c7, c8 = st.columns(4)
        test_tarihi = c5.date_input("Test Tarihi", date.today())
        test_yeri = c6.text_input("Test Yeri (Okul/Salon)").upper()
        
        # Daha önce tercihi varsa otomatik getir
        def_el, def_ayak = "Sağ", "Sağ"
        if ogrenci_id and not df.empty:
            prev_data = df[df['OgrenciID'] == ogrenci_id]
            if not prev_data.empty:
                last_rec = prev_data.iloc[-1]
                if str(last_rec['TercihEl']) in ["Sağ", "Sol", "Belirsiz"]: def_el = last_rec['TercihEl']
                if str(last_rec['TercihAyak']) in ["Sağ", "Sol", "Belirsiz"]: def_ayak = last_rec['TercihAyak']
        
        el = c7.selectbox("Tercih Edilen El", ["Sağ", "Sol", "Belirsiz"], index=["Sağ", "Sol", "Belirsiz"].index(def_el))
        ayak = c8.selectbox("Tercih Edilen Ayak", ["Sağ", "Sol", "Belirsiz"], index=["Sağ", "Sol", "Belirsiz"].index(def_ayak))

        # ID Üretimi
        if not ogrenci_id:
            ogrenci_id = generate_student_id(ad, soyad, dt)
        
        test_id = generate_test_id(ogrenci_id, test_tarihi)
        
        # Mevcut Test Kontrolü
        existing_scores = {}
        is_update = False
        if not df.empty and test_id in df['TestID'].values:
            st.warning(f"⚠️ {ad} {soyad} için {test_tarihi} tarihinde zaten bir kayıt var. Aşağıdan düzenleyebilirsiniz.")
            existing_scores = df[df['TestID'] == test_id].iloc[0].to_dict()
            is_update = True
        
        # --- PUANLAMA FORMU ---
        st.markdown("---")
        form_data = {}
        toplamlar = {}
        col_l, col_n = st.columns(2)
        
        with col_l:
            st.subheader("🏃 LOKOMOTOR")
            for test_name, items in PROTOCOL["LOKOMOTOR"].items():
                t_total = 0
                with st.expander(test_name):
                    for i, item in enumerate(items):
                        key = f"L_{test_name}_{i}"
                        # Varsa eski puan, yoksa 0
                        val_idx = int(existing_scores.get(key, 0))
                        val = st.radio(item, [0, 1, 2], index=val_idx, key=f"{test_id}_{key}", horizontal=True)
                        form_data[key] = val
                        t_total += val
                    toplamlar[f"{test_name}_Toplam"] = t_total
                    st.caption(f"Skor: {t_total}")

        with col_n:
            st.subheader("🏀 NESNE KONTROL")
            for test_name, items in PROTOCOL["NESNE_KONTROL"].items():
                t_total = 0
                with st.expander(test_name):
                    for i, item in enumerate(items):
                        key = f"N_{test_name}_{i}"
                        val_idx = int(existing_scores.get(key, 0))
                        val = st.radio(item, [0, 1, 2], index=val_idx, key=f"{test_id}_{key}", horizontal=True)
                        form_data[key] = val
                        t_total += val
                    toplamlar[f"{test_name}_Toplam"] = t_total
                    st.caption(f"Skor: {t_total}")
        
        # KAYDET BUTONU
        btn_label = "GÜNCELLE" if is_update else "KAYDET"
        if st.button(f"💾 {btn_label}", type="primary"):
            yas_ay, yas_grup = calculate_age_group(dt, test_tarihi)
            
            record = {
                "TestID": test_id, "OgrenciID": ogrenci_id,
                "Ad": ad, "Soyad": soyad, "DogumTarihi": dt, "Cinsiyet": cinsiyet,
                "TestTarihi": test_tarihi, "TestYeri": test_yeri,
                "TercihEl": el, "TercihAyak": ayak,
                "YasAy": yas_ay, "YasGrubu": yas_grup,
                "SonIslemTarihi": str(date.today())
            }
            record.update(form_data)
            record.update(toplamlar)
            
            save_to_db(record)
            st.balloons()
            st.success("Veriler başarıyla işlendi!")

elif menu == "2. Gelişim Raporu":
    st.header("📈 Gelişim Takip")
    df = load_db()
    if not df.empty:
        # Tekil öğrenci listesi (Görünüm için)
        unique_students = df[['OgrenciID', 'Ad', 'Soyad', 'DogumTarihi']].drop_duplicates(subset='OgrenciID')
        unique_students['Label'] = unique_students['Ad'] + " " + unique_students['Soyad'] + " (" + unique_students['DogumTarihi'].astype(str) + ")"
        
        choice = st.selectbox("Raporlanacak Öğrenciyi Seçin:", unique_students['Label'])
        
        if choice:
            selected_id = unique_students[unique_students['Label'] == choice].iloc[0]['OgrenciID']
            student_data = df[df['OgrenciID'] == selected_id].sort_values(by='TestTarihi')
            
            st.info(f"Bu öğrenciye ait {len(student_data)} farklı ölçüm bulundu.")
            
            # Grafik
            if len(student_data) > 0:
                dates = student_data['TestTarihi'].tolist()
                l_scores = [sum([row[f"{t}_Toplam"] for t in PROTOCOL['LOKOMOTOR']]) for _, row in student_data.iterrows()]
                n_scores = [sum([row[f"{t}_Toplam"] for t in PROTOCOL['NESNE_KONTROL']]) for _, row in student_data.iterrows()]
                
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(dates, l_scores, 'o-', label='Lokomotor')
                ax.plot(dates, n_scores, 's-', label='Nesne Kontrol')
                ax.legend()
                ax.set_title("Gelişim Grafiği")
                st.pyplot(fig)
            
            # Detay Tablo
            st.write("Ölçüm Geçmişi:")
            st.dataframe(student_data[['TestTarihi', 'YasGrubu', 'TestYeri'] + SCORE_COLUMNS])

elif menu == "3. Veri Yönetimi (Excel)":
    st.header("💾 Veri Yönetimi")
    df = load_db()
    if not df.empty:
        st.dataframe(df.head())
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("Tüm Veriyi İndir (Long Format)", buffer.getvalue(), "tgmd3_full.xlsx")
    else:
        st.warning("Veri yok.")
