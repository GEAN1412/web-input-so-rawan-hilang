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

# --- 2. FUNGSI PENDUKUNG ---

@st.cache_data(ttl=60)
def get_master_info():
    try:
        p_id = "so_rawan_hilang/master_utama.xlsx"
        res = cloudinary.api.resource(p_id, resource_type="raw", cache_control="no-cache")
        v_id = str(res.get('version', '1'))
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{v_id}/{p_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df, v_id
    except:
        return None, None
    return None, None

def load_user_save(toko_id, v_id):
    """Mengambil data draft terakhir yang disimpan di cloud"""
    try:
        p_id = f"so_rawan_hilang/hasil/Hasil_{toko_id}_v{v_id}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{p_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except:
        return None
    return None

# --- 3. FRAGMENT EDITOR (ANTI-LAG & ANTI-BLANK) ---
@st.fragment
def show_input_table(df_display, c_sales, c_fisik, c_stok, c_selisih, toko_id, v_now):
    # Menggunakan session_state agar data yang sedang diketik tidak hilang saat rerun
    edited = st.data_editor(
        df_display,
        disabled=[c for c in df_display.columns if c not in [c_sales, c_fisik]],
        hide_index=True,
        use_container_width=True,
        key=f"editor_{toko_id}"
    )

    st.divider()
    
    if st.button("🚀 Simpan Laporan ke Cloud", type="primary", use_container_width=True):
        # 1. Validasi Baris Kosong
        if edited[c_sales].isnull().any() or edited[c_fisik].isnull().any():
            st.error("⚠️ Gagal Simpan! Ada kolom yang masih kosong. Pastikan semua baris terisi (isi 0 jika tidak ada).")
        else:
            with st.spinner("Sedang menyimpan data..."):
                # 2. Perhitungan Selisih Final
                vs = pd.to_numeric(edited[c_sales], errors='coerce').fillna(0)
                vf = pd.to_numeric(edited[c_fisik], errors='coerce').fillna(0)
                vh = pd.to_numeric(edited[c_stok], errors='coerce').fillna(0)
                edited[c_selisih] = (vs + vf) - vh
                
                # 3. Proses Simpan
                buf = io.BytesIO()
                with pd.ExcelWriter(buf, engine='openpyxl') as writer:
                    edited.to_excel(writer, index=False)
                buf.seek(0)
                
                try:
                    p_id_cloud = f"so_rawan_hilang/hasil/Hasil_{toko_id}_v{v_now}.xlsx"
                    cloudinary.uploader.upload(
                        buf, resource_type="raw", 
                        public_id=p_id_cloud, 
                        overwrite=True, invalidate=True
                    )
                    st.success(f"✅ Data Toko {toko_id} Berhasil Disimpan!")
                    time.sleep(1)
                except Exception as e:
                    st.error(f"Error Cloudinary: {e}")

# --- 4. NAVIGASI ---
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'search_trigger' not in st.session_state: st.session_state.search_trigger = False

# ==========================================
#              HALAMAN UTAMA (HOME)
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
    if oc.button("🚪 Keluar"):
        st.session_state.admin_auth = False; st.session_state.page = "HOME"; st.rerun()

    if not st.session_state.admin_auth:
        pw = st.text_input("Password Admin:", type="password")
        if st.button("Masuk"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
            else: st.error("Salah!")
    else:
        st.subheader("Upload Master Baru")
        f_adm = st.file_uploader("Pilih Excel Master", type=["xlsx"])
        if f_adm and st.button("🚀 Publish Master & Bersihkan Semua Data Toko"):
            with st.spinner("Mereset data cloud..."):
                try: cloudinary.api.delete_resources_by_prefix("so_rawan_hilang/hasil/", resource_type="raw")
                except: pass
                cloudinary.uploader.upload(f_adm, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
                st.cache_data.clear()
                st.success("✅ Cloud Bersih & Master Baru Aktif!"); time.sleep(1); st.rerun()

        st.divider()
        st.subheader("Tarik Rekap Seluruh Toko")
        if st.button("🔄 Gabung Data"):
            with st.spinner("Menarik data..."):
                m_df, m_ver = get_master_info()
                if m_df is not None:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"so_rawan_hilang/hasil/Hasil_")
                    count = 0
                    for r in res.get('resources', []):
                        if f"_v{m_ver}" in r['public_id']:
                            s_df = pd.read_excel(r['secure_url'])
                            s_df.columns = [str(c).strip() for c in s_df.columns]
                            for _, row in s_df.iterrows():
                                mask = (m_df[m_df.columns[2]] == row[s_df.columns[2]]) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                                if mask.any():
                                    cols_up = [c for c in s_df.columns if c in m_df.columns]
                                    m_df.loc[mask, cols_up] = row[cols_up].values
                            count += 1
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                    st.download_button(f"📥 Download ({count} Toko)", buf.getvalue(), f"Rekap_SO_{datetime.now().strftime('%d%m')}.xlsx")

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    if st.button("🏠 Kembali ke Home"):
        st.session_state.page = "HOME"
        st.session_state.search_trigger = False
        st.rerun()

    st.header("📋 Menu Input Toko")
    
    # Input dan Tombol Cari (Horizontal)
    col_input, col_btn = st.columns([3, 1])
    with col_input:
        t_id = st.text_input("📍 Masukkan Kode Toko (4 Digit):", max_chars=4, placeholder="Contoh: F2AA").upper()
    with col_btn:
        st.write("##") # Spacer
        if st.button("🔍 Cari Data", use_container_width=True):
            if t_id:
                st.session_state.search_trigger = True
                st.session_state.active_toko = t_id
            else:
                st.error("Isi Kode Toko!")

    # LOGIKA SETELAH KLIK CARI
    if st.session_state.search_trigger:
        df_m, v_now = get_master_info()
        if df_m is not None:
            # 1. CEK DRAFT LAMA DI CLOUD (AUTO-RECOVERY)
            df_u = load_user_save(st.session_state.active_toko, v_now)
            
            if df_u is not None:
                data_show = df_u
                st.success("🔄 Data Anda berhasil dipulihkan dari sesi sebelumnya.")
            else:
                # 2. JIKA BELUM ADA, AMBIL DARI MASTER
                m_filt = df_m[df_m[df_m.columns[0]].astype(str).str.contains(st.session_state.active_toko)].copy()
                if m_filt.empty:
                    st.error("Toko tidak ditemukan di database.")
                    data_show = None
                else:
                    data_show = m_filt
                    # Set kolom isian menjadi None (Blank) di awal
                    c_s_in = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                    c_f_in = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                    c_sl_in = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')
                    data_show[c_s_in] = None
                    data_show[c_f_in] = None
                    data_show[c_sl_in] = 0
            
            if data_show is not None:
                st.subheader(f"🏠 Toko: {st.session_state.active_toko}")
                c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')

                # TAMPILKAN TABEL INPUTAN
                show_input_table(data_show, c_sales, c_fisik, c_stok, c_selisih, st.session_state.active_toko, v_now)
        else:
            st.error("Admin belum mengunggah file Master.")
