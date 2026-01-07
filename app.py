import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import io

# --- 1. KONFIGURASI CLOUDINARY ---
# Ganti dengan data dari Dashboard Cloudinary Anda
cloudinary.config( 
  cloud_name = "Root", 
  api_key = "127374559923575", 
  api_secret = "ISI_API_SECRETAKwLhasHqgDZ_M8HcAH6ScoBxs0",
  secure = True
)

st.set_page_config(page_title="Excel Master Editor", layout="wide")

st.title("📊 Excel Data Editor")
st.write("Upload file ke Cloudinary, edit kolom tertentu, dan unduh hasilnya.")

# --- 2. TENTUKAN KOLOM YANG BOLEH DIEDIT ---
# Masukkan nama kolom yang boleh diedit di sini (harus sama persis dengan di Excel)
EDITABLE_COLUMNS = ["query sales hari H", "jml fisik"]

# --- 3. FITUR UPLOAD ---
uploaded_file = st.file_uploader("Pilih file Excel (.xlsx)", type=["xlsx"])

if uploaded_file:
    # Simpan file ke Cloudinary (Opsional, jika Anda ingin arsip di Cloudinary)
    if st.button("Simpan File Asli ke Cloudinary"):
        upload_result = cloudinary.uploader.upload(uploaded_file, resource_type="raw")
        st.success(f"File berhasil diunggah ke Cloudinary! URL: {upload_result['secure_url']}")

    # Membaca file Excel ke Pandas DataFrame
    df = pd.read_excel(uploaded_file)
    
    st.divider()
    st.subheader("Edit Data di Bawah Ini")
    st.info(f"Kolom yang dapat diedit: {', '.join(EDITABLE_COLUMNS)}")

    # --- 4. FITUR EDIT TABEL (CORE) ---
    # Tentukan kolom mana yang di-disable (semua kecuali yang ada di EDITABLE_COLUMNS)
    disabled_cols = [col for col in df.columns if col not in EDITABLE_COLUMNS]

    edited_df = st.data_editor(
        df,
        disabled=disabled_cols, # Mengunci kolom selain yang ditentukan
        hide_index=True,
        use_container_width=True,
        num_rows="dynamic" # Memungkinkan tambah/hapus baris jika perlu
    )

    st.divider()

    # --- 5. EKSPOR/DOWNLOAD HASIL EDIT ---
    # Mengubah DataFrame yang sudah diedit kembali ke format Excel
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
        edited_df.to_excel(writer, index=False, sheet_name='Sheet1')
    
    st.download_button(
        label="📥 Download Hasil Edit (Excel)",
        data=buffer.getvalue(),
        file_name="Data_Master_Updated.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    # Opsi jika ingin upload ulang hasil edit ke Cloudinary
    if st.button("Unggah Hasil Edit ke Cloudinary"):
        # Reset buffer untuk upload
        buffer.seek(0)
        upload_edited = cloudinary.uploader.upload(buffer, resource_type="raw", public_id="Data_Master_Updated")
        st.success("Hasil editan berhasil disimpan kembali di Cloudinary!")