import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import hashlib
from datetime import date
import matplotlib.pyplot as plt
import scipy.stats as stats

# =============================================================================
# 1. AYARLAR VE PROTOKOL
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO: Tam Protokol", layout="wide", page_icon="🧬")

FILE_NAME = "tgmd3_final_db.xlsx"

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

# --- SÜTUN YAPILANDIRMASI ---
# Her madde için T1 (Trial 1) ve T2 (Trial 2) saklanacak
ITEM_COLUMNS = []
MAX_SCORES_SUBTEST = {} # Alt test bazlı max puan (Örn: Koşu Max = 8)

for domain in PROTOCOL:
    for test, items in PROTOCOL[domain].items():
        # Max Puan: Madde Sayısı * 2 (Çünkü her madde 2 deneme)
        MAX_SCORES_SUBTEST[test] = len(items) * 2
        prefix = "L" if domain == "LOKOMOTOR" else "N"
        for i in range(len(items)):
            ITEM_COLUMNS.append(f"{prefix}_{test}_{i}_T1") # Deneme 1
            ITEM_COLUMNS.append(f"{prefix}_{test}_{i}_T2") # Deneme 2

# Toplam Puan Sütunları
SCORE_COLUMNS = [f"{test}_Toplam" for domain in PROTOCOL for test in PROTOCOL[domain]]
MAIN_SCORES = ["Lokomotor_Genel_Toplam", "Nesne_Genel_Toplam", "Kaba_Motor_Toplam"]

BASE_COLUMNS = ['TestID', 'OgrenciID', 'Ad', 'Soyad', 'Cinsiyet', 'DogumTarihi', 'TestTarihi', 'TestYeri', 'TercihEl', 'TercihAyak', 'YasGrubu', 'YasAy', 'SonIslemTarihi']
FULL_DB_COLUMNS = BASE_COLUMNS + MAIN_SCORES + SCORE_COLUMNS + ITEM_COLUMNS

# =============================================================================
# 2. YARDIMCI FONKSİYONLAR
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
        # Eksik sütun tamamlama
        for col in FULL_DB_COLUMNS:
            if col not in df.columns: df[col] = "" if col in BASE_COLUMNS else 0
        # String dönüşümleri
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
    if z >= 1.5: return "Çok İleri (Üstün)"
    elif 0.5 <= z < 1.5: return "Ortalama Üstü"
    elif -0.5 <= z < 0.5: return "Ortalama (Normal)"
    elif -1.5 <= z < -0.5: return "Ortalama Altı"
    else: return "Gelişimsel Gecikme Riski"

def draw_bell_curve(z_score, title, ax):
    """
    Belirtilen Z-Skoru için Normal Dağılım Grafiği çizer.
    """
    x = np.linspace(-4, 4, 1000)
    y = stats.norm.pdf(x, 0, 1)
    
    # Eğriyi çiz
    ax.plot(x, y, color='black', lw=2)
    ax.fill_between(x, y, alpha=0.1, color='gray')
    
    # Z-Skoru çizgisi
    ax.axvline(z_score, color='red', linestyle='--', lw=2, label=f'Öğrenci: {z_score}')
    
    # Bölgeleri renklendir
    # Ortalama Alanı (-1 ile +1 arası)
    ax.fill_between(x, y, where=(x >= -1) & (x <= 1), color='green', alpha=0.2, label='Normal Aralık')
    
    ax.set_title(title, fontsize=10)
    ax.set_yticks([]) # Y ekseni değerlerini gizle
    ax.legend(loc='upper right', fontsize=8)
    
    # X ekseni etiketleri
    ax.set_xticks([-3, -2, -1, 0, 1, 2, 3])
    ax.set_xticklabels(['-3SS', '-2SS', '-1SS', 'Ort', '+1SS', '+2SS', '+3SS'])

