import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import hashlib
from datetime import date
import matplotlib.pyplot as plt

# =============================================================================
# 1. AYARLAR VE PROTOKOL
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO: Analitik Rapor", layout="wide", page_icon="📊")

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

# Max Puanları Hesapla
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

def calculate_detailed_stats(student_row, full_df):
    """
    Z-Skoru, Ortalama, SS ve Yorumları hesaplayan ana fonksiyon.
    Sadece aynı cinsiyet ve aynı yaş grubundaki kayıtları baz alır.
    """
    # Norm grubunu filtrele (Aynı Cinsiyet + Aynı Yaş Grubu)
    norm_group = full_df[
        (full_df['Cinsiyet'] == student_row['Cinsiyet']) & 
        (full_df['YasGrubu'] == student_row['YasGrubu'])
    ]
    
    stats_data = []
    
    # Tüm alt testleri dolaş
    for domain in PROTOCOL:
        for test in PROTOCOL[domain]:
            col_name = f"{test}_Toplam"
            puan = float(student_row.get(col_name, 0))
            max_puan = MAX_SCORES[test]
            
            # Norm istatistikleri
            if len(norm_group) > 1:
                ort = norm_group[col_name].mean()
                ss = norm_group[col_name].std(ddof=1)
                
                if ss == 0: # Herkes aynı puanı almışsa
                    z_score = 0
                    yorum = "Grup Eşit"
                else:
                    z_score = (puan - ort) / ss
                    
                    # Z-Skoru Yorumlama
                    if z_score >= 1.5: yorum = "Çok İleri"
                    elif 0.5 <= z_score < 1.5: yorum = "İleri"
                    elif -0.5 <= z_score < 0.5: yorum = "Normal"
                    elif -1.5 <= z_score < -0.5: yorum = "Geliştirilmeli"
                    else: yorum = "Risk Grubu"
            else:
                # Yeterli veri yoksa (Sisteme girilen ilk kişi)
                ort = puan
                ss = 0
                z_score = 0
                yorum = "Veri Yetersiz (İlk Kayıt)"
            
            stats_data.append({
                "Alan": domain,
                "Alt Test": test,
                "Puan": int(puan),
                "Max Puan": max_puan,
                "Grup Ort.": round(ort, 2),
                "Std. Sapma": round(ss, 2),
                "Z-Skoru": round(z_score, 2),
                "Yorum": yorum
            })
            
    return pd.DataFrame(stats_data)

# =============================================================================
# 3. ARAYÜZ
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Test ve Veri Girişi", "2. Detaylı Analiz & Rapor", "3. Veri Yönetimi"])

