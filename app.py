import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import matplotlib.pyplot as plt
from fpdf import FPDF
from datetime import date

# =============================================================================
# 1. AYARLAR VE SABİT PROTOKOL (DOKUNULMAZ ALAN)
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO: Araştırma Sürümü", layout="wide", page_icon="📈")

FILE_NAME = "tgmd3_arastirma_db.xlsx"

# PROTOKOL: Sizin belirttiğiniz madde sayıları ve içerikleri
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

# Maksimum Puanları Hesapla (Madde Sayısı x 2)
MAX_SCORES = {}
for domain in PROTOCOL:
    for test, items in PROTOCOL[domain].items():
        MAX_SCORES[test] = len(items) * 2

# =============================================================================
# 2. VERİTABANI YÖNETİCİSİ (CRUD İŞLEMLERİ)
# =============================================================================
def load_db():
    if not os.path.exists(FILE_NAME):
        return pd.DataFrame()
    try:
        df = pd.read_excel(FILE_NAME)
        # Veri tiplerini garantiye al
        str_cols = ['ID', 'Ad', 'Soyad', 'Cinsiyet', 'YasGrubu', 'DogumTarihi', 'TestTarihi']
        for c in str_cols:
            if c in df.columns: df[c] = df[c].astype(str)
        return df
    except:
        return pd.DataFrame()

def save_db(df):
    with pd.ExcelWriter(FILE_NAME, engine='openpyxl') as writer:
        df.to_excel(writer, index=False)

def calculate_age_group(birth_date, test_date):
    """Doğum ve Test tarihine göre 3 aylık dilim hesaplar."""
    b_date = pd.to_datetime(birth_date)
    t_date = pd.to_datetime(test_date)
    
    diff_days = (t_date - b_date).days
    age_months = int(diff_days / 30.44)
    
    # 3 Aylık Dilim Formülü
    quarter = (age_months // 3) * 3
    group_name = f"{quarter}-{quarter+2} Ay"
    return age_months, group_name

# =============================================================================
# 3. İSTATİSTİK VE GRAFİK MOTORU
# =============================================================================
def get_z_score_stats(student_row, full_df):
    """
    Öğrenciyi kendi Cinsiyet ve Yaş Grubundaki popülasyonla kıyaslar.
    """
    # Filtreleme: Aynı Cinsiyet VE Aynı Yaş Grubu
    group_df = full_df[
        (full_df['Cinsiyet'] == student_row['Cinsiyet']) & 
        (full_df['YasGrubu'] == student_row['YasGrubu'])
    ]
    
    stats_data = []
    
    # Her alt test için hesaplama
    all_tests = list(MAX_SCORES.keys())
    for test in all_tests:
        col = f"{test}_Toplam"
        student_score = float(student_row.get(col, 0))
        max_score = MAX_SCORES[test]
        
        # Grup İstatistikleri
        if len(group_df) > 1:
            mean = group_df[col].mean()
            std = group_df[col].std(ddof=1) # Sample Std Dev
            if std == 0: std = 1 # Division by zero protection
            z_score = (student_score - mean) / std
        else:
            mean = student_score
            std = 0
            z_score = 0
        
        # Yorumlama
        if z_score > 1: durum = "Ortalama Üzeri"
        elif z_score < -1: durum = "Geliştirilmeli"
        else: durum = "Normal (Ortalama)"
        
        if len(group_df) < 2: durum = "Veri Yetersiz (N<2)"
        
        stats_data.append({
            "Alt Test": test,
            "Puan": student_score,
            "Max": max_score,
            "Grup Ort": round(mean, 2),
            "SS": round(std, 2),
            "Z-Skor": round(z_score, 2),
            "Durum": durum
        })
        
    return pd.DataFrame(stats_data)

def draw_bell_curve(z_score, title):
    """Z-Skorunun normal dağılımdaki yerini çizer."""
    try:
        fig, ax = plt.subplots(figsize=(6, 3))
        x = np.linspace(-4, 4, 100)
        y = (1 / np.sqrt(2 * np.pi)) * np.exp(-0.5 * x**2)
        
        ax.plot(x, y, color='black', lw=2)
        ax.fill_between(x, y, alpha=0.1, color='gray')
        
        # Bölgeler
        ax.axvline(-1, color='green', linestyle=':', alpha=0.5)
        ax.axvline(1, color='green', linestyle=':', alpha=0.5)
        
        # Öğrenci
        ax.axvline(z_score, color='red', linewidth=2)
        ax.text(z_score, max(y)*1.1, f"Z={z_score}", color='red', ha='center', fontweight='bold')
        
        ax.set_title(title, fontsize=10)
        ax.set_yticks([])
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)
        plt.tight_layout()
        return fig
    except: return plt.figure()

