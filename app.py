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
def confirm_submit_dialog(data_to_save, toko_code):
    st.warning(f"⚠️ Apakah data Toko {toko_code} sudah ter-input dengan benar?")
    
    if st.button("Ya, Submit Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_to_save.to_excel(writer, index=False)
        
        buffer.seek(0)
        try:
            result = cloudinary.uploader.upload(
                buffer, 
                resource_type="raw", 
                public_id=f"Laporan_{toko_code}", 
                folder="laporan_toko_harian",
                overwrite=True # Menimpa file lama jika toko yang sama submit ulang
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

if uploaded_file and st.session_state.master_df is None:
    st.session_state.master_df = pd.read_excel(uploaded_file)

if st.session_state.master_df is not None:
    df = st.session_state.master_df

    st.divider()
    col_f1, col_f2 = st.columns([1, 2])
    with col_f1:
        search_toko = st.text_input("🔍 Masukkan Kode Toko Anda:", placeholder="Contoh: F2AA").upper()

    if search_toko:
        # Filter data
        filtered_df = df[df['toko'].astype(str).str.contains(search_toko)].copy()
        
        if filtered_df.empty:
            st.error(f"Data untuk toko {search_toko} tidak ditemukan.")
        else:
            st.subheader(f"Data Toko: {search_toko}")
            
            # Kolom yang BOLEH diedit
            EDITABLE_COLUMNS = ["query sales hari H", "jml fisik"]
            
            # Pastikan kolom target ada, jika tidak ada kita buat kolom kosongnya
            for col in ["query sales hari H", "jml fisik", "sls+fisik", "ket input", "selisih"]:
                if col not in filtered_df.columns:
                    filtered_df[col] = 0 if col != "ket input" else "tidak input"

            # Tentukan kolom yang dikunci
            disabled_cols = [col for col in filtered_df.columns if col not in EDITABLE_COLUMNS]

            # --- 4. DATA EDITOR ---
            edited_df = st.data_editor(
                filtered_df,
                disabled=disabled_cols,
                hide_index=True,
                use_container_width=True,
                key=f"editor_{search_toko}"
            )

            # --- 5. LOGIKA RUMUS OTOMATIS ---
            # Mengonversi ke numeric untuk menghindari error perhitungan
            s_sales = pd.to_numeric(edited_df['query sales hari H']).fillna(0)
            s_fisik = pd.to_numeric(edited_df['jml fisik']).fillna(0)
            s_lpp   = pd.to_numeric(edited_df['stok lpp h-1']).fillna(0)

            # A. Rumus sls+fisik = query sales hari H + jml fisik
            edited_df['sls+fisik'] = s_sales + s_fisik

            # B. Rumus selisih = (query sales hari H + jml fisik) - stok lpp h-1
            edited_df['selisih'] = (s_sales + s_fisik) - s_lpp

            # C. Rumus ket input = Jika dua-duanya diisi muncul 'input', jika tidak 'tidak input'
            # Kita anggap 'diisi' jika salah satu atau keduanya bukan nol/kosong
            edited_df['ket input'] = edited_df.apply(
                lambda row: "input" if (pd.notnull(row['query sales hari H']) and pd.notnull(row['jml fisik'])) else "tidak input", 
                axis=1
            )

            # Tampilkan Ringkasan Perubahan (Opsional, agar user yakin rumusnya jalan)
            st.write("---")
            
            # --- 6. TOMBOL SUBMIT ---
            if st.button("🚀 Submit Data Toko"):
                confirm_submit_dialog(edited_df, search_toko)
    else:
        st.info("Silakan masukkan Kode Toko di atas.")
else:
    st.warning("Silakan upload file Master Excel.")