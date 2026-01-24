import streamlit as st
import pandas as pd
import cloudinary
import cloudinary.uploader
import cloudinary.api
import io
import requests
import time
import json
from datetime import datetime, timedelta

# =================================================================
# 1. KONFIGURASI CLOUDINARY & HIDE UI (ANTI-GITHUB)
# =================================================================
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
# CSS untuk menyembunyikan Header (Logo GitHub & Fork) dan Footer Streamlit
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            header {visibility: hidden;}
            footer {visibility: hidden;}
            #stDecoration {display:none !important;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# =================================================================
# 2. FUNGSI DATABASE (JSON & LOGS)
# =================================================================
USER_DB_PATH = "so_rawan_hilang/config/users.json"
LOG_DB_PATH = "so_rawan_hilang/config/access_logs.json"

def get_now_wita():
    """Mengambil waktu saat ini dalam zona WITA (UTC+8)."""
    return datetime.utcnow() + timedelta(hours=8)

def load_json_db(path):
    """Memuat database JSON dari Cloudinary."""
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{path}"
        resp = requests.get(url, timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except: return {}

def save_json_db(path, db_dict):
    """Menyimpan dictionary ke file JSON di Cloudinary."""
    try:
        json_data = json.dumps(db_dict)
        cloudinary.uploader.upload(io.BytesIO(json_data.encode()), resource_type="raw", public_id=path, overwrite=True, invalidate=True)
        return True
    except: return False

def record_login_hit(nik):
    """Mencatat aktivitas login user berdasarkan NIK dan Tanggal."""
    db_logs = load_json_db(LOG_DB_PATH)
    today = get_now_wita().strftime('%Y-%m-%d')
    if nik not in db_logs: db_logs[nik] = {}
    db_logs[nik][today] = db_logs[nik].get(today, 0) + 1
    save_json_db(LOG_DB_PATH, db_logs)

# =================================================================
# 3. FUNGSI OLAH EXCEL & DASHBOARD
# =================================================================
def get_indonesia_date():
    """Format tanggal Indonesia untuk penamaan file rekap."""
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    now = get_now_wita()
    return f"{now.day}_{bulan[now.month-1]}_{now.year}"

@st.cache_data(ttl=10)
def get_master_info():
    """Mengambil data master utama dan versi terbarunya."""
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
    except: return None, None
    return None, None

def load_user_save(toko_id, v_id):
    """Memuat hasil input yang sudah disimpan oleh toko tertentu."""
    try:
        p_id = f"so_rawan_hilang/hasil/Hasil_{toko_id}_v{v_id}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{p_id}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except: return None

@st.cache_data(ttl=60)
def get_report_status(m_ver, df_master):
    """Menghitung progres toko: siapa yang sudah dan belum kirim laporan."""
    try:
        submitted_codes = set()
        next_cursor = None
        while True:
            res = cloudinary.api.resources(
                resource_type="raw", type="upload", 
                prefix="so_rawan_hilang/hasil/Hasil_", 
                max_results=500, next_cursor=next_cursor
            )
            for r in res.get('resources', []):
                if f"_v{m_ver}" in r['public_id']:
                    code = r['public_id'].split('Hasil_')[-1].split('_v')[0]
                    submitted_codes.add(code)
            next_cursor = res.get('next_cursor')
            if not next_cursor: break
            
        all_stores = set(df_master[df_master.columns[0]].astype(str).unique())
        not_submitted = sorted(list(all_stores - submitted_codes))
        return list(submitted_codes), not_submitted
    except:
        return [], []

# =================================================================
# 4. DIALOGS & FRAGMENTS
# =================================================================
@st.dialog("⚠️ Konfirmasi Publish Master")
def confirm_admin_publish(file_obj):
    st.warning("Anda akan Publish Master baru & mereset progres toko hari ini.")
    if st.button("IYA, Publish Sekarang", type="primary", use_container_width=True):
        msg = st.empty()
        is_ok = False
        try:
            cloudinary.uploader.upload(file_obj, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
            msg.success("✅ Master Berhasil Terbit!")
            is_ok = True
        except Exception as e:
            msg.error(f"Gagal Upload: {e}")
        
        if is_ok:
            time.sleep(2); st.rerun()

@st.dialog("Konfirmasi Simpan")
def confirm_user_submit(data_toko, toko_code, v_id):
    if st.button("Ya, Simpan ke Cloud", use_container_width=True):
        msg = st.empty()
        is_ok = False
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: data_toko.to_excel(w, index=False)
        try:
            p_id = f"so_rawan_hilang/hasil/Hasil_{toko_code}_v{v_id}.xlsx"
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            msg.success("✅ Data Berhasil Tersimpan!")
            is_ok = True
        except Exception as e:
            msg.error(f"Gagal Simpan: {e}")
        
        if is_ok:
            time.sleep(1.5); st.rerun()

@st.fragment
def show_user_editor(df_in, c_sales, c_fisik, c_stok, c_selisih, toko_id, v_now):
    """Tabel editor untuk input angka sales dan fisik."""
    df_in[c_sales] = pd.to_numeric(df_in[c_sales], errors='coerce')
    df_in[c_fisik] = pd.to_numeric(df_in[c_fisik], errors='coerce')
    
    edited = st.data_editor(df_in, column_config={
            c_sales: st.column_config.NumberColumn(f"📥 {c_sales}", format="%d", min_value=0),
            c_fisik: st.column_config.NumberColumn(f"📥 {c_fisik}", format="%d", min_value=0),
            c_selisih: st.column_config.NumberColumn(c_selisih, format="%d"),
            c_stok: st.column_config.NumberColumn(c_stok, format="%d"),
        }, disabled=[c for c in df_in.columns if c not in [c_sales, c_fisik]], hide_index=True, use_container_width=True, key=f"ed_{toko_id}")
    
    if st.button("🚀 Simpan Laporan", type="primary", use_container_width=True):
        if edited[c_sales].isnull().any() or edited[c_fisik].isnull().any():
            st.error("⚠️ Masih ada data yang kosong (blank)!")
        else:
            vs, vf, vh = edited[c_sales].fillna(0).astype(int), edited[c_fisik].fillna(0).astype(int), edited[c_stok].fillna(0).astype(int)
            edited[c_selisih] = (vs + vf) - vh
            confirm_user_submit(edited, toko_id, v_now)

# =================================================================
# 5. SISTEM STATE & ROUTING HALAMAN
# =================================================================
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_nik' not in st.session_state: st.session_state.user_nik = ""
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'user_search_active' not in st.session_state: st.session_state.user_search_active = False

# --- 5A. HALAMAN UTAMA (HOME) ---
if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    
    df_m, v_now = get_master_info()
    if v_now:
        with st.spinner("Memuat progres harian..."):
            list_masuk, list_belum = get_report_status(v_now, df_m)
            total_toko = len(df_m[df_m.columns[0]].unique())
            jumlah_masuk = len(list_masuk)
            jumlah_belum = len(list_belum)

        st.subheader("📊 Progres Real-Time Hari Ini")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Toko", total_toko)
        m2.metric("Sudah Kirim", jumlah_masuk, delta=f"{jumlah_masuk/total_toko:.1%}")
        m3.metric("Belum Kirim", jumlah_belum, delta=f"-{jumlah_belum}", delta_color="inverse")
        
        st.progress(jumlah_masuk / total_toko if total_toko > 0 else 0)

        with st.expander(f"🚩 Lihat {jumlah_belum} Toko yang BELUM Kirim"):
            if jumlah_belum > 0:
                cols = st.columns(5)
                for idx, t_code in enumerate(list_belum):
                    cols[idx % 5].write(f"• {t_code}")
            else:
                st.success("🎉 Luar biasa! Semua toko sudah kirim laporan.")
    else:
        st.warning("⚠️ Master data belum diterbitkan oleh Admin.")

    st.divider()
    c1, c2, c3 = st.columns(3)
    if c1.button("🔑 LOGIN KARYAWAN", use_container_width=True, type="primary"): 
        st.session_state.page = "LOGIN"; st.rerun()
    if c2.button("📝 DAFTAR AKUN", use_container_width=True): 
        st.session_state.page = "REGISTER"; st.rerun()
    if c3.button("🛡️ ADMIN PANEL", use_container_width=True): 
        st.session_state.page = "ADMIN"; st.rerun()

# --- 5B. REGISTER ---
elif st.session_state.page == "REGISTER":
    st.header("📝 Daftar Akun Baru")
    new_nik = st.text_input("NIK (10 Digit):", max_chars=10)
    new_pw = st.text_input("Password:", type="password")
    if st.button("Daftar Sekarang", use_container_width=True):
        if len(new_nik) != 10 or not new_nik.isdigit(): st.error("NIK harus 10 digit angka!")
        else:
            db = load_json_db(USER_DB_PATH)
            if new_nik in db: st.error("NIK sudah terdaftar!")
            else:
                db[new_nik] = new_pw
                if save_json_db(USER_DB_PATH, db):
                    st.success("✅ Berhasil terdaftar!"); time.sleep(1); st.session_state.page = "LOGIN"; st.rerun()
    if st.button("⬅️ Kembali"): st.session_state.page = "HOME"; st.rerun()

# --- 5C. LOGIN ---
elif st.session_state.page == "LOGIN":
    st.header("🔑 Login Karyawan")
    log_nik = st.text_input("NIK:", max_chars=10)
    log_pw = st.text_input("Password:", type="password")
    if st.button("Masuk Sekarang", use_container_width=True, type="primary"):
        db = load_json_db(USER_DB_PATH)
        if log_nik in db and db[log_nik] == log_pw:
            record_login_hit(log_nik)
            st.session_state.logged_in, st.session_state.user_nik, st.session_state.page = True, log_nik, "USER_INPUT"; st.rerun()
        else: st.error("NIK atau Password salah!")
    if st.button("⬅️ Kembali", use_container_width=True): st.session_state.page = "HOME"; st.rerun()

# --- 5D. ADMIN PANEL ---
elif st.session_state.page == "ADMIN":
    hc, oc = st.columns([5, 1])
    hc.header("🛡️ Admin Panel")
    if oc.button("🚪 Logout"): 
        st.session_state.admin_auth, st.session_state.page = False, "HOME"; st.rerun()
    
    if not st.session_state.admin_auth:
        pw = st.text_input("Password Admin:", type="password")
        if st.button("Buka Panel"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
            else: st.error("Akses Ditolak!")
    else:
        tab1, tab2, tab3 = st.tabs(["📤 Master & Rekap", "📊 Monitoring", "🔐 Reset Password"])
        with tab1:
            st.subheader("Update Master Data")
            f_adm = st.file_uploader("Upload Excel Master Baru", type=["xlsx"])
            if f_adm and st.button("🚀 Publish Master"): confirm_admin_publish(f_adm)
            
            st.divider()
            st.subheader("📥 Penarikan Data Rekap")
            m_df, m_ver = get_master_info()
            if m_df is not None:
                with st.spinner("Mencari laporan masuk..."):
                    all_files = []
                    next_cursor = None
                    while True:
                        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500, next_cursor=next_cursor)
                        batch = [r for r in res.get('resources', []) if f"_v{m_ver}" in r['public_id']]
                        all_files.extend(batch)
                        next_cursor = res.get('next_cursor')
                        if not next_cursor: break
                    t_count = len(all_files)
                
                if t_count > 0:
                    st.info(f"📊 Ditemukan **{t_count}** laporan toko untuk versi master saat ini.")
                    if st.button("🔄 Gabung & Download Rekap", use_container_width=True):
                        with st.spinner("Proses penggabungan data..."):
                            for r in all_files:
                                s_df = pd.read_excel(r['secure_url'])
                                s_df.columns = [str(c).strip() for c in s_df.columns]
                                for _, row in s_df.iterrows():
                                    mask = (m_df[m_df.columns[2]] == row[s_df.columns[2]]) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                                    if mask.any(): m_df.loc[mask, s_df.columns] = row.values
                            buf = io.BytesIO()
                            with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                            st.download_button(f"📥 Download File Rekap", buf.getvalue(), f"Rekap_{get_indonesia_date()}.xlsx", use_container_width=True)
                else: st.warning("ℹ️ Belum ada laporan yang masuk untuk versi ini.")

        with tab2:
            logs = load_json_db(LOG_DB_PATH)
            if logs:
                flat = [{"NIK": k, "Tanggal": t, "Hits": h} for k, d in logs.items() for t, h in d.items()]
                st.dataframe(pd.DataFrame(flat).sort_values(by="Tanggal", ascending=False), use_container_width=True, hide_index=True)
        with tab3:
            t_nik = st.text_input("NIK yang akan direset:"); n_pw = st.text_input("Password Baru:", type="password")
            if st.button("Update Password"):
                db = load_json_db(USER_DB_PATH)
                if t_nik in db: 
                    db[t_nik] = n_pw
                    save_json_db(USER_DB_PATH, db)
                    st.success(f"✅ Password NIK {t_nik} berhasil diupdate!")
                else: st.error("NIK tidak ditemukan.")

# --- 5E. USER INPUT (STOCK OPNAME) ---
elif st.session_state.page == "USER_INPUT":
    if not st.session_state.logged_in: st.session_state.page = "HOME"; st.rerun()
    
    hc, oc = st.columns([5, 1])
    hc.header(f"📋 Input Data SO ({st.session_state.user_nik})")
    if oc.button("🚪 Logout"): 
        st.session_state.logged_in, st.session_state.user_search_active = False, False
        st.session_state.page = "HOME"; st.rerun()

    t_col, b_col = st.columns([3, 1])
    with t_col: 
        t_id = st.text_input("📍 Kode Toko:", max_chars=4, placeholder="Contoh: TQ86").upper()
    with b_col:
        st.write("##")
        btn_cari = st.button("🔍 Cari Data", use_container_width=True)

    if t_id and len(t_id) < 4:
        st.warning(f"⚠️ Kode Toko harus 4 digit (Baru: {len(t_id)})")
        st.session_state.user_search_active = False
    elif btn_cari:
        st.session_state.active_toko, st.session_state.user_search_active = t_id, True

    st.divider()

    if st.session_state.user_search_active:
        df_m, v_now = get_master_info()
        if df_m is not None:
            # PENCARIAN EXACT MATCH (==) UNTUK KEAMANAN
            m_filt = df_m[df_m[df_m.columns[0]].astype(str) == st.session_state.active_toko].copy()
            
            if not m_filt.empty:
                df_u = load_user_save(st.session_state.active_toko, v_now)
                data_show = df_u if df_u is not None else m_filt
                st.subheader(f"🏠 Toko: {st.session_state.active_toko}")
                
                # Deteksi Otomatis Kolom
                c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')
                
                show_user_editor(data_show, c_sales, c_fisik, c_stok, c_selisih, st.session_state.active_toko, v_now)
            else: 
                st.error(f"❌ Kode Toko '{st.session_state.active_toko}' tidak ada dalam Master.")
                st.session_state.user_search_active = False


