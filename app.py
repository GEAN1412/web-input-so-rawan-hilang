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

@st.cache_data(ttl=60)
def get_master_data_and_version():
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

# --- 3. FRAGMENT UNTUK INPUT CEPAT (ANTI-FLICKER) ---
@st.fragment
def input_data_fragment(df_input, c_sales, c_fisik, c_stok, c_selisih, toko_id, v_now):
    # Editor dengan durasi render sangat cepat
    edited = st.data_editor(
        df_input,
        disabled=[c for c in df_input.columns if c not in [c_sales, c_fisik]],
        hide_index=True,
        use_container_width=True,
        key="fast_editor_so"
    )

    st.divider()
    if st.button("🚀 Simpan Laporan", type="primary", use_container_width=True):
        # 1. Validasi Blank
        if edited[c_sales].isnull().any() or edited[c_fisik].isnull().any():
            st.error("⚠️ Ada item/kolom yang belum terisi!")
        else:
            with st.spinner("Menghitung & Menyimpan..."):
                # 2. Kalkulasi Selisih
                vs = pd.to_numeric(edited[c_sales], errors='coerce').fillna(0)
                vf = pd.to_numeric(edited[c_fisik], errors='coerce').fillna(0)
                vh = pd.to_numeric(edited[c_stok], errors='coerce').fillna(0)
                edited[c_selisih] = (vs + vf) - vh
                
                # 3. Upload ke Cloudinary
                buffer = io.BytesIO()
                with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                    edited.to_excel(writer, index=False)
                buffer.seek(0)
                try:
                    p_id = f"so_rawan_hilang/hasil/Hasil_{toko_id}_v{v_now}.xlsx"
                    cloudinary.uploader.upload(buffer, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                    st.success("✅ Berhasil Tersimpan!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Gagal simpan: {e}")

# --- 4. SISTEM NAVIGASI ---
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
        st.subheader("Upload Master Baru")
        f_admin = st.file_uploader("Pilih Excel Master (.xlsx)", type=["xlsx"])
        if f_admin and st.button("🚀 Publish Master & Reset Semua"):
            with st.spinner("Resetting cloud..."):
                try: cloudinary.api.delete_resources_by_prefix("so_rawan_hilang/hasil/", resource_type="raw")
                except: pass
                cloudinary.uploader.upload(f_admin, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
                st.cache_data.clear()
                st.success("✅ Berhasil Publish!"); time.sleep(1.5); st.rerun()

        st.divider()
        if st.button("🔄 Gabung Data Seluruh Toko"):
            with st.spinner("Tunggu..."):
                m_df, m_ver = get_master_data_and_version()
                if m_df is not None:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_")
                    count = 0
                    for r in res.get('resources', []):
                        if f"_v{m_ver}" in r['public_id']:
                            s_df = pd.read_excel(r['secure_url'])
                            s_df.columns = [str(c).strip() for c in s_df.columns]
                            for _, row in s_df.iterrows():
                                mask = (m_df[m_df.columns[2]] == row[s_df.columns[2]]) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                                if mask.any():
                                    cols = [c for c in s_df.columns if c in m_df.columns]
                                    m_df.loc[mask, cols] = row[cols].values
                            count += 1
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                    st.download_button(f"📥 Download ({count} Toko)", buf.getvalue(), "rekap_so.xlsx")

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    if st.button("🚪 Logout"):
        st.session_state.page = "HOME"; st.rerun()

    st.header("📋 Input Toko")
    t_id = st.text_input("📍 Masukkan Kode Toko:", max_chars=4, placeholder="F2AA").upper()
    
    if t_id:
        df_m, v_now = get_master_data_and_version()
        if df_m is not None:
            df_u = load_user_save(t_id, v_now)
            m_filt = df_m[df_m[df_m.columns[0]].astype(str).str.contains(t_id)].copy()
            
            # Tentukan data awal
            if df_u is not None:
                data_show = df_u
            else:
                data_show = m_filt
                c_s_init = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                c_f_init = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_sl_init = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')
                data_show[c_s_init] = None
                data_show[c_f_init] = None
                data_show[c_sl_init] = 0
            
            if not data_show.empty:
                st.subheader(f"🏠 Toko: {t_id}")
                
                # Identifikasi Kolom
                c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')

                # PANGGIL FRAGMENT (INTI PERBAIKAN)
                # Menghilangkan kedipan dan lag saat input cepat
                input_data_fragment(data_show, c_sales, c_fisik, c_stok, c_selisih, t_id, v_now)
            else:
                st.error("Toko tidak ketemu.")
        else:
            st.error("Admin belum upload master.")
