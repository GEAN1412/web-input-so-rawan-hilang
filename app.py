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
    st.error("Konfigurasi Secrets Cloudinary tidak ditemukan!")

st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# --- 2. FUNGSI INTI (VERSIONING SYSTEM) ---

def get_master_info():
    """Mendapatkan isi Master dan Version ID uniknya dari Cloudinary"""
    try:
        # Ambil metadata master terbaru
        res = cloudinary.api.resource("so_rawan_hilang/master_so_utama.xlsx", resource_type="raw", cache_control="no-cache")
        v_id = str(res.get('version', '1')) # Mengambil nomor versi unik
        
        # Ambil isi file menggunakan URL dengan versi tersebut
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{v_id}/so_rawan_hilang/master_so_utama.xlsx"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df, v_id
    except:
        return None, None
    return None, None

def load_user_save(toko_id, master_version):
    """Memuat simpanan toko dari folder versi master yang aktif saat ini"""
    try:
        # Path Folder: so_rawan_hilang/rekap/[MASTER_VERSION]/Hasil_[TOKO].xlsx
        path = f"so_rawan_hilang/rekap/{master_version}/Hasil_{toko_id}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{path}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except:
        return None
    return None

# --- 3. DIALOG KONFIRMASI ---
@st.dialog("Konfirmasi Simpan Data")
def confirm_submit_dialog(data_toko, toko_code, master_version):
    st.warning(f"⚠️ Apakah data Toko {toko_code} sudah benar?")
    if st.button("Ya, Submit Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        try:
            # Simpan di folder versi master saat ini
            public_id = f"so_rawan_hilang/rekap/{master_version}/Hasil_{toko_code}.xlsx"
            cloudinary.uploader.upload(
                buffer, resource_type="raw", 
                public_id=public_id, 
                overwrite=True, invalidate=True
            )
            st.success(f"✅ Laporan Toko {toko_code} Berhasil Tersimpan!")
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal simpan: {e}")

# --- 4. SISTEM MENU (TANPA SIDEBAR) ---
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'toko_cari' not in st.session_state: st.session_state.toko_cari = ""

# ==========================================
#              HALAMAN UTAMA
# ==========================================
if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
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
    if oc.button("🚪 Logout"):
        st.session_state.admin_auth = False; st.session_state.page = "HOME"; st.rerun()

    if not st.session_state.admin_auth:
        pw = st.text_input("Password Admin:", type="password")
        if st.button("Masuk Panel Admin"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
            else: st.error("Password Salah!")
    else:
        st.divider()
        st.info("🟢 Panel Admin Aktif")
        
        f_admin = st.file_uploader("Upload Master Excel Baru (.xlsx)", type=["xlsx"])
        if f_admin and st.button("🚀 Publish Master Baru"):
            with st.spinner("Publishing Master..."):
                # Upload master dan otomatis Cloudinary memberikan Version ID baru
                cloudinary.uploader.upload(
                    f_admin, resource_type="raw", 
                    public_id="so_rawan_hilang/master_so_utama.xlsx", 
                    overwrite=True, invalidate=True
                )
                st.success("✅ Master Berhasil Terbit! Seluruh inputan toko lama otomatis di-reset.")
                time.sleep(2); st.rerun()

        st.divider()
        if st.button("🔄 Gabungkan & Download Rekap Final"):
            with st.spinner("Menarik data..."):
                m_df, m_ver = get_master_info()
                if m_df is not None:
                    try:
                        # Identifikasi kolom kunci otomatis
                        possible_keys = ['prdcd', 'plu', 'gab', 'prd cd']
                        m_key = next((c for c in m_df.columns if c.lower() in possible_keys), m_df.columns[2])
                        m_tk = m_df.columns[0]
                        
                        # Hanya tarik rekap dari FOLDER VERSI MASTER saat ini
                        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"so_rawan_hilang/rekap/{m_ver}/")
                        
                        count = 0
                        for r in res.get('resources', []):
                            s_df = pd.read_excel(r['secure_url'])
                            s_df.columns = [str(c).strip() for c in s_df.columns]
                            s_key = next((c for c in s_df.columns if c.lower() in possible_keys), s_df.columns[2])
                            s_tk = s_df.columns[0]
                            for _, row in s_df.iterrows():
                                mask = (m_df[m_key].astype(str) == str(row[s_key])) & (m_df[m_tk].astype(str) == str(row[s_tk]))
                                if mask.any():
                                    cols = [c for c in s_df.columns if c in m_df.columns]
                                    m_df.loc[mask, cols] = row[cols].values
                            count += 1
                        
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                        fn = f"so rawan hilang {datetime.now().strftime('%d-%m-%Y')}.xlsx"
                        st.download_button(f"📥 Download ({count} Toko)", buf.getvalue(), fn)
                    except Exception as e: st.error(f"Error: {e}")

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    hc, oc = st.columns([5, 1])
    hc.header("📋 Input Toko")
    if oc.button("🚪 Logout"):
        st.session_state.page = "HOME"; st.session_state.toko_cari = ""; st.rerun()

    ti = st.text_input("📍 Kode Toko (4 Digit):", max_chars=4).upper()
    
    if st.button("🔍 Cari Data") or st.session_state.toko_cari:
        if ti:
            st.session_state.toko_cari = ti
            # 1. AMBIL MASTER & VERSI UNIKNYA
            df_master, m_ver = get_master_info()
            
            if df_master is not None:
                # 2. CARI SIMPANAN TOKO HANYA DI FOLDER VERSI MASTER INI
                df_user = load_user_save(st.session_state.toko_cari, m_ver)
                
                col_tk = df_master.columns[0]
                master_filtered = df_master[df_master[col_tk].astype(str).str.contains(st.session_state.toko_cari)].copy()

                if df_user is not None:
                    data_show = df_user
                    st.success("📝 Melanjutkan inputan Anda (Master Aktif).")
                else:
                    data_show = master_filtered
                    st.info("🆕 Menggunakan Master Data Terbaru.")

                if not data_show.empty:
                    st.subheader(f"🏠 Toko: {st.session_state.toko_cari}")
                    
                    # Kolom Dinamis (Rumus)
                    c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), None)
                    c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                    c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                    c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')

                    for cn in [c_sales, c_fisik, c_selisih]:
                        if cn not in data_show.columns: data_show[cn] = 0

                    edited = st.data_editor(
                        data_show,
                        disabled=[c for c in data_show.columns if c not in [c_sales, c_fisik]],
                        hide_index=True, use_container_width=True, key=f"ed_v_final_{st.session_state.toko_cari}"
                    )

                    vs = pd.to_numeric(edited[c_sales], errors='coerce').fillna(0)
                    vf = pd.to_numeric(edited[c_fisik], errors='coerce').fillna(0)
                    if c_stok:
                        vh = pd.to_numeric(edited[c_stok], errors='coerce').fillna(0)
                        edited[c_selisih] = (vs + vf) - vh

                    st.write("### 📝 Preview Hasil:")
                    st.dataframe(edited, use_container_width=True, hide_index=True)
                    
                    if st.button("🚀 Submit Laporan", type="primary", use_container_width=True):
                        confirm_submit_dialog(edited, st.session_state.toko_cari, m_ver)
            else:
                st.error("Admin belum upload master.")
