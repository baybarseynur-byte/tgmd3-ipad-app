import streamlit as st
import pandas as pd
import numpy as np
import os
import hashlib
import tempfile
from datetime import date
import matplotlib.pyplot as plt
from fpdf import FPDF

# =============================================================================
# 1. AYARLAR VE TEST PROTOKOLÜ
# =============================================================================
st.set_page_config(page_title="TGMD-3 PRO (Grafik Rapor)", layout="wide", page_icon="📊")

# Temiz bir başlangıç için dosya adını değiştirdim
DB_FILE = "tgmd3_no_scipy_v1.xlsx"

# TGMD-3 Alt Testleri ve Maddeleri
TGMD3_PROTOCOL = {
    "LOKOMOTOR": {
        "Koşu": ["1. Kollar bükülü", "2. Ayaklar havada", "3. Ayak ucu basma", "4. Destek bacağı 90°"],
        "Galop": ["1. Kollar bükülü", "2. İki ayak havada", "3. Ritmik yapı", "4. Ayak takibi"],
        "Sek Sek": ["1. Salınım ayağı", "2. Salınım vücuda yakın", "3. Kollar bükülü", "4. 3 kez ardışık"],
        "Atlama": ["1. Ritmik adım", "2. Kollar çapraz", "3. İniş dengesi"],
        "Uzun Atlama": ["1. Hazırlık çökmesi", "2. Kollar yukarı", "3. Çift ayak iniş", "4. Denge"],
        "Kayma": ["1. Yan duruş", "2. Ayak takibi", "3. Ritmik kayma", "4. Yön değişimi"]
    },
    "NESNE_KONTROL": {
        "Sopa Vuruş": ["1. Tutuş", "2. Yan duruş", "3. Rotasyon", "4. İsabet", "5. Takip"],
        "Forehand": ["1. Geriye alma", "2. Adımlama", "3. Temas", "4. Raket takibi"],
        "Top Sürme": ["1. Bel hizası", "2. Parmak ucu", "3. Top kontrolü"],
        "Yakalama": ["1. Hazırlık", "2. Uzanma", "3. Elle kavrama"],
        "Ayak Vuruş": ["1. Yaklaşma", "2. Destek ayağı", "3. Vuruş", "4. Takip"],
        "Fırlatma": ["1. Geriye alma", "2. Zıt ayak", "3. Rotasyon", "4. Takip"],
        "Yuvarlama": ["1. Kol salınımı", "2. Diz bükme", "3. Zemin teması", "4. Takip"]
    }
}

# Maksimum Puanları Otomatik Hesapla (Madde Sayısı * 2)
MAX_PUANLAR = {}
for grup in TGMD3_PROTOCOL:
    for test, maddeler in TGMD3_PROTOCOL[grup].items():
        MAX_PUANLAR[test] = len(maddeler) * 2

# =============================================================================
# 2. VERİTABANI İŞLEMLERİ (KIRILMAZ YAPI)
# =============================================================================
def veri_yukle():
    if not os.path.exists(DB_FILE): return pd.DataFrame()
    try:
        df = pd.read_excel(DB_FILE)
        # Metinleri temizle
        for c in ["Ad", "Soyad", "Tarih", "ID", "Grup"]:
            if c in df.columns: df[c] = df[c].fillna("").astype(str)
        # Sayıları temizle
        for c in df.columns:
            if "Puan" in c or c == "Toplam": 
                df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
        return df
    except: return pd.DataFrame()

def veri_kaydet(yeni_veri):
    df = veri_yukle()
    if not df.empty:
        # ID ve Tarih çakışmasını engelle (Eski kaydı sil)
        mask = (df["ID"] == yeni_veri["ID"]) & (df["Tarih"] == yeni_veri["Tarih"])
        df = df[~mask]
    
    yeni_df = pd.DataFrame([yeni_veri])
    son_df = pd.concat([df, yeni_df], ignore_index=True)
    
    with pd.ExcelWriter(DB_FILE, engine="openpyxl") as w:
        son_df.to_excel(w, index=False)
    return True

