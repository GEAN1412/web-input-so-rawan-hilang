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
# 1. KONFIGURASI & HIDE UI
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

st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    header {visibility: hidden;}
    footer {visibility: hidden;}
    #stDecoration {display:none !important;}
    </style>
    """, unsafe_allow_html=True)

# =================================================================
# 2. FUNGSI DATABASE & LOGS
# =================================================================
USER_DB_PATH = "so_rawan_hilang/config/users.json"
LOG_DB_PATH = "so_rawan_hilang/config/access_logs.json"

def get_now_wita():
    return datetime.utcnow() + timedelta(hours=8)

def get_indonesia_date():
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    now = get_now_wita()
    return f"{now.day}_{bulan[now.month-1]}_{now.year}"

def load_json_db(path):
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v1/{path}"
        resp = requests.get(url, timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except: return {}

def save_json_db(path, db_dict):
    try:
        json_data = json.dumps(db_dict)
        cloudinary.uploader.upload(io.BytesIO(json_data.encode()), resource_type="raw", public_id=path, overwrite=True, invalidate=True)
        return True
    except: return False

def record_login_hit(nik):
    db_logs = load_json_db(LOG_DB_PATH)
    today = get_now_wita().strftime('%Y-%m-%d')
    if nik not in db_logs: db_logs[nik] = {}
    db_logs[nik][today] = db_logs[nik].get(today, 0) + 1
    save_json_db(LOG_DB_PATH, db_logs)

# =================================================================
# 3. FUNGSI OLAH DATA & DASHBOARD
# =================================================================

@st.cache_data(ttl=60) # Dikurangi ke 1 menit agar lebih responsif setelah upload
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
    except: return None, None
    return None, None

def load_user_save(toko_id, v_id):
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
def get_progress_rankings(m_ver, df_master):
    try:
        submitted_codes = set()
        next_cursor = None
        while True:
            res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500, next_cursor=next_cursor)
            for r in res.get('resources', []):
                if f"_v{m_ver}" in r['public_id']:
                    code = r['public_id'].split('Hasil_')[-1].split('_v')[0]
                    submitted_codes.add(code)
            next_cursor = res.get('next_cursor')
            if not next_cursor: break
        
        # Cari kolom AM & AS secara fleksibel (tidak peduli huruf besar/kecil)
        col_am = next((c for c in df_master.columns if c.lower() == 'am'), None)
        col_as = next((c for c in df_master.columns if c.lower() == 'as'), None)
        
        if not col_am or not col_as:
            return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

        df_stores = df_master[[df_master.columns[0], df_master.columns[1], col_am, col_as]].drop_duplicates()
        df_stores.columns = ['Kode', 'Nama', 'AM', 'AS']
        df_stores['Status'] = df_stores['Kode'].astype(str).apply(lambda x: 1 if x in submitted_codes else 0)
        
        # SUMMARY AM - Urut Terjelek (Ascending)
        am_sum = df_stores.groupby('AM').agg(Target=('Kode', 'count'), Sudah=('Status', 'sum')).reset_index()
        am_sum['Belum'] = am_sum['Target'] - am_sum['Sudah']
        am_sum['Progres'] = (am_sum['Sudah'] / am_sum['Target']) * 100
        am_sum.columns = ['AM', 'Target Toko SO', 'Sudah Input', 'Belum Input', 'Progres']
        am_sum = am_sum.sort_values(by=['Progres', 'Target Toko SO'], ascending=[True, False])

        # SUMMARY AS - Urut Terjelek (Ascending)
        as_sum = df_stores.groupby('AS').agg(Target=('Kode', 'count'), Sudah=('Status', 'sum')).reset_index()
        as_sum['Belum'] = as_sum['Target'] - as_sum['Sudah']
        as_sum['Progres'] = (as_sum['Sudah'] / as_sum['Target']) * 100
        as_sum.columns = ['AS', 'Target Toko SO', 'Sudah Input', 'Belum Input', 'Progres']
        as_sum = as_sum.sort_values(by=['Progres', 'Target Toko SO'], ascending=[True, False])
        
        return df_stores, am_sum, as_sum
    except: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def delete_old_reports(current_ver):
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500)
        deleted_count = 0
        for r in res.get('resources', []):
            if f"_v{current_ver}" not in r['public_id']:
                cloudinary.uploader.destroy(r['public_id'], resource_type="raw")
                deleted_count += 1
        return True, deleted_count
    except Exception as e: return False, str(e)

# =================================================================
# 4. DIALOGS & FRAGMENTS
# =================================================================

@st.dialog("🗑️ Bersihkan Data Lama")
def confirm_delete_old_data(v_now):
    st.error("⚠️ Semua hasil input periode SEBELUMNYA akan dihapus permanen.")
    if st.button("IYA, Hapus Sekarang", type="primary", use_container_width=True):
        success, result = delete_old_reports(v_now)
        if success:
            st.success(f"✅ Berhasil menghapus {result} file!"); time.sleep(2); st.rerun()
        else: st.error(f"Gagal: {result}")

@st.dialog("⚠️ Konfirmasi Publish")
def confirm_admin_publish(file_obj):
    st.warning("Publish Master baru akan mereset progres toko hari ini.")
    if st.button("IYA, Publish Sekarang", type="primary", use_container_width=True):
        try:
            cloudinary.uploader.upload(file_obj, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
            st.cache_data.clear() # Paksa dashboard update
            st.success("✅ Master Terbit!"); time.sleep(2); st.rerun()
        except Exception as e: st.error(f"Gagal: {e}")

@st.dialog("Konfirmasi Simpan")
def confirm_user_submit(data_full, toko_code, v_id):
    if st.button("Ya, Simpan ke Cloud", use_container_width=True):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: data_full.to_excel(w, index=False)
        try:
            p_id = f"so_rawan_hilang/hasil/Hasil_{toko_code}_v{v_id}.xlsx"
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            st.success("✅ Tersimpan!"); time.sleep(1.5); st.rerun()
        except: st.error("Gagal!")

@st.fragment
def show_user_editor(df_full, c_sales, c_fisik, c_stok, c_selisih, toko_id, v_now):
    # Hide identitas (Toko, Nama, AM, AS)
    display_cols = [c for c in df_full.columns if c not in [df_full.columns[0], df_full.columns[1], 'AM', 'AS', 'am', 'as']]
    df_full[c_sales] = pd.to_numeric(df_full[c_sales], errors='coerce')
    df_full[c_fisik] = pd.to_numeric(df_full[c_fisik], errors='coerce')

    edited_display = st.data_editor(
        df_full[display_cols],
        column_config={
            c_sales: st.column_config.NumberColumn(f"📥 {c_sales}", format="%d", min_value=0),
            c_fisik: st.column_config.NumberColumn(f"📥 {c_fisik}", format="%d", min_value=0),
            c_selisih: st.column_config.NumberColumn(c_selisih, format="%d"),
        },
        disabled=[c for c in display_cols if c not in [c_sales, c_fisik]],
        hide_index=True, use_container_width=True, key=f"ed_{toko_id}"
    )
    
    if st.button("🚀 Simpan Laporan", type="primary", use_container_width=True):
        if edited_display[c_sales].isnull().any() or edited_display[c_fisik].isnull().any():
            st.error("⚠️ Data belum lengkap!")
        else:
            # Kembalikan kolom identitas untuk simpan utuh
            for col in [df_full.columns[0], df_full.columns[1], 'AM', 'AS']:
                if col not in edited_display.columns:
                    edited_display.insert(0, col, df_full[col].values)
            
            vs, vf, vh = edited_display[c_sales].fillna(0), edited_display[c_fisik].fillna(0), edited_display[c_stok].fillna(0)
            edited_display[c_selisih] = (vs + vf) - vh
            confirm_user_submit(edited_display, toko_id, v_now)

# =================================================================
# 5. SISTEM MENU & ROUTING
# =================================================================
for key in ['page', 'logged_in', 'user_nik', 'admin_auth', 'user_search_active', 'active_toko']:
    if key not in st.session_state: st.session_state[key] = False if 'auth' in key or 'in' in key or 'active' in key else "HOME"

# --- HOME ---
if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    df_m, v_now = get_master_info()
    if v_now and df_m is not None:
        df_full, df_am, df_as = get_progress_rankings(v_now, df_m)
        if not df_am.empty:
            t_t = df_am['Target Toko SO'].sum(); s_t = df_am['Sudah Input'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Toko", t_t)
            c2.metric("Sudah Input", s_t, f"{(s_t/t_t):.1%}")
            c3.metric("Belum Input", t_t-s_t, delta=f"-({t_t-s_t})", delta_color="inverse")
            st.progress(s_t/t_t)
            
            st.subheader("📊 Ringkasan Progres Input AM (Urutan Terendah)")
            st.dataframe(df_am, column_config={"Progres": st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
            
            st.subheader("📊 Ringkasan Progres Input AS (Urutan Terendah)")
            st.dataframe(df_as, column_config={"Progres": st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
            
            with st.expander("🚩 Cek Detail Toko Belum SO"):
                list_as = sorted(df_as[df_as['Sudah Input'] < df_as['Target Toko SO']]['AS'].unique())
                sel_as = st.selectbox("Pilih Area Supervisor (AS):", list_as)
                if sel_as:
                    pending = df_full[(df_full['AS'] == sel_as) & (df_full['Status'] == 0)]
                    st.warning(f"Ada {len(pending)} toko di wilayah AS {sel_as} belum input:")
                    st.table(pending[['Kode', 'Nama']])
    else:
        st.info("💡 Menunggu Admin mempublikasikan master data.")
    
    st.divider()
    cl1, cl2, cl3 = st.columns(3)
    if cl1.button("🔑 LOGIN", use_container_width=True, type="primary"): st.session_state.page = "LOGIN"; st.rerun()
    if cl2.button("📝 DAFTAR", use_container_width=True): st.session_state.page = "REGISTER"; st.rerun()
    if cl3.button("🛡️ ADMIN", use_container_width=True): st.session_state.page = "ADMIN"; st.rerun()

# --- REGISTER & LOGIN ---
elif st.session_state.page == "REGISTER":
    st.header("📝 Daftar Akun")
    n_nik = st.text_input("NIK (10 Digit):", max_chars=10)
    n_pw = st.text_input("Password:", type="password")
    if st.button("Daftar Sekarang"):
        if len(n_nik) == 10 and len(n_pw) >= 4:
            db = load_json_db(USER_DB_PATH)
            if n_nik not in db:
                db[n_nik] = n_pw
                if save_json_db(USER_DB_PATH, db): st.success("✅ Berhasil!"); time.sleep(1); st.session_state.page = "LOGIN"; st.rerun()
            else: st.error("NIK Terdaftar!")
    if st.button("⬅️ Kembali"): st.session_state.page = "HOME"; st.rerun()

elif st.session_state.page == "LOGIN":
    st.header("🔑 Login")
    l_nik = st.text_input("NIK:", max_chars=10); l_pw = st.text_input("Password:", type="password")
    if st.button("Masuk", type="primary"):
        db = load_json_db(USER_DB_PATH)
        if l_nik in db and db[l_nik] == l_pw:
            record_login_hit(l_nik)
            st.session_state.logged_in, st.session_state.user_nik, st.session_state.page = True, l_nik, "USER_INPUT"; st.rerun()
        else: st.error("Gagal!")
    if st.button("⬅️ Kembali"): st.session_state.page = "HOME"; st.rerun()

# --- ADMIN ---
elif st.session_state.page == "ADMIN":
    hc, oc = st.columns([5, 1]); hc.header("🛡️ Admin Panel")
    if oc.button("🚪 Logout"): st.session_state.admin_auth, st.session_state.page = False, "HOME"; st.rerun()
    if not st.session_state.admin_auth:
        pw = st.text_input("Admin Password:", type="password")
        if st.button("Buka Panel"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
    else:
        t1, t2, t3 = st.tabs(["📤 Master & Rekap", "📊 Monitoring", "🔐 Reset PW"])
        with t1:
            f = st.file_uploader("Upload Master Baru", type=["xlsx"])
            if f and st.button("🚀 Publish Master"): confirm_admin_publish(f)
            st.divider()
            m_df, m_ver = get_master_info()
            if m_df is not None:
                if st.button("🔄 Gabung Data Seluruh Toko"):
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500)
                    all_f = [r for r in res.get('resources', []) if f"_v{m_ver}" in r['public_id']]
                    # Pencarian kolom kunci
                    m_key = next((c for c in m_df.columns if c.lower() == 'prdcd'), m_df.columns[2])
                    for r in all_f:
                        s_df = pd.read_excel(r['secure_url']); s_df.columns = [str(c).strip() for c in s_df.columns]
                        s_key = next((c for c in s_df.columns if c.lower() == 'prdcd'), s_df.columns[2])
                        for _, row in s_df.iterrows():
                            try:
                                mask = (m_df[m_key].astype(str) == str(row[s_key])) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                                if mask.any(): m_df.loc[mask, s_df.columns] = row.values
                            except: pass
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                    st.download_button("📥 Download Rekap", buf.getvalue(), f"Rekap_{get_indonesia_date()}.xlsx")
            st.divider()
            if st.button("🗑️ Hapus Inputan Lama"):
                if m_ver: confirm_delete_old_data(m_ver)

        with t2:
            logs = load_json_db(LOG_DB_PATH)
            if logs:
                flat = [{"NIK": k, "Tanggal": t, "Hits": h} for k, d in logs.items() for t, h in d.items()]
                st.dataframe(pd.DataFrame(flat).sort_values(by="Tanggal", ascending=False), hide_index=True, use_container_width=True)

        with t3:
            r_nik = st.text_input("NIK reset:", max_chars=10); r_pw = st.text_input("PW Baru:", type="password")
            if st.button("Simpan"):
                db = load_json_db(USER_DB_PATH)
                if r_nik in db: db[r_nik] = r_pw; save_json_db(USER_DB_PATH, db); st.success("OK!")

# --- USER INPUT ---
elif st.session_state.page == "USER_INPUT":
    if not st.session_state.logged_in: st.session_state.page = "HOME"; st.rerun()
    hc, oc = st.columns([5, 1]); hc.header(f"📋 Menu Input ({st.session_state.user_nik})")
    if oc.button("🚪 Logout"): 
        st.session_state.logged_in, st.session_state.user_search_active, st.session_state.active_toko = False, False, ""
        st.session_state.page = "HOME"; st.rerun()
    
    t_in = st.text_input("📍 Kode Toko:", max_chars=4, placeholder="Contoh TQ86").upper()
    if st.button("🔍 Cari"):
        if len(t_in) == 4: st.session_state.active_toko, st.session_state.user_search_active = t_in, True
        else: st.error("Isi 4 Digit Kode Toko!")

    if st.session_state.user_search_active:
        df_m, v_now = get_master_info()
        if df_m is not None:
            # Normalisasi pencarian
            col_toko_master = df_m.columns[0]
            m_filt = df_m[df_m[col_toko_master].astype(str) == st.session_state.active_toko].copy()
            
            if not m_filt.empty:
                # 1. LABEL HIJAU IDENTITAS LENGKAP
                n_tk = m_filt.iloc[0, 1]
                # Cari AM dan AS (case insensitive)
                c_am_idx = next((i for i, c in enumerate(m_filt.columns) if c.lower() == 'am'), 2)
                c_as_idx = next((i for i, c in enumerate(m_filt.columns) if c.lower() == 'as'), 3)
                
                am_tk = m_filt.iloc[0, c_am_idx]
                as_tk = m_filt.iloc[0, c_as_idx]
                st.success(f"🏠 **{n_tk}** | 👤 AM: **{am_tk}** | 🛡️ AS: **{as_tk}**")
                
                data_input = load_user_save(st.session_state.active_toko, v_now)
                if data_input is None: 
                    data_input = m_filt
                    # Inisialisasi kolom input agar blank (NaN)
                    c_s = next((c for c in data_input.columns if 'sales' in c.lower()), 'Query Sales')
                    c_f = next((c for c in data_input.columns if 'fisik' in c.lower()), 'Jml Fisik')
                    data_input[c_s], data_input[c_f] = None, None
                
                c_stok = next((c for c in data_input.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_input.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_input.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_input.columns if 'selisih' in c.lower()), 'Selisih')
                
                show_user_editor(data_input, c_sales, c_fisik, c_stok, c_selisih, st.session_state.active_toko, v_now)
            else: st.error("Toko tidak terdaftar di database master.")
