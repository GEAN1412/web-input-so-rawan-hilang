import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
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
    st.error("Konfigurasi Cloudinary di Secrets belum lengkap!")

st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# --- 2. FUNGSI LOAD DATA DARI CLOUD (SINKRONISASI) ---
def load_data_from_cloud():
    """Mengambil file master_so_utama dari Cloudinary agar semua user melihat data yang sama"""
    try:
        # Generate URL untuk file raw di Cloudinary
        file_url = cloudinary.utils.cloudinary_url("master_so_utama", resource_type="raw")[0]
        # Berikan timestamp unik agar browser tidak mengambil cache lama
        import time
        file_url += f"?t={int(time.time())}"
        
        response = requests.get(file_url)
        if response.status_code == 200:
            return pd.read_excel(io.BytesIO(response.content))
        return None
    except:
        return None

# --- 3. DIALOG KONFIRMASI SIMPAN ---
@st.dialog("Konfirmasi Simpan Data")
def confirm_submit_dialog(data_toko, toko_code):
    st.warning(f"⚠️ Apakah input data Toko {toko_code} sudah benar?")
    if st.button("Ya, Submit Sekarang"):
        # Proses simpan hasil inputan toko ke Cloudinary dengan nama file toko masing-masing
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        
        try:
            cloudinary.uploader.upload(
                buffer, resource_type="raw", 
                public_id=f"Hasil_Toko_{toko_code}", 
                folder="rekap_harian_toko", overwrite=True
            )
            st.success(f"✅ Data Toko {toko_code} Berhasil Disimpan!")
        except Exception as e:
            st.error(f"Gagal simpan: {e}")

# --- 4. SISTEM NAVIGASI ---
if 'menu_active' not in st.session_state:
    st.session_state.menu_active = "HOME"

# ==========================================
#              HALAMAN UTAMA
# ==========================================
if st.session_state.menu_active == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
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
    if st.button("⬅️ Kembali ke Home"):
        st.session_state.menu_active = "HOME"
        st.rerun()

    st.header("🔐 Admin Panel")
    pw = st.text_input("Password Admin:", type="password")
    
    if pw == "icnkl034":
        st.success("Akses Diterima")
        st.divider()
        
        # --- UPLOAD & PUBLISH ---
        st.subheader("1. Upload & Publish Data Baru")
        file_admin = st.file_uploader("Upload Master Excel (.xlsx)", type=["xlsx"])
        if file_admin and st.button("🚀 Publish ke Semua Toko"):
            with st.spinner("Sedang memproses..."):
                cloudinary.uploader.upload(
                    file_admin, resource_type="raw", 
                    public_id="master_so_utama", overwrite=True
                )
                st.success("✅ Berhasil Publish! Toko sekarang bisa mengakses data ini.")

        st.divider()

        # --- DOWNLOAD REKAP ---
        st.subheader("2. Download Data Master Saat Ini")
        df_admin = load_data_from_cloud()
        if df_admin is not None:
            buf = io.BytesIO()
            with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                df_admin.to_excel(writer, index=False)
            st.download_button(
                label="📥 Download Excel Master (Update)",
                data=buf.getvalue(),
                file_name="Master_SO_Update.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        else:
            st.info("Belum ada data master di server.")

# ==========================================
#              HALAMAN TOKO
# ==========================================
elif st.session_state.menu_active == "INPUT_TOKO":
    if st.button("⬅️ Kembali ke Home"):
        st.session_state.menu_active = "HOME"
        st.rerun()

    st.header("📋 Input Data Toko")
    
    # LOAD DATA DARI CLOUD
    df_global = load_data_from_cloud()
    
    if df_global is None:
        st.warning("⚠️ Data belum di-Publish oleh Admin.")
    else:
        col_t1, col_t2 = st.columns([1, 4])
        with col_t1:
            toko_id = st.text_input("📍 Kode Toko:", max_chars=4, placeholder="F2AA").upper()
        
        if toko_id:
            # Filter Data
            filtered = df_global[df_global['toko'].astype(str).str.contains(toko_id)].copy()
            
            if filtered.empty:
                st.error("Data Toko Tidak Ditemukan!")
            else:
                st.subheader(f"🏠 Toko: {toko_id}")
                
                # --- BERSIHKAN KOLOM SEBELUM EDITOR ---
                for c in ["sls+fisik", "ket input", "selisih"]:
                    if c in filtered.columns:
                        filtered = filtered.drop(columns=[c])
                
                # Inisialisasi Kolom Baru
                filtered["sls+fisik"] = 0
                filtered["ket input"] = "tidak input"
                filtered["selisih"] = 0

                # --- EDITOR ---
                EDITABLE = ["query sales hari H", "jml fisik"]
                disabled = [c for c in filtered.columns if c not in EDITABLE]

                edited = st.data_editor(
                    filtered,
                    disabled=disabled,
                    hide_index=True,
                    use_container_width=True,
                    key=f"ed_{toko_id}"
                )

                # --- RUMUS REAL-TIME ---
                # Konversi ke numeric agar tidak error jika ada data kosong
                s_sales = pd.to_numeric(edited['query sales hari H'], errors='coerce').fillna(0)
                s_fisik = pd.to_numeric(edited['jml fisik'], errors='coerce').fillna(0)
                s_lpp   = pd.to_numeric(edited['stok lpp h-1'], errors='coerce').fillna(0)

                edited['sls+fisik'] = s_sales + s_fisik
                edited['selisih'] = edited['sls+fisik'] - s_lpp
                
                # Update Keterangan: Jika kedua kolom ada isinya (meskipun 0)
                edited['ket input'] = [
                    "input" if pd.notnull(s) and pd.notnull(f) else "tidak input" 
                    for s, f in zip(edited['query sales hari H'], edited['jml fisik'])
                ]

                st.divider()
                st.write("### 📝 Preview Hasil Perhitungan")
                st.dataframe(edited, use_container_width=True, hide_index=True)

                if st.button("🚀 Simpan & Kirim Laporan"):
                    confirm_submit_dialog(edited, toko_id)