def calculate_full_stats(student_row, full_df):
    """
    Hem alt testler hem de Ana Toplamlar (Loko, Nesne, Kaba Motor) için istatistik üretir.
    """
    norm_group = full_df[
        (full_df['Cinsiyet'] == student_row['Cinsiyet']) & 
        (full_df['YasGrubu'] == student_row['YasGrubu'])
    ]
    
    # 1. Alt Test İstatistikleri
    subtest_stats = []
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
                
            subtest_stats.append({
                "Kategori": "Alt Test",
                "Başlık": test,
                "Puan": int(puan),
                "Max": max_p,
                "Grup Ort.": round(ort, 2),
                "Z-Skoru": round(z, 2),
                "Yorum": get_z_comment(z)
            })
            
    # 2. Ana Alan İstatistikleri (Loko, Nesne, Kaba Motor)
    main_stats = []
    
    # Hesaplama Kolaylığı İçin Mapping
    mapping = {
        "Lokomotor Beceriler": "Lokomotor_Genel_Toplam",
        "Nesne Kontrol Becerileri": "Nesne_Genel_Toplam",
        "KABA MOTOR TOPLAM": "Kaba_Motor_Toplam"
    }
    
    # Max Puanlar (Ana Alanlar İçin)
    max_loko = sum([MAX_SCORES_SUBTEST[t] for t in PROTOCOL["LOKOMOTOR"]])
    max_nesne = sum([MAX_SCORES_SUBTEST[t] for t in PROTOCOL["NESNE_KONTROL"]])
    max_kaba = max_loko + max_nesne
    max_map = {"Lokomotor Beceriler": max_loko, "Nesne Kontrol Becerileri": max_nesne, "KABA MOTOR TOPLAM": max_kaba}

    for label, col in mapping.items():
        puan = float(student_row.get(col, 0))
        
        if len(norm_group) > 1:
            ort = norm_group[col].mean()
            ss = norm_group[col].std(ddof=1)
            z = (puan - ort) / ss if ss > 0 else 0
        else:
            ort, ss, z = puan, 0, 0
            
        main_stats.append({
            "Kategori": "Ana Alan",
            "Başlık": label,
            "Puan": int(puan),
            "Max": max_map[label],
            "Grup Ort.": round(ort, 2),
            "Z-Skoru": round(z, 2),
            "Yorum": get_z_comment(z)
        })

    return pd.DataFrame(subtest_stats), pd.DataFrame(main_stats)

# =============================================================================
# 3. ARAYÜZ
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Test Girişi (Çift Deneme)", "2. Kapsamlı Raporlama", "3. Veri Tabanı"])

