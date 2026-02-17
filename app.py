import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import hashlib
from datetime import date
import matplotlib.pyplot as plt
import scipy.stats as stats
from fpdf import FPDF

# =============================================================================
# 1. AYARLAR VE PROTOKOL
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO: Master Sürüm", layout="wide", page_icon="🎓")

FILE_NAME = "tgmd3_master_db.xlsx"

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

# --- Puan Yapılandırması ---
MAX_SCORES_SUBTEST = {} 
ITEM_COLUMNS = []

for domain in PROTOCOL:
    for test, items in PROTOCOL[domain].items():
        MAX_SCORES_SUBTEST[test] = len(items) * 2
        prefix = "L" if domain == "LOKOMOTOR" else "N"
        for i in range(len(items)):
            ITEM_COLUMNS.append(f"{prefix}_{test}_{i}_T1")
            ITEM_COLUMNS.append(f"{prefix}_{test}_{i}_T2")

SCORE_COLUMNS = [f"{test}_Toplam" for domain in PROTOCOL for test in PROTOCOL[domain]]
MAIN_SCORES = ["Lokomotor_Genel_Toplam", "Nesne_Genel_Toplam", "Kaba_Motor_Toplam"]
BASE_COLUMNS = ['TestID', 'OgrenciID', 'Ad', 'Soyad', 'Cinsiyet', 'DogumTarihi', 'TestTarihi', 'TestYeri', 'TercihEl', 'TercihAyak', 'YasGrubu', 'YasAy', 'SonIslemTarihi']
FULL_DB_COLUMNS = BASE_COLUMNS + MAIN_SCORES + SCORE_COLUMNS + ITEM_COLUMNS

# =============================================================================
# 2. FONKSİYONLAR
# =============================================================================
def generate_ids(ad, soyad, dogum_tarihi, test_tarihi):
    tr_map = str.maketrans("ğĞıİşŞüÜöÖçÇ", "gGiIsSuUoOcC")
    clean_ad = ad.strip().upper().translate(tr_map)
    clean_soyad = soyad.strip().upper().translate(tr_map)
    raw_student = f"{clean_ad}{clean_soyad}{str(dogum_tarihi)}"
    student_id = hashlib.md5(raw_student.encode('utf-8')).hexdigest()[:10]
    raw_test = f"{student_id}{str(test_tarihi)}"
    test_id = hashlib.md5(raw_test.encode('utf-8')).hexdigest()[:12]
    return student_id, test_id

def load_db():
    if not os.path.exists(FILE_NAME): return pd.DataFrame(columns=FULL_DB_COLUMNS)
    try:
        df = pd.read_excel(FILE_NAME)
        for col in FULL_DB_COLUMNS:
            if col not in df.columns: df[col] = "" if col in BASE_COLUMNS else 0
        for col in ['DogumTarihi', 'TestTarihi', 'Ad', 'Soyad', 'Cinsiyet', 'TestYeri', 'TercihEl', 'TercihAyak']:
            if col in df.columns: df[col] = df[col].astype(str).replace('nan', '')
        return df.fillna(0)
    except: return pd.DataFrame(columns=FULL_DB_COLUMNS)

def save_to_db(data_dict):
    df = load_db()
    test_id = data_dict["TestID"]
    data_dict["TestTarihi"] = str(data_dict["TestTarihi"])
    data_dict["DogumTarihi"] = str(data_dict["DogumTarihi"])
    
    if not df.empty and test_id in df["TestID"].values:
        idx = df[df["TestID"] == test_id].index[0]
        for key, val in data_dict.items(): df.at[idx, key] = val
    else:
        df = pd.concat([df, pd.DataFrame([data_dict])], ignore_index=True)
    with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer: df.to_excel(writer, index=False)
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

def get_z_comment(z):
    if z >= 1.5: return "Çok İleri"
    elif 0.5 <= z < 1.5: return "İleri"
    elif -0.5 <= z < 0.5: return "Normal"
    elif -1.5 <= z < -0.5: return "Geliştirilmeli"
    else: return "Risk Grubu"

