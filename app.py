import streamlit as st
import pandas as pd
import numpy as np
import os
import hashlib
import tempfile
from datetime import date
from io import BytesIO
import matplotlib.pyplot as plt
from matplotlib import cm
from math import pi
from fpdf import FPDF

# =============================================================================
# 1. AYARLAR VE PROTOKOL
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO (Görsel Rapor)", layout="wide", page_icon="🧬")

DB_FILE = "tgmd3_database_pro.xlsx"

TGMD3_PROTOCOL = {
    "LOKOMOTOR": {
        "Koşu (Run)": ["1. Kol-bacak çapraz hareket-dirsekler bükülü", "2. Ayakların yerden kesilmesi", "3. Ayak ucuyla basma", "4. Havadaki ayak 90 derece bükülü"],
        "Galop (Gallop)": ["1. Kollar sıçramada bel hizasında bükülü", "2. Kısa süre iki ayak da havada", "3. Arka arkaya 4 galopta ritmi sürdürme", "4. İlk adımın yanına yada gerisine ikinci adım"],
        "Sek Sek (Hop)": ["1. Havadaki ayağın güç almak için salınımı", "2. Havadaki ayak vücuda yakın", "3. Kollar bükülü güç almak için salınım", "4. Arka arkaya 4 kez sıçrama-iniş (destek ayağı)", "5. Arka arkaya 3 kez sıçrama-iniş (diğer ayak)"],
        "Atlama (Skip)": ["1. İleriye doğru atlama yapan ayağın üzerine inme", "2. Kollar güç üretmek için bükülü ve bacaklarla çapraz durumda", "3. Hareketin birbirini takip eden dört tane ardışık tekrarını yapabilme"],
        "Durarak Uzun Atlama (H. Jump)": ["1. Harekete hazırlık için dizler bükülü ve kollar bükülü", "2. Atlama anında Kolları hızlı ve güçlü bir şekilde başın üstüne kaldırma", "3. İki ayakla sıçrama ve iniş", "4. Kollar iniş boyunca aşağı doğru itiş yapar"],
        "Kayma (Slide)": ["1. Beden yan dönerek gidiş yönünde", "2. Arkadan gelen ayak ilkinin yerine konur", "3. Sağa kaymada en az 4 adım", "4. Sola kaymada en az 4 adım"]
    },
    "NESNE_KONTROL": {
        "Topa Sopayla Vuruş (Bat)": ["1. Sopayı tutuşta baskın el üstte, diğeri altta", "2. Baskın olmayan taraf vuruş yönünde, ayaklar paralel duruş", "3. Salınım sırasında omuz ve kalça rotasyonu", "4. Ağırlığı gerideki ayaktan öndekine aktarma", "5. Topa vurma ve topun net bir şekilde ileriye gitmesi"],
        "Forehand Vuruş": ["1. Çocuğun top yerden gelirken geriye salınımı", "2. Baskın olmayan ayakla adım atma", "3. Topu duvara doğru vurma", "4. Topu yere bırakan omuza doğru raketin takibi"],
        "Top Sürme (Dribble)": ["1. Topun bel hizasında değmesi", "2. Topun parmak uçlarıyla itilmesi", "3. Hareket formunun bozmadan ard arda 4 kez topu sürme ve topu tutma"],
        "Yakalama (Catch)": ["1. Kollar önde ve bükülü hazırlanma", "2. Topa yetişmek için kolu uzatma", "3. Topu sadece ellerle yakalama"],
        "Ayakla Vuruş (Kick)": ["1. Topa hızlı yaklaşma", "2. Topa temas etmeden önce uzun bir adım ya da sıçrama", "3. Yerdeki ayak topun yanında ya da gerisinde", "4. Topa ayamın üst kısmıyla ya da ucuyla vurma"],
        "Top Fırlatma (Throw)": ["1. Hazırlık için el ve kollar aşağıda", "2. Kalça-omuz rotasyonu ile topu tutan kolun geri hareketi", "3. Ağırlık atış yapan kolun çaprazındaki ayakta", "4. Top elden çıkınca kolun çapraz yönde hareketi"],
        "Duvara Çarptırma (Rolling)": ["1. Topu tutan kolun gövde arkasına salınımı", "2. Atış anında topu tutan kolun çapraz ayağı önde", "3. Topun direk olarak duvara çarptırılması", "4. Topu atan elin atışı göğüs seviyesine kadar takip etmesi"],
    }
}