if menu == "1. Test Girişi (Çift Deneme)":
    st.header("📋 TGMD-3 Test Girişi (Prosedürel Uyumlu)")
    st.info("ℹ️ Protokol Gereği: Her beceri kriteri için öğrenciye 2 deneme hakkı verilir. Her deneme Başarılı (1) veya Başarısız (0) olarak işaretlenir.")
    
    mode = st.radio("Mod:", ["📂 Kayıtlı Öğrenci", "➕ Yeni Öğrenci"], horizontal=True)
    df = load_db()
    
    # Varsayılanlar
    ad, soyad, cinsiyet = "", "", "Kız"
    dt = date(2018, 1, 1)
    test_tarihi = date.today(); test_yeri = ""; el = "Sağ"; ayak = "Sağ"
    ogrenci_id = None
    
    if mode == "📂 Kayıtlı Öğrenci":
        if df.empty: st.warning("Kayıt yok."); st.stop()
        uniqs = df[['OgrenciID', 'Ad', 'Soyad', 'DogumTarihi']].drop_duplicates(subset='OgrenciID')
        uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad'] + " (" + uniqs['DogumTarihi'] + ")"
        secim = st.selectbox("Öğrenci Seç:", uniqs['Etiket'], index=None)
        if secim:
            rec = uniqs[uniqs['Etiket'] == secim].iloc[0]
            ad, soyad, dt, ogrenci_id = rec['Ad'], rec['Soyad'], pd.to_datetime(rec['DogumTarihi']).date(), rec['OgrenciID']
            last = df[df['OgrenciID'] == ogrenci_id].iloc[-1]
            cinsiyet, test_yeri, el, ayak = last['Cinsiyet'], last['TestYeri'], last['TercihEl'], last['TercihAyak']
    else:
        c1,c2,c3,c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper(); soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("DT", date(2018, 1, 1)); cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)

    if ad and soyad:
        st.markdown("---")
        r1,r2,r3,r4 = st.columns(4)
        test_tarihi = r1.date_input("Test Tarihi", date.today()); test_yeri = r2.text_input("Yer", test_yeri)
        el = r3.selectbox("El", ["Sağ","Sol"], index=0 if el=="Sağ" else 1)
        ayak = r4.selectbox("Ayak", ["Sağ","Sol"], index=0 if ayak=="Sağ" else 1)
        
        if not ogrenci_id: ogrenci_id, test_id = generate_ids(ad, soyad, dt, test_tarihi)
        else: test_id = generate_ids(ad, soyad, dt, test_tarihi)[1]
        
        exist = {}
        if not df.empty and test_id in df['TestID'].values:
            st.warning("⚠️ Bu tarihte kayıt var. Güncelleme yapıyorsunuz."); exist = df[df['TestID'] == test_id].iloc[0].to_dict()

        # --- PUANLAMA LOOP ---
        col_l, col_n = st.columns(2)
        form_data = {}
        
        # Puan Sayaçları
        loko_grand_total = 0
        nesne_grand_total = 0
        
        subtest_totals = {} # Her alt testin toplamı için

        # LOKOMOTOR
        with col_l:
            st.subheader("🏃 LOKOMOTOR")
            for t_name, items in PROTOCOL["LOKOMOTOR"].items():
                st.markdown(f"**{t_name}**")
                sub_total = 0
                with st.expander(f"{t_name} Kriterleri", expanded=False):
                    for i, item in enumerate(items):
                        # İki Deneme İçin Keyler
                        k1 = f"L_{t_name}_{i}_T1"
                        k2 = f"L_{t_name}_{i}_T2"
                        
                        # Checkboxlar
                        c_row1, c_row2 = st.columns([3, 1])
                        c_row1.write(f"{i+1}. {item}")
                        
                        # Deneme 1 ve 2
                        val1 = c_row2.checkbox("D1", value=bool(exist.get(k1, 0)), key=f"{test_id}_{k1}")
                        val2 = c_row2.checkbox("D2", value=bool(exist.get(k2, 0)), key=f"{test_id}_{k2}")
                        
                        # Veriye kaydet
                        form_data[k1] = int(val1)
                        form_data[k2] = int(val2)
                        
                        # Toplam hesabı
                        item_score = int(val1) + int(val2)
                        sub_total += item_score
                
                # Alt test toplamını kaydet
                subtest_totals[f"{t_name}_Toplam"] = sub_total
                loko_grand_total += sub_total
                st.info(f"{t_name} Puanı: {sub_total} / {MAX_SCORES_SUBTEST[t_name]}")

        # NESNE KONTROL
        with col_n:
            st.subheader("🏀 NESNE KONTROL")
            for t_name, items in PROTOCOL["NESNE_KONTROL"].items():
                st.markdown(f"**{t_name}**")
                sub_total = 0
                with st.expander(f"{t_name} Kriterleri", expanded=False):
                    for i, item in enumerate(items):
                        k1 = f"N_{t_name}_{i}_T1"
                        k2 = f"N_{t_name}_{i}_T2"
                        
                        c_row1, c_row2 = st.columns([3, 1])
                        c_row1.write(f"{i+1}. {item}")
                        
                        val1 = c_row2.checkbox("D1", value=bool(exist.get(k1, 0)), key=f"{test_id}_{k1}")
                        val2 = c_row2.checkbox("D2", value=bool(exist.get(k2, 0)), key=f"{test_id}_{k2}")
                        
                        form_data[k1] = int(val1)
                        form_data[k2] = int(val2)
                        item_score = int(val1) + int(val2)
                        sub_total += item_score
                
                subtest_totals[f"{t_name}_Toplam"] = sub_total
                nesne_grand_total += sub_total
                st.info(f"{t_name} Puanı: {sub_total} / {MAX_SCORES_SUBTEST[t_name]}")

        # ANA TOPLAMLARI HESAPLA
        grand_totals = {
            "Lokomotor_Genel_Toplam": loko_grand_total,
            "Nesne_Genel_Toplam": nesne_grand_total,
            "Kaba_Motor_Toplam": loko_grand_total + nesne_grand_total
        }

        st.success(f"📊 ÖZET: Lokomotor ({loko_grand_total}) + Nesne ({nesne_grand_total}) = Kaba Motor ({loko_grand_total + nesne_grand_total})")

        if st.button("💾 TÜM SONUÇLARI KAYDET", type="primary", use_container_width=True):
            ay, grup = calculate_age(dt, test_tarihi)
            rec = {
                "TestID": test_id, "OgrenciID": ogrenci_id,
                "Ad": ad, "Soyad": soyad, "DogumTarihi": dt, "Cinsiyet": cinsiyet,
                "TestTarihi": test_tarihi, "TestYeri": test_yeri,
                "TercihEl": el, "TercihAyak": ayak,
                "YasAy": ay, "YasGrubu": grup,
                "SonIslemTarihi": str(date.today())
            }
            rec.update(form_data)
            rec.update(subtest_totals)
            rec.update(grand_totals)
            
            save_to_db(rec)
            st.balloons()
            st.success("Test başarıyla veritabanına işlendi.")

