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

# --- 2. INITIALIZE SESSION STATE ---
if 'master_df' not in st.session_state:
    st.session_state.master_df = None
if 'menu_active' not in st.session_state:
    st.session_state.menu_active = "HOME" # HOME, ADMIN, INPUT_TOKO

# --- 3. FUNGSI DIALOG KONFIRMASI ---
@st.dialog("Konfirmasi Simpan Data")
def confirm_submit_dialog(data_toko, toko_code):
    st.warning(f"⚠️ Apakah data Toko {toko_code} sudah benar?")
    if st.button("Ya, Submit Sekarang"):
        # Sinkronkan data toko yang diedit kembali ke master utama
        master = st.session_state.master_df
        # Ambil kolom yang kita miliki di data_toko (yang sudah dikalkulasi)
        cols_to_update = data_toko.columns
        # Update baris yang sesuai berdasarkan kolom 'toko' dan 'plu' (atau 'gab') sebagai primary key
        for _, row in data_toko.iterrows():
            mask = (master['toko'].astype(str) == str(toko_code)) & (master['plu'] == row['plu'])
            master.loc[mask, cols_to_update] = row.values
        
        st.session_state.master_df = master
        
        # Simpan ke Cloudinary
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
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

# ==========================================
#              TAMPILAN MENU UTAMA
# ==========================================
if st.session_state.menu_active == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    st.write("Selamat datang, silakan pilih menu di bawah ini:")
    st.divider()
    
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
    if st.button("⬅️ Kembali ke Menu Utama"):
        st.session_state.menu_active = "HOME"
        st.rerun()

    st.header("🔐 Admin Panel")
    password = st.text_input("Masukkan Password Admin:", type="password")
    
    if password == "icnkl034":
        st.success("Akses Diterima")
        st.divider()
        
        # --- UPLOAD MASTER ---
        st.subheader("1. Upload Master Data")
        file_admin = st.file_uploader("Upload File Master Baru (.xlsx)", type=["xlsx"])
        if file_admin:
            if st.button("Proses & Simpan Master"):
                st.session_state.master_df = pd.read_excel(file_admin)
                st.success("Master data berhasil diperbarui!")

        # --- DOWNLOAD UPDATED DATA ---
        if st.session_state.master_df is not None:
            st.divider()
            st.subheader("2. Download Rekap Seluruh Toko")
            buffer_admin = io.BytesIO()
            with pd.ExcelWriter(buffer_admin, engine='openpyxl') as writer:
                st.session_state.master_df.to_excel(writer, index=False)
            
            st.download_button(
                label="📥 Download Excel Terupdate",
                data=buffer_admin.getvalue(),
                file_name="Rekap_Update_SO.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
    elif password != "":
        st.error("Password Salah!")

# ==========================================
#              HALAMAN TOKO
# ==========================================
elif st.session_state.menu_active == "INPUT_TOKO":
    if st.button("⬅️ Kembali ke Menu Utama"):
        st.session_state.menu_active = "HOME"
        st.rerun()

    st.header("📋 Input Data Item")
    
    if st.session_state.master_df is None:
        st.warning("⚠️ Data master belum tersedia. Hubungi Admin untuk upload data.")
    else:
        # Filter Toko (Tampilan Pendek)
        col1, col2 = st.columns([1, 4])
        with col1:
            toko_input = st.text_input("📍 Kode Toko:", max_chars=4, placeholder="F2AA").upper()
        with col2:
            st.write("") # Spacer
            st.write("")
            btn_cari = st.button("🔍 Cari Data Item")

        if toko_input:
            # Filter data
            master = st.session_state.master_df.copy()
            filtered_df = master[master['toko'].astype(str).str.contains(toko_input)].copy()

            if filtered_df.empty:
                st.error(f"Data toko {toko_input} tidak ditemukan!")
            else:
                st.subheader(f"🏠 Toko: {toko_input}")
                
                # --- BERSIHKAN & SIAPKAN KOLOM ---
                for c in ["sls+fisik", "ket input", "selisih"]:
                    if c in filtered_df.columns:
                        filtered_df = filtered_df.drop(columns=[c])

                # --- DATA EDITOR (MENGGUNAKAN SESSION STATE AGAR TIDAK HILANG) ---
                EDITABLE = ["query sales hari H", "jml fisik"]
                disabled = [c for c in filtered_df.columns if c not in EDITABLE]

                # Tampilkan Editor
                # Key harus unik per toko agar tidak tertukar data antar toko
                edited_df = st.data_editor(
                    filtered_df,
                    disabled=disabled,
                    hide_index=True,
                    use_container_width=True,
                    key=f"editor_toko_{toko_input}"
                )

                # --- LOGIKA RUMUS REAL-TIME (Langsung diproses) ---
                # Memastikan data dihitung setiap kali user mengubah sel
                sales = pd.to_numeric(edited_df['query sales hari H'], errors='coerce').fillna(0)
                fisik = pd.to_numeric(edited_df['jml fisik'], errors='coerce').fillna(0)
                lpp   = pd.to_numeric(edited_df['stok lpp h-1'], errors='coerce').fillna(0)

                edited_df['sls+fisik'] = sales + fisik
                edited_df['selisih'] = edited_df['sls+fisik'] - lpp
                
                # Update Keterangan
                # Kondisi: Jika kolom sales dan fisik keduanya TIDAK KOSONG (bisa angka 0)
                edited_df['ket input'] = edited_df.apply(
                    lambda x: "input" if pd.notnull(x['query sales hari H']) and pd.notnull(x['jml fisik']) else "tidak input", axis=1
                )

                st.divider()
                st.write("### 📝 Preview & Kalkulasi")
                # Tampilkan hasil kalkulasi terbaru
                st.dataframe(edited_df, use_container_width=True, hide_index=True)

                if st.button("🚀 Submit & Simpan Ke Cloud"):
                    confirm_submit_dialog(edited_df, toko_input)