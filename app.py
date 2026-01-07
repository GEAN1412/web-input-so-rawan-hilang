import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import io

# --- 1. KONFIGURASI CLOUDINARY ---
# Mengambil dari st.secrets dengan penanganan error lebih baik
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"],
      secure = True
    )
except:
    st.error("Konfigurasi Cloudinary tidak ditemukan di Secrets!")

st.set_page_config(page_title="Input Stok Toko", layout="wide")

# --- 2. FUNGSI DIALOG KONFIRMASI ---
@st.dialog("Konfirmasi Simpan Data")
def confirm_submit_dialog(data_to_save, toko_code):
    st.warning(f"⚠️ Apakah data Toko {toko_code} sudah ter-input dengan benar?")
    
    if st.button("Ya, Submit Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_to_save.to_excel(writer, index=False)
        
        buffer.seek(0)
        try:
            # Menggunakan cloud_name langsung dari secrets untuk memastikan validitas
            result = cloudinary.uploader.upload(
                buffer, 
                resource_type="raw", 
                public_id=f"Laporan_{toko_code}", 
                folder="laporan_toko_harian",
                overwrite=True
            )
            st.success(f"✅ Berhasil! Data Toko {toko_code} telah tersimpan.")
            st.info(f"Link File: {result['secure_url']}")
        except Exception as e:
            st.error(f"Gagal upload: {e}")

# --- 3. TAMPILAN UTAMA ---
st.title("📑 Sistem Input Fisik & Sales Toko")

if 'master_df' not in st.session_state:
    st.session_state.master_df = None

uploaded_file = st.file_uploader("Upload File Excel Master", type=["xlsx"])

if uploaded_file:
    # Hanya baca file jika belum ada di session state
    if st.session_state.master_df is None:
        st.session_state.master_df = pd.read_excel(uploaded_file)

if st.session_state.master_df is not None:
    df_main = st.session_state.master_df.copy()

    st.divider()
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        search_toko = st.text_input("🔍 Masukkan Kode Toko Anda:", placeholder="Contoh: F2AA").upper()

    if search_toko:
        # Filter data awal
        filtered_df = df_main[df_main['toko'].astype(str).str.contains(search_toko)].copy()
        
        if filtered_df.empty:
            st.error(f"Data untuk toko {search_toko} tidak ditemukan.")
        else:
            # Pastikan kolom-kolom target ada
            target_cols = ["query sales hari H", "jml fisik", "sls+fisik", "ket input", "selisih"]
            for col in target_cols:
                if col not in filtered_df.columns:
                    filtered_df[col] = 0 if col != "ket input" else "tidak input"

            # Tentukan kolom yang dikunci
            EDITABLE_COLUMNS = ["query sales hari H", "jml fisik"]
            disabled_cols = [col for col in filtered_df.columns if col not in EDITABLE_COLUMNS]

            # --- 4. DATA EDITOR ---
            # Editor akan mengembalikan dataframe yang sudah diedit
            edited_df = st.data_editor(
                filtered_df,
                disabled=disabled_cols,
                hide_index=True,
                use_container_width=True,
                key=f"editor_{search_toko}"
            )

            # --- 5. LOGIKA RUMUS REAL-TIME ---
            # Gunakan data dari edited_df untuk menghitung ulang secara instan
            # pd.to_numeric dengan errors='coerce' akan mengubah data tidak valid menjadi NaN
            sales = pd.to_numeric(edited_df['query sales hari H'], errors='coerce')
            fisik = pd.to_numeric(edited_df['jml fisik'], errors='coerce')
            lpp   = pd.to_numeric(edited_df['stok lpp h-1'], errors='coerce').fillna(0)

            # A. Update sls+fisik
            edited_df['sls+fisik'] = sales.fillna(0) + fisik.fillna(0)

            # B. Update selisih
            edited_df['selisih'] = edited_df['sls+fisik'] - lpp

            # C. Update ket input (Jika keduanya memiliki nilai/angka, termasuk 0)
            # Kondisi: notnull() memastikan sel tidak kosong
            edited_df['ket input'] = edited_df.apply(
                lambda row: "input" if pd.notnull(row['query sales hari H']) and pd.notnull(row['jml fisik']) else "tidak input", 
                axis=1
            )

            # Tampilkan tabel yang sudah berisi hasil kalkulasi (Read Only)
            st.write("### Review Hasil Perhitungan:")
            st.dataframe(edited_df, use_container_width=True, hide_index=True)

            # --- 6. TOMBOL SUBMIT ---
            if st.button("🚀 Submit Data Toko"):
                confirm_submit_dialog(edited_df, search_toko)
    else:
        st.info("Silakan masukkan Kode Toko di atas.")
else:
    st.warning("Silakan upload file Master Excel.")