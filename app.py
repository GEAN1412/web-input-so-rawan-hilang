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

# --- 3. DIALOG KONFIRMASI (SIMPAN & HAPUS) ---

@st.dialog("Konfirmasi Simpan")
def confirm_submit_dialog(data_toko, toko_code, date_str):
    st.warning(f"⚠️ Simpan data Toko {toko_code} untuk tanggal {date_str}?")
    if st.button("Ya, Simpan Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        try:
            public_id = f"so_rawan_hilang/rekap/{date_str}/Hasil_{toko_code}.xlsx"
            cloudinary.uploader.upload(buffer, resource_type="raw", public_id=public_id, overwrite=True, invalidate=True)
            st.success("✅ Berhasil Tersimpan!")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal: {e}")

@st.dialog("Hapus File Master")
def confirm_delete_dialog(public_id):
    st.error(f"🚨 Apakah Anda yakin ingin menghapus file ini?")
    st.code(public_id)
    st.write("Tindakan ini tidak dapat dibatalkan.")
    
    if st.button("Ya, Hapus Permanen", type="primary"):
        try:
            # Resource_type='raw' sangat penting agar Cloudinary mengenali file Excel
            result = cloudinary.uploader.destroy(public_id, resource_type="raw", invalidate=True)
            if result.get("result") == "ok":
                st.success("✅ File berhasil dihapus!")
                time.sleep(1.5)
                st.rerun()
            else:
                st.error(f"Gagal menghapus: {result.get('result')}")
        except Exception as e:
            st.error(f"Error: {e}")

# --- 4. SISTEM MENU ---
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'preview_data' not in st.session_state: st.session_state.preview_data = None

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
        tab1, tab2 = st.tabs(["📤 Upload & Download", "🗑️ Manajemen File"])
        
        with tab1:
            st.subheader("Upload Master Harian")
            u_date = st.date_input("Tanggal Master:", datetime.now())
            d_str = u_date.strftime("%Y-%m-%d")
            f_admin = st.file_uploader("Pilih Excel", type=["xlsx"])
            if f_admin and st.button("🚀 Publish Master"):
                p_id = f"so_rawan_hilang/master/master_{d_str}.xlsx"
                cloudinary.uploader.upload(f_admin, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                st.success(f"✅ Master {d_str} Berhasil di-Publish!")

            st.divider()
            st.subheader("Tarik Rekap Toko")
            r_date = st.date_input("Pilih Tanggal Laporan:", datetime.now())
            r_str = r_date.strftime("%Y-%m-%d")
            if st.button("🔄 Gabung & Download"):
                m_df = load_excel_from_cloud(f"so_rawan_hilang/master/master_{r_str}.xlsx")
                if m_df is not None:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"so_rawan_hilang/rekap/{r_str}/")
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
                    st.download_button(f"📥 Download Rekap {r_str}", buf.getvalue(), f"rekap_{r_str}.xlsx")
                else: st.error("Master tanggal tsb tidak ada.")

        with tab2:
            st.subheader("Daftar File Master di Cloud")
            if st.button("📁 Cek / Refresh Daftar Master"):
                # Menarik daftar file dari folder master
                files = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/master/")
                if not files.get('resources'):
                    st.info("Tidak ada file master yang ditemukan.")
                else:
                    for f in files.get('resources', []):
                        col_name, col_btn = st.columns([3, 1])
                        col_name.write(f"📄 {f['public_id']}")
                        # Tombol hapus memicu dialog konfirmasi
                        if col_btn.button("🗑️ Hapus", key=f['public_id']):
                            confirm_delete_dialog(f['public_id'])

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    if st.button("🚪 Logout"):
        st.session_state.page = "HOME"
        st.session_state.preview_data = None
        st.rerun()

    st.header("📋 Input Data Toko")
    col_d, col_t, col_b = st.columns([2, 2, 1])
    with col_d:
        user_date = st.date_input("Pilih Tanggal:", datetime.now())
    with col_t:
        t_id = st.text_input("📍 Kode Toko:", max_chars=4).upper()
    with col_b:
        st.write("##")
        if st.button("🔍 Cari Data", use_container_width=True):
            st.session_state.preview_data = None
            st.session_state.trigger_cari = True

    if t_id:
        d_str = user_date.strftime("%Y-%m-%d")
        df_master = load_excel_from_cloud(f"so_rawan_hilang/master/master_{d_str}.xlsx")
        
        if df_master is not None:
            u_file = f"so_rawan_hilang/rekap/{d_str}/Hasil_{t_id}.xlsx"
            df_user = load_excel_from_cloud(u_file)
            
            master_filtered = df_master[df_master[df_master.columns[0]].astype(str).str.contains(t_id)].copy()
            data_to_edit = df_user if df_user is not None else master_filtered

            if not data_to_edit.empty:
                st.subheader(f"🏠 Toko: {t_id} | 📅 {d_str}")
                
                # Dinamis Kolom
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

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔄 Update / Hitung Selisih", use_container_width=True):
                        vs = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        vf = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        vh = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (vs + vf) - vh
                        st.session_state.preview_data = edited_df
                        st.success("Perhitungan diperbarui! Lihat di bawah.")

                with col_btn2:
                    if st.button("🚀 Simpan Laporan", type="primary", use_container_width=True):
                        vs = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        vf = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        vh = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (vs + vf) - vh
                        confirm_submit_dialog(edited_df, t_id, d_str)

                if st.session_state.preview_data is not None:
                    st.divider()
                    st.write("### 📊 Preview Hasil Perhitungan")
                    st.dataframe(st.session_state.preview_data, use_container_width=True, hide_index=True)
            
            else: st.error("Toko tidak ditemukan.")
        else: st.error(f"Master tanggal {d_str} tidak ditemukan.")
