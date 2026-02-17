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
st.set_page_config(page_title="TGMD-3 PRO: Yönetim Paneli", layout="wide", page_icon="🎽")

FILE_NAME = "tgmd3_master_db.xlsx"

# PROTOKOL (Dokunulmaz - Aynen Korundu)
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
    'ID', 'Ad', 'Soyad', 'Cinsiyet', 'DogumTarihi', 
    'TestTarihi', 'TestYeri', 'TercihEl', 'TercihAyak', 
    'YasGrubu', 'SonIslemTarihi'
]
ITEM_COLUMNS = []

for domain in PROTOCOL:
    for test, items in PROTOCOL[domain].items():
        MAX_SCORES[test] = len(items) * 2
        # Her madde için ayrı sütun (Veri kaybını önlemek için)
        prefix = "L" if domain == "LOKOMOTOR" else "N"
        for i in range(len(items)):
            ITEM_COLUMNS.append(f"{prefix}_{test}_{i}")

# Toplam puan sütunları (Örn: Kosu_Toplam)
SCORE_COLUMNS = [f"{test}_Toplam" for domain in PROTOCOL for test in PROTOCOL[domain]]

FULL_DB_COLUMNS = BASE_COLUMNS + SCORE_COLUMNS + ITEM_COLUMNS

# =============================================================================
# 2. VERİTABANI MOTORU
# =============================================================================
def generate_universal_id(ad, soyad, dogum_tarihi):
    """Ad+Soyad+DT -> Benzersiz ID"""
    # Türkçe karakter toleransı için basit replace
    clean_ad = ad.strip().upper().replace('İ','I').replace('Ğ','G').replace('Ü','U').replace('Ş','S').replace('Ö','O').replace('Ç','C')
    clean_soyad = soyad.strip().upper().replace('İ','I').replace('Ğ','G').replace('Ü','U').replace('Ş','S').replace('Ö','O').replace('Ç','C')
    raw_str = f"{clean_ad}{clean_soyad}{str(dogum_tarihi)}"
    return hashlib.md5(raw_str.encode('utf-8')).hexdigest()[:12]

def load_db():
    if not os.path.exists(FILE_NAME):
        return pd.DataFrame(columns=FULL_DB_COLUMNS)
    try:
        df = pd.read_excel(FILE_NAME)
        # Eksik sütunları tamamla
        for col in FULL_DB_COLUMNS:
            if col not in df.columns:
                if col in BASE_COLUMNS:
                    df[col] = ""
                else:
                    df[col] = 0
        
        # String alanları temizle
        for c in BASE_COLUMNS:
            if c in df.columns: df[c] = df[c].astype(str).replace("nan", "")
            
        return df
    except:
        return pd.DataFrame(columns=FULL_DB_COLUMNS)

def save_to_db(data_dict):
    """Veriyi kaydeder veya günceller."""
    df = load_db()
    student_id = data_dict["ID"]
    
    if not df.empty and student_id in df["ID"].values:
        # GÜNCELLEME
        idx = df[df["ID"] == student_id].index[0]
        for key, val in data_dict.items():
            df.at[idx, key] = val
    else:
        # YENİ KAYIT
        new_row = pd.DataFrame([data_dict])
        df = pd.concat([df, new_row], ignore_index=True)
    
    df = df.fillna(0) # Sayısal boşlukları 0 yap
    with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)
    return True

def delete_from_db(student_id):
    """ID'ye göre satırı siler."""
    df = load_db()
    if not df.empty and student_id in df["ID"].values:
        df = df[df["ID"] != student_id]
        with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)
        return True
    return False

