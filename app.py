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

def get_file_metadata(public_id):
    """Mendapatkan jam terakhir file di-upload/di-update di Cloudinary (Anti-Cache)"""
    try:
        res = cloudinary.api.resource(public_id, resource_type="raw", cache_control="no-cache")
        return datetime.strptime(res['created_at'], '%Y-%m-%dT%H:%M:%SZ')
    except:
        return None

def load_excel_from_cloud(public_id):
    """Memuat isi file Excel dari Cloudinary (Anti-Cache)"""
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns] # Bersihkan spasi header
            return df
    except:
        return None
    return None

def find_join_key(df):
    possible_keys = ['prdcd', 'plu', 'gab', 'prd cd']
    for col in df.columns:
        if col.lower() in possible_keys: return col
    return df.columns[2]

# --- 3. DIALOG KONFIRMASI SIMPAN ---
@st.dialog("Konfirmasi Simpan")
def confirm_submit_dialog(data_toko, toko_code, date_str):
    st.warning(f"⚠️ Simpan data Toko {toko_code} untuk tanggal {date_str}?")
    if st.button("Ya, Simpan Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        try:
            # File disimpan dengan prefix Tanggal
            p_id = f"so_rawan_hilang/{date_str}_Hasil_{toko_code}.xlsx"
            cloudinary.uploader.upload(buffer, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            st.success("✅ Berhasil Tersimpan!")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal simpan: {e}")

# --- 4. SISTEM MENU & STATE ---
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'search_active' not in st.session_state: st.session_state.search_active = False

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
        if st.button("Masuk"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
            else: st.error("Salah!")
    else:
        tab1, tab2 = st.tabs(["📤 Upload & Download", "🗑️ Hapus Data"])
        with tab1:
            st.subheader("Upload Master Baru")
            u_date = st.date_input("Berlaku untuk Tanggal:", datetime.now())
            d_str = u_date.strftime("%Y-%m-%d")
            f_admin = st.file_uploader("Pilih Excel", type=["xlsx"])
            if f_admin and st.button("🚀 Publish Master"):
                p_id = f"so_rawan_hilang/{d_str}_Master.xlsx"
                cloudinary.uploader.upload(f_admin, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                st.success(f"✅ Master {d_str} Berhasil Publish! Seluruh inputan toko lama otomatis di-reset.")

            st.divider()
            st.subheader("Tarik Rekap Gabungan")
            r_date = st.date_input("Tarik Rekap Tanggal:", datetime.now(), key="r_date")
            r_str = r_date.strftime("%Y-%m-%d")
            if st.button("🔄 Gabungkan Data"):
                m_df = load_excel_from_cloud(f"so_rawan_hilang/{r_str}_Master.xlsx")
                if m_df is not None:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"so_rawan_hilang/{r_str}_Hasil_")
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
                    st.download_button(f"📥 Download Rekap {r_str} ({count} Toko)", buf.getvalue(), f"so rawan hilang {r_str}.xlsx")
                else: st.error("Master tdk ditemukan.")

        with tab2:
            st.subheader("Manajemen Penghapusan")
            if st.button("🔍 Scan Data"):
                files = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/")
                all_ids = [f['public_id'] for f in files.get('resources', [])]
                dates = sorted(list(set([p.split('/')[1].split('_')[0] for p in all_ids if '_' in p.split('/')[1]])))
                if not dates: st.info("Kosong.")
                else:
                    for d in dates:
                        c_n, c_b = st.columns([3, 1])
                        c_n.write(f"📅 **Data Tanggal: {d}**")
                        if c_b.button("🗑️ Hapus", key=f"del_{d}"):
                            cloudinary.api.delete_resources_by_prefix(f"so_rawan_hilang/{d}_", resource_type="raw", invalidate=True)
                            st.rerun()

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    if st.button("🚪 Logout"):
        st.session_state.page = "HOME"; st.session_state.search_active = False; st.rerun()

    st.header("📋 Input Data Toko")
    col_d, col_t, col_b = st.columns([2, 2, 1])
    with col_d: u_date = st.date_input("Pilih Tanggal:", datetime.now())
    with col_t: t_id = st.text_input("📍 Kode Toko:", max_chars=4).upper()
    with col_b:
        st.write("##")
        if st.button("🔍 Cari Data", use_container_width=True):
            if t_id:
                st.session_state.search_active = True
                st.session_state.active_toko = t_id
                st.session_state.active_date = u_date.strftime("%Y-%m-%d")
            else: st.error("Isi kode toko!")

    if st.session_state.search_active:
        d_str = st.session_state.active_date
        t_id = st.session_state.active_toko
        
        # 1. AMBIL WAKTU & DATA MASTER
        master_id = f"so_rawan_hilang/{d_str}_Master.xlsx"
        time_m = get_file_metadata(master_id)
        df_master = load_excel_from_cloud(master_id)
        
        if df_master is not None:
            # 2. AMBIL WAKTU & DATA USER
            user_id = f"so_rawan_hilang/{d_str}_Hasil_{t_id}.xlsx"
            time_u = get_file_metadata(user_id)
            df_user = load_excel_from_cloud(user_id)
            
            # --- LOGIKA RESET OTOMATIS ---
            # Jika jam master lebih baru dari jam simpan toko -> Pakai Master (Reset)
            if df_user is not None and time_m and time_u:
                if time_m > time_u:
                    st.info("🆕 Admin baru saja update Master. Data Anda telah di-reset.")
                    master_filt = df_master[df_master[df_master.columns[0]].astype(str).str.contains(t_id)].copy()
                    data_to_edit = master_filt
                else:
                    data_to_edit = df_user
            else:
                master_filt = df_master[df_master[df_master.columns[0]].astype(str).str.contains(t_id)].copy()
                data_to_edit = master_filt

            if not data_to_edit.empty:
                st.subheader(f"🏠 Toko: {t_id} | 📅 {d_str}")
                
                # Identifikasi Kolom (Case Insensitive)
                c_stok = next((c for c in data_to_edit.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_to_edit.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_to_edit.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_to_edit.columns if 'selisih' in c.lower()), 'Selisih')

                # Editor
                edited_df = st.data_editor(
                    data_to_edit,
                    disabled=[c for c in data_to_edit.columns if c not in [c_sales, c_fisik]],
                    hide_index=True, use_container_width=True, key=f"editor_{d_str}_{t_id}"
                )

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🔄 Update Selisih"):
                        vs = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        vf = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        vh = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (vs + vf) - vh
                        st.session_state.preview_calc = edited_df
                        st.success("Tabel preview muncul di bawah!")

                with c2:
                    if st.button("🚀 Simpan", type="primary"):
                        vs = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        vf = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        vh = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (vs + vf) - vh
                        confirm_submit_dialog(edited_df, t_id, d_str)

                if 'preview_calc' in st.session_state:
                    st.divider()
                    st.dataframe(st.session_state.preview_calc, use_container_width=True, hide_index=True)
            else: st.error("Toko tdk ditemukan.")
        else: st.error(f"Master {d_str} belum tersedia.")
