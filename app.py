import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import time
from datetime import datetime

# --- 1. KONFIGURASI CLOUDINARY ---
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"],
      secure = True
    )
except:
    st.error("Konfigurasi Secrets Cloudinary belum lengkap!")

st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# --- 2. FUNGSI PENDUKUNG (HELPERS) ---

def get_last_update(public_id, is_raw=True):
    """Mendapatkan waktu terakhir file diupdate di Cloudinary"""
    try:
        res = cloudinary.api.resource(public_id, resource_type="raw" if is_raw else "image")
        dt = datetime.strptime(res['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        # Sederhanakan tampilan: Jam:Menit - Tanggal/Bulan/Tahun
        return dt.strftime('%H:%M - %d/%m/%Y')
    except:
        return "Belum ada data"

def get_last_user_input():
    """Mencari file terbaru di folder rekap toko untuk tahu kapan terakhir user input"""
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="rekap_harian_toko/", max_results=1)
        if res.get('resources'):
            dt = datetime.strptime(res['resources'][0]['created_at'], '%Y-%m-%dT%H:%M:%SZ')
            return dt.strftime('%H:%M - %d/%m/%Y')
        return "Belum ada input"
    except:
        return "-"

def load_excel(public_id):
    """Ambil excel dari cloud"""
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"
        resp = requests.get(url, timeout=10)
        return pd.read_excel(io.BytesIO(resp.content)) if resp.status_code == 200 else None
    except:
        return None

# --- 3. LOGIKA MENU (SINGLE PAGE) ---
if 'page' not in st.session_state:
    st.session_state.page = "HOME"
if 'toko_cari' not in st.session_state:
    st.session_state.toko_cari = ""

# ==========================================
#              HALAMAN UTAMA (HOME)
# ==========================================
if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    st.write("Pilih menu untuk memulai operasional.")
    st.divider()
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("🏪 MENU INPUT TOKO", use_container_width=True, type="primary"):
            st.session_state.page = "USER"
            st.rerun()
    with col2:
        if st.button("🔑 MENU ADMIN PANEL", use_container_width=True):
            st.session_state.page = "ADMIN"
            st.rerun()

# ==========================================
#              HALAMAN ADMIN
# ==========================================
elif st.session_state.page == "ADMIN":
    c1, c2 = st.columns([5, 1])
    c1.header("🔐 Admin Panel")
    if c2.button("🚪 Logout", use_container_width=True):
        st.session_state.page = "HOME"
        st.rerun()

    pw = st.text_input("Password Admin:", type="password")
    if pw == "icnkl034":
        st.divider()
        
        # INFO TIMESTAMP (PENGGANTI PREVIEW TABEL)
        st.subheader("📊 Status Data Live")
        col_info1, col_info2 = st.columns(2)
        with col_info1:
            st.metric("Terakhir Master Diupload", get_last_update("master_so_utama.xlsx"))
        with col_info2:
            st.metric("Terakhir User Input Data", get_last_user_input())

        st.divider()
        
        # FITUR UPLOAD
        st.subheader("📤 Upload Master Data Baru")
        f = st.file_uploader("Pilih File Excel Master", type=["xlsx"])
        if f and st.button("🚀 Publish ke Seluruh Toko"):
            cloudinary.uploader.upload(f, resource_type="raw", public_id="master_so_utama.xlsx", overwrite=True)
            st.success("Master Berhasil Diperbarui!")
            time.sleep(1)
            st.rerun()

        st.divider()
        
        # FITUR DOWNLOAD GABUNGAN
        st.subheader("📥 Tarik Hasil Input")
        if st.button("🔄 Gabungkan & Download Semua Laporan Toko"):
            with st.spinner("Menggabungkan data..."):
                master = load_excel("master_so_utama.xlsx")
                if master is not None:
                    try:
                        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="rekap_harian_toko/")
                        for r in res.get('resources', []):
                            store_df = pd.read_excel(r['secure_url'])
                            key = 'plu' if 'plu' in store_df.columns else 'gab'
                            for _, row in store_df.iterrows():
                                mask = (master[key] == row[key]) & (master['toko'].astype(str) == str(row['toko']))
                                if mask.any():
                                    master.loc[mask, store_df.columns] = row.values
                        
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                            master.to_excel(writer, index=False)
                        st.download_button("📥 Klik Download Hasil Gabungan", buf.getvalue(), "Rekap_Final.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
                    except:
                        st.error("Gagal menggabungkan. Mungkin belum ada toko yang input.")

# ==========================================
#              HALAMAN USER INPUT
# ==========================================
elif st.session_state.page == "USER":
    c1, c2 = st.columns([5, 1])
    c1.header("📋 Input Data Toko")
    if c2.button("🚪 Logout", use_container_width=True):
        st.session_state.page = "HOME"
        st.session_state.toko_cari = ""
        st.rerun()

    # INFO TIMESTAMP UNTUK USER
    st.caption(f"Update Master Terakhir: {get_last_update('master_so_utama.xlsx')}")

    # INPUT KODE TOKO DENGAN TOMBOL CARI
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        toko_id = st.text_input("📍 Masukkan Kode Toko (4 Digit):", max_chars=4).upper()
    with col_btn:
        st.write("##") # Spacer
        cari_clicked = st.button("🔍 Cari Data", use_container_width=True)

    if cari_clicked or st.session_state.toko_cari:
        if toko_id:
            st.session_state.toko_cari = toko_id # Simpan status cari
            master = load_excel("master_so_utama.xlsx")
            
            if master is not None:
                filtered = master[master['toko'].astype(str).str.contains(st.session_state.toko_cari)].copy()
                
                if not filtered.empty:
                    st.subheader(f"🏠 Toko: {st.session_state.toko_cari}")
                    # Hapus kolom lama agar tidak double
                    for c in ["sls+fisik", "ket input", "selisih"]:
                        if c in filtered.columns: filtered.drop(columns=[c], inplace=True)
                    
                    # Setup awal kolom kalkulasi
                    filtered["sls+fisik"], filtered["ket input"], filtered["selisih"] = 0, "tidak input", 0

                    # DATA EDITOR
                    edited = st.data_editor(
                        filtered,
                        disabled=[c for c in filtered.columns if c not in ["query sales hari H", "jml fisik"]],
                        hide_index=True, use_container_width=True, key=f"ed_{st.session_state.toko_cari}"
                    )

                    # LOGIKA RUMUS REAL-TIME
                    sales = pd.to_numeric(edited['query sales hari H'], errors='coerce').fillna(0)
                    fisik = pd.to_numeric(edited['jml fisik'], errors='coerce').fillna(0)
                    lpp = pd.to_numeric(edited['stok lpp h-1'], errors='coerce').fillna(0)
                    edited['sls+fisik'] = sales + fisik
                    edited['selisih'] = edited['sls+fisik'] - lpp
                    edited['ket input'] = ["input" if pd.notnull(s) and pd.notnull(f) else "tidak input" 
                                           for s, f in zip(edited['query sales hari H'], edited['jml fisik'])]

                    st.write("### 📝 Preview Hasil Perhitungan:")
                    st.dataframe(edited, use_container_width=True, hide_index=True)

                    if st.button("🚀 Submit & Kirim Laporan", type="primary"):
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                            edited.to_excel(writer, index=False)
                        buf.seek(0)
                        cloudinary.uploader.upload(buf, resource_type="raw", public_id=f"rekap_harian_toko/Hasil_Toko_{st.session_state.toko_cari}.xlsx", overwrite=True)
                        st.success("✅ Laporan Berhasil Dikirim!")
                else:
                    st.error("Toko tidak ditemukan.")
