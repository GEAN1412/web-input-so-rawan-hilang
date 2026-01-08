import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import time
from datetime import datetime, timedelta

# --- 1. KONFIGURASI CLOUDINARY ---
try:
    cloudinary.config( 
      cloud_name = st.secrets["cloud_name"], 
      api_key = st.secrets["api_key"], 
      api_secret = st.secrets["api_secret"],
      secure = True
    )
except:
    st.error("Konfigurasi Secrets Cloudinary tidak ditemukan!")

st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# --- 2. FUNGSI PENDUKUNG (HELPERS) ---

def get_wita_time(utc_dt_str):
    """Konversi waktu UTC dari Cloudinary ke WITA (UTC+8)"""
    try:
        dt_utc = datetime.strptime(utc_dt_str, '%Y-%m-%dT%H:%M:%SZ')
        dt_wita = dt_utc + timedelta(hours=8)
        return dt_wita.strftime('%H:%M:%S - %d/%m/%Y WITA')
    except:
        return "-"

def get_last_update_master():
    try:
        # Panggil API secara langsung untuk menghindari cache
        res = cloudinary.api.resource("master_so_utama.xlsx", resource_type="raw", cache_control="no-cache")
        return get_wita_time(res['created_at'])
    except:
        return "Belum ada data"

def get_last_user_input():
    try:
        res = cloudinary.api.resources(
            resource_type="raw", 
            type="upload", 
            prefix="rekap_harian_toko/", 
            max_results=1,
            direction="desc",
            sort_by="created_at"
        )
        if res.get('resources'):
            return get_wita_time(res['resources'][0]['created_at'])
        return "Belum ada input"
    except:
        return "-"

def load_excel_from_cloud(public_id):
    """Memuat file Excel dari Cloudinary dengan Anti-Cache keras"""
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            return pd.read_excel(io.BytesIO(resp.content))
    except:
        return None
    return None