# =============================================================================
# 🔒 GÜVENLİK (ŞİFRE KONTROLÜ)
# =============================================================================
def sifre_kontrol():
    """Kullanıcı doğru şifreyi girene kadar uygulamayı durdurur."""
    
    if "sifre_dogru" not in st.session_state:
        st.session_state["sifre_dogru"] = False

    if st.session_state["sifre_dogru"]:
        return True

    st.markdown("## 🔒 Giriş Yapınız")
    st.info("Erişim için şifre gereklidir.")
    
    girilen_sifre = st.text_input("Şifre:", type="password")

    if st.button("Giriş Yap"):
        try:
            dogru_sifre = st.secrets["giris_sifresi"]
        except:
            dogru_sifre = "Sporcu2024" # Secrets dosyası yoksa yedek şifre

        if girilen_sifre == dogru_sifre:
            st.session_state["sifre_dogru"] = True
            st.rerun()
        else:
            st.error("Hatalı şifre! Lütfen tekrar deneyiniz.")
    
    return False

# Şifre kontrolünü çalıştır
if not sifre_kontrol():
    st.stop()

# =============================================================================
# 2. YARDIMCI FONKSİYONLAR
# =============================================================================

def yas_hesapla_ay(dogum_tarihi, test_tarihi):
    try:
        d1 = pd.to_datetime(dogum_tarihi)
        d2 = pd.to_datetime(test_tarihi)
        return int((d2.year - d1.year) * 12 + (d2.month - d1.month))
    except: return 0

def yas_araligi_bul(ay):
    baslangic = (ay // 3) * 3
    return f"{baslangic}-{baslangic+2} Ay"

def id_uret(ad, soyad, dogum, kaynak="LOC"):
    raw = f"{ad}{soyad}{dogum}".lower().replace(" ", "")
    hash_code = hashlib.md5(raw.encode()).hexdigest()[:8].upper()
    return f"{kaynak}_{hash_code}"

def z_skor_yorumla(z_score):
    if z_score is None or pd.isna(z_score): return "Yetersiz Veri"
    if z_score <= -2.0: return "Cok Zayif (Gecikme)"
    elif -2.0 < z_score <= -1.0: return "Zayif"
    elif -1.0 < z_score <= 1.0: return "Normal"
    elif 1.0 < z_score <= 2.0: return "Iyi"
    else: return "Ustun"

def tr_chars(text):
    return str(text).replace("ğ","g").replace("Ğ","G")\
                    .replace("ş","s").replace("Ş","S")\
                    .replace("ı","i").replace("İ","I")\
                    .replace("ü","u").replace("Ü","U")\
                    .replace("ö","o").replace("Ö","O")\
                    .replace("ç","c").replace("Ç","C")

def veritabani_yukle():
    if not os.path.exists(DB_FILE): return pd.DataFrame()
    try:
        df = pd.read_excel(DB_FILE)
        cols_to_str = ["OgrenciID", "TestTarihi"]
        for col in cols_to_str:
            if col in df.columns: df[col] = df[col].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

# -----------------------------------------------------------------------------
# 🔥 ÖNEMLİ GÜNCELLEME: VERİ BİRLEŞTİRME (MERGE) FONKSİYONU
# -----------------------------------------------------------------------------
def veritabani_kaydet(yeni_veriler_sozluk, ogrenci_id, test_tarihi):
    """
    Var olan kaydı bulur, sadece yeni girilen alanları günceller ve puanları yeniden hesaplar.
    """
    mevcut_df = veritabani_yukle()
    test_tarihi_str = str(test_tarihi)
    
    # Yeni veri için DataFrame oluştur
    mask = (mevcut_df["OgrenciID"] == ogrenci_id) & (mevcut_df["TestTarihi"] == test_tarihi_str)
    
    if mevcut_df.empty or not mask.any():
        # Yeni satır ekle
        yeni_df = pd.DataFrame([yeni_veriler_sozluk])
        son_df = pd.concat([mevcut_df, yeni_df], ignore_index=True)
    else:
        # Kayıt varsa: Mevcut satırı güncelle
        idx = mevcut_df[mask].index[0]
        
        # Yeni değerleri işle
        for key, value in yeni_veriler_sozluk.items():
            mevcut_df.at[idx, key] = value
            
        # --- OTOMATİK PUAN HESAPLAMA ---
        cols = mevcut_df.columns
        
        # Lokomotor Toplam
        loko_sum = 0
        for main_key in TGMD3_PROTOCOL["LOKOMOTOR"].keys():
            col_name = f"{main_key}_Toplam"
            if col_name in cols:
                loko_sum += pd.to_numeric(mevcut_df.at[idx, col_name], errors='coerce') or 0
        
        # Nesne Kontrol Toplam
        nesne_sum = 0
        for main_key in TGMD3_PROTOCOL["NESNE_KONTROL"].keys():
            col_name = f"{main_key}_Toplam"
            if col_name in cols:
                nesne_sum += pd.to_numeric(mevcut_df.at[idx, col_name], errors='coerce') or 0
        
        # Ana puanları güncelle
        mevcut_df.at[idx, "Lokomotor_Puan"] = loko_sum
        mevcut_df.at[idx, "Nesne_Puan"] = nesne_sum
        mevcut_df.at[idx, "Kaba_Motor_Puan"] = loko_sum + nesne_sum
        
        son_df = mevcut_df

    with pd.ExcelWriter(DB_FILE, engine="openpyxl") as w:
        son_df.to_excel(w, index=False)
    
    return son_df

# =============================================================================
# 3. PDF OLUŞTURMA
# =============================================================================
class PDFReport(FPDF):
    def header(self):
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'TGMD-3 GELISIMSEL TAKIP RAPORU', 0, 1, 'C')
        self.ln(5)

    def footer(self):
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Sayfa {self.page_no()}', 0, 0, 'C')

