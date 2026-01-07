import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import io

# --- 1. KONFIGURASI CLOUDINARY ---
cloudinary.config( 
  cloud_name = st.secrets["cloud_name"] if "cloud_name" in st.secrets else "DUMMY", 
  api_key = st.secrets["api_key"] if "api_key" in st.secrets else "DUMMY", 
  api_secret = st.secrets["api_secret"] if "api_secret" in st.secrets else "DUMMY",
  secure = True
)

st.set_page_config(page_title="Input Stok Toko", layout="wide")

# --- 2. FUNGSI DIALOG KONFIRMASI ---
@st.dialog("Konfirmasi Simpan Data")
def confirm_submit_dialog(data_to_save):
    st.warning("⚠️ Apakah data sudah ter-input dengan benar?")
    st.write("Setelah menekan tombol di bawah, file akan diproses untuk disimpan.")
    
    if st.button("Ya, Submit Sekarang"):
        # Proses Simpan ke Excel di dalam Memory
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_to_save.to_excel(writer, index=False)
        
        # Upload ke Cloudinary
        buffer.seek(0)
        try:
            result = cloudinary.uploader.upload(
                buffer, 
                resource_type="raw", 
                public_id=f"Laporan_Update_{st.session_state.kode_toko}", # Nama file unik per toko
                folder="laporan_toko_harian"
            )
            st.success(f"Berhasil! Data Toko {st.session_state.kode_toko} telah tersimpan.")
            st.info(f"Link File: {result['secure_url']}")
        except Exception as e:
            st.error(f"Gagal upload: {e}")

# --- 3. TAMPILAN UTAMA ---
st.title("📑 Sistem Input Fisik Toko")

# Inisialisasi session state untuk menyimpan master data agar tidak hilang saat refresh
if 'master_df' not in st.session_state:
    st.session_state.master_df = None

uploaded_file = st.file_uploader("Upload File Excel Master (Hanya Sekali)", type=["xlsx"])

if uploaded_file and st.session_state.master_df is None:
    st.session_state.master_df = pd.read_excel(uploaded_file)

if st.session_state.master_df is not None:
    df = st.session_state.master_df

    # --- 4. FITUR FILTER TOKO ---
    st.divider()
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        # User menginput kode toko (misal: F02X)
        search_toko = st.text_input("🔍 Masukkan Kode Toko Anda:", placeholder="Contoh: F02X").upper()

    if search_toko:
        # Filter data berdasarkan kode toko
        filtered_df = df[df['toko'].astype(str).str.contains(search_toko)]
        
        if filtered_df.empty:
            st.error(f"Data untuk toko {search_toko} tidak ditemukan.")
        else:
            st.session_state.kode_toko = search_toko
            st.subheader(f"Data Toko: {search_toko}")
            
            # Kolom yang boleh diedit
            EDITABLE_COLUMNS = ["query sales hari H", "jml fisik", "ket input"]
            existing_editable = [col for col in EDITABLE_COLUMNS if col in filtered_df.columns]
            disabled_cols = [col for col in filtered_df.columns if col not in existing_editable]

            # --- 5. DATA EDITOR ---
            edited_df = st.data_editor(
                filtered_df,
                disabled=disabled_cols,
                hide_index=True,
                use_container_width=True,
                key="editor_toko"
            )

            # Hitung otomatis untuk kolom selisih (jika ada)
            if 'jml fisik' in edited_df.columns and 'stok lpp h-1' in edited_df.columns:
                edited_df['jml fisik'] = edited_df['jml fisik'].fillna(0)
                edited_df['query sales hari H'] = edited_df['query sales hari H'].fillna(0)
                edited_df['sls+fisik'] = edited_df['query sales hari H'] + edited_df['jml fisik']
                edited_df['selisih'] = edited_df['sls+fisik'] - edited_df['stok lpp h-1']

            st.divider()
            
            # --- 6. TOMBOL SUBMIT ---
            if st.button("🚀 Submit Data Toko"):
                # Panggil dialog konfirmasi
                confirm_submit_dialog(edited_df)
    else:
        st.info("Silakan masukkan Kode Toko di atas untuk menampilkan data.")

else:
    st.warning("Silakan upload file Master Excel terlebih dahulu.")