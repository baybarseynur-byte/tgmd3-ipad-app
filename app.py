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
st.set_page_config(page_title="TGMD-3 PRO: Tam Kontrol", layout="wide", page_icon="📋")

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

# Sütun Tanımları
MAX_SCORES = {}
ITEM_COLUMNS = []
for domain in PROTOCOL:
    for test, items in PROTOCOL[domain].items():
        MAX_SCORES[test] = len(items) * 2
        prefix = "L" if domain == "LOKOMOTOR" else "N"
        for i in range(len(items)):
            ITEM_COLUMNS.append(f"{prefix}_{test}_{i}")

SCORE_COLUMNS = [f"{test}_Toplam" for domain in PROTOCOL for test in PROTOCOL[domain]]
BASE_COLUMNS = ['TestID', 'OgrenciID', 'Ad', 'Soyad', 'Cinsiyet', 'DogumTarihi', 'TestTarihi', 'TestYeri', 'TercihEl', 'TercihAyak', 'YasGrubu', 'YasAy', 'SonIslemTarihi']
FULL_DB_COLUMNS = BASE_COLUMNS + SCORE_COLUMNS + ITEM_COLUMNS

# =============================================================================
# 2. FONKSİYONLAR
# =============================================================================
def generate_ids(ad, soyad, dogum_tarihi, test_tarihi):
    # Türkçe karakter temizliği
    tr_map = str.maketrans("ğĞıİşŞüÜöÖçÇ", "gGiIsSuUoOcC")
    clean_ad = ad.strip().upper().translate(tr_map)
    clean_soyad = soyad.strip().upper().translate(tr_map)
    
    # Öğrenci ID (Sabit)
    raw_student = f"{clean_ad}{clean_soyad}{str(dogum_tarihi)}"
    student_id = hashlib.md5(raw_student.encode('utf-8')).hexdigest()[:10]
    
    # Test ID (Her test için benzersiz)
    raw_test = f"{student_id}{str(test_tarihi)}"
    test_id = hashlib.md5(raw_test.encode('utf-8')).hexdigest()[:12]
    
    return student_id, test_id

def load_db():
    if not os.path.exists(FILE_NAME):
        return pd.DataFrame(columns=FULL_DB_COLUMNS)
    try:
        df = pd.read_excel(FILE_NAME)
        # Eksik sütunları tamamla
        for col in FULL_DB_COLUMNS:
            if col not in df.columns:
                df[col] = "" if col in BASE_COLUMNS else 0
        
        # Format düzeltmeleri
        for col in ['DogumTarihi', 'TestTarihi', 'Ad', 'Soyad', 'Cinsiyet', 'TestYeri', 'TercihEl', 'TercihAyak']:
            if col in df.columns: df[col] = df[col].astype(str).replace('nan', '')
            
        return df.fillna(0)
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
    
    with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return True