# =============================================================================
# 3. GRAFİK MOTORU (SÜTUN GRAFİĞİ VE NORMAL DAĞILIM)
# =============================================================================
def grafik_ciz(isim, puanlar):
    """
    Hedef tahtası yerine anlaşılır Sütun Grafiği çizer.
    """
    labels = list(MAX_PUANLAR.keys())
    max_values = list(MAX_PUANLAR.values())
    student_values = [puanlar.get(f"{l}_Puan", 0) for l in labels]
    
    # Grafik Alanı
    fig, ax = plt.subplots(figsize=(10, 8))
    
    y_pos = np.arange(len(labels))
    
    # 1. Arka Plan (Gri Çubuk - Maksimum Puan)
    ax.barh(y_pos, max_values, align='center', color='#ecf0f1', label='Maksimum Puan', height=0.7)
    
    # 2. Ön Plan (Renkli Çubuk - Öğrenci Puanı)
    colors = []
    for s, m in zip(student_values, max_values):
        oran = s / m if m > 0 else 0
        if oran < 0.4: colors.append('#e74c3c') # Kırmızı
        elif oran < 0.7: colors.append('#f1c40f') # Sarı
        else: colors.append('#2ecc71') # Yeşil
        
    ax.barh(y_pos, student_values, align='center', color=colors, label='Öğrenci Puanı', height=0.5)
    
    # Ayarlar
    ax.set_yticks(y_pos)
    ax.set_yticklabels(labels, fontsize=11, fontweight='bold')
    ax.invert_yaxis()  # Yukarıdan aşağı sırala
    ax.set_xlabel('Puan Değeri')
    ax.set_title(f"{isim} - Beceri Gelişim Grafiği", fontweight='bold', fontsize=14)
    
    # Çubukların içine puanları yaz
    for i, (s, m) in enumerate(zip(student_values, max_values)):
        ax.text(0.2, i, f"Alınan: {int(s)} / Max: {int(m)}", color='black', va='center', fontweight='bold', fontsize=9)
    
    # Çerçeveyi temizle
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.get_xaxis().set_visible(False)
    
    plt.tight_layout()
    return fig

def normal_dagilim_manuel(puan, ort, ss):
    """
    Scipy kütüphanesi OLMADAN Normal Dağılım Çizer.
    Formül: (1 / (ss * sqrt(2*pi))) * exp(-0.5 * ((x-ort)/ss)**2)
    """
    try:
        if ss == 0: ss = 1 # Hata önleyici
        
        fig, ax = plt.subplots(figsize=(8, 4))
        
        # X ekseni (ortalamanın +- 3 standart sapması)
        x = np.linspace(ort - 3*ss, ort + 3*ss, 100)
        
        # Manuel Normal Dağılım Formülü
        y = (1 / (ss * np.sqrt(2 * np.pi))) * np.exp(-0.5 * ((x - ort) / ss) ** 2)
        
        ax.plot(x, y, color='black', linewidth=2)
        ax.fill_between(x, y, alpha=0.2, color='blue')
        
        # Öğrencinin Yeri
        ax.axvline(puan, color='red', linestyle='--', linewidth=2)
        
        # Etiket
        max_y = np.max(y)
        ax.text(puan, max_y * 1.05, f"Öğrenci\n{int(puan)}", color='red', ha='center', fontweight='bold')
        
        ax.set_yticks([])
        ax.set_title("Gelişimsel Konum (Çan Eğrisi)", fontweight='bold')
        
        # Alt ekseni temizle
        ax.spines['top'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['right'].set_visible(False)
        
        return fig
    except:
        return plt.figure()

# =============================================================================
# 4. RAPOR OLUŞTURMA (PDF)
# =============================================================================
def pdf_uret(bilgi, tablo_df, fig_bar, fig_norm):
    pdf = FPDF()
    pdf.add_page()
    
    # Başlık
    pdf.set_font("Arial", "B", 16)
    pdf.cell(0, 10, "TGMD-3 GELISIM RAPORU", ln=True, align="C")
    pdf.ln(5)
    
    # Bilgiler
    pdf.set_font("Arial", size=11)
    pdf.cell(0, 7, f"Ogrenci: {bilgi['Ad']} {bilgi['Soyad']}", ln=True)
    pdf.cell(0, 7, f"Tarih: {bilgi['Tarih']}", ln=True)
    pdf.cell