# =============================================================================
# 4. ARAYÜZ
# =============================================================================
st.sidebar.title("TGMD-3 PRO")
menu = st.sidebar.radio("MENÜ", ["1. Veri Girişi / Düzenle", "2. Bireysel Rapor", "3. Toplu Veri (Excel)"])

# --- MODÜL 1: VERİ GİRİŞİ VE DÜZENLEME ---
if menu == "1. Veri Girişi / Düzenle":
    st.header("📝 Öğrenci Veri Yönetimi")
    
    df = load_db()
    
    # 1. Adım: Öğrenci Seç veya Yeni Oluştur
    student_list = ["Yeni Kayıt Oluştur"]
    if not df.empty:
        df['Display'] = df['Ad'] + " " + df['Soyad'] + " (" + df['TestTarihi'] + ")"
        student_list += df['Display'].tolist()
    
    selected_option = st.selectbox("İşlem Yapılacak Kişi:", student_list)
    
    # Form Verilerini Hazırla
    default_vals = {}
    is_edit_mode = False
    edit_id = None
    
    if selected_option != "Yeni Kayıt Oluştur":
        is_edit_mode = True
        record = df[df['Display'] == selected_option].iloc[0]
        edit_id = record['ID']
        # Temel Bilgiler
        default_vals['Ad'] = record['Ad']
        default_vals['Soyad'] = record['Soyad']
        default_vals['DT'] = pd.to_datetime(record['DogumTarihi']).date()
        default_vals['TT'] = pd.to_datetime(record['TestTarihi']).date()
        default_vals['Cin'] = record['Cinsiyet']
        # Puanlar
        for col in record.index:
            if "_Puan" in col: # Checkbox verisi değil, toplam puanı tutuyoruz ama geri yüklemek zor
                pass           # Bu versiyonda checkboxları değil skorları yönetiyoruz.
    
    # 2. Adım: Form
    with st.form("data_entry_form"):
        c1, c2, c3, c4 = st.columns(4)
        ad = c1.text_input("Ad", value=default_vals.get('Ad', "")).upper()
        soyad = c2.text_input("Soyad", value=default_vals.get('Soyad', "")).upper()
        dt = c3.date_input("Doğum Tarihi", value=default_vals.get('DT', date(2018,1,1)))
        tt = c4.date_input("Test Tarihi", value=default_vals.get('TT', date.today()))
        cinsiyet = st.radio("Cinsiyet", ["Kız", "Erkek"], index=0 if default_vals.get('Cin') == "Kız" else 1, horizontal=True)
        
        st.divider()
        
        # Test Girişleri (Checkboxlar)
        scores = {}
        
        col_l, col_n = st.columns(2)
        
        with col_l:
            st.subheader("🏃 LOKOMOTOR")
            for test, items in PROTOCOL["LOKOMOTOR"].items():
                with st.expander(test):
                    total = 0
                    for i, item in enumerate(items):
                        st.write(f"_{item}_")
                        # Not: Düzenleme modunda checkboxları tek tek geri yüklemek çok karmaşık olduğu için
                        # Düzenleme modunda sadece isim/tarih değiştiriyoruz veya testi yeniden giriyoruz.
                        d1 = st.checkbox("1. Deneme", key=f"L_{test}_{i}_1")
                        d2 = st.checkbox("2. Deneme", key=f"L_{test}_{i}_2")
                        total += int(d1) + int(d2)
                    scores[f"{test}_Toplam"] = total
                    st.caption(f"Test Toplamı: {total}")

        with col_n:
            st.subheader("🏀 NESNE KONTROL")
            for test, items in PROTOCOL["NESNE_KONTROL"].items():
                with st.expander(test):
                    total = 0
                    for i, item in enumerate(items):
                        st.write(f"_{item}_")
                        d1 = st.checkbox("1. Deneme", key=f"N_{test}_{i}_1")
                        d2 = st.checkbox("2. Deneme", key=f"N_{test}_{i}_2")
                        total += int(d1) + int(d2)
                    scores[f"{test}_Toplam"] = total
                    st.caption(f"Test Toplamı: {total}")
        
        # Butonlar
        c_btn1, c_btn2 = st.columns(2)
        submitted = c_btn1.form_submit_button("✅ KAYDET / GÜNCELLE")
        
        if submitted:
            if ad and soyad:
                yas_ay, yas_grup = calculate_age_group(dt, tt)
                # ID Oluşturma (İsim+Soyad+DT benzersizliği)
                unique_str = f"{ad}{soyad}{dt}".replace(" ", "").lower()
                import hashlib
                new_id = hashlib.md5(unique_str.encode()).hexdigest()[:10]
                
                # Veri Sözlüğü
                new_data = {
                    "ID": new_id,
                    "Ad": ad, "Soyad": soyad, "Cinsiyet": cinsiyet,
                    "DogumTarihi": str(dt), "TestTarihi": str(tt),
                    "YasAy": yas_ay, "YasGrubu": yas_grup
                }
                new_data.update(scores)
                
                # Veritabanı İşlemi
                current_df = load_db()
                if is_edit_mode:
                    # Eski kaydı çıkar (ID değişmiş olabilir diye eski ID kullanıyoruz)
                    current_df = current_df[current_df['ID'] != edit_id]
                
                # Eğer yeni ID ile çakışan varsa onu da çıkar (Duplicate önlemi)
                current_df = current_df[current_df['ID'] != new_id]
                
                # Ekle
                new_df = pd.DataFrame([new_data])
                final_df = pd.concat([current_df, new_df], ignore_index=True)
                save_db(final_df)
                
                st.success("Kayıt Başarıyla İşlendi!")
                st.rerun()
            else:
                st.error("Ad ve Soyad zorunludur.")

    if is_edit_mode:
        if st.button("🗑 Bu Öğrenciyi Sil", type="primary"):
            df = df[df['ID'] != edit_id]
            # Sütun temizliği (Display sütunu kaydetmeden önce silinmeli)
            if 'Display' in df.columns: df = df.drop(columns=['Display'])
            save_db(df)
            st.success("Kayıt Silindi.")
            st.rerun()