def calculate_full_stats_table(student_row, full_df):
    """
    Hem Alt Testleri hem Ana Toplamları tek bir tabloda birleştirir.
    """
    # Norm Grubu: Aynı Cinsiyet + Aynı Yaş Grubu
    norm_group = full_df[
        (full_df['Cinsiyet'] == student_row['Cinsiyet']) & 
        (full_df['YasGrubu'] == student_row['YasGrubu'])
    ]
    
    rows = []
    
    # 1. ALT TESTLER
    for domain in PROTOCOL:
        for test in PROTOCOL[domain]:
            col = f"{test}_Toplam"
            puan = float(student_row.get(col, 0))
            max_p = MAX_SCORES_SUBTEST[test]
            
            if len(norm_group) > 1:
                ort = norm_group[col].mean()
                ss = norm_group[col].std(ddof=1)
                z = (puan - ort) / ss if ss > 0 else 0
            else:
                ort, ss, z = puan, 0, 0
                
            rows.append({
                "Kategori": "Alt Test",
                "Test Adı": test,
                "Puan": int(puan),
                "Max": max_p,
                "Grup Ort.": round(ort, 2),
                "SS": round(ss, 2),
                "Z-Skoru": round(z, 2),
                "Yorum": get_z_comment(z)
            })
            
    # 2. ANA ALANLAR
    mapping = {
        "Lokomotor Toplam": "Lokomotor_Genel_Toplam",
        "Nesne Kontrol Toplam": "Nesne_Genel_Toplam",
        "KABA MOTOR TOPLAM": "Kaba_Motor_Toplam"
    }
    
    max_loko = sum([MAX_SCORES_SUBTEST[t] for t in PROTOCOL["LOKOMOTOR"]])
    max_nesne = sum([MAX_SCORES_SUBTEST[t] for t in PROTOCOL["NESNE_KONTROL"]])
    max_map = {"Lokomotor Toplam": max_loko, "Nesne Kontrol Toplam": max_nesne, "KABA MOTOR TOPLAM": max_loko + max_nesne}

    for label, col in mapping.items():
        puan = float(student_row.get(col, 0))
        
        if len(norm_group) > 1:
            ort = norm_group[col].mean()
            ss = norm_group[col].std(ddof=1)
            z = (puan - ort) / ss if ss > 0 else 0
        else:
            ort, ss, z = puan, 0, 0
            
        rows.append({
            "Kategori": "ANA TOPLAM",
            "Test Adı": label,
            "Puan": int(puan),
            "Max": max_map[label],
            "Grup Ort.": round(ort, 2),
            "SS": round(ss, 2),
            "Z-Skoru": round(z, 2),
            "Yorum": get_z_comment(z)
        })
        
    return pd.DataFrame(rows)

# =============================================================================
# 3. ARAYÜZ
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Test Girişi", "2. Bireysel & Gelişim Raporu", "3. Veri Tabanı"])