def create_full_report(ogrenci_bilgi, fig_radar, fig_line, gecmis_df, df_ana):
    pdf = PDFReport()
    
    # SAYFA 1: KAPAK ve GENEL GRAFİKLER
    pdf.add_page()
    pdf.set_font("Arial", size=10)
    pdf.set_font("Arial", 'B', 14)
    # --- DÜZELTİLEN SATIR BURASI ---
    pdf.cell(0, 10, tr_chars(f"Öğrenci: {ogrenci_bilgi['Ad']} {ogrenci_bilgi['Soyad']}"), ln=True, align='C')
    # --------------------------------
    pdf.set_font("Arial", size=10)
    pdf.cell(0, 6, f"ID: {ogrenci_bilgi['ID']} | Cinsiyet: {tr_chars(ogrenci_bilgi['Cinsiyet'])}", ln=True, align='C')
    pdf.ln(10)
    
    # Grafikleri yerleştir
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_radar, \
         tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp_line:
        
        fig_radar.savefig(tmp_radar.name, format="png", bbox_inches='tight')
        fig_line.savefig(tmp_line.name, format="png", bbox_inches='tight')
        
        pdf.image(tmp_radar.name, x=60, y=50, w=90)
        pdf.image(tmp_line.name, x=30, y=150, w=150)
    
    try:
        os.remove(tmp_radar.name)
        os.remove(tmp_line.name)
    except: pass
    
    # SAYFA 2+: HER TEST İÇİN DETAY
    tum_testler = list(TGMD3_PROTOCOL["LOKOMOTOR"].keys()) + list(TGMD3_PROTOCOL["NESNE_KONTROL"].keys())
    
    for idx, row in gecmis_df.iterrows():
        pdf.add_page()
        tarih = row["TestTarihi"]
        yas_grup = row["Yas_Grup_3Ay"]
        norm_grubu = df_ana[(df_ana["Cinsiyet"] == row["Cinsiyet"]) & (df_ana["Yas_Grup_3Ay"] == row["Yas_Grup_3Ay"])]
        
        pdf.set_font("Arial", 'B', 12)
        pdf.cell(0, 10, tr_chars(f"TEST TARİHİ: {tarih}"), ln=True)
        pdf.set_font("Arial", size=10)
        pdf.cell(0, 8, tr_chars(f"Yaş Grubu: {yas_grup}"), ln=True)
        pdf.ln(5)
        
        pdf.set_font("Arial", 'B', 9)
        cols = [50, 20, 20, 20, 25, 20, 35]
        headers = ["Beceri", "Puan", "Ort", "SS", "Min-Max", "Z-Skor", "Yorum"]
        for i, h in enumerate(headers): pdf.cell(cols[i], 7, h, 1, 0, 'C')
        pdf.ln()
        
        pdf.set_font("Arial", size=8)
        # Alt Testler
        for test_adi in tum_testler:
            col_key = f"{test_adi}_Toplam"
            puan = row.get(col_key, 0)
            if col_key in norm_grubu.columns:
                ort, std = norm_grubu[col_key].mean(), norm_grubu[col_key].std()
                mn, mx = norm_grubu[col_key].min(), norm_grubu[col_key].max()
                z = (puan - ort) / std if std > 0 else 0
            else: ort, std, mn, mx, z = 0, 0, 0, 0, 0
            
            pdf.cell(cols[0], 6, tr_chars(test_adi.split("(")[0].strip())[:30], 1)
            pdf.cell(cols[1], 6, str(puan), 1, 0, 'C')
            pdf.cell(cols[2], 6, f"{ort:.1f}", 1, 0, 'C')
            pdf.cell(cols[3], 6, f"{std:.1f}", 1, 0, 'C')
            pdf.cell(cols[4], 6, f"{mn}-{mx}", 1, 0, 'C')
            pdf.cell(cols[5], 6, f"{z:.2f}", 1, 0, 'C')
            pdf.cell(cols[6], 6, tr_chars(z_skor_yorumla(z)), 1, 0, 'C')
            pdf.ln()
            
        # Toplamlar
        pdf.ln(2)
        pdf.set_font("Arial", 'B', 8)
        toplamlar = [("LOKOMOTOR", "Lokomotor_Puan"), ("NESNE KONTROL", "Nesne_Puan"), ("KABA MOTOR", "Kaba_Motor_Puan")]
        for etiket, db_col in toplamlar:
            puan = row.get(db_col, 0)
            if db_col in norm_grubu.columns:
                ort, std = norm_grubu[db_col].mean(), norm_grubu[db_col].std()
                mn, mx = norm_grubu[db_col].min(), norm_grubu[db_col].max()
                z = (puan - ort) / std if std > 0 else 0
            else: ort, std, mn, mx, z = 0, 0, 0, 0, 0
            
            pdf.cell(cols[0], 6, tr_chars(etiket), 1)
            pdf.cell(cols[1], 6, str(puan), 1, 0, 'C')
            pdf.cell(cols[2], 6, f"{ort:.1f}", 1, 0, 'C')
            pdf.cell(cols[3], 6, f"{std:.1f}", 1, 0, 'C')
            pdf.cell(cols[4], 6, f"{mn}-{mx}", 1, 0, 'C')
            pdf.cell(cols[5], 6, f"{z:.2f}", 1, 0, 'C')
            pdf.cell(cols[6], 6, tr_chars(z_skor_yorumla(z)), 1, 0, 'C')
            pdf.ln()
            
    return pdf.output(dest='S').encode('latin-1')

