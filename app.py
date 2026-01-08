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

# --- 3. DIALOG KONFIRMASI (SIMPAN & HAPUS TOTAL) ---

@st.dialog("Konfirmasi Simpan")
def confirm_submit_dialog(data_toko, toko_code, date_str):
    st.warning(f"⚠️ Simpan data Toko {toko_code} ke folder {date_str}?")
    if st.button("Ya, Simpan Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        try:
            p_id = f"so_rawan_hilang/{date_str}/Hasil_{toko_code}.xlsx"
            cloudinary.uploader.upload(buffer, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            st.success(f"✅ Data tersimpan di cloud.")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal: {e}")

@st.dialog("⚠️ HAPUS FOLDER TANGGAL")
def delete_entire_folder_dialog(folder_name):
    st.error(f"🚨 PERINGATAN KRUSIAL!")
    st.write(f"Anda akan menghapus **SELURUH** isi folder tanggal: **{folder_name}**")
    st.write("Ini mencakup File Master dan semua Laporan Toko pada tanggal tersebut.")
    
    confirm_text = st.text_input("Ketik 'HAPUS' untuk mengonfirmasi:", "")
    
    if st.button("HAPUS SEKARANG", type="primary", disabled=(confirm_text != "HAPUS")):
        try:
            full_path = f"so_rawan_hilang/{folder_name}"
            # 1. Hapus semua file raw di dalam folder tersebut secara massal
            cloudinary.api.delete_resources_by_prefix(full_path + "/", resource_type="raw", invalidate=True)
            
            # 2. Hapus folder itu sendiri secara permanen (hanya bisa jika sudah kosong)
            # Cloudinary API delete_folder membutuhkan nama path folder
            try:
                cloudinary.api.delete_folder(full_path)
            except:
                pass # Folder kadang otomatis hilang jika isinya kosong
                
            st.success(f"✅ Folder {folder_name} dan isinya telah bersih!")
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal menghapus folder: {e}")

# --- 4. SISTEM MENU ---
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False

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
        tab1, tab2 = st.tabs(["📤 Upload & Download", "📂 Manajemen Folder"])
        
        with tab1:
            st.subheader("Upload Master Harian")
            u_date = st.date_input("Tanggal Operasional:", datetime.now())
            d_str = u_date.strftime("%Y-%m-%d")
            f_admin = st.file_uploader("Upload File Excel", type=["xlsx"])
            if f_admin and st.button("🚀 Publish ke Folder"):
                p_id = f"so_rawan_hilang/{d_str}/Master_{d_str}.xlsx"
                cloudinary.uploader.upload(f_admin, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                st.success(f"✅ Master terbit di folder {d_str}!")

            st.divider()
            st.subheader("Tarik Laporan Gabungan")
            r_date = st.date_input("Cek Tanggal:", datetime.now())
            r_str = r_date.strftime("%Y-%m-%d")
            if st.button("🔄 Gabungkan Data"):
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
                    st.download_button(f"📥 Download Rekap ({count} Toko)", buf.getvalue(), f"rekap_{r_str}.xlsx")
                else: st.error("Master tidak ditemukan.")

        with tab2:
            st.subheader("🗑️ Hapus Seluruh Folder")
            st.write("Pilih folder tanggal untuk dihapus permanen dari Cloudinary.")
            
            # Mengambil daftar folder secara dinamis dari Cloudinary
            if st.button("🔍 Scan Folder Cloud"):
                try:
                    # Cari semua file master untuk mendapatkan list folder
                    res_files = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/")
                    paths = [f['public_id'] for f in res_files.get('resources', [])]
                    # Ambil bagian tanggal dari path so_rawan_hilang/YYYY-MM-DD/...
                    folders = sorted(list(set([p.split('/')[1] for p in paths if len(p.split('/')) > 1])))
                    
                    if not folders:
                        st.info("Tidak ada folder ditemukan.")
                    else:
                        for f_name in folders:
                            col_n, col_b = st.columns([3, 1])
                            col_n.write(f"📁 Folder Tanggal: **{f_name}**")
                            if col_b.button("🗑️ Hapus Folder", key=f"del_{f_name}"):
                                delete_entire_folder_dialog(f_name)
                except Exception as e:
                    st.error(f"Error Scan: {e}")

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    if st.button("🚪 Logout"):
        st.session_state.page = "HOME"
        st.rerun()

    st.header("📋 Input Toko")
    col_d, col_t, col_b = st.columns([2, 2, 1])
    with col_d:
        user_date = st.date_input("Pilih Tanggal:", datetime.now())
    with col_t:
        t_id = st.text_input("📍 Kode Toko:", max_chars=4).upper()
    with col_b:
        st.write("##")
        btn_cari = st.button("🔍 Cari Data", use_container_width=True)

    if t_id and btn_cari:
        d_str = user_date.strftime("%Y-%m-%d")
        df_master = load_excel_from_cloud(f"so_rawan_hilang/{d_str}/Master_{d_str}.xlsx")
        
        if df_master is not None:
            u_file = f"so_rawan_hilang/{d_str}/Hasil_{t_id}.xlsx"
            df_user = load_excel_from_cloud(u_file)
            
            # Tentukan data mana yang ditampilkan (prioritas hasil inputan user)
            master_filtered = df_master[df_master[df_master.columns[0]].astype(str).str.contains(t_id)].copy()
            data_to_edit = df_user if df_user is not None else master_filtered

            if not data_to_edit.empty:
                st.subheader(f"🏠 Toko: {t_id} | 📅 {d_str}")
                
                c_stok = next((c for c in data_to_edit.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_to_edit.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_to_edit.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_to_edit.columns if 'selisih' in c.lower()), 'Selisih')

                # TAMPILAN EDITOR
                edited_df = st.data_editor(
                    data_to_edit,
                    disabled=[c for c in data_to_edit.columns if c not in [c_sales, c_fisik]],
                    hide_index=True, use_container_width=True, key=f"editor_{d_str}_{t_id}"
                )

                cb1, cb2 = st.columns(2)
                with cb1:
                    if st.button("🔄 Update Selisih"):
                        v_s = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        v_f = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        v_h = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (v_s + v_f) - v_h
                        st.session_state.temp_edit = edited_df
                        st.success("Dihitung. Cek tabel di atas.")
                
                with cb2:
                    if st.button("🚀 Simpan", type="primary"):
                        v_s = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        v_f = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        v_h = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (v_s + v_f) - v_h
                        confirm_submit_dialog(edited_df, t_id, d_str)
            else:
                st.error("Data toko tidak ketemu.")
        else:
            st.error(f"Folder tanggal {d_str} tidak ditemukan.")
