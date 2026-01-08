import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import time

# --- 1. KONFIGURASI CLOUDINARY ---
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"],
      secure = True
    )
except:
    st.error("Setting Secrets Cloudinary dulu!")

st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# --- 2. FUNGSI INTI ---

def get_cloud_url(public_id):
    """Mendapatkan URL file dengan timestamp agar tidak terkena cache browser"""
    return f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"

def load_excel_from_url(url):
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            return pd.read_excel(io.BytesIO(resp.content))
    except:
        return None
    return None

def merge_all_reports(master_df):
    """Menggabungkan master data dengan semua hasil input toko yang ada di Cloudinary"""
    try:
        # Cari semua file yang diawali dengan 'Hasil_Toko_' di folder 'rekap_harian_toko'
        resources = cloudinary.api.resources(resource_type="raw", type="upload", prefix="rekap_harian_toko/Hasil_Toko_")
        
        for res in resources.get('resources', []):
            url = res['secure_url']
            store_df = load_excel_from_url(url)
            if store_df is not None:
                # Timpa data di master dengan data dari toko (berdasarkan PLU/Gab)
                for _, row in store_df.iterrows():
                    # Pastikan kolom join ada (misal: 'plu' atau 'gab')
                    key = 'plu' if 'plu' in row else 'gab'
                    mask = (master_df[key] == row[key]) & (master_df['toko'].astype(str) == str(row['toko']))
                    if mask.any():
                        master_df.loc[mask, store_df.columns] = row.values
        return master_df
    except:
        return master_df

# --- 3. LOGIKA MENU ---
if 'menu_active' not in st.session_state:
    st.session_state.menu_active = "HOME"

# Tombol Navigasi Home selalu muncul di atas
if st.session_state.menu_active != "HOME":
    if st.button("🏠 Kembali ke Menu Utama"):
        st.session_state.menu_active = "HOME"
        st.rerun()

# ==========================================
#              HALAMAN UTAMA
# ==========================================
if st.session_state.menu_active == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("🏪 INPUT DATA TOKO", use_container_width=True, type="primary"):
        st.session_state.menu_active = "INPUT_TOKO"
        st.rerun()
    if c2.button("🔑 MENU ADMIN", use_container_width=True):
        st.session_state.menu_active = "ADMIN"
        st.rerun()

# ==========================================
#              HALAMAN ADMIN
# ==========================================
elif st.session_state.menu_active == "ADMIN":
    st.header("🔐 Admin Panel")
    pw = st.text_input("Password:", type="password")
    if pw == "icnkl034":
        st.divider()
        # UPLOAD
        st.subheader("1. Upload Master Baru")
        f = st.file_uploader("Pilih Excel", type=["xlsx"])
        if f and st.button("🚀 Publish ke Toko"):
            cloudinary.uploader.upload(f, resource_type="raw", public_id="master_so_utama.xlsx", overwrite=True)
            st.success("Berhasil di-Publish!")
            time.sleep(2)
            st.rerun()

        st.divider()
        # DOWNLOAD
        st.subheader("2. Download Hasil Akhir (Gabungan)")
        if st.button("🔄 Tarik & Gabung Data Semua Toko"):
            with st.spinner("Sedang mengambil data dari semua toko..."):
                master = load_excel_from_url(get_cloud_url("master_so_utama.xlsx"))
                if master is not None:
                    final_df = merge_all_reports(master)
                    
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                        final_df.to_excel(writer, index=False)
                    
                    st.download_button(
                        label="📥 Download Excel Hasil Gabungan",
                        data=buf.getvalue(),
                        file_name=f"Rekap_Total_{int(time.time())}.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )
                else:
                    st.error("File master tidak ditemukan di cloud.")

# ==========================================
#              HALAMAN TOKO
# ==========================================
elif st.session_state.menu_active == "INPUT_TOKO":
    st.header("📋 Input Data Toko")
    master = load_excel_from_url(get_cloud_url("master_so_utama.xlsx"))
    
    if master is None:
        st.warning("Data belum di-publish Admin.")
    else:
        toko_id = st.text_input("📍 Kode Toko:", max_chars=4).upper()
        if toko_id:
            filtered = master[master['toko'].astype(str).str.contains(toko_id)].copy()
            if not filtered.empty:
                # Hapus kolom lama agar tidak double
                for c in ["sls+fisik", "ket input", "selisih"]:
                    if c in filtered.columns: filtered.drop(columns=[c], inplace=True)
                
                # Setup kolom
                filtered["sls+fisik"] = 0
                filtered["ket input"] = "tidak input"
                filtered["selisih"] = 0

                # EDITOR
                edited = st.data_editor(filtered, hide_index=True, use_container_width=True, key=f"ed_{toko_id}")
                
                # RUMUS REALTIME
                sales = pd.to_numeric(edited['query sales hari H'], errors='coerce').fillna(0)
                fisik = pd.to_numeric(edited['jml fisik'], errors='coerce').fillna(0)
                lpp = pd.to_numeric(edited['stok lpp h-1'], errors='coerce').fillna(0)
                edited['sls+fisik'] = sales + fisik
                edited['selisih'] = edited['sls+fisik'] - lpp
                edited['ket input'] = ["input" if pd.notnull(s) and pd.notnull(f) else "tidak input" 
                                       for s, f in zip(edited['query sales hari H'], edited['jml fisik'])]

                if st.button("🚀 Submit & Simpan"):
                    # SIMPAN KE FOLDER KHUSUS AGAR BISA DI-MERGE ADMIN
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                        edited.to_excel(writer, index=False)
                    buf.seek(0)
                    cloudinary.uploader.upload(
                        buf, resource_type="raw", 
                        public_id=f"rekap_harian_toko/Hasil_Toko_{toko_id}.xlsx", 
                        overwrite=True
                    )
                    st.success(f"Data Toko {toko_id} tersimpan!")
            else:
                st.error("Toko tidak ketemu.")