# =============================================================================
# 4. ARAYÜZ
# =============================================================================
menu = st.sidebar.radio("MENÜ", ["1. Test Girişi", "2. Veri Import", "3. Gelişimsel Rapor", "4. Araştırmacı Verisi"])
df_ana = veritabani_yukle()

# --- 1. TEST GİRİŞİ (GÜNCELLENMİŞ - VERİ KAYBI OLMAZ) ---
if menu == "1. Test Girişi":
    st.header("📝 Test Giriş Ekranı (Grup Ölçümü Modu)")
    
    # Öğrenci Seçimi
    mod = st.radio("Kayıt Tipi:", ["Yeni Öğrenci", "Kayıtlı Öğrenci"], horizontal=True)
    d_ad, d_soyad, d_dt, d_cin = "", "", date(2018,1,1), "Kız"
    sabit_id = None
    
    if mod == "Kayıtlı Öğrenci" and not df_ana.empty:
        ozet = df_ana[["OgrenciID", "Ad", "Soyad"]].drop_duplicates("OgrenciID")
        ozet["Gosterim"] = ozet["Ad"] + " " + ozet["Soyad"] + " (" + ozet["OgrenciID"] + ")"
        secim = st.selectbox("Öğrenci Seç:", ozet["Gosterim"])
        if secim:
            sabit_id = secim.split("(")[-1].strip(")")
            row_info = df_ana[df_ana["OgrenciID"] == sabit_id].iloc[-1]
            d_ad, d_soyad = row_info["Ad"], row_info["Soyad"]
            d_dt = pd.to_datetime(row_info["DogumTarihi"]).date()
            d_cin = row_info["Cinsiyet"]

    # Kimlik Bilgileri Formu
    with st.expander("Kimlik Bilgileri", expanded=True):
        c1, c2, c3, c4 = st.columns(4)
        ad = c1.text_input("Ad", d_ad).upper()
        soyad = c2.text_input("Soyad", d_soyad).upper()
        cin = c3.selectbox("Cinsiyet", ["Kız", "Erkek"], index=0 if d_cin=="Kız" else 1)
        dt = c4.date_input("Doğum Tarihi", d_dt)
        
        c5, c6, c7, c8 = st.columns(4)
        tt = c5.date_input("Test Tarihi", date.today())
        el = c6.selectbox("El", ["Sağ", "Sol"])
        ayak = c7.selectbox("Ayak", ["Sağ", "Sol"])
        yer = c8.text_input("Yer", "Spor Salonu")
        
        yas_ay = yas_hesapla_ay(dt, tt)
        final_id = sabit_id if sabit_id else id_uret(ad, soyad, str(dt))
        st.info(f"ID: {final_id} | Yaş: {yas_ay} Ay")

    # --- VAR OLAN VERİYİ ÇEKME (PRE-FILL) ---
    mevcut_veri = {}
    if not df_ana.empty:
        bulunan = df_ana[(df_ana["OgrenciID"] == final_id) & (df_ana["TestTarihi"] == str(tt))]
        if not bulunan.empty:
            mevcut_veri = bulunan.iloc[0].to_dict()
            st.success(f"⚠️ Bu öğrenci için {tt} tarihinde girilmiş veri bulundu. Veriler yüklendi.")

    if ad and soyad:
        with st.form("test_form"):
            ham_veri_form = {} # Formdan toplanacak veriler
            
            # --- LOKOMOTOR ---
            st.info("A. LOKOMOTOR")
            for t_ad, kr in TGMD3_PROTOCOL["LOKOMOTOR"].items():
                with st.expander(t_ad):
                    sub_total = 0
                    for i, k in enumerate(kr):
                        st.write(k)
                        ca, cb = st.columns([1, 1])
                        
                        # Mevcut veriden değerleri çek (yoksa False)
                        val_d1 = bool(mevcut_veri.get(f"{t_ad}_K{i+1}_D1", 0))
                        val_d2 = bool(mevcut_veri.get(f"{t_ad}_K{i+1}_D2", 0))
                        
                        d1 = ca.checkbox("D1", key=f"L_{t_ad}_{i}_1", value=val_d1)
                        d2 = cb.checkbox("D2", key=f"L_{t_ad}_{i}_2", value=val_d2)
                        
                        p = int(d1) + int(d2)
                        sub_total += p
                        
                        ham_veri_form[f"{t_ad}_K{i+1}_D1"] = int(d1)
                        ham_veri_form[f"{t_ad}_K{i+1}_D2"] = int(d2)
                        ham_veri_form[f"{t_ad}_K{i+1}_Top"] = p
                    
                    ham_veri_form[f"{t_ad}_Toplam"] = sub_total
            
            # --- NESNE KONTROL ---
            st.warning("B. NESNE KONTROL")
            for t_ad, kr in TGMD3_PROTOCOL["NESNE_KONTROL"].items():
                with st.expander(t_ad):
                    sub_total = 0
                    for i, k in enumerate(kr):
                        st.write(k)
                        ca, cb = st.columns([1, 1])
                        
                        val_d1 = bool(mevcut_veri.get(f"{t_ad}_K{i+1}_D1", 0))
                        val_d2 = bool(mevcut_veri.get(f"{t_ad}_K{i+1}_D2", 0))

                        d1 = ca.checkbox("D1", key=f"N_{t_ad}_{i}_1", value=val_d1)
                        d2 = cb.checkbox("D2", key=f"N_{t_ad}_{i}_2", value=val_d2)
                        
                        p = int(d1) + int(d2)
                        sub_total += p
                        
                        ham_veri_form[f"{t_ad}_K{i+1}_D1"] = int(d1)
                        ham_veri_form[f"{t_ad}_K{i+1}_D2"] = int(d2)
                        ham_veri_form[f"{t_ad}_K{i+1}_Top"] = p
                    
                    ham_veri_form[f"{t_ad}_Toplam"] = sub_total

            # KAYDET BUTONU
            if st.form_submit_button("GÜNCELLE / KAYDET"):
                kayit = {
                    "OgrenciID": final_id, "Ad": ad, "Soyad": soyad, "Cinsiyet": cin,
                    "DogumTarihi": str(dt), "TestTarihi": str(tt), "El": el, "Ayak": ayak, "Konum": yer,
                    "Yas_Ay": yas_ay, "Yas_Grup_3Ay": yas_araligi_bul(yas_ay), "Kaynak": "Local"
                }
                kayit.update(ham_veri_form)
                
                # Yeni güncelleme fonksiyonunu çağır
                veritabani_kaydet(kayit, final_id, tt)
                st.success("Veriler başarıyla birleştirildi ve kaydedildi!")

