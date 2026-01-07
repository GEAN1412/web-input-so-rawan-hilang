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
    pass

st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# --- 2. SESSION STATE (Penyimpanan Data Sementara) ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = None

# --- 3. FUNGSI DIALOG KONFIRMASI ---
@st.dialog("Konfirmasi Simpan Data")
def confirm_submit_dialog(data_to_save, toko_code):
    st.warning(f"⚠️ Apakah data Toko {toko_code} sudah benar?")
    if st.button("Ya, Submit Sekarang"):
        # Update data di master_df utama agar admin bisa download versi terbaru
        idx = st.session_state.master_df[st.session_state.master_df['toko'].astype(str) == toko_code].index
        st.session_state.master_df.loc[idx, data_to_save.columns] = data_to_save.values
        
        # Simpan ke Excel untuk Cloudinary
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_to_save.to_excel(writer, index=False)
        
        buffer.seek(0)
        try:
            cloudinary.uploader.upload(
                buffer, resource_type="raw", 
                public_id=f"Laporan_{toko_code}", 
                folder="laporan_toko_harian", overwrite=True
            )
            st.success(f"✅ Data Toko {toko_code} Berhasil Tersimpan!")
        except Exception as e:
            st.error(f"Gagal upload ke Cloudinary: {e}")

# --- 4. SIDEBAR NAVIGATION ---
st.sidebar.title("🚀 Navigasi")
menu = st.sidebar.radio("Pilih Menu:", ["Input Data Toko", "Admin Panel"])

# ==========================================
#              HALAMAN ADMIN
# ==========================================
if menu == "Admin Panel":
    st.header("🔐 Admin Panel")
    password = st.text_input("Masukkan Password Admin:", type="password")
    
    if password == "icnkl034":
        st.success("Akses Diterima")
        st.divider()
        
        # --- UPLOAD MASTER ---
        st.subheader("1. Upload Master Data")
        file_admin = st.file_uploader("Upload File Master Baru (.xlsx)", type=["xlsx"], key="admin_up")
        if file_admin:
            if st.button("Proses & Simpan Master"):
                st.session_state.master_df = pd.read_excel(file_admin)
                st.success("Master data berhasil diperbarui!")

        # --- DOWNLOAD UPDATED DATA ---
        if st.session_state.master_df is not None:
            st.divider()
            st.subheader("2. Download Rekap Seluruh Toko")
            st.write("Data ini mencakup semua inputan yang sudah masuk selama sesi ini.")
            
            buffer_admin = io.BytesIO()
            with pd.ExcelWriter(buffer_admin, engine='openpyxl') as writer:
                st.session_state.master_df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Excel Terupdate",
                data=buffer_admin.getvalue(),
                file_name="Rekap_SO_Rawan_Hilang_Update.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    elif password != "":
        st.error("Password Salah!")

# ==========================================
#              HALAMAN TOKO
# ==========================================
else:
    st.header("📋 Input Data Item SO Rawan Hilang")
    
    if st.session_state.master_df is None:
        st.info("💡 Menunggu Admin mengupload data master...")
    else:
        # Filter Toko
        col1, col2 = st.columns([1, 2])
        with col1:
            toko_input = st.text_input("📍 Masukkan Kode Toko (4 Digit):", max_chars=4, placeholder="Contoh: F2AA").upper()
            btn_cari = st.button("🔍 Cari Data")

        if btn_cari and toko_input:
            # Filter data berdasarkan toko
            master = st.session_state.master_df.copy()
            filtered_df = master[master['toko'].astype(str).str.contains(toko_input)].copy()

            if filtered_df.empty:
                st.error(f"Data toko {toko_input} tidak ditemukan!")
            else:
                # --- CLEANING KOLOM AGAR TIDAK DOUBLE ---
                # Hapus kolom kalkulasi jika sudah ada di excel asli agar tidak duplikat
                for c in ["sls+fisik", "ket input", "selisih"]:
                    if c in filtered_df.columns:
                        filtered_df = filtered_df.drop(columns=[c])
                
                # Inisialisasi kolom dengan nilai default
                filtered_df["sls+fisik"] = 0
                filtered_df["ket input"] = "tidak input"
                filtered_df["selisih"] = 0

                st.subheader(f"🏠 Toko: {toko_input}")
                
                # --- DATA EDITOR ---
                EDITABLE = ["query sales hari H", "jml fisik"]
                disabled = [c for c in filtered_df.columns if c not in EDITABLE]

                edited_df = st.data_editor(
                    filtered_df,
                    disabled=disabled,
                    hide_index=True,
                    use_container_width=True,
                    key=f"editor_{toko_input}"
                )

                # --- LOGIKA RUMUS REAL-TIME ---
                sales = pd.to_numeric(edited_df['query sales hari H'], errors='coerce').fillna(0)
                fisik = pd.to_numeric(edited_df['jml fisik'], errors='coerce').fillna(0)
                lpp   = pd.to_numeric(edited_df['stok lpp h-1'], errors='coerce').fillna(0)

                edited_df['sls+fisik'] = sales + fisik
                edited_df['selisih'] = edited_df['sls+fisik'] - lpp
                
                # Logika Ket Input: Hanya satu kolom dan pasti update
                edited_df['ket input'] = edited_df.apply(
                    lambda x: "input" if pd.notnull(x['query sales hari H']) and pd.notnull(x['jml fisik']) else "tidak input", axis=1
                )

                st.divider()
                st.write("### 📝 Review Hasil Input")
                st.dataframe(edited_df, use_container_width=True, hide_index=True)

                if st.button("🚀 Submit & Simpan"):
                    confirm_submit_dialog(edited_df, toko_input)
        elif btn_cari and not toko_input:
            st.warning("Silakan masukkan kode toko terlebih dahulu.")