def calculate_age(birth_date, test_date):
    if isinstance(birth_date, str): b_date = pd.to_datetime(birth_date).date()
    else: b_date = birth_date
    if isinstance(test_date, str): t_date = pd.to_datetime(test_date).date()
    else: t_date = test_date
    
    diff = (t_date - b_date).days
    months = int(diff / 30.44)
    q = (months // 3) * 3
    return months, f"{q}-{q+2} Ay"

# =============================================================================
# 3. ARAYÜZ
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Test ve Veri Girişi", "2. Gelişim Raporu", "3. Veri Yönetimi"])

if menu == "1. Test ve Veri Girişi":
    st.header("📋 Test Veri Girişi")
    
    mode = st.radio("Seçim Yapınız:", ["📂 KAYITLI ÖĞRENCİ", "➕ YENİ ÖĞRENCİ KAYDI"], horizontal=True)
    
    df = load_db()
    
    # DEĞİŞKENLERİ BAŞLAT
    ad, soyad, cinsiyet = "", "", "Kız"
    dt = date(2018, 1, 1)
    test_tarihi = date.today()
    test_yeri = ""
    el_tercih = "Sağ"
    ayak_tercih = "Sağ"
    
    ogrenci_id = None
    
    # --- MOD 1: KAYITLI ÖĞRENCİ ---
    if mode == "📂 KAYITLI ÖĞRENCİ":
        if df.empty:
            st.warning("Sistemde kayıtlı öğrenci yok. Lütfen 'Yeni Öğrenci Kaydı' yapın.")
        else:
            # Benzersiz liste
            uniqs = df[['OgrenciID', 'Ad', 'Soyad', 'DogumTarihi', 'Cinsiyet']].drop_duplicates(subset='OgrenciID')
            uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad'] + " (" + uniqs['DogumTarihi'] + ")"
            
            secim = st.selectbox("Öğrenci Ara / Seç:", uniqs['Etiket'].tolist(), index=None, placeholder="İsim yazın...")
            
            if secim:
                rec = uniqs[uniqs['Etiket'] == secim].iloc[0]
                ad, soyad, cinsiyet = rec['Ad'], rec['Soyad'], rec['Cinsiyet']
                dt = pd.to_datetime(rec['DogumTarihi']).date()
                ogrenci_id = rec['OgrenciID']
                
                # Eski tercihlerini bul (Kolaylık olsun diye)
                last_test = df[df['OgrenciID'] == ogrenci_id].iloc[-1]
                test_yeri = last_test['TestYeri']
                el_tercih = last_test['TercihEl'] if last_test['TercihEl'] in ["Sağ", "Sol", "Belirsiz"] else "Sağ"
                ayak_tercih = last_test['TercihAyak'] if last_test['TercihAyak'] in ["Sağ", "Sol", "Belirsiz"] else "Sağ"

    # --- MOD 2: YENİ ÖĞRENCİ ---
    else:
        st.subheader("1. Kimlik Bilgileri")
        c1, c2, c3, c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper()
        soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("Doğum Tarihi", date(2018, 1, 1))
        cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)

    # --- ORTAK ALAN: TEST DETAYLARI VE FİZİKSEL ÖZELLİKLER ---
    # Hem yeni hem eski kayıt için burası zorunlu
    if ad and soyad:
        st.markdown("---")
        st.subheader("2. Test ve Fiziksel Bilgiler")
        
        # Test Tarihi ve Fiziksel Özellikler (Yeni öğrenci için de burada görünecek)
        r1, r2, r3, r4 = st.columns(4)
        
        # Test Tarihi (Varsayılan: Bugün)
        test_tarihi = r1.date_input("Test Tarihi", date.today())
        
        # Test Yeri
        test_yeri = r2.text_input("Test Yeri (Okul/Kulüp)", value=test_yeri).upper()
        
        # El / Ayak
        el_tercih = r3.selectbox("Tercih Edilen El", ["Sağ", "Sol", "Belirsiz"], index=["Sağ", "Sol", "Belirsiz"].index(el_tercih))
        ayak_tercih = r4.selectbox("Tercih Edilen Ayak", ["Sağ", "Sol", "Belirsiz"], index=["Sağ", "Sol", "Belirsiz"].index(ayak_tercih))
        
        # ID ÜRETME
        if not ogrenci_id:
            ogrenci_id, test_id = generate_ids(ad, soyad, dt, test_tarihi)[0], generate_ids(ad, soyad, dt, test_tarihi)[1]
        else:
            # Eski öğrenci ama yeni tarih olabilir, o yüzden TestID tekrar hesaplanır
            test_id = generate_ids(ad, soyad, dt, test_tarihi)[1]

        # ÇAKIŞMA KONTROLÜ
        existing_scores = {}
        is_update = False
        if not df.empty and test_id in df['TestID'].values:
            st.warning(f"⚠️ DİKKAT: {ad} {soyad} için {test_tarihi} tarihinde zaten kayıt var. Aşağıdaki işlem GÜNCELLEME olacaktır.")
            existing_scores = df[df['TestID'] == test_id].iloc[0].to_dict()
            is_update = True
        
        # --- TEST FORMU ---
        st.markdown("---")
        st.subheader("3. Performans Puanlama")
        
        form_data = {}
        toplamlar = {}
        col_l, col_n = st.columns(2)
        
        with col_l:
            st.info("🏃 LOKOMOTOR ALT TESTİ")
            for test_name, items in PROTOCOL["LOKOMOTOR"].items():
                t_total = 0
                with st.expander(test_name):
                    for i, item in enumerate(items):
                        key = f"L_{test_name}_{i}"
                        val_idx = int(existing_scores.get(key, 0))
                        val = st.radio(item, [0, 1, 2], index=val_idx, key=f"{test_id}_{key}", horizontal=True)
                        form_data[key] = val
                        t_total += val
                    toplamlar[f"{test_name}_Toplam"] = t_total
        
        with col_n:
            st.info("🏀 NESNE KONTROL ALT TESTİ")
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
        
        # KAYDET BUTONU
        st.markdown("---")
        btn_text = "VERİLERİ GÜNCELLE" if is_update else "YENİ TESTİ KAYDET"
        
        if st.button(f"💾 {btn_text}", type="primary", use_container_width=True):
            yas_ay, yas_grup = calculate_age(dt, test_tarihi)
            
            record = {
                "TestID": test_id, "OgrenciID": ogrenci_id,
                "Ad": ad, "Soyad": soyad, "DogumTarihi": dt, "Cinsiyet": cinsiyet,
                "TestTarihi": test_tarihi, "TestYeri": test_yeri,
                "TercihEl": el_tercih, "TercihAyak": ayak_tercih,
                "YasAy": yas_ay, "YasGrubu": yas_grup,
                "SonIslemTarihi": str(date.today())
            }
            record.update(form_data)
            record.update(toplamlar)
            
            save_to_db(record)
            st.success(f"✅ İşlem Başarılı! {ad} {soyad} verileri kaydedildi.")
            st.balloons()

