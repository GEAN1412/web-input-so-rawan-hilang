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

# --- 2. FUNGSI PENDUKUNG ---

def get_wita_time(utc_dt_str):
    try:
        dt_utc = datetime.strptime(utc_dt_str, '%Y-%m-%dT%H:%M:%SZ')
        dt_wita = dt_utc + timedelta(hours=8)
        return dt_wita.strftime('%H:%M:%S - %d/%m/%Y WITA')
    except:
        return "-"

def get_last_update_master():
    try:
        res = cloudinary.api.resource("master_so_utama.xlsx", resource_type="raw")
        return get_wita_time(res['created_at'])
    except:
        return "Belum ada data"

def get_last_user_input():
    try:
        res = cloudinary.api.resources(
            resource_type="raw", type="upload", prefix="rekap_harian_toko/", 
            max_results=1, direction="desc", sort_by="created_at"
        )
        if res.get('resources'):
            return get_wita_time(res['resources'][0]['created_at'])
        return "Belum ada input"
    except:
        return "-"

def load_excel_from_cloud(public_id):
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            # NORMALISASI HEADER: Menghilangkan spasi di awal/akhir dan membuat huruf kecil untuk pengecekan
            df.columns = [c.strip() for c in df.columns]
            return df
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
                overwrite=True, invalidate=True
            )
            st.success(f"✅ Berhasil Tersimpan!")
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal simpan: {e}")

# --- 4. NAVIGASI ---
if 'page' not in st.session_state:
    st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state:
    st.session_state.admin_auth = False
if 'toko_cari' not in st.session_state:
    st.session_state.toko_cari = ""

# ==========================================
#              HALAMAN UTAMA
# ==========================================
if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    st.write("Silakan pilih menu untuk memulai.")
    st.divider()
    c1, c2 = st.columns(2)
    if c1.button("🏪 MENU INPUT TOKO", use_container_width=True, type="primary"):
        st.session_state.page = "USER"; st.rerun()
    if c2.button("🔑 MENU ADMIN PANEL", use_container_width=True):
        st.session_state.page = "ADMIN"; st.rerun()

# ==========================================
#              HALAMAN ADMIN
# ==========================================
elif st.session_state.page == "ADMIN":
    hc, oc = st.columns([5, 1])
    hc.header("🔐 Admin Panel")
    if oc.button("🚪 Keluar"):
        st.session_state.admin_auth = False; st.session_state.page = "HOME"; st.rerun()

    if not st.session_state.admin_auth:
        pw = st.text_input("Password Admin:", type="password")
        if st.button("Masuk Panel Admin"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
            else: st.error("Password Salah!")
    else:
        st.divider()
        st.subheader("📊 Status Data Live (WITA)")
        c1, c2 = st.columns(2)
        c1.metric("Terakhir Master Diupload", get_last_update_master())
        c2.metric("Terakhir User Input Data", get_last_user_input())
        
        st.divider()
        f_admin = st.file_uploader("Upload Master Excel (.xlsx)", type=["xlsx"])
        if f_admin and st.button("🚀 Publish Master Baru"):
            cloudinary.uploader.upload(f_admin, resource_type="raw", public_id="master_so_utama.xlsx", overwrite=True, invalidate=True)
            st.success("✅ Master Terbit!"); time.sleep(2); st.rerun()

        st.divider()
        if st.button("🔄 Gabungkan & Download Rekap"):
            m_df = load_excel_from_cloud("master_so_utama.xlsx")
            if m_df is not None:
                try:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="rekap_harian_toko/")
                    for r in res.get('resources', []):
                        s_df = pd.read_excel(r['secure_url'])
                        k = 'Prdcd' if 'Prdcd' in s_df.columns else ('prdcd' if 'prdcd' in s_df.columns else m_df.columns[2])
                        for _, row in s_df.iterrows():
                            mask = (m_df[k] == row[k]) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                            if mask.any(): m_df.loc[mask, s_df.columns] = row.values
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                    st.download_button("📥 Download", buf.getvalue(), "Rekap_Final.xlsx")
                except: st.error("Gagal gabung data.")

# ==========================================
#              HALAMAN USER
# ==========================================
elif st.session_state.page == "USER":
    hc, oc = st.columns([5, 1])
    hc.header("📋 Menu Input Toko")
    if oc.button("🚪 Logout"):
        st.session_state.page = "HOME"; st.session_state.toko_cari = ""; st.rerun()

    st.caption(f"Update Master: {get_last_update_master()}")
    ci, cb = st.columns([3, 1])
    t_id = ci.text_input("📍 Kode Toko (4 Digit):", max_chars=4).upper()
    if cb.button("🔍 Cari Data") or st.session_state.toko_cari:
        if t_id:
            st.session_state.toko_cari = t_id
            u_file = f"rekap_harian_toko/Hasil_Toko_{st.session_state.toko_cari}.xlsx"
            data_show = load_excel_from_cloud(u_file)
            
            if data_show is None:
                df_m = load_excel_from_cloud("master_so_utama.xlsx")
                if df_m is not None:
                    # Cari kolom Toko secara fleksibel (kolom pertama)
                    col_toko = df_m.columns[0]
                    data_show = df_m[df_m[col_toko].astype(str).str.contains(st.session_state.toko_cari)].copy()
            
            if data_show is not None and not data_show.empty:
                st.subheader(f"🏠 Toko: {st.session_state.toko_cari}")
                
                # --- VALIDASI & PENYESUAIAN KOLOM ---
                # Cari kolom stok yang mengandung kata 'Stok' atau 'stok'
                col_stok = next((c for c in data_show.columns if 'stok' in c.lower()), None)
                col_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                col_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                col_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')

                # Pastikan kolom-kolom ini ada
                for col_name in [col_sales, col_fisik, col_selisih]:
                    if col_name not in data_show.columns:
                        data_show[col_name] = 0

                # --- DATA EDITOR ---
                edited = st.data_editor(
                    data_show,
                    disabled=[c for c in data_show.columns if c not in [col_sales, col_fisik]],
                    hide_index=True, use_container_width=True, key=f"ed_{st.session_state.toko_cari}"
                )

                # --- RUMUS CALCULATION ---
                val_sales = pd.to_numeric(edited[col_sales], errors='coerce').fillna(0)
                val_fisik = pd.to_numeric(edited[col_fisik], errors='coerce').fillna(0)
                
                if col_stok and col_stok in edited.columns:
                    val_stok = pd.to_numeric(edited[col_stok], errors='coerce').fillna(0)
                    edited[col_selisih] = (val_sales + val_fisik) - val_stok
                
                # Kolom Keterangan Input (Opsional)
                if 'ket input' in edited.columns or 'Keterangan' in edited.columns:
                    col_ket = 'ket input' if 'ket input' in edited.columns else 'Keterangan'
                    edited[col_ket] = ["input" if pd.notnull(s) and pd.notnull(f) else "tidak input" 
                                       for s, f in zip(edited[col_sales], edited[col_fisik])]

                st.write("### 📝 Preview Kalkulasi:")
                st.dataframe(edited, use_container_width=True, hide_index=True)
                if st.button("🚀 Submit Laporan", type="primary", use_container_width=True):
                    confirm_submit_dialog(edited, st.session_state.toko_cari)
            else:
                st.error("Data toko tidak ditemukan.")