def calculate_age_group(birth_date, test_date=None):
    if test_date is None: test_date = date.today()
    if isinstance(birth_date, str): b_date = pd.to_datetime(birth_date).date()
    else: b_date = birth_date
    if isinstance(test_date, str): t_date = pd.to_datetime(test_date).date()
    else: t_date = test_date
        
    diff_days = (t_date - b_date).days
    age_months = int(diff_days / 30.44)
    quarter = (age_months // 3) * 3
    return f"{quarter}-{quarter+2} Ay"

# =============================================================================
# 3. İSTATİSTİK VE GRAFİK
# =============================================================================
def get_stats(student_row, full_df):
    # Kendi cinsiyet ve yaş grubundakileri filtrele
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
st.sidebar.image("https://img.icons8.com/color/96/gymnastics.png", width=80)
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Yeni Kayıt / Veri Girişi", "2. Öğrenci Düzenle / Sil", "3. Gelişim Raporu", "4. Toplu Veri (Excel)"])

# --- MODÜL 1: YENİ KAYIT / VERİ GİRİŞİ ---
if menu == "1. Yeni Kayıt / Veri Girişi":
    st.header("📝 Veri Girişi")
    st.info("Yeni bir öğrenci girin veya mevcut bir öğrencinin adını yazarak testine devam edin.")

    # 1. Kimlik Bilgileri Formu
    with st.expander("Kimlik Bilgileri", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper()
        soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("Doğum Tarihi", date(2018, 1, 1))
        cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)
        
        c5, c6, c7, c8 = st.columns(4)
        test_tarihi = c5.date_input("Test Tarihi", date.today())
        test_yeri = c6.text_input("Test Yeri (Okul/Kulüp)").upper()
        el = c7.selectbox("Tercih Edilen El", ["Sağ", "Sol", "Belirsiz"])
        ayak = c8.selectbox("Tercih Edilen Ayak", ["Sağ", "Sol", "Belirsiz"])

    # 2. Akıllı Veritabanı Kontrolü
    active_id = None
    existing_data = {}
    
    if ad and soyad:
        active_id = generate_universal_id(ad, soyad, dt)
        df = load_db()
        
        if not df.empty and active_id in df["ID"].values:
            existing_data = df[df["ID"] == active_id].iloc[0].to_dict()
            st.success(f"📂 **Kayıt Bulundu:** {ad} {soyad}. Mevcut puanlar yüklendi. Değişiklik yapıp güncelleyebilirsiniz.")
        else:
            st.warning("🆕 **Yeni Kayıt:** Bu öğrenci için ilk kez kayıt oluşturulacak.")

        st.divider()

        # 3. Test Giriş Formu
        form_data = {}
        toplamlar = {}
        
        col_l, col_n = st.columns(2)
        
        with col_l:
            st.subheader("🏃 LOKOMOTOR")
            for test, items in PROTOCOL["LOKOMOTOR"].items():
                test_total = 0
                with st.expander(test):
                    for i, item in enumerate(items):
                        key_name = f"L_{test}_{i}"
                        default_val = int(existing_data.get(key_name, 0))
                        val = st.radio(item, [0, 1, 2], index=default_val, key=f"{key_name}_{active_id}", horizontal=True)
                        form_data[key_name] = val
                        test_total += val
                    st.caption(f"Toplam: {test_total}")
                    toplamlar[f"{test}_Toplam"] = test_total

        with col_n:
            st.subheader("🏀 NESNE KONTROL")
            for test, items in PROTOCOL["NESNE_KONTROL"].items():
                test_total = 0
                with st.expander(test):
                    for i, item in enumerate(items):
                        key_name = f"N_{test}_{i}"
                        default_val = int(existing_data.get(key_name, 0))
                        val = st.radio(item, [0, 1, 2], index=default_val, key=f"{key_name}_{active_id}", horizontal=True)
                        form_data[key_name] = val
                        test_total += val
                    st.caption(f"Toplam: {test_total}")
                    toplamlar[f"{test}_Toplam"] = test_total
        
        # 4. Kaydetme
        if st.button("💾 KAYDET / GÜNCELLE", type="primary"):
            final_record = {
                "ID": active_id, "Ad": ad, "Soyad": soyad, "DogumTarihi": str(dt),
                "Cinsiyet": cinsiyet, "TestTarihi": str(test_tarihi), "TestYeri": test_yeri,
                "TercihEl": el, "TercihAyak": ayak,
                "YasGrubu": calculate_age_group(dt, test_tarihi),
                "SonIslemTarihi": str(date.today())
            }
            final_record.update(form_data)
            final_record.update(toplamlar)
            
            save_to_db(final_record)
            st.success("Veriler başarıyla kaydedildi!")
            st.balloons()
            
    else:
        st.info("Lütfen veri girişi yapmak için isim ve doğum tarihi giriniz.")

# --- MODÜL 2: DÜZENLEME VE SİLME (İSTENEN ÖZELLİK) ---
elif menu == "2. Öğrenci Düzenle / Sil":
    st.header("🔧 Öğrenci Yönetimi")
    st.markdown("Mevcut öğrencileri buradan çağırıp bilgilerini düzenleyebilir veya silebilirsiniz.")
    
    df = load_db()
    if df.empty:
        st.warning("Veritabanında kayıtlı öğrenci yok.")
    else:
        # Seçim Kutusu
        df['Display'] = df['Ad'] + " " + df['Soyad'] + " (" + df['DogumTarihi'] + ")"
        selected_student = st.selectbox("Düzenlenecek Öğrenciyi Seçin:", df['Display'].unique())
        
        if selected_student:
            # Seçilen veriyi çek
            record = df[df['Display'] == selected_student].iloc[0]
            edit_id = record['ID']
            
            st.markdown("---")
            st.subheader("Kayıt Bilgileri")
            
            # Form (Mevcut bilgilerle dolu)
            with st.form("edit_form"):
                col1, col2 = st.columns(2)
                new_yer = col1.text_input("Test Yeri", value=str(record['TestYeri']))
                new_el = col2.selectbox("Tercih Edilen El", ["Sağ", "Sol", "Belirsiz"], index=["Sağ", "Sol", "Belirsiz"].index(record['TercihEl']) if record['TercihEl'] in ["Sağ", "Sol", "Belirsiz"] else 0)
                new_ayak = col2.selectbox("Tercih Edilen Ayak", ["Sağ", "Sol", "Belirsiz"], index=["Sağ", "Sol", "Belirsiz"].index(record['TercihAyak']) if record['TercihAyak'] in ["Sağ", "Sol", "Belirsiz"] else 0)
                
                # Not: Ad/Soyad/DT ID'yi bozacağı için buradan değiştirilmesini önermek risklidir,
                # ama basit düzeltmeler için izin verilebilir. Şimdilik sadece detayları düzenletiyoruz.
                
                update_btn = st.form_submit_button("Bilgileri Güncelle")
                
                if update_btn:
                    # Sadece ID dışı alanları güncelle
                    update_data = record.to_dict()
                    update_data['TestYeri'] = new_yer
                    update_data['TercihEl'] = new_el
                    update_data['TercihAyak'] = new_ayak
                    save_to_db(update_data)
                    st.success("Bilgiler güncellendi!")
                    st.rerun()

            st.markdown("---")
            st.subheader("🗑 Kayıt Silme")
            st.error("Dikkat: Bu işlem geri alınamaz!")
            if st.button("BU ÖĞRENCİYİ KALICI OLARAK SİL"):
                delete_from_db(edit_id)
                st.success("Öğrenci kaydı silindi.")
                st.rerun()

# --- MODÜL 3: RAPOR ---
elif menu == "3. Gelişim Raporu":
    st.header("📊 Gelişimsel Sonuç Raporu")
    df = load_db()
    
    if not df.empty:
        df['Display'] = df['Ad'] + " " + df['Soyad']
        choice = st.selectbox("Öğrenci Seç:", df['Display'].unique())
        
        if choice:
            row = df[df['Display'] == choice].iloc[0]
            stats = get_stats(row, df)
            
            st.markdown(f"**Öğrenci:** {row['Ad']} {row['Soyad']} | **Grup:** {row['Cinsiyet']} {row['YasGrubu']}")
            st.dataframe(stats, hide_index=True)
            
            # Grafik
            fig, ax = plt.subplots(figsize=(10, 4))
            x = np.arange(len(stats['Alt Test']))
            width = 0.35
            ax.bar(x - width/2, stats['Max'], width, label='Max', color='#eee')
            ax.bar(x + width/2, stats['Puan'], width, label='Öğrenci', color='#3498db')
            ax.set_xticks(x)
            ax.set_xticklabels(stats['Alt Test'], rotation=45)
            ax.legend()
            st.pyplot(fig)
            
            # PDF
            if st.button("PDF İndir"):
                pdf = FPDF()
                pdf.add_page()
                tr = str.maketrans("ğĞıİşŞüÜöÖçÇ", "gGiIsSuUoOcC")
                
                pdf.set_font("Arial", "B", 14)
                pdf.cell(0, 10, "TGMD-3 SONUC RAPORU", ln=True, align="C")
                pdf.set_font("Arial", size=10)
                
                info_text = f"""
                Ad Soyad: {row['Ad']} {row['Soyad']}
                Dogum Tarihi: {row['DogumTarihi']} | Yas Grubu: {row['YasGrubu']}
                Test Yeri: {row['TestYeri']} | Tarih: {row['TestTarihi']}
                El: {row['TercihEl']} | Ayak: {row['TercihAyak']}
                """
                pdf.multi_cell(0, 5, info_text.strip().translate(tr))
                pdf.ln(5)
                
                # Tablo
                pdf.set_font("Arial", "B", 9)
                headers = ["Test", "Puan", "Max", "Ort", "SS", "Z", "Durum"]
                w = [35, 15, 15, 15, 15, 20, 40]
                for i, h in enumerate(headers): pdf.cell(w[i], 7, h, 1)
                pdf.ln()
                
                pdf.set_font("Arial", size=9)
                for _, r in stats.iterrows():
                    pdf.cell(w[0], 7, r['Alt Test'].translate(tr), 1)
                    pdf.cell(w[1], 7, str(r['Puan']), 1)
                    pdf.cell(w[2], 7, str(r['Max']), 1)
                    pdf.cell(w[3], 7, str(r['Ort']), 1)
                    pdf.cell(w[4], 7, str(r['SS']), 1)
                    pdf.cell(w[5], 7, str(r['Z']), 1)
                    pdf.cell(w[6], 7, r['Durum'].translate(tr), 1)
                    pdf.ln()
                
                out = pdf.output(dest='S').encode('latin-1')
                st.download_button("Raporu İndir", out, "sonuc.pdf", "application/pdf")

# --- MODÜL 4: EXCEL ---
elif menu == "4. Toplu Veri (Excel)":
    st.header("💾 Excel Çıktısı")
    df = load_db()
    if not df.empty:
        st.dataframe(df.head())
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df.to_excel(writer, index=False)
        st.download_button("Tüm Veriyi İndir", buffer.getvalue(), "tgmd3_full.xlsx")
    else:
        st.info("Veri yok.")