elif menu == "2. Gelişim Raporu":
    st.header("📈 Gelişim Raporu")
    df = load_db()
    if not df.empty:
        # Öğrenci Seç
        uniqs = df[['OgrenciID', 'Ad', 'Soyad']].drop_duplicates(subset='OgrenciID')
        uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad']
        secim = st.selectbox("Öğrenci:", uniqs['Etiket'])
        
        if secim:
            oid = uniqs[uniqs['Etiket'] == secim].iloc[0]['OgrenciID']
            sub_df = df[df['OgrenciID'] == oid].sort_values('TestTarihi')
            
            # Grafik
            if len(sub_df) > 0:
                dates = sub_df['TestTarihi'].tolist()
                l_sc = [sum([row[f"{t}_Toplam"] for t in PROTOCOL['LOKOMOTOR']]) for _, row in sub_df.iterrows()]
                n_sc = [sum([row[f"{t}_Toplam"] for t in PROTOCOL['NESNE_KONTROL']]) for _, row in sub_df.iterrows()]
                
                fig, ax = plt.subplots(figsize=(10, 4))
                ax.plot(dates, l_sc, 'o-', label='Lokomotor')
                ax.plot(dates, n_sc, 's-', label='Nesne Kontrol')
                ax.set_title("Gelişim Grafiği")
                ax.legend()
                st.pyplot(fig)
                
            st.dataframe(sub_df[['TestTarihi', 'YasGrubu', 'TestYeri'] + SCORE_COLUMNS])

elif menu == "3. Veri Yönetimi":
    st.header("💾 Veri Yönetimi")
    df = load_db()
    if not df.empty:
        st.dataframe(df)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("Excel İndir", buffer.getvalue(), "tgmd3_data.xlsx")
