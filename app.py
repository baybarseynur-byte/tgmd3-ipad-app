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
        return df.fillna(0)
    except: return pd.DataFrame(columns=FULL_DB_COLUMNS)

def save_to_db(data_dict):
    df = load_db()
    test_id = data_dict["TestID"]
    if not df.empty and test_id in df["TestID"].values:
        idx = df[df["TestID"] == test_id].index[0]
        for key, val in data_dict.items(): df.at[idx, key] = val
    else:
        df = pd.concat([df, pd.DataFrame([data_dict])], ignore_index=True)
    df.to_excel(FILE_NAME, index=False)
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
    if z >= 1.5: return "Cok Ileri"
    elif 0.5 <= z < 1.5: return "Ileri"
    elif -0.5 <= z < 0.5: return "Normal"
    elif -1.5 <= z < -0.5: return "Gelistirilmeli"
    else: return "Risk Grubu"

def calculate_full_stats_table(student_row, full_df):
    norm_group = full_df[(full_df['Cinsiyet'] == student_row['Cinsiyet']) & (full_df['YasGrubu'] == student_row['YasGrubu'])]
    rows = []
    for domain in PROTOCOL:
        for test in PROTOCOL[domain]:
            col = f"{test}_Toplam"
            puan = float(student_row.get(col, 0))
            max_p = MAX_SCORES_SUBTEST[test]
            if len(norm_group) > 1:
                ort = norm_group[col].mean(); ss = norm_group[col].std(ddof=1)
                z = (puan - ort) / ss if ss > 0 else 0
            else: ort, ss, z = puan, 0, 0
            rows.append({"Kategori": "Alt Test", "Test Adı": test, "Puan": int(puan), "Max": max_p, "Grup Ort.": round(ort, 2), "SS": round(ss, 2), "Z-Skoru": round(z, 2), "Yorum": get_z_comment(z)})
    mapping = {"Lokomotor Toplam": "Lokomotor_Genel_Toplam", "Nesne Kontrol Toplam": "Nesne_Genel_Toplam", "KABA MOTOR TOPLAM": "Kaba_Motor_Toplam"}
    max_loko = sum([MAX_SCORES_SUBTEST[t] for t in PROTOCOL["LOKOMOTOR"]])
    max_nesne = sum([MAX_SCORES_SUBTEST[t] for t in PROTOCOL["NESNE_KONTROL"]])
    max_map = {"Lokomotor Toplam": max_loko, "Nesne Kontrol Toplam": max_nesne, "KABA MOTOR TOPLAM": max_loko + max_nesne}
    for label, col in mapping.items():
        puan = float(student_row.get(col, 0))
        if len(norm_group) > 1:
            ort = norm_group[col].mean(); ss = norm_group[col].std(ddof=1)
            z = (puan - ort) / ss if ss > 0 else 0
        else: ort, ss, z = puan, 0, 0
        rows.append({"Kategori": "ANA TOPLAM", "Test Adı": label, "Puan": int(puan), "Max": max_map[label], "Grup Ort.": round(ort, 2), "SS": round(ss, 2), "Z-Skoru": round(z, 2), "Yorum": get_z_comment(z)})
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
    if mode == "📂 Kayıtlı Öğrenci":
        if df.empty: st.warning("Kayıt yok."); st.stop()
        uniqs = df[['OgrenciID', 'Ad', 'Soyad', 'DogumTarihi']].drop_duplicates(subset='OgrenciID')
        uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad'] + " (" + str(uniqs['DogumTarihi']) + ")"
        secim = st.selectbox("Öğrenci Seç:", uniqs['Etiket'], index=None)
        if secim:
            rec = uniqs[uniqs['Etiket'] == secim].iloc[0]
            ad, soyad, dt, ogrenci_id = rec['Ad'], rec['Soyad'], pd.to_datetime(rec['DogumTarihi']).date(), rec['OgrenciID']
            cinsiyet = df[df['OgrenciID'] == ogrenci_id].iloc[-1]['Cinsiyet']
    else:
        c1,c2,c3,c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper(); soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("DT", date(2018, 1, 1)); cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)

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
        col_l, col_n = st.columns(2); form_data = {}; sub_totals = {}
        l_total, n_total = 0, 0
        with col_l:
            st.info("🏃 LOKOMOTOR")
            for t_name, items in PROTOCOL["LOKOMOTOR"].items():
                s_tot = 0
                with st.expander(t_name):
                    for i, item in enumerate(items):
                        k1, k2 = f"L_{t_name}_{i}_T1", f"L_{t_name}_{i}_T2"
                        c1, c2 = st.columns([3,1])
                        c1.write(item)
                        v1 = c2.checkbox("D1", bool(exist.get(k1,0)), key=f"{test_id}_{k1}")
                        v2 = c2.checkbox("D2", bool(exist.get(k2,0)), key=f"{test_id}_{k2}")
                        form_data[k1], form_data[k2] = int(v1), int(v2); s_tot += int(v1)+int(v2)
                sub_totals[f"{t_name}_Toplam"] = s_tot; l_total += s_tot
        with col_n:
            st.info("🏀 NESNE KONTROL")
            for t_name, items in PROTOCOL["NESNE_KONTROL"].items():
                s_tot = 0
                with st.expander(t_name):
                    for i, item in enumerate(items):
                        k1, k2 = f"N_{t_name}_{i}_T1", f"N_{t_name}_{i}_T2"
                        c1, c2 = st.columns([3,1])
                        c1.write(item)
                        v1 = c2.checkbox("D1", bool(exist.get(k1,0)), key=f"{test_id}_{k1}")
                        v2 = c2.checkbox("D2", bool(exist.get(k2,0)), key=f"{test_id}_{k2}")
                        form_data[k1], form_data[k2] = int(v1), int(v2); s_tot += int(v1)+int(v2)
                sub_totals[f"{t_name}_Toplam"] = s_tot; n_total += s_tot
        if st.button("💾 KAYDET", type="primary", use_container_width=True):
            ay, grup = calculate_age(dt, test_tarihi)
            rec = {"TestID": test_id, "OgrenciID": ogrenci_id, "Ad": ad, "Soyad": soyad, "DogumTarihi": str(dt), "Cinsiyet": cinsiyet, "TestTarihi": str(test_tarihi), "TestYeri": test_yeri, "TercihEl": el, "TercihAyak": ayak, "YasAy": ay, "YasGrubu": grup, "SonIslemTarihi": str(date.today()), "Lokomotor_Genel_Toplam": l_total, "Nesne_Genel_Toplam": n_total, "Kaba_Motor_Toplam": l_total + n_total}
            rec.update(form_data); rec.update(sub_totals)
            save_to_db(rec); st.success("Kaydedildi!"); st.balloons()

