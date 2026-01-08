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

# --- 2. FUNGSI INTI (FOLDER: so_rawan_hilang) ---

def load_excel_with_metadata(public_id):
    """Memuat Excel sekaligus mendapatkan waktu terakhir diupdate"""
    try:
        # Get Metadata (Panggil API tanpa cache)
        meta = cloudinary.api.resource(public_id, resource_type="raw", cache_control="no-cache")
        last_update = datetime.strptime(meta['created_at'], '%Y-%m-%dT%H:%M:%SZ')
        
        # Get Content dengan URL Unik agar tidak terkena cache browser
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df, last_update
    except:
        return None, None
    return None, None

def find_join_key(df):
    possible_keys = ['prdcd', 'plu', 'gab', 'prd cd']
    for col in df.columns:
        if col.lower() in possible_keys:
            return col
    return df.columns[2]

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
            # Simpan di dalam folder so_rawan_hilang/rekap_harian_toko/
            cloudinary.uploader.upload(
                buffer, resource_type="raw", 
                public_id=f"so_rawan_hilang/rekap_harian_toko/Hasil_Toko_{toko_code}.xlsx", 
                overwrite=True, invalidate=True
            )
            st.success(f"✅ Berhasil Tersimpan!")
            time.sleep(2)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal simpan: {e}")

# --- 4. SISTEM MENU (TANPA SIDEBAR) ---
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
        st.success("🟢 Server Aktif. Menunggu upload harian.")
        
        st.subheader("📤 Upload Master Harian")
        f_admin = st.file_uploader("Pilih File Excel Baru (.xlsx)", type=["xlsx"])
        if f_admin and st.button("🚀 Publish ke Seluruh Toko"):
            with st.spinner("Publishing..."):
                # Simpan di folder so_rawan_hilang/
                cloudinary.uploader.upload(
                    f_admin, resource_type="raw", 
                    public_id="so_rawan_hilang/master_so_utama.xlsx", 
                    overwrite=True, invalidate=True
                )
                st.success("✅ Master Berhasil Terbit! Seluruh data input toko otomatis di-reset."); time.sleep(2); st.rerun()

        st.divider()
        if st.button("🔄 Gabungkan & Download Rekap Final"):
            with st.spinner("Menarik data..."):
                m_df, _ = load_excel_with_metadata("so_rawan_hilang/master_so_utama.xlsx")
                if m_df is not None:
                    try:
                        m_key = find_join_key(m_df)
                        m_tk = m_df.columns[0]
                        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/rekap_harian_toko/")
                        
                        count = 0
                        for r in res.get('resources', []):
                            s_df = pd.read_excel(r['secure_url'])
                            s_df.columns = [str(c).strip() for c in s_df.columns]
                            s_key = find_join_key(s_df)
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

    ci, cb = st.columns([3, 1])
    t_id = ci.text_input("📍 Kode Toko:", max_chars=4).upper()
    
    if cb.button("🔍 Cari Data") or st.session_state.toko_cari:
        if t_id:
            st.session_state.toko_cari = t_id
            
            # 1. LOAD MASTER & WAKTUNYA
            df_master, time_master = load_excel_with_metadata("so_rawan_hilang/master_so_utama.xlsx")
            
            if df_master is not None:
                # 2. LOAD SIMPANAN TOKO & WAKTUNYA
                u_file = f"so_rawan_hilang/rekap_harian_toko/Hasil_Toko_{st.session_state.toko_cari}.xlsx"
                df_user, time_user = load_excel_with_metadata(u_file)
                
                # 3. LOGIKA FRESH START:
                # Jika simpanan toko lebih LAMA dari Master (misal data hari sebelumnya), paksa pakai Master.
                if df_user is not None and time_user is not None and time_master is not None:
                    if time_user > time_master:
                        data_show = df_user
                        st.success("📝 Melanjutkan inputan Anda.")
                    else:
                        st.info("🆕 Admin telah upload Master baru. Data hari ini telah dimulai ulang.")
                        col_tk = df_master.columns[0]
                        data_show = df_master[df_master[col_tk].astype(str).str.contains(st.session_state.toko_cari)].copy()
                else:
                    col_tk = df_master.columns[0]
                    data_show = df_master[df_master[col_tk].astype(str).str.contains(st.session_state.toko_cari)].copy()
                
                if not data_show.empty:
                    st.subheader(f"🏠 Toko: {st.session_state.toko_cari}")
                    
                    # Identifikasi kolom dinamis
                    c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), None)
                    c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                    c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                    c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')

                    for cn in [c_sales, c_fisik, c_selisih]:
                        if cn not in data_show.columns: data_show[cn] = 0

                    edited = st.data_editor(
                        data_show,
                        disabled=[c for c in data_show.columns if c not in [c_sales, c_fisik]],
                        hide_index=True, use_container_width=True, key=f"ed_v8_{st.session_state.toko_cari}"
                    )

                    vs = pd.to_numeric(edited[c_sales], errors='coerce').fillna(0)
                    vf = pd.to_numeric(edited[c_fisik], errors='coerce').fillna(0)
                    if c_stok:
                        vh = pd.to_numeric(edited[c_stok], errors='coerce').fillna(0)
                        edited[c_selisih] = (vs + vf) - vh

                    st.write("### 📝 Preview Hasil:")
                    st.dataframe(edited, use_container_width=True, hide_index=True)
                    
                    if st.button("🚀 Submit Laporan", type="primary", use_container_width=True):
                        confirm_submit_dialog(edited, st.session_state.toko_cari)
            else:
                st.error("Admin belum upload master.")
