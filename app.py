import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import io

# --- 1. KONFIGURASI CLOUDINARY ---
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
    st.warning(f"⚠️ Apakah data Toko {toko_code} sudah benar?")
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
                overwrite=True
            )
            st.success(f"✅ Berhasil Terarsip di Cloudinary!")
            st.info(f"Link: {result['secure_url']}")
        except Exception as e:
            st.error(f"Gagal upload: {e}")

# --- 3. TAMPILAN UTAMA ---
st.title("📑 Sistem Input Fisik & Sales Toko")

if 'master_df' not in st.session_state:
    st.session_state.master_df = None

uploaded_file = st.file_uploader("Upload File Excel Master", type=["xlsx"])

if uploaded_file:
    if st.session_state.master_df is None:
        # Load data dan hapus kolom duplikat jika ada di file asli
        temp_df = pd.read_excel(uploaded_file)
        st.session_state.master_df = temp_df.loc[:, ~temp_df.columns.duplicated()].copy()

if st.session_state.master_df is not None:
    df_main = st.session_state.master_df.copy()

    st.divider()
    search_toko = st.text_input("🔍 Masukkan Kode Toko Anda:", placeholder="Contoh: F2AA").upper()

    if search_toko:
        # 1. Filter data berdasarkan toko
        filtered_df = df_main[df_main['toko'].astype(str).str.contains(search_toko)].copy()
        
        if filtered_df.empty:
            st.error(f"Data toko {search_toko} tidak ditemukan.")
        else:
            # 2. BERSIHKAN KOLOM (Hapus kolom lama agar tidak duplikat saat dihitung ulang)
            cols_to_fix = ["sls+fisik", "ket input", "selisih"]
            for c in cols_to_fix:
                if c in filtered_df.columns:
                    filtered_df = filtered_df.drop(columns=[c])

            # 3. INISIALISASI KOLOM BARU (Kosong)
            filtered_df["sls+fisik"] = 0
            filtered_df["ket input"] = "tidak input"
            filtered_df["selisih"] = 0

            # 4. DATA EDITOR
            st.subheader(f"Data Toko: {search_toko}")
            EDITABLE_COLUMNS = ["query sales hari H", "jml fisik"]
            disabled_cols = [col for col in filtered_df.columns if col not in EDITABLE_COLUMNS]

            edited_df = st.data_editor(
                filtered_df,
                disabled=disabled_cols,
                hide_index=True,
                use_container_width=True,
                key=f"editor_{search_toko}"
            )

            # 5. LOGIKA RUMUS (Dijalankan setelah editor berubah)
            sales = pd.to_numeric(edited_df['query sales hari H'], errors='coerce').fillna(0)
            fisik = pd.to_numeric(edited_df['jml fisik'], errors='coerce').fillna(0)
            lpp   = pd.to_numeric(edited_df['stok lpp h-1'], errors='coerce').fillna(0)

            # Hitung Rumus
            edited_df['sls+fisik'] = sales + fisik
            edited_df['selisih'] = edited_df['sls+fisik'] - lpp
            
            # Logika Keterangan: Input jika kolom sales DAN fisik tidak kosong (bukan NaN)
            raw_sales = edited_df['query sales hari H']
            raw_fisik = edited_df['jml fisik']
            edited_df['ket input'] = ["input" if pd.notnull(s) and pd.notnull(f) else "tidak input" 
                                      for s, f in zip(raw_sales, raw_fisik)]

            # 6. TAMPILKAN HASIL AKHIR (Satu tabel saja agar tidak bingung)
            st.write("### Preview Hasil Sebelum Submit:")
            st.dataframe(edited_df, use_container_width=True, hide_index=True)

            if st.button("🚀 Submit Data Toko"):
                confirm_submit_dialog(edited_df, search_toko)
    else:
        st.info("Silakan masukkan Kode Toko.")
else:
    st.warning("Silakan upload file Master Excel.")