elif menu == "2. Bireysel & Gelişim Raporu":
    st.header("📊 Detaylı Performans Karnesi")
    df = load_db()
    if df.empty: st.warning("Veri yok."); st.stop()
    uniqs = df[['OgrenciID', 'Ad', 'Soyad']].drop_duplicates(subset='OgrenciID')
    uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad']
    secim = st.selectbox("Öğrenci:", uniqs['Etiket'])
    if secim:
        oid = uniqs[uniqs['Etiket'] == secim].iloc[0]['OgrenciID']
        history = df[df['OgrenciID'] == oid].sort_values('TestTarihi')
        dates = history['TestTarihi'].tolist()
        s_date = st.selectbox("Rapor Tarihi:", dates, index=len(dates)-1)
        curr_rec = history[history['TestTarihi'] == s_date].iloc[0]
        stats_table = calculate_full_stats_table(curr_rec, df)
        
        st.subheader(f"{curr_rec['Ad']} {curr_rec['Soyad']} | {s_date}")
        st.markdown("### 1. Detaylı Performans İstatistikleri")
        st.dataframe(stats_table, use_container_width=True, hide_index=True)
        
        st.markdown("### 2. Görsel Analiz (Radar ve Norm Eğrisi)")
        col_g1, col_g2 = st.columns(2)
        sub_data = stats_table[stats_table['Kategori'] == "Alt Test"]
        categories = sub_data['Test Adı'].tolist()
        student_pct = [(s / m) * 100 for s, m in zip(sub_data['Puan'], sub_data['Max'])]
        group_pct = [(g / m) * 100 for g, m in zip(sub_data['Grup Ort.'], sub_data['Max'])]
        angles = np.linspace(0, 2 * np.pi, len(categories), endpoint=False).tolist()
        student_pct += student_pct[:1]; group_pct += group_pct[:1]; angles += angles[:1]
        fig1, ax1 = plt.subplots(figsize=(6, 6), subplot_kw=dict(polar=True))
        ax1.plot(angles, student_pct, color='#3498db', linewidth=2, label='Öğrenci (%)')
        ax1.fill(angles, student_pct, color='#3498db', alpha=0.25)
        ax1.plot(angles, group_pct, color='gray', linestyle='dashed', label='Grup Ort. (%)')
        ax1.set_xticks(angles[:-1]); ax1.set_xticklabels(categories, fontsize=8)
        ax1.set_ylim(0, 100); ax1.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1))
        with col_g1: st.pyplot(fig1)
        km_z = float(stats_table[stats_table['Test Adı'] == "KABA MOTOR TOPLAM"]['Z-Skoru'].values[0])
        fig2, ax2 = plt.subplots(figsize=(8, 6))
        x_norm = np.linspace(-4, 4, 100); y_norm = stats.norm.pdf(x_norm, 0, 1)
        ax2.plot(x_norm, y_norm, 'k')
        ax2.fill_between(x_norm, y_norm, where=(x_norm >= -1) & (x_norm <= 1), color='green', alpha=0.2)
        ax2.axvline(km_z, color='red', linestyle='--', label=f'Öğrenci (Z={km_z})')
        ax2.legend(); ax2.set_title("Genel Gelişim (Norm Eğrisi)")
        with col_g2: st.pyplot(fig2)
        fig3 = None
        if len(history) > 1:
            st.markdown("### 3. Zaman İçindeki Gelişim")
            fig3, ax3 = plt.subplots(figsize=(10, 4))
            ax3.plot(history['TestTarihi'], history['Lokomotor_Genel_Toplam'], 'o-', label='Lokomotor')
            ax3.plot(history['TestTarihi'], history['Nesne_Genel_Toplam'], 's-', label='Nesne Kontrol')
            ax3.legend(); ax3.grid(True)
            st.pyplot(fig3)

        # --- PDF OLUŞTURMA (YENİ DÜZEN) ---
        if st.button("📄 PDF RAPORU İNDİR"):
            pdf = FPDF()
            pdf.add_page()
            tr = str.maketrans("ğĞıİşŞüÜöÖçÇ", "gGiIsSuUoOcC")
            
            # 1. ÜST: ÖĞRENCİ BİLGİLERİ (ORTALANMIŞ)
            pdf.set_font("Arial", "B", 16)
            pdf.cell(0, 10, "TGMD-3 PERFORMANS KARNESI", ln=True, align="C")
            pdf.set_font("Arial", "B", 12)
            pdf.cell(0, 10, f"Ogrenci: {curr_rec['Ad']} {curr_rec['Soyad']}".translate(tr), ln=True, align="C")
            pdf.set_font("Arial", size=10)
            pdf.cell(0, 7, f"Test Tarihi: {s_date} | Yas Grubu: {curr_rec['YasGrubu']} | Cinsiyet: {curr_rec['Cinsiyet']}".translate(tr), ln=True, align="C")
            pdf.ln(5)

            # 2. ORTA: GRAFİKLER (YAN YANA)
            fig1.savefig("temp_radar.png", format="png", bbox_inches='tight')
            fig2.savefig("temp_norm.png", format="png", bbox_inches='tight')
            pdf.image("temp_radar.png", x=10, y=45, w=90)
            pdf.image("temp_norm.png", x=105, y=45, w=95)
            pdf.ln(85) # Grafiklerden sonra boşluk bırak

            # 3. ALT: TEST PUANLARI TABLOSU
            pdf.set_font("Arial", "B", 11)
            pdf.cell(0, 10, "Detayli Test Puanlari ve Analiz", ln=True, align="L")
            headers = ["Test Adi", "Puan", "Max", "Ort", "Z", "Yorum"]
            w = [45, 15, 15, 20, 20, 40]
            pdf.set_font("Arial", "B", 8)
            for i, h in enumerate(headers): pdf.cell(w[i], 7, h, 1, 0, 'C')
            pdf.ln()
            pdf.set_font("Arial", size=8)
            for _, r in stats_table.iterrows():
                # Ana toplamları kalın yap
                if r['Kategori'] == "ANA TOPLAM": pdf.set_font("Arial", "B", 8)
                else: pdf.set_font("Arial", "", 8)
                pdf.cell(w[0], 7, r['Test Adı'].translate(tr), 1)
                pdf.cell(w[1], 7, str(r['Puan']), 1, 0, 'C')
                pdf.cell(w[2], 7, str(r['Max']), 1, 0, 'C')
                pdf.cell(w[3], 7, str(r['Grup Ort.']), 1, 0, 'C')
                pdf.cell(w[4], 7, str(r['Z-Skoru']), 1, 0, 'C')
                pdf.cell(w[5], 7, r['Yorum'].translate(tr), 1); pdf.ln()

            # 4. (OPSİYONEL) SAYFA 2: GELİŞİM GRAFİĞİ
            if fig3:
                pdf.add_page()
                pdf.set_font("Arial", "B", 12)
                pdf.cell(0, 10, "Zaman Icindeki Gelisim Grafigi", ln=True)
                fig3.savefig("temp_gelisim.png", format="png", bbox_inches='tight')
                pdf.image("temp_gelisim.png", x=10, y=30, w=180)

            # Temizlik ve Çıktı
            pdf_data = pdf.output(dest='S').encode('latin-1')
            for f in ["temp_radar.png", "temp_norm.png", "temp_gelisim.png"]:
                if os.path.exists(f): os.remove(f)
            st.download_button("İndir", pdf_data, f"Rapor_{curr_rec['Ad']}.pdf")

elif menu == "3. Veri Tabanı":
    st.header("💾 Veri Yönetimi")
    df = load_db()
    if not df.empty:
        st.dataframe(df)
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
        st.download_button("Excel Olarak İndir", buffer.getvalue(), "tgmd3_data.xlsx")