if menu == "1. Test ve Veri Girişi":
    st.header("📋 Test Veri Girişi")
    mode = st.radio("Seçim Yapınız:", ["📂 KAYITLI ÖĞRENCİ", "➕ YENİ ÖĞRENCİ KAYDI"], horizontal=True)
    df = load_db()
    
    ad, soyad, cinsiyet = "", "", "Kız"
    dt = date(2018, 1, 1)
    test_tarihi = date.today()
    test_yeri, el_tercih, ayak_tercih = "", "Sağ", "Sağ"
    ogrenci_id = None
    
    if mode == "📂 KAYITLI ÖĞRENCİ":
        if df.empty: st.warning("Kayıt yok."); st.stop()
        uniqs = df[['OgrenciID', 'Ad', 'Soyad', 'DogumTarihi', 'Cinsiyet']].drop_duplicates(subset='OgrenciID')
        uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad'] + " (" + uniqs['DogumTarihi'] + ")"
        secim = st.selectbox("Öğrenci Ara:", uniqs['Etiket'].tolist(), index=None, placeholder="İsim yazın...")
        if secim:
            rec = uniqs[uniqs['Etiket'] == secim].iloc[0]
            ad, soyad, cinsiyet, dt, ogrenci_id = rec['Ad'], rec['Soyad'], rec['Cinsiyet'], pd.to_datetime(rec['DogumTarihi']).date(), rec['OgrenciID']
            last = df[df['OgrenciID'] == ogrenci_id].iloc[-1]
            test_yeri, el_tercih, ayak_tercih = last['TestYeri'], last['TercihEl'], last['TercihAyak']
    else:
        st.subheader("Kimlik"); c1,c2,c3,c4 = st.columns(4)
        ad = c1.text_input("Ad").strip().upper(); soyad = c2.text_input("Soyad").strip().upper()
        dt = c3.date_input("DT", date(2018, 1, 1)); cinsiyet = c4.radio("Cinsiyet", ["Kız", "Erkek"], horizontal=True)

    if ad and soyad:
        st.divider(); st.subheader("Test Detayları"); r1,r2,r3,r4 = st.columns(4)
        test_tarihi = r1.date_input("Tarih", date.today()); test_yeri = r2.text_input("Yer", test_yeri).upper()
        el_tercih = r3.selectbox("El", ["Sağ","Sol","Belirsiz"], ["Sağ","Sol","Belirsiz"].index(el_tercih) if el_tercih in ["Sağ","Sol","Belirsiz"] else 0)
        ayak_tercih = r4.selectbox("Ayak", ["Sağ","Sol","Belirsiz"], ["Sağ","Sol","Belirsiz"].index(ayak_tercih) if ayak_tercih in ["Sağ","Sol","Belirsiz"] else 0)
        
        if not ogrenci_id: ogrenci_id, test_id = generate_ids(ad, soyad, dt, test_tarihi)
        else: test_id = generate_ids(ad, soyad, dt, test_tarihi)[1]
        
        exist = {}
        if not df.empty and test_id in df['TestID'].values:
            st.warning("⚠️ Güncelleme Modu"); exist = df[df['TestID'] == test_id].iloc[0].to_dict()
        
        st.divider(); col_l, col_n = st.columns(2); form_data = {}; toplamlar = {}
        with col_l:
            st.info("🏃 LOKOMOTOR")
            for t_name, items in PROTOCOL["LOKOMOTOR"].items():
                tot = 0
                with st.expander(t_name):
                    for i, item in enumerate(items):
                        k = f"L_{t_name}_{i}"; v = st.radio(item, [0,1,2], int(exist.get(k,0)), key=f"{test_id}_{k}", horizontal=True)
                        form_data[k] = v; tot += v
                    toplamlar[f"{t_name}_Toplam"] = tot
        with col_n:
            st.info("🏀 NESNE KONTROL")
            for t_name, items in PROTOCOL["NESNE_KONTROL"].items():
                tot = 0
                with st.expander(t_name):
                    for i, item in enumerate(items):
                        k = f"N_{t_name}_{i}"; v = st.radio(item, [0,1,2], int(exist.get(k,0)), key=f"{test_id}_{k}", horizontal=True)
                        form_data[k] = v; tot += v
                    toplamlar[f"{t_name}_Toplam"] = tot
        
        if st.button("💾 KAYDET", type="primary"):
            ay, grup = calculate_age(dt, test_tarihi)
            rec = {"TestID": test_id, "OgrenciID": ogrenci_id, "Ad": ad, "Soyad": soyad, "DogumTarihi": dt, "Cinsiyet": cinsiyet, "TestTarihi": test_tarihi, "TestYeri": test_yeri, "TercihEl": el_tercih, "TercihAyak": ayak_tercih, "YasAy": ay, "YasGrubu": grup, "SonIslemTarihi": str(date.today())}
            rec.update(form_data); rec.update(toplamlar)
            save_to_db(rec); st.success("Kaydedildi!"); st.balloons()