if menu == "1. Test Girişi":
    st.header("📋 Test Veri Girişi")
    mode = st.radio("Seçim:", ["📂 Kayıtlı Öğrenci", "➕ Yeni Öğrenci"], horizontal=True)
    df = load_db()
    
    ad, soyad, cinsiyet = "", "", "Kız"
    dt = date(2018, 1, 1)
    ogrenci_id = None
    
    # Kimlik Bilgileri
    if mode == "📂 Kayıtlı Öğrenci":
        if df.empty: st.warning("Kayıt yok."); st.stop()
        uniqs = df[['OgrenciID', 'Ad', 'Soyad', 'DogumTarihi']].drop_duplicates(subset='OgrenciID')
        uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad'] + " (" + uniqs['DogumTarihi'] + ")"
        secim = st.selectbox("Öğrenci Seç:", uniqs['Etiket'], index=None)
        if secim:
            rec = uniqs[uniqs['Etiket'] == secim].iloc[0]
            ad, soyad, dt, ogrenci_id = rec['Ad'], rec['Soyad'], pd.to_datetime(rec['DogumTarihi']).date(), rec['OgrenciID']
            last = df[df['OgrenciID'] == ogrenci_id].iloc[-1]
            cinsiyet = last['Cinsiyet']
    else:
        c1,c2,c3,c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper(); soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("DT", date(2018, 1, 1)); cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)

    # Test Detayları
    if ad and soyad:
        st.divider()
        r1,r2,r3,r4 = st.columns(4)
        test_tarihi = r1.date_input("Test Tarihi", date.today()); test_yeri = r2.text_input("Yer").upper()
        el = r3.selectbox("El", ["Sağ","Sol"]); ayak = r4.selectbox("Ayak", ["Sağ","Sol"])
        
        if not ogrenci_id: ogrenci_id, test_id = generate_ids(ad, soyad, dt, test_tarihi)
        else: test_id = generate_ids(ad, soyad, dt, test_tarihi)[1]
        
        exist = {}
        if not df.empty and test_id in df['TestID'].values:
            st.warning("⚠️ Güncelleme Modu"); exist = df[df['TestID'] == test_id].iloc[0].to_dict()

        # Puanlama
        col_l, col_n = st.columns(2); form_data = {}; sub_totals = {}
        l_total = 0; n_total = 0
        
        with col_l:
            st.info("🏃 LOKOMOTOR")
            for t_name, items in PROTOCOL["LOKOMOTOR"].items():
                s_tot = 0
                with st.expander(t_name):
                    for i, item in enumerate(items):
                        k1 = f"L_{t_name}_{i}_T1"; k2 = f"L_{t_name}_{i}_T2"
                        c1, c2 = st.columns([3,1])
                        c1.write(item)
                        v1 = c2.checkbox("D1", bool(exist.get(k1,0)), key=f"{test_id}_{k1}")
                        v2 = c2.checkbox("D2", bool(exist.get(k2,0)), key=f"{test_id}_{k2}")
                        form_data[k1]=int(v1); form_data[k2]=int(v2); s_tot += int(v1)+int(v2)
                sub_totals[f"{t_name}_Toplam"] = s_tot; l_total += s_tot
        
        with col_n:
            st.info("🏀 NESNE KONTROL")
            for t_name, items in PROTOCOL["NESNE_KONTROL"].items():
                s_tot = 0
                with st.expander(t_name):
                    for i, item in enumerate(items):
                        k1 = f"N_{t_name}_{i}_T1"; k2 = f"N_{t_name}_{i}_T2"
                        c1, c2 = st.columns([3,1])
                        c1.write(item)
                        v1 = c2.checkbox("D1", bool(exist.get(k1,0)), key=f"{test_id}_{k1}")
                        v2 = c2.checkbox("D2", bool(exist.get(k2,0)), key=f"{test_id}_{k2}")
                        form_data[k1]=int(v1); form_data[k2]=int(v2); s_tot += int(v1)+int(v2)
                sub_totals[f"{t_name}_Toplam"] = s_tot; n_total += s_tot

        if st.button("💾 KAYDET", type="primary", use_container_width=True):
            ay, grup = calculate_age(dt, test_tarihi)
            rec = {
                "TestID": test_id, "OgrenciID": ogrenci_id, "Ad": ad, "Soyad": soyad, "DogumTarihi": dt, 
                "Cinsiyet": cinsiyet, "TestTarihi": test_tarihi, "TestYeri": test_yeri, "TercihEl": el, 
                "TercihAyak": ayak, "YasAy": ay, "YasGrubu": grup, "SonIslemTarihi": str(date.today()),
                "Lokomotor_Genel_Toplam": l_total, "Nesne_Genel_Toplam": n_total, 
                "Kaba_Motor_Toplam": l_total + n_total
            }
            rec.update(form_data); rec.update(sub_totals)
            save_to_db(rec); st.success("Kaydedildi!"); st.balloons()

