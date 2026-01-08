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
    st.warning(f"⚠️ Simpan data Toko {toko_code} ke folder tanggal {date_str}?")
    if st.button("Ya, Simpan Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        try:
            p_id = f"so_rawan_hilang/{date_str}/Hasil_{toko_code}.xlsx"
            cloudinary.uploader.upload(buffer, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            st.success(f"✅ Tersimpan di folder {date_str}!")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal: {e}")

@st.dialog("🚨 Hapus Permanen Data Tanggal")
def confirm_delete_folder_dialog(folder_prefix):
    st.error(f"Apakah Anda yakin ingin menghapus seluruh data pada folder:")
    st.info(f"📁 {folder_prefix}")
    st.write("Tindakan ini akan menghapus Master dan semua hasil Toko secara permanen.")
    
    if st.button("YA, HAPUS PERMANEN", type="primary"):
        with st.spinner("Sedang membersihkan Cloudinary..."):
            try:
                # 1. Cari semua file dengan prefix folder tersebut (termasuk sub-folder)
                # Harus menggunakan resource_type="raw"
                list_resources = cloudinary.api.resources(
                    resource_type="raw", 
                    type="upload", 
                    prefix=folder_prefix
                )
                
                resources = list_resources.get('resources', [])
                
                if not resources:
                    st.warning("Tidak ada file ditemukan di folder ini.")
                else:
                    # 2. Ambil semua public_id
                    public_ids = [res['public_id'] for res in resources]
                    
                    # 3. Hapus resources berdasarkan ID secara paksa
                    # invalidate=True sangat penting agar cache di CDN hilang
                    cloudinary.api.delete_resources(
                        public_ids, 
                        resource_type="raw", 
                        invalidate=True
                    )
                    
                    st.success(f"✅ Berhasil menghapus {len(public_ids)} file.")
                    time.sleep(2)
                    st.rerun()
            except Exception as e:
                st.error(f"Terjadi kesalahan saat menghapus: {e}")

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
        tab1, tab2 = st.tabs(["📤 Upload & Download", "📂 Manajemen Data Per Tanggal"])
        
        with tab1:
            st.subheader("Upload Master Harian")
            u_date = st.date_input("Tanggal Operasional:", datetime.now())
            d_str = u_date.strftime("%Y-%m-%d")
            f_admin = st.file_uploader("Pilih Excel", type=["xlsx"])
            if f_admin and st.button("🚀 Publish ke Folder Tanggal"):
                p_id = f"so_rawan_hilang/{d_str}/Master_{d_str}.xlsx"
                cloudinary.uploader.upload(f_admin, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                st.success(f"✅ Master Berhasil Terbit di folder {d_str}!")

            st.divider()
            st.subheader("Tarik Rekap Gabungan")
            r_date = st.date_input("Pilih Tanggal Rekap:", datetime.now())
            r_str = r_date.strftime("%Y-%m-%d")
            if st.button("🔄 Gabung Data Toko"):
                m_df = load_excel_from_cloud(f"so_rawan_hilang/{r_str}/Master_{r_str}.xlsx")
                if m_df is not None:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"so_rawan_hilang/{r_str}/Hasil_")
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
                    st.download_button(f"📥 Download Rekap {r_str} ({count} Toko)", buf.getvalue(), f"rekap_so_{r_str}.xlsx")
                else: st.error(f"Master folder {r_str} tidak ditemukan.")

        with tab2:
            st.subheader("🗑️ Hapus Data Per Tanggal")
            st.write("Klik tombol cari untuk melihat folder yang tersimpan.")
            if st.button("🔍 Cari Folder Tanggal"):
                try:
                    # Mengambil semua file di dalam folder utama
                    files = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/")
                    # Ekstrak nama folder (tanggal) secara unik
                    all_paths = [f['public_id'] for f in files.get('resources', [])]
                    # Format folder: so_rawan_hilang/YYYY-MM-DD/Master_...
                    # Kita ambil bagian YYYY-MM-DD nya saja
                    folders = sorted(list(set([p.split('/')[1] for p in all_paths if len(p.split('/')) > 2])))
                    
                    if not folders:
                        st.info("Tidak ada folder tanggal yang ditemukan.")
                    else:
                        for f_date in folders:
                            full_path = f"so_rawan_hilang/{f_date}"
                            c_name, c_btn = st.columns([3, 1])
                            c_name.write(f"📅 **Folder Tanggal: {f_date}**")
                            if c_btn.button("🗑️ Hapus Semua Data", key=f"del_{f_date}"):
                                confirm_delete_folder_dialog(full_path)
                except Exception as e:
                    st.error(f"Gagal mengambil data: {e}")

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
        user_date = st.date_input("Pilih Tanggal Operasional:", datetime.now())
    with col_t:
        t_id = st.text_input("📍 Kode Toko:", max_chars=4).upper()
    with col_b:
        st.write("##")
        if st.button("🔍 Cari Data", use_container_width=True):
            st.session_state.preview_data = None
            st.session_state.trigger_cari = True

    if t_id:
        d_str = user_date.strftime("%Y-%m-%d")
        df_master = load_excel_from_cloud(f"so_rawan_hilang/{d_str}/Master_{d_str}.xlsx")
        
        if df_master is not None:
            u_file = f"so_rawan_hilang/{d_str}/Hasil_{t_id}.xlsx"
            df_user = load_excel_from_cloud(u_file)
            
            master_filtered = df_master[df_master[df_master.columns[0]].astype(str).str.contains(t_id)].copy()
            data_to_edit = df_user if df_user is not None else master_filtered

            if not data_to_edit.empty:
                st.subheader(f"🏠 Toko: {t_id} | 📅 {d_str}")
                
                c_stok = next((c for c in data_to_edit.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_to_edit.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_to_edit.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_to_edit.columns if 'selisih' in c.lower()), 'Selisih')

                edited_df = st.data_editor(
                    data_to_edit,
                    disabled=[c for c in data_to_edit.columns if c not in [c_sales, c_fisik]],
                    hide_index=True, use_container_width=True, key=f"editor_{d_str}_{t_id}"
                )

                col_btn1, col_btn2 = st.columns(2)
                with col_btn1:
                    if st.button("🔄 Update Selisih", use_container_width=True):
                        vs = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        vf = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        vh = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (vs + vf) - vh
                        st.session_state.preview_data = edited_df
                        st.success("Kalkulasi Selesai.")

                with col_btn2:
                    if st.button("🚀 Simpan Laporan", type="primary", use_container_width=True):
                        vs = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        vf = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        vh = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (vs + vf) - vh
                        confirm_submit_dialog(edited_df, t_id, d_str)

                if st.session_state.preview_data is not None:
                    st.divider()
                    st.write("### 📊 Preview Perhitungan")
                    st.dataframe(st.session_state.preview_data, use_container_width=True, hide_index=True)
            
            else: st.error("Toko tidak ditemukan.")
        else: st.error(f"Folder tanggal {d_str} tidak ditemukan.")