elif menu == "2. Detaylı Analiz & Rapor":
    st.header("📊 Bireysel Gelişim ve Norm Raporu")
    df = load_db()
    
    if df.empty:
        st.warning("Veritabanında veri yok.")
    else:
        # 1. ÖĞRENCİ SEÇİMİ
        uniqs = df[['OgrenciID', 'Ad', 'Soyad']].drop_duplicates(subset='OgrenciID')
        uniqs['Etiket'] = uniqs['Ad'] + " " + uniqs['Soyad']
        secim = st.selectbox("Öğrenci Seçiniz:", uniqs['Etiket'])
        
        if secim:
            oid = uniqs[uniqs['Etiket'] == secim].iloc[0]['OgrenciID']
            student_history = df[df['OgrenciID'] == oid].sort_values('TestTarihi')
            
            # 2. TEST TARİHİ SEÇİMİ (Karşılaştırma ve tablo için)
            test_dates = student_history['TestTarihi'].tolist()
            selected_date = st.selectbox("Analiz Edilecek Test Tarihi:", test_dates, index=len(test_dates)-1)
            
            # Seçilen kaydı al
            current_record = student_history[student_history['TestTarihi'] == selected_date].iloc[0]
            
            # İSTATİSTİKLERİ HESAPLA
            stats_df = calculate_detailed_stats(current_record, df)
            
            # --- TABLO VE GRAFİKLERİ SEKMELE ---
            tab1, tab2 = st.tabs(["📝 İstatistiksel Tablo & Alt Test Grafiği", "📈 Boylamsal Gelişim (Tarihsel)"])
            
            with tab1:
                st.subheader(f"Test Detayı: {selected_date} ({current_record['YasGrubu']})")
                
                # A) İSTATİSTİK TABLOSU
                st.markdown("##### 1. Alt Test Puanları ve Norm Karşılaştırması")
                
                # Tabloyu daha şık göstermek için renklendirme fonksiyonu
                def highlight_z(val):
                    color = 'black'
                    if isinstance(val, (int, float)):
                        if val < -1: color = 'red'
                        elif val > 1: color = 'green'
                    return f'color: {color}'

                # Dataframe'i göster
                st.dataframe(
                    stats_df.style.map(highlight_z, subset=['Z-Skoru']).format({"Grup Ort.": "{:.2f}", "Std. Sapma": "{:.2f}", "Z-Skoru": "{:.2f}"}),
                    hide_index=True,
                    use_container_width=True
                )
                
                st.info("ℹ️ **Z-Skoru:** Öğrencinin grup ortalamasından kaç standart sapma uzakta olduğunu gösterir. +1 üzeri 'İleri', -1 altı 'Geliştirilmeli' olarak yorumlanabilir.")
                
                # B) ALT TEST GRAFİĞİ (Bar Chart: Öğrenci vs Grup Ortalaması vs Max)
                st.markdown("---")
                st.markdown("##### 2. Grafiksel Karşılaştırma")
                
                # Grafik Hazırlığı
                labels = stats_df['Alt Test']
                x = np.arange(len(labels))
                width = 0.25
                
                fig, ax = plt.subplots(figsize=(12, 6))
                rects1 = ax.bar(x - width, stats_df['Puan'], width, label='Öğrenci Puanı', color='#3498db')
                rects2 = ax.bar(x, stats_df['Grup Ort.'], width, label='Grup Ortalaması', color='#95a5a6')
                rects3 = ax.bar(x + width, stats_df['Max Puan'], width, label='Max Puan', color='#ecf0f1', hatch='//')
                
                ax.set_ylabel('Puan')
                ax.set_title(f"{current_record['Ad']} {current_record['Soyad']} - Alt Test Performansı")
                ax.set_xticks(x)
                ax.set_xticklabels(labels, rotation=45, ha='right')
                ax.legend()
                
                # Bar üstlerine değer yazdırma
                ax.bar_label(rects1, padding=3)
                ax.bar_label(rects2, padding=3, fmt='%.1f')
                
                plt.tight_layout()
                st.pyplot(fig)

            with tab2:
                st.subheader("Öğrencinin Zaman İçindeki Gelişimi")
                if len(student_history) < 2:
                    st.warning("Bu öğrencinin sadece 1 testi var. Gelişim grafiği için en az 2 test gerekli.")
                else:
                    dates = student_history['TestTarihi'].tolist()
                    
                    # Toplam Puanları Hesapla
                    loko_total = []
                    nesne_total = []
                    
                    for _, row in student_history.iterrows():
                        l = sum([row[f"{t}_Toplam"] for t in PROTOCOL['LOKOMOTOR']])
                        n = sum([row[f"{t}_Toplam"] for t in PROTOCOL['NESNE_KONTROL']])
                        loko_total.append(l)
                        nesne_total.append(n)
                        
                    # Çizgi Grafik
                    fig2, ax2 = plt.subplots(figsize=(10, 5))
                    ax2.plot(dates, loko_total, marker='o', linewidth=2, label='Lokomotor Toplam')
                    ax2.plot(dates, nesne_total, marker='s', linewidth=2, label='Nesne Kontrol Toplam')
                    
                    ax2.set_xlabel('Test Tarihleri')
                    ax2.set_ylabel('Toplam Puan')
                    ax2.grid(True, linestyle='--', alpha=0.6)
                    ax2.legend()
                    st.pyplot(fig2)
                    
                    # Veri Tablosu
                    st.write("Özet Gelişim Tablosu:")
                    summary_df = pd.DataFrame({
                        "Tarih": dates,
                        "Yaş Grubu": student_history['YasGrubu'].tolist(),
                        "Lokomotor Puan": loko_total,
                        "Nesne Kontrol Puan": nesne_total
                    })
                    st.dataframe(summary_df, hide_index=True)

elif menu == "3. Veri Yönetimi":
    st.header("💾 Veri Yönetimi")
    df = load_db()
    if not df.empty:
        st.dataframe(df.head())
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer: df.to_excel(writer, index=False)
        st.download_button("Excel İndir (Full Veri)", buffer.getvalue(), "tgmd3_full_data.xlsx")
    else: st.warning("Veri yok.")