elif menu == "2. Bireysel & Gelişim Raporu":
    st.header("📊 Detaylı Performans Karnesi")
    df = load_db()
    if df.empty: st.warning("Veri yok."); st.stop()

    # Öğrenci Seçimi
    uniqs = df[['OgrenciID', 'Ad', 'Soyad']].drop_duplicates(subset='OgrenciID')
    uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad']
    secim = st.selectbox("Öğrenci:", uniqs['Etiket'])
    
    if secim:
        oid = uniqs[uniqs['Etiket'] == secim].iloc[0]['OgrenciID']
        history = df[df['OgrenciID'] == oid].sort_values('TestTarihi')
        
        # Test Tarihi Seçimi
        dates = history['TestTarihi'].tolist()
        s_date = st.selectbox("Raporlanacak Test Tarihi:", dates, index=len(dates)-1)
        
        curr_rec = history[history['TestTarihi'] == s_date].iloc[0]
        
        # --- İSTATİSTİK HESAPLAMA ---
        stats_table = calculate_full_stats_table(curr_rec, df)
        
        # --- EKRAN GÖSTERİMİ ---
        st.subheader(f"Öğrenci: {curr_rec['Ad']} {curr_rec['Soyad']} | Tarih: {s_date}")
        st.markdown(f"**Grup:** {curr_rec['Cinsiyet']} - {curr_rec['YasGrubu']} | **Yer:** {curr_rec['TestYeri']}")
        
        # 1. TABLO (Renkli Z-Skor ile)
        def color_z(val):
            color = 'black'
            if val < -1: color = 'red'
            elif val > 1: color = 'green'
            return f'color: {color}'
            
        st.markdown("### 1. Detaylı Performans İstatistikleri")
        st.dataframe(
            stats_table.style.map(color_z, subset=['Z-Skoru']).format("{:.2f}", subset=['Grup Ort.', 'SS', 'Z-Skoru']),
            use_container_width=True,
            hide_index=True
        )
        
        # 2. GRAFİKLER (Yan Yana)
        st.markdown("### 2. Görsel Analiz")
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            # Alt Test Grafiği
            sub_data = stats_table[stats_table['Kategori'] == "Alt Test"]
            fig1, ax1 = plt.subplots(figsize=(8, 5))
            x = np.arange(len(sub_data))
            ax1.bar(x - 0.2, sub_data['Puan'], 0.4, label='Öğrenci', color='#3498db')
            ax1.bar(x + 0.2, sub_data['Grup Ort.'], 0.4, label='Grup Ort.', color='gray', alpha=0.5)
            ax1.set_xticks(x); ax1.set_xticklabels(sub_data['Test Adı'], rotation=45, ha='right')
            ax1.legend(); ax1.set_title("Alt Test Performansları")
            st.pyplot(fig1)
            
        with col_g2:
            # Norm Eğrisi (Kaba Motor İçin)
            km_z = float(stats_table[stats_table['Test Adı'] == "KABA MOTOR TOPLAM"]['Z-Skoru'].values[0])
            fig2, ax2 = plt.subplots(figsize=(8, 5))
            x_norm = np.linspace(-4, 4, 100)
            y_norm = stats.norm.pdf(x_norm, 0, 1)
            ax2.plot(x_norm, y_norm, 'k')
            ax2.fill_between(x_norm, y_norm, alpha=0.1)
            ax2.axvline(km_z, color='red', linestyle='--', label=f'Öğrenci (Z={km_z})')
            ax2.legend(); ax2.set_title("Genel Gelişim (Norm Eğrisi)")
            ax2.set_yticks([])
            st.pyplot(fig2)
            
        # 3. GELİŞİM GRAFİĞİ (Varsa)
        if len(history) > 1:
            st.markdown("### 3. Zaman İçindeki Gelişim")
            fig3, ax3 = plt.subplots(figsize=(10, 4))
            ax3.plot(history['TestTarihi'], history['Lokomotor_Genel_Toplam'], 'o-', label='Lokomotor')
            ax3.plot(history['TestTarihi'], history['Nesne_Genel_Toplam'], 's-', label='Nesne Kontrol')
            ax3.legend(); ax3.grid(True, linestyle='--')
            st.pyplot(fig3)

        # PDF İNDİRME
        if st.button("📄 PDF RAPORU İNDİR"):
            pdf = FPDF()
            pdf.add_page()
            tr = str.maketrans("ğĞıİşŞüÜöÖçÇ", "gGiIsSuUoOcC")
            
            # Başlık
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "TGMD-3 DETAYLI PERFORMANS RAPORU", ln=True, align="C")
            
            # Bilgi
            pdf.set_font("Arial", size=10)
            txt = f"Ad Soyad: {curr_rec['Ad']} {curr_rec['Soyad']}\nTarih: {s_date} | Yas Grubu: {curr_rec['YasGrubu']}"
            pdf.multi_cell(0, 5, txt.translate(tr))
            pdf.ln(5)
            
            # Tablo
            pdf.set_font("Arial", "B", 8)
            headers = ["Test Adi", "Puan", "Max", "Ort", "SS", "Z", "Yorum"]
            w = [45, 15, 15, 15, 15, 15, 35]
            for i, h in enumerate(headers): pdf.cell(w[i], 7, h, 1)
            pdf.ln()
            
            pdf.set_font("Arial", size=8)
            for _, r in stats_table.iterrows():
                # Kategori ayrımı için koyu font
                if r['Kategori'] == "ANA TOPLAM": pdf.set_font("Arial", "B", 8)
                else: pdf.set_font("Arial", "", 8)
                
                pdf.cell(w[0], 7, r['Test Adı'].translate(tr), 1)
                pdf.cell(w[1], 7, str(r['Puan']), 1)
                pdf.cell(w[2], 7, str(r['Max']), 1)
                pdf.cell(w[3], 7, f"{r['Grup Ort.']:.2f}", 1)
                pdf.cell(w[4], 7, f"{r['SS']:.2f}", 1)
                pdf.cell(w[5], 7, f"{r['Z-Skoru']:.2f}", 1)
                pdf.cell(w[6], 7, r['Yorum'].translate(tr), 1)
                pdf.ln()
                
            st.download_button("İndir", pdf.output(dest='S').encode('latin-1'), "rapor.pdf")

elif menu == "3. Veri Tabanı":
    st.header("💾 Excel Çıktısı")
    df = load_db()
    if not df.empty:
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
        st.download_button("Excel İndir", buffer.getvalue(), "tgmd3_data.xlsx")
    else: st.warning("Veri yok.")
