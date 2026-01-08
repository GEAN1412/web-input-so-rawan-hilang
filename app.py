import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import time
from datetime import datetime

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

# --- 2. FUNGSI PEMBANTU (HELPERS) ---

def get_cloud_metadata(public_id):
    """Mengambil informasi waktu terakhir file diupdate di Cloudinary"""
    try:
        res = cloudinary.api.resource(public_id, resource_type="raw")
        # Format waktu ke WIB (Asumsi UTC+7)
        dt = datetime.strptime(res['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        return dt.strftime('%d-%m-%Y %H:%M:%S')
    except:
        return "-"

def load_excel_from_cloud(public_id):
    """Memuat file Excel dari Cloudinary tanpa cache browser"""
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return pd.read_excel(io.BytesIO(resp.content))
    except:
        return None
    return None

# --- 3. LOGIKA NAVIGASI ---
if 'menu_active' not in st.session_state:
    st.session_state.menu_active = "HOME"

# Tombol navigasi universal di bagian atas
if st.session_state.menu_active != "HOME":
    if st.sidebar.button("🏠 Kembali ke Menu Utama"):
        st.session_state.menu_active = "HOME"
        st.rerun()

# ==========================================
#              HALAMAN UTAMA
# ==========================================
if st.session_state.menu_active == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    st.write("Silakan pilih menu untuk melanjutkan.")
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
    pw = st.text_input("Password Admin:", type="password")
    
    if pw == "icnkl034":
        st.success("Akses Diterima")
        
        # --- INFO TIMESTAMP ---
        last_upload = get_cloud_metadata("master_so_utama.xlsx")
        st.info(f"📅 **Update Terakhir Master oleh Admin:** {last_upload}")

        st.divider()
        
        # --- BAGIAN UPLOAD ---
        st.subheader("1. Upload/Ganti Master Data")
        f = st.file_uploader("Upload File Master Baru (.xlsx)", type=["xlsx"])
        if f and st.button("🚀 Publish ke Cloud"):
            with st.spinner("Mengirim data..."):
                cloudinary.uploader.upload(f, resource_type="raw", public_id="master_so_utama.xlsx", overwrite=True)
                st.success("Berhasil! Data master baru telah aktif.")
                time.sleep(2)
                st.rerun()

        st.divider()

        # --- TAMPILAN DATA LIVE ---
        st.subheader("2. Tampilan Data Master Saat Ini (Live)")
        master_live = load_excel_from_cloud("master_so_utama.xlsx")
        
        if master_live is not None:
            st.write("Data di bawah ini adalah data yang saat ini tampil di menu Toko:")
            st.dataframe(master_live.head(10), use_container_width=True) # Tampilkan 10 baris pertama sebagai preview
            
            # --- DOWNLOAD GABUNGAN ---
            st.subheader("3. Download Rekap Keseluruhan")
            if st.button("🔄 Tarik & Gabung Inputan Toko"):
                with st.spinner("Menggabungkan data..."):
                    # Logika merge (mirip versi sebelumnya)
                    try:
                        resources = cloudinary.api.resources(resource_type="raw", type="upload", prefix="rekap_harian_toko/Hasil_Toko_")
                        for res in resources.get('resources', []):
                            store_df = pd.read_excel(res['secure_url'])
                            # Update master_live dengan data dari toko
                            for _, row in store_df.iterrows():
                                key = 'plu' if 'plu' in row else 'gab'
                                mask = (master_live[key] == row[key]) & (master_live['toko'].astype(str) == str(row['toko']))
                                if mask.any():
                                    master_live.loc[mask, store_df.columns] = row.values
                        
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                            master_live.to_excel(writer, index=False)
                        
                        st.download_button(
                            label="📥 Download Hasil Rekap Final",
                            data=buf.getvalue(),
                            file_name=f"Rekap_SO_Full_{datetime.now().strftime('%H%M')}.xlsx",
                            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                        )
                    except:
                        st.error("Gagal menarik data toko. Pastikan toko sudah ada yang submit.")
        else:
            st.warning("Belum ada data master di server.")

# ==========================================
#              HALAMAN TOKO
# ==========================================
elif st.session_state.menu_active == "INPUT_TOKO":
    st.header("📋 Input Data Toko")
    
    # Load Master harian
    master = load_excel_from_cloud("master_so_utama.xlsx")
    
    if master is None:
        st.warning("⚠️ Admin belum mempublikasikan data master hari ini.")
    else:
        toko_id = st.text_input("📍 Kode Toko (4 Digit):", max_chars=4).upper()
        
        if toko_id:
            filtered = master[master['toko'].astype(str).str.contains(toko_id)].copy()
            
            if filtered.empty:
                st.error(f"Toko {toko_id} tidak ditemukan.")
            else:
                st.subheader(f"🏠 Toko: {toko_id}")
                
                # Bersihkan kolom rumus agar tidak duplikat
                for c in ["sls+fisik", "ket input", "selisih"]:
                    if c in filtered.columns: filtered.drop(columns=[c], inplace=True)
                
                # Inisialisasi awal kolom rumus
                filtered["sls+fisik"] = 0
                filtered["ket input"] = "tidak input"
                filtered["selisih"] = 0

                # --- DATA EDITOR ---
                edited_df = st.data_editor(
                    filtered,
                    disabled=[c for c in filtered.columns if c not in ["query sales hari H", "jml fisik"]],
                    hide_index=True,
                    use_container_width=True,
                    key=f"editor_{toko_id}"
                )

                # --- 1. LOGIKA RUMUS REAL-TIME (UPDATE OTOMATIS SAAT KETIK) ---
                # Ambil data dari editor
                sales = pd.to_numeric(edited_df['query sales hari H'], errors='coerce').fillna(0)
                fisik = pd.to_numeric(edited_df['jml fisik'], errors='coerce').fillna(0)
                lpp   = pd.to_numeric(edited_df['stok lpp h-1'], errors='coerce').fillna(0)

                # Eksekusi Rumus
                edited_df['sls+fisik'] = sales + fisik
                edited_df['selisih'] = edited_df['sls+fisik'] - lpp
                
                # Logika Keterangan: Jika kedua kolom diisi (termasuk angka 0)
                edited_df['ket input'] = edited_df.apply(
                    lambda x: "input" if pd.notnull(x['query sales hari H']) and pd.notnull(x['jml fisik']) else "tidak input", axis=1
                )

                # --- TAMPILAN REVIEW RUMUS ---
                st.write("### 📝 Preview & Hasil Perhitungan:")
                st.dataframe(edited_df, use_container_width=True, hide_index=True)

                if st.button("🚀 Submit & Simpan Laporan"):
                    with st.spinner("Menyimpan..."):
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                            edited_df.to_excel(writer, index=False)
                        buf.seek(0)
                        
                        cloudinary.uploader.upload(
                            buf, resource_type="raw", 
                            public_id=f"rekap_harian_toko/Hasil_Toko_{toko_id}.xlsx", 
                            overwrite=True
                        )
                        st.success(f"✅ Data Toko {toko_id} berhasil dikirim ke Cloud!")