# --- MODÜL 2: BİREYSEL RAPOR ---
elif menu == "2. Bireysel Rapor":
    st.header("📊 Gelişimsel Sonuç Raporu")
    df = load_db()
    
    if df.empty:
        st.warning("Henüz veri yok.")
    else:
        df['Display'] = df['Ad'] + " " + df['Soyad'] + " (" + df['YasGrubu'] + ")"
        choice = st.selectbox("Raporu Hazırlanacak Öğrenci:", df['Display'].unique())
        
        if choice:
            row = df[df['Display'] == choice].iloc[0]
            
            # İstatistikleri Hesapla
            stats_df = get_z_score_stats(row, df)
            
            # Ekrana Bas
            st.subheader(f"{row['Ad']} {row['Soyad']} - Performans Analizi")
            st.info(f"Karşılaştırma Grubu: {row['Cinsiyet']} | {row['YasGrubu']}")
            
            # Tablo
            st.dataframe(stats_df, hide_index=True, use_container_width=True)
            
            # Grafikler
            st.markdown("---")
            c1, c2 = st.columns(2)
            
            with c1:
                # Bar Grafiği (Puan vs Max)
                fig_bar, ax = plt.subplots(figsize=(6, 4))
                ax.barh(stats_df['Alt Test'], stats_df['Max'], color='#f0f0f0', label='Max')
                ax.barh(stats_df['Alt Test'], stats_df['Puan'], color='#3498db', label='Öğrenci')
                ax.invert_yaxis()
                ax.set_title("Puan vs Maksimum Kapasite")
                ax.legend()
                st.pyplot(fig_bar)
            
            with c2:
                # Çan Eğrisi (Ortalama Z Skoru üzerinden genel durum)
                avg_z = stats_df['Z-Skor'].mean()
                fig_bell = draw_bell_curve(avg_z, "Genel Gelişimsel Konum (Ortalama Z)")
                st.pyplot(fig_bell)
                st.caption(f"Öğrencinin tüm testlerdeki ortalama Z-skoru: {avg_z:.2f}")

            # Sonuç Cümlesi
            st.markdown("### 📝 Sonuç Değerlendirmesi")
            if avg_z > 0.5:
                sentence = f"{row['Ad']}, kendi yaş grubu ve cinsiyetindeki akranlarına kıyasla genel motor becerilerde **ortalama üzeri** bir performans sergilemektedir."
            elif avg_z < -0.5:
                sentence = f"{row['Ad']}, motor beceri gelişiminde akran ortalamasının gerisinde kalmış olup, destekleyici çalışmalara ihtiyaç duymaktadır."
            else:
                sentence = f"{row['Ad']}, kendi yaş grubu ve cinsiyetindeki akranlarıyla **benzer (normal)** gelişim özellikleri göstermektedir."
            st.success(sentence)
            
            # PDF İndir
            def create_pdf():
                pdf = FPDF()
                pdf.add_page()
                pdf.set_font('Arial', 'B', 14)
                pdf.cell(0, 10, 'TGMD-3 GELISIM RAPORU', 0, 1, 'C')
                
                pdf.set_font('Arial', '', 11)
                pdf.ln(5)
                # Türkçe karakterleri basitçe değiştir
                tr_map = str.maketrans("ğĞıİşŞüÜöÖçÇ", "gGiIsSuUoOcC")
                pdf.cell(0, 7, f"Ad Soyad: {row['Ad']} {row['Soyad']}".translate(tr_map), ln=True)
                pdf.cell(0, 7, f"Grup: {row['Cinsiyet']} - {row['YasGrubu']}".translate(tr_map), ln=True)
                pdf.ln(5)
                
                # Tablo
                pdf.set_font('Arial', 'B', 9)
                headers = ["Test", "Puan", "Max", "Ort", "SS", "Z", "Durum"]
                w = [35, 20, 20, 20, 20, 20, 40]
                for i, h in enumerate(headers): pdf.cell(w[i], 7, h, 1)
                pdf.ln()
                
                pdf.set_font('Arial', '', 9)
                for _, r in stats_df.iterrows():
                    pdf.cell(w[0], 7, r['Alt Test'].translate(tr_map), 1)
                    pdf.cell(w[1], 7, str(r['Puan']), 1)
                    pdf.cell(w[2], 7, str(r['Max']), 1)
                    pdf.cell(w[3], 7, str(r['Grup Ort']), 1)
                    pdf.cell(w[4], 7, str(r['SS']), 1)
                    pdf.cell(w[5], 7, str(r['Z-Skor']), 1)
                    pdf.cell(w[6], 7, r['Durum'].translate(tr_map), 1)
                    pdf.ln()
                
                pdf.ln(5)
                pdf.multi_cell(0, 5, "SONUC: " + sentence.translate(tr_map))
                
                return pdf.output(dest='S').encode('latin-1')

            st.download_button("📥 PDF Raporunu İndir", create_pdf(), "rapor.pdf", "application/pdf")

# --- MODÜL 3: TOPLU VERİ (EXCEL) ---
elif menu == "3. Toplu Veri (Excel)":
    st.header("💾 Araştırma Verisi İndir")
    st.markdown("Bu bölümdeki veriler SPSS veya Excel analizleri için ham formatta sunulmaktadır.")
    
    df = load_db()
    if not df.empty:
        # Görsel Tablo
        if 'Display' in df.columns: df_show = df.drop(columns=['Display'])
        else: df_show = df
        
        st.dataframe(df_show)
        
        # Excel İndirme
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_show.to_excel(writer, index=False, sheet_name='TGMD3_Data')
        
        st.download_button(
            label="📥 Excel Olarak İndir (Araştırma Formatı)",
            data=buffer.getvalue(),
            file_name="tgmd3_arastirma_verisi.xlsx",
            mime="application/vnd.ms-excel"
        )
    else:
        st.info("Veritabanı boş.")