# --- 3. DIALOG KONFIRMASI ---
@st.dialog("Konfirmasi Simpan Data")
def confirm_submit_dialog(data_toko, toko_code):
    st.warning(f"⚠️ Apakah data Toko {toko_code} sudah benar?")
    if st.button("Ya, Submit Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        
        try:
            cloudinary.uploader.upload(
                buffer, resource_type="raw", 
                public_id=f"rekap_harian_toko/Hasil_Toko_{toko_code}.xlsx", 
                overwrite=True,
                invalidate=True # Paksa Cloudinary hapus cache lama
            )
            st.success(f"✅ Berhasil Tersimpan!")
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal simpan: {e}")

# --- 4. SISTEM NAVIGASI ---
if 'page' not in st.session_state:
    st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'toko_cari' not in st.session_state:
    st.session_state.toko_cari = ""

# ==========================================
#              HALAMAN UTAMA (HOME)
# ==========================================
if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    st.write("Silakan pilih menu untuk memulai.")
    st.divider()
    
    col_u, col_a = st.columns(2)
    with col_u:
        if st.button("🏪 MENU INPUT TOKO", use_container_width=True, type="primary"):
            st.session_state.page = "USER"
            st.rerun()
    with col_a:
        if st.button("🔑 MENU ADMIN PANEL", use_container_width=True):
            st.session_state.page = "ADMIN"
            st.rerun()

# ==========================================
#              HALAMAN ADMIN
# ==========================================
elif st.session_state.page == "ADMIN":
    head_col, out_col = st.columns([5, 1])
    head_col.header("🔐 Admin Panel")
    if out_col.button("🚪 Keluar", use_container_width=True):
        st.session_state.admin_auth = False
        st.session_state.page = "HOME"
        st.rerun()

    if not st.session_state.admin_auth:
        pw = st.text_input("Masukkan Password Admin:", type="password")
        if st.button("Masuk Panel Admin"):
            if pw == "icnkl034":
                st.session_state.admin_auth = True
                st.rerun()
            else:
                st.error("Password Salah!")
    else:
        st.divider()
        st.subheader("📊 Status Data Live")
        c_up1, c_up2 = st.columns(2)
        with c_up1:
            st.metric("Terakhir Master Diupload", get_last_update_master())
        with c_up2:
            st.metric("Terakhir User Input Data", get_last_user_input())

        st.divider()
        st.subheader("📤 Upload Master Data Baru")
        f_admin = st.file_uploader("Pilih File Excel Master (.xlsx)", type=["xlsx"])
        if f_admin and st.button("🚀 Publish Master Baru"):
            with st.spinner("Mengupload..."):
                cloudinary.uploader.upload(
                    f_admin, resource_type="raw", 
                    public_id="master_so_utama.xlsx", overwrite=True, invalidate=True
                )
                st.success("✅ Master Berhasil Terbit!")
                time.sleep(2)
                st.rerun()

        st.divider()
        st.subheader("📥 Tarik Rekapitulasi")
        if st.button("🔄 Gabungkan & Download Semua Laporan"):
            with st.spinner("Menggabungkan data..."):
                master_df = load_excel_from_cloud("master_so_utama.xlsx")
                if master_df is not None:
                    try:
                        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="rekap_harian_toko/")
                        for r in res.get('resources', []):
                            # Ambil nama file tanpa ekstensi untuk folder
                            store_df = pd.read_excel(r['secure_url'])
                            join_key = 'plu' if 'plu' in store_df.columns else 'gab'
                            for _, row in store_df.iterrows():
                                mask = (master_df[join_key] == row[join_key]) & (master_df['toko'].astype(str) == str(row['toko']))
                                if mask.any():
                                    master_df.loc[mask, store_df.columns] = row.values
                        
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                            master_df.to_excel(writer, index=False)
                        st.download_button("📥 Klik Download Hasil Gabungan", buf.getvalue(), "Rekap_Final_SO.xlsx")
                    except:
                        st.error("Gagal gabung data.")

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    head_col, out_col = st.columns([5, 1])
    head_col.header("📋 Menu Input Toko")
    if out_col.button("🚪 Logout", use_container_width=True):
        st.session_state.page = "HOME"
        st.session_state.toko_cari = ""
        st.rerun()

    st.caption(f"Update Master: {get_last_update_master()}")

    c_in, c_bt = st.columns([3, 1])
    with c_in:
        t_id = st.text_input("📍 Kode Toko (4 Digit):", max_chars=4).upper()
    with c_bt:
        st.write("##")
        btn_cari = st.button("🔍 Cari Data", use_container_width=True)

    if btn_cari or st.session_state.toko_cari:
        if t_id:
            st.session_state.toko_cari = t_id
            
            # --- CEK DATA PERSISTENCE ---
            # Cari apakah toko sudah pernah input sebelumnya
            user_saved_file = f"rekap_harian_toko/Hasil_Toko_{st.session_state.toko_cari}.xlsx"
            data_to_show = load_excel_from_cloud(user_saved_file)
            
            # Jika belum pernah input, baru ambil dari master harian
            if data_to_show is None:
                df_master = load_excel_from_cloud("master_so_utama.xlsx")
                if df_master is not None:
                    data_to_show = df_master[df_master['toko'].astype(str).str.contains(st.session_state.toko_cari)].copy()
            
            if data_to_show is not None and not data_to_show.empty:
                st.subheader(f"🏠 Toko: {st.session_state.toko_cari}")
                
                # Pastikan kolom kalkulasi ada
                for c in ["sls+fisik", "ket input", "selisih"]:
                    if c not in data_to_show.columns:
                        data_to_show[c] = 0 if c != "ket input" else "tidak input"

                # EDITOR
                edited = st.data_editor(
                    data_to_show,
                    disabled=[c for c in data_to_show.columns if c not in ["query sales hari H", "jml fisik"]],
                    hide_index=True, use_container_width=True, key=f"ed_{st.session_state.toko_cari}"
                )

                # RUMUS
                s_sales = pd.to_numeric(edited['query sales hari H'], errors='coerce').fillna(0)
                s_fisik = pd.to_numeric(edited['jml fisik'], errors='coerce').fillna(0)
                s_lpp   = pd.to_numeric(edited['stok lpp h-1'], errors='coerce').fillna(0)

                edited['sls+fisik'] = s_sales + s_fisik
                edited['selisih'] = edited['sls+fisik'] - s_lpp
                edited['ket input'] = ["input" if pd.notnull(s) and pd.notnull(f) else "tidak input" 
                                       for s, f in zip(edited['query sales hari H'], edited['jml fisik'])]

                st.write("### 📝 Preview Kalkulasi:")
                st.dataframe(edited, use_container_width=True, hide_index=True)

                if st.button("🚀 Submit Laporan", type="primary", use_container_width=True):
                    confirm_submit_dialog(edited, st.session_state.toko_cari)
            else:
                st.error("Data toko tidak ditemukan.")
