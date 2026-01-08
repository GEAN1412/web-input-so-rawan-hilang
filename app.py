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
    st.error("Konfigurasi Secrets Cloudinary belum lengkap!")

st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# --- 2. FUNGSI PENDUKUNG ---

def load_excel_from_cloud(public_id):
    """Memuat Excel dari Cloudinary berdasarkan ID"""
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except:
        return None
    return None

def find_join_key(df):
    possible_keys = ['prdcd', 'plu', 'gab', 'prd cd']
    for col in df.columns:
        if col.lower() in possible_keys: return col
    return df.columns[2]

# --- 3. DIALOG KONFIRMASI ---
@st.dialog("Konfirmasi Simpan")
def confirm_submit_dialog(data_toko, toko_code, date_str):
    st.warning(f"⚠️ Simpan data Toko {toko_code} untuk tanggal {date_str}?")
    if st.button("Ya, Simpan Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        try:
            # File disimpan sesuai tanggal
            public_id = f"so_rawan_hilang/rekap/{date_str}/Hasil_{toko_code}.xlsx"
            cloudinary.uploader.upload(buffer, resource_type="raw", public_id=public_id, overwrite=True, invalidate=True)
            st.success("✅ Tersimpan!")
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal: {e}")

# --- 4. SISTEM MENU ---
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

# ==========================================
#              HALAMAN UTAMA
# ==========================================
if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    st.write("Sistem Operasional Berbasis Tanggal")
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
        if st.button("Masuk"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
            else: st.error("Salah!")
    else:
        tab1, tab2 = st.tabs(["📤 Upload & Download", "🗑️ Manajemen File Cloud"])

        with tab1:
            st.subheader("Upload Master Baru")
            u_date = st.date_input("Pilih Tanggal Berlaku Master:", datetime.now(), key="u_date")
            date_str = u_date.strftime("%Y-%m-%d")
            f_admin = st.file_uploader("Upload File Excel", type=["xlsx"])
            if f_admin and st.button("🚀 Publish Master"):
                with st.spinner("Publishing..."):
                    p_id = f"so_rawan_hilang/master/master_{date_str}.xlsx"
                    cloudinary.uploader.upload(f_admin, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                    st.success(f"✅ Master {date_str} Aktif!")

            st.divider()
            st.subheader("Tarik Hasil Input")
            d_date = st.date_input("Pilih Tanggal Rekap:", datetime.now(), key="d_date")
            d_date_str = d_date.strftime("%Y-%m-%d")
            if st.button("🔄 Gabung & Download"):
                m_df = load_excel_from_cloud(f"so_rawan_hilang/master/master_{d_date_str}.xlsx")
                if m_df is not None:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"so_rawan_hilang/rekap/{d_date_str}/")
                    count = 0
                    for r in res.get('resources', []):
                        s_df = pd.read_excel(r['secure_url'])
                        s_df.columns = [str(c).strip() for c in s_df.columns]
                        m_key, s_key = find_join_key(m_df), find_join_key(s_df)
                        for _, row in s_df.iterrows():
                            mask = (m_df[m_key].astype(str) == str(row[s_key])) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                            if mask.any():
                                cols = [c for c in s_df.columns if c in m_df.columns]
                                m_df.loc[mask, cols] = row[cols].values
                        count += 1
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                    st.download_button(f"📥 Download Rekap {d_date_str}", buf.getvalue(), f"so rawan hilang {d_date_str}.xlsx")
                else: st.error("Master tanggal tersebut tidak ditemukan.")

        with tab2:
            st.subheader("Hapus File di Cloudinary")
            st.write("Gunakan menu ini untuk membersihkan file lama agar tidak penuh.")
            if st.button("📁 Lihat Semua File Master"):
                files = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/master/")
                for f in files.get('resources', []):
                    c1, c2 = st.columns([3, 1])
                    c1.write(f['public_id'])
                    if c2.button("🗑️ Hapus", key=f['public_id']):
                        cloudinary.uploader.destroy(f['public_id'], resource_type="raw")
                        st.rerun()

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    if st.button("🚪 Logout"):
        st.session_state.page = "HOME"; st.rerun()

    st.header("📋 Input Toko")
    col_d, col_t, col_b = st.columns([2, 2, 1])
    with col_d:
        user_date = st.date_input("Pilih Tanggal:", datetime.now())
    with col_t:
        t_id = st.text_input("📍 Kode Toko:", max_chars=4).upper()
    with col_b:
        st.write("##")
        btn_cari = st.button("🔍 Cari", use_container_width=True)

    if btn_cari and t_id:
        date_str = user_date.strftime("%Y-%m-%d")
        # 1. Load Master Tanggal Terpilih
        df_master = load_excel_from_cloud(f"so_rawan_hilang/master/master_{date_str}.xlsx")
        
        if df_master is not None:
            # 2. Load Hasil Toko Tanggal Terpilih
            u_file = f"so_rawan_hilang/rekap/{date_str}/Hasil_{t_id}.xlsx"
            df_user = load_excel_from_cloud(u_file)
            
            master_filtered = df_master[df_master[df_master.columns[0]].astype(str).str.contains(t_id)].copy()
            data_show = df_user if df_user is not None else master_filtered

            if not data_show.empty:
                st.subheader(f"🏠 Toko: {t_id} | 📅 {date_str}")
                
                # Dinamis Kolom
                c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), None)
                c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')

                for cn in [c_sales, c_fisik, c_selisih]:
                    if cn not in data_show.columns: data_show[cn] = 0

                # --- EDITOR ---
                edited = st.data_editor(
                    data_show,
                    disabled=[c for c in data_show.columns if c not in [c_sales, c_fisik]],
                    hide_index=True, use_container_width=True, key=f"ed_{date_str}_{t_id}"
                )

                # --- RUMUS OTOMATIS (Langsung di Editor) ---
                vs = pd.to_numeric(edited[c_sales], errors='coerce').fillna(0)
                vf = pd.to_numeric(edited[c_fisik], errors='coerce').fillna(0)
                if c_stok:
                    vh = pd.to_numeric(edited[c_stok], errors='coerce').fillna(0)
                    edited[c_selisih] = (vs + vf) - vh

                if st.button("🚀 Simpan Laporan", type="primary", use_container_width=True):
                    confirm_submit_dialog(edited, t_id, date_str)
            else: st.error("Data toko tidak ketemu.")
        else: st.error(f"Maaf, Admin belum upload Master untuk tanggal {date_str}")