# --- 2. IMPORT ---
elif menu == "2. Veri Import":
    st.header("Excel Import")
    up = st.file_uploader("Dosya Seç", type=["xlsx"])
    if up:
        try:
            df = pd.read_excel(up)
            if {"Ad", "Soyad"}.issubset(df.columns):
                for _, r in df.iterrows():
                    ad, soy = str(r.get("Ad","-")).strip().upper(), str(r.get("Soyad","-")).strip().upper()
                    dt, tt = str(r.get("DogumTarihi", date.today())), str(r.get("TestTarihi", date.today()))
                    uid = id_uret(ad, soy, dt, "EXT")
                    d = r.to_dict()
                    d.update({"OgrenciID": uid, "Yas_Ay": yas_hesapla_ay(dt, tt)})
                    d["Yas_Grup_3Ay"] = yas_araligi_bul(d["Yas_Ay"])
                    veritabani_kaydet(d, uid, tt)
                st.success("İşlem Tamam.")
                df_ana = veritabani_yukle()
        except Exception as e: st.error(f"Hata: {e}")

# --- 3. RAPOR ---
elif menu == "3. Gelişimsel Rapor":
    st.header("📊 Bireysel Gelişim ve Takip Raporu")
    df_ana = veritabani_yukle()
    
    if not df_ana.empty:
        ozet = df_ana[["OgrenciID", "Ad", "Soyad"]].drop_duplicates("OgrenciID")
        ozet["Gosterim"] = ozet["Ad"] + " " + ozet["Soyad"] + " (" + ozet["OgrenciID"] + ")"
        secim = st.selectbox("Öğrenci Seçiniz:", ozet["Gosterim"])
        if secim:
            sid = secim.split("(")[-1].strip(")")
            gecmis = df_ana[df_ana["OgrenciID"] == sid].sort_values("TestTarihi")
            ogr_info = df_ana[df_ana["OgrenciID"] == sid].iloc[-1]
            
            # --- A: TEK BİRLEŞİK GRAFİK ---
            st.markdown("### A. Grafiksel Genel Bakış")
            col_g1, col_g2 = st.columns([1, 1])

            test_isimleri = list(TGMD3_PROTOCOL["LOKOMOTOR"].keys()) + list(TGMD3_PROTOCOL["NESNE_KONTROL"].keys())
            kisa_isimler = [t.split("(")[0].strip() for t in test_isimleri]
            N = len(kisa_isimler)
            angles = [n / float(N) * 2 * pi for n in range(N)]
            angles += [angles[0]]
            
            # Radar Grafiği Ayarları
            fig_radar, ax_radar = plt.subplots(figsize=(5, 5), subplot_kw=dict(polar=True))
            
            # --- DÜZELTME BURADA: SABİT SKALA (0-10 ARASI) ---
            ax_radar.set_ylim(0, 10) 
            ax_radar.set_yticks([2, 4, 6, 8, 10])  # Ara çizgiler
            ax_radar.set_yticklabels(["2", "4", "6", "8", "10"], color="grey", size=8)
            # ------------------------------------------------
            
            colors = cm.viridis(np.linspace(0, 1, len(gecmis)))
            
            for idx, (index, row) in enumerate(gecmis.iterrows()):
                puanlar = [row.get(f"{t}_Toplam", 0) for t in test_isimleri]
                values = puanlar + [puanlar[0]]
                ax_radar.plot(angles, values, linewidth=2, label=str(row["TestTarihi"]), color=colors[idx])
                ax_radar.fill(angles, values, color=colors[idx], alpha=0.05)

            ax_radar.set_xticks(angles[:-1])
            ax_radar.set_xticklabels(kisa_isimler, size=8)
            # Legend kutusunu dışarı alalım ki grafik üstüne binmesin
            ax_radar.legend(loc='upper right', bbox_to_anchor=(1.3, 1.1), fontsize=8, title="Test Tarihleri")
            
            with col_g1:
                st.pyplot(fig_radar)

            # Çizgi Grafik (Z-Skor)
            fig_line, ax_line = plt.subplots(figsize=(8, 5))
            z_dates, z_values = [], []
            for _, row in gecmis.iterrows():
                norm = df_ana[(df_ana["Cinsiyet"]==row["Cinsiyet"]) & (df_ana["Yas_Grup_3Ay"]==row["Yas_Grup_3Ay"])]
                m, s = norm["Kaba_Motor_Puan"].mean(), norm["Kaba_Motor_Puan"].std()
                z = (row["Kaba_Motor_Puan"] - m) / s if s > 0 else 0
                z_dates.append(pd.to_datetime(row["TestTarihi"]))
                z_values.append(z)
            
            ax_line.plot(z_dates, z_values, marker='o', linestyle='-', color='blue')
            ax_line.axhline(0, color='gray', linestyle='--', label="Ortalama")
            ax_line.axhspan(-1, 1, color='green', alpha=0.1, label="Normal")
            ax_line.set_ylabel("Z-Skor")
            ax_line.legend()
            
            with col_g2:
                st.pyplot(fig_line)
            
            st.divider()
            
            # --- PDF İNDİRME ---
            pdf_data = create_full_report(
                {"Ad": ogr_info["Ad"], "Soyad": ogr_info["Soyad"], "ID": sid, "Cinsiyet": ogr_info["Cinsiyet"]},
                fig_radar, fig_line, gecmis, df_ana
            )
            st.download_button("📄 RAPORU İNDİR (PDF)", pdf_data, f"Rapor_{sid}.pdf", "application/pdf")

            # --- C: DETAYLI İNCELEME ---
            st.markdown("### C. Detaylı Veri")
            for idx, row in gecmis.iterrows():
                with st.expander(f"🗓️ Test Tarihi: {row['TestTarihi']} (Detaylar)", expanded=False):
                    col_tablo, col_grafik = st.columns([2, 1])
                    norm_grubu = df_ana[(df_ana["Cinsiyet"] == row["Cinsiyet"]) & (df_ana["Yas_Grup_3Ay"] == row["Yas_Grup_3Ay"])]
                    tablo_verisi = []
                    puanlar_tekil = []
                    
                    for t in test_isimleri:
                        col = f"{t}_Toplam"
                        p = row.get(col, 0)
                        puanlar_tekil.append(p)
                        if col in norm_grubu.columns:
                            mn, mx = norm_grubu[col].min(), norm_grubu[col].max()
                            ort, std = norm_grubu[col].mean(), norm_grubu[col].std()
                            z = (p - ort) / std if std > 0 else 0
                        else: mn, mx, ort, std, z = 0, 0, 0, 0, 0
                        
                        tablo_verisi.append({
                            "Beceri": t.split("(")[0], "Puan": p, "Ort": round(ort,1), 
                            "SS": round(std,1), "Min-Max": f"{mn}-{mx}", "Z": round(z,2), "Yorum": z_skor_yorumla(z)
                        })
                    
                    with col_tablo: st.dataframe(pd.DataFrame(tablo_verisi), use_container_width=True)
                    with col_grafik:
                        fig_tek, ax_tek = plt.subplots(figsize=(3, 3), subplot_kw=dict(polar=True))
                        
                        # --- DÜZELTME BURADA: KÜÇÜK GRAFİKLERDE DE SABİT SKALA ---
                        ax_tek.set_ylim(0, 10)
                        ax_tek.set_yticks([5, 10]) # Daha az çizgi yeterli
                        ax_tek.set_yticklabels(["5", "10"], color="grey", size=6)
                        # ---------------------------------------------------------

                        vals = puanlar_tekil + [puanlar_tekil[0]]
                        ax_tek.plot(angles, vals, color='blue', linewidth=2)
                        ax_tek.fill(angles, vals, color='blue', alpha=0.1)
                        ax_tek.set_xticks(angles[:-1])
                        ax_tek.set_xticklabels(kisa_isimler, size=6)
                        st.pyplot(fig_tek)
                        plt.close(fig_tek)
# --- 4. HAM VERİ ---
elif menu == "4. Araştırmacı Verisi":
    st.header("Ham Veri")
    df_ana = veritabani_yukle()
    if not df_ana.empty:
        st.dataframe(df_ana)