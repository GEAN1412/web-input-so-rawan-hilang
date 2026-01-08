import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests

# --- 1. KONFIGURASI CLOUDINARY ---
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"],
      secure = True
    )
except:
    st.error("Konfigurasi API Cloudinary belum disetting di Secrets!")

st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# --- 2. FUNGSI UNTUK MENGAMBIL DATA DARI CLOUDINARY ---
@st.cache_data(ttl=600) # Simpan cache selama 10 menit agar tidak terus-menerus download
def load_data_from_cloud():
    try:
        # Mencari URL file master terbaru di Cloudinary
        # Kita gunakan public_id tetap agar mudah dipanggil
        file_url = cloudinary.utils.cloudinary_url("master_so_utama", resource_type="raw")[0]
        
        # Download file
        response = requests.get(file_url)
        if response.status_code == 200:
            return pd.read_excel(io.BytesIO(response.content))
        else:
            return None
    except:
        return None

# --- 3. INITIALIZE MENU ---
if 'menu_active' not in st.session_state:
    st.session_state.menu_active = "HOME"

# ==========================================
#              HALAMAN UTAMA
# ==========================================
if st.session_state.menu_active == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    st.info("💡 Pastikan Admin sudah mengupload data terbaru pagi ini.")
    
    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("🏪 INPUT DATA TOKO", use_container_width=True, type="primary"):
            st.session_state.menu_active = "INPUT_TOKO"
            st.rerun()
    with col_b:
        if st.button("🔑 MENU ADMIN", use_container_width=True):
            st.session_state.menu_active = "ADMIN"
            st.rerun()

# ==========================================
#              HALAMAN ADMIN
# ==========================================
elif st.session_state.menu_active == "ADMIN":
    if st.button("⬅️ Kembali"):
        st.session_state.menu_active = "HOME"
        st.rerun()

    st.header("🔐 Admin Panel")
    pw = st.text_input("Password:", type="password")
    if pw == "icnkl034":
        st.subheader("Upload Master Data Harian")
        file_admin = st.file_uploader("Pilih File Excel", type=["xlsx"])
        
        if file_admin and st.button("🚀 Publish ke Semua Toko"):
            # Upload ke Cloudinary dengan public_id TETAP
            # Ini akan menimpa file lama sehingga toko selalu dapat yang terbaru
            res = cloudinary.uploader.upload(
                file_admin, 
                resource_type="raw", 
                public_id="master_so_utama", 
                overwrite=True
            )
            st.success("✅ File Berhasil di-Publish! Toko sekarang bisa melihat data ini.")
            st.cache_data.clear() # Hapus cache agar data baru langsung terbaca

# ==========================================
#              HALAMAN TOKO
# ==========================================
elif st.session_state.menu_active == "INPUT_TOKO":
    if st.button("⬅️ Kembali"):
        st.session_state.menu_active = "HOME"
        st.rerun()

    st.header("📋 Input Data Toko")
    
    # OTOMATIS LOAD DATA DARI CLOUD
    df_cloud = load_data_from_cloud()
    
    if df_cloud is None:
        st.warning("⚠️ Data belum diupload oleh Admin atau koneksi bermasalah.")
    else:
        toko_input = st.text_input("📍 Masukkan Kode Toko (4 digit):", max_chars=4).upper()
        
        if st.button("🔍 Cari & Sinkron Data"):
            # Filter data
            filtered_df = df_cloud[df_cloud['toko'].astype(str).str.contains(toko_input)].copy()
            
            if filtered_df.empty:
                st.error("Data Toko Tidak Ditemukan.")
            else:
                # (Bagian Editor & Perhitungan sama seperti sebelumnya...)
                st.write(f"Menampilkan data untuk toko: {toko_input}")
                # Hapus kolom lama agar tidak duplikat
                for c in ["sls+fisik", "ket input", "selisih"]:
                    if c in filtered_df.columns: filtered_df.drop(columns=[c], inplace=True)
                
                # Editor
                edited = st.data_editor(filtered_df, hide_index=True, use_container_width=True)
                
                # Rumus
                # ... (Logika rumus Anda) ...
                st.button("🚀 Simpan Hasil Akhir")