elif menu == "2. Kapsamlı Raporlama":
    st.header("📊 Bireysel Performans ve Norm Raporu")
    df = load_db()
    if df.empty: st.warning("Veri yok."); st.stop()
    
    # Seçimler
    uniqs = df[['OgrenciID', 'Ad', 'Soyad']].drop_duplicates(subset='OgrenciID')
    uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad']
    secim = st.selectbox("Öğrenci:", uniqs['Etiket'])
    
    if secim:
        oid = uniqs[uniqs['Etiket'] == secim].iloc[0]['OgrenciID']
        history = df[df['OgrenciID'] == oid].sort_values('TestTarihi')
        
        t_date = st.selectbox("Test Tarihi:", history['TestTarihi'].tolist(), index=len(history)-1)
        record = history[history['TestTarihi'] == t_date].iloc[0]
        
        # İstatistikleri Hesapla
        sub_stats, main_stats = calculate_full_stats(record, df)
        
        # --- TAB 1: GENEL BECERİ DEĞERLENDİRMESİ ---
        st.subheader(f"Rapor: {record['Ad']} {record['Soyad']} ({t_date}) - {record['YasGrubu']}")
        
        c1, c2 = st.columns([1, 2])
        
        with c1:
            st.markdown("### 🏆 Kaba Motor Karnesi")
            
            # Kaba Motor Satırını Bul
            km_row = main_stats[main_stats['Başlık'] == "KABA MOTOR TOPLAM"].iloc[0]
            
            st.metric("Kaba Motor Toplam Puan", f"{km_row['Puan']} / {km_row['Max']}")
            st.metric("Z-Skoru", f"{km_row['Z-Skoru']}")
            
            st.info(f"**Yorum:** {km_row['Yorum']}")
            st.markdown(f"""
            *Bu öğrenci, kendi yaş ve cinsiyet grubuna göre **{km_row['Yorum']}** düzeyindedir.*
            """)

        with c2:
            st.markdown("### 🔔 Norm Dağılım Grafiği (Çan Eğrisi)")
            # Bell Curve Çizimi
            fig_bell, ax_bell = plt.subplots(figsize=(8, 4))
            draw_bell_curve(float(km_row['Z-Skoru']), "Kaba Motor Becerisi - Popülasyondaki Yeri", ax_bell)
            st.pyplot(fig_bell)

        # --- TAB 2: DETAYLI TABLOLAR ---
        st.markdown("---")
        t1, t2 = st.tabs(["📌 Ana Alan Puanları", "🧩 Alt Test Detayları"])
        
        with t1:
            st.dataframe(main_stats.style.format({"Grup Ort.": "{:.2f}", "Z-Skoru": "{:.2f}"}), use_container_width=True, hide_index=True)
            
            # Alan Grafiği
            fig_main, ax_main = plt.subplots(figsize=(10, 4))
            x = np.arange(len(main_stats))
            ax_main.bar(x - 0.2, main_stats['Puan'], 0.4, label='Öğrenci', color='#3498db')
            ax_main.bar(x + 0.2, main_stats['Grup Ort.'], 0.4, label='Grup Ort.', color='#95a5a6')
            ax_main.set_xticks(x)
            ax_main.set_xticklabels(main_stats['Başlık'])
            ax_main.legend()
            ax_main.set_title("Lokomotor vs Nesne Kontrol Karşılaştırması")
            st.pyplot(fig_main)

        with t2:
            st.dataframe(sub_stats.style.format({"Grup Ort.": "{:.2f}", "Z-Skoru": "{:.2f}"}), use_container_width=True, hide_index=True)
            
            # Alt Test Grafiği
            fig_sub, ax_sub = plt.subplots(figsize=(12, 5))
            x_sub = np.arange(len(sub_stats))
            ax_sub.bar(x_sub, sub_stats['Puan'], color='#e74c3c', alpha=0.7, label='Öğrenci Puanı')
            ax_sub.plot(x_sub, sub_stats['Grup Ort.'], color='black', marker='o', linestyle='--', label='Grup Ortalaması')
            ax_sub.set_xticks(x_sub)
            ax_sub.set_xticklabels(sub_stats['Başlık'], rotation=45, ha="right")
            ax_sub.legend()
            ax_sub.set_title("Alt Test Bazlı Performans")
            st.pyplot(fig_sub)

elif menu == "3. Veri Tabanı":
    st.header("💾 Araştırma Verisi (Excel)")
    df = load_db()
    if not df.empty:
        st.dataframe(df.head())
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
        st.download_button("Excel İndir (Full Protokol)", buffer.getvalue(), "tgmd3_research_final.xlsx")
    else: st.warning("Veri yok.")
