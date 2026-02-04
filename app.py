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
# 2. FUNGSI DATABASE (JSON & LOGS)
# =================================================================
USER_DB_PATH = "so_rawan_hilang/config/users.json"
LOG_DB_PATH = "so_rawan_hilang/config/access_logs.json"

def get_now_wita():
    return datetime.utcnow() + timedelta(hours=8)

def get_indonesia_date():
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", 
             "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
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
# 3. FUNGSI OLAH DATA
# =================================================================

def find_join_key(df):
    possible = ['prdcd', 'prd cd', 'product code', 'kode barang']
    for c in df.columns:
        if c.lower() in possible: return c
    return df.columns[4] if len(df.columns) > 4 else df.columns[0]

@st.cache_data(ttl=60)
def get_master_info():
    try:
        p_id = "so_rawan_hilang/master_utama.xlsx"
        res = cloudinary.api.resource(p_id, resource_type="raw", cache_control="no-cache")
        v_id = str(res.get('version', '1'))
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{v_id}/{p_id}"
        resp = requests.get(url, timeout=15)
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
        
        # Ambil kolom identitas 0-3 (Toko, Nama, AM, AS)
        df_temp = df_master.iloc[:, [0, 1, 2, 3]].copy()
        df_temp.columns = ['Kode', 'Nama', 'AM', 'AS']
        df_temp = df_temp.drop_duplicates()
        df_temp['Status'] = df_temp['Kode'].astype(str).apply(lambda x: 1 if x in submitted_codes else 0)
        
        # Rank AM
        am_sum = df_temp.groupby('AM').agg(Target=('Kode', 'count'), Sudah=('Status', 'sum')).reset_index()
        am_sum['Belum Input'] = am_sum['Target'] - am_sum['Sudah']
        am_sum['Progres'] = (am_sum['Sudah'] / am_sum['Target']) * 100
        am_sum.columns = ['AM', 'Target Toko SO', 'Sudah Input', 'Belum Input', 'Progres']
        am_sum = am_sum.sort_values(by=['Progres', 'Target Toko SO'], ascending=[True, False])

        # Rank AS
        as_sum = df_temp.groupby('AS').agg(Target=('Kode', 'count'), Sudah=('Status', 'sum')).reset_index()
        as_sum['Belum Input'] = as_sum['Target'] - as_sum['Sudah']
        as_sum['Progres'] = (as_sum['Sudah'] / as_sum['Target']) * 100
        as_sum.columns = ['AS', 'Target Toko SO', 'Sudah Input', 'Belum Input', 'Progres']
        as_sum = as_sum.sort_values(by=['Progres', 'Target Toko SO'], ascending=[True, False])
        
        return df_temp, am_sum, as_sum
    except: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def delete_old_reports(current_ver):
    try:
        next_cursor = None
        deleted_count = 0
        while True:
            res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500, next_cursor=next_cursor)
            for r in res.get('resources', []):
                if f"_v{current_ver}" not in r['public_id']:
                    cloudinary.uploader.destroy(r['public_id'], resource_type="raw")
                    deleted_count += 1
            next_cursor = res.get('next_cursor')
            if not next_cursor: break
        return True, deleted_count
    except Exception as e: return False, str(e)

# =================================================================
# 4. DIALOGS & FRAGMENTS
# =================================================================

@st.dialog("🗑️ Bersihkan Data Lama")
def confirm_delete_old_data(v_now):
    st.error("⚠️ Semua hasil input periode SEBELUMNYA akan dihapus permanen.")
    if st.button("IYA, Hapus Sekarang", type="primary", use_container_width=True):
        with st.spinner("Cleaning..."):
            ok, res = delete_old_reports(v_now)
            if ok:
                st.success(f"✅ Berhasil menghapus {res} file!"); time.sleep(1.5); st.rerun()
            else: st.error(f"Gagal: {res}")

@st.dialog("⚠️ Konfirmasi Publish")
def confirm_admin_publish(file_obj):
    st.warning("Publish Master baru akan mereset progres toko hari ini.")
    if st.button("IYA, Publish Sekarang", type="primary", use_container_width=True):
        status = False
        try:
            cloudinary.uploader.upload(file_obj, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
            status = True
        except Exception as e: st.error(f"Gagal: {e}")
        if status:
            st.success("✅ Master Terbit!"); time.sleep(1.5); st.rerun()

@st.dialog("Konfirmasi Simpan")
def confirm_user_submit(data_full, toko_code, v_id):
    if st.button("Ya, Simpan ke Cloud", use_container_width=True):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: data_full.to_excel(w, index=False)
        status = False
        try:
            p_id = f"so_rawan_hilang/hasil/Hasil_{toko_code}_v{v_id}.xlsx"
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            status = True
        except Exception as e: st.error(f"Gagal: {e}")
        if status:
            st.success("✅ Berhasil!"); time.sleep(1.5); st.rerun()

@st.fragment
def show_user_editor(df_full, c_sales, c_fisik, c_stok, c_selisih, toko_id, v_now):
    display_cols = [c for c in df_full.columns if c not in [df_full.columns[0], df_full.columns[1], df_full.columns[2], df_full.columns[3]]]
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
            st.error("⚠️ Ada kolom yang kosong!")
        else:
            for col_idx in [0, 1, 2, 3]:
                col_name = df_full.columns[col_idx]
                edited_display.insert(col_idx, col_name, df_full[col_name].values)
            vs, vf, vh = edited_display[c_sales].fillna(0), edited_display[c_fisik].fillna(0), edited_display[c_stok].fillna(0)
            edited_display[c_selisih] = (vs + vf) - vh
            confirm_user_submit(edited_display, toko_id, v_now)

# =================================================================
# 5. ROUTING & PAGES
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
            t_t = df_am['Target Toko SO'].sum()
            s_t = df_am['Sudah Input'].sum()
            c1, c2, c3 = st.columns(3)
            c1.metric("Total Toko SO", t_t)
            c2.metric("Sudah SO", s_t, f"{(s_t/t_t):.1%}" if t_t > 0 else "0%")
            c3.metric("Belum SO", t_t-s_t, delta=f"-({t_t-s_t})", delta_color="inverse")
            st.progress(s_t/t_t if t_t > 0 else 0)
            
            st.subheader("📊 Ringkasan Progres AM (Urutan Terendah)")
            st.dataframe(df_am, column_config={"Progres": st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
            
            st.subheader("📊 Ringkasan Progres AS (Urutan Terendah)")
            st.dataframe(df_as, column_config={"Progres": st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)

            # EXPANDER AM (YANG DIMINTA)
            with st.expander("🔍 Cek Detail Toko Belum SO Per AM"):
                list_am = sorted(df_am[df_am['Sudah Input'] < df_am['Target Toko SO']]['AM'].unique())
                if list_am:
                    sel_am = st.selectbox("Pilih Area Manager (AM):", list_am, key="sel_am_home")
                    if sel_am:
                        pending_am = df_full[(df_full['AM'] == sel_am) & (df_full['Status'] == 0)]
                        st.warning(f"Terdapat {len(pending_am)} toko di wilayah AM {sel_am} belum SO:")
                        st.table(pending_am[['Kode', 'Nama']])
                else: st.success("Semua AM sudah 100%!")

            # EXPANDER AS (YANG DIMINTA)
            with st.expander("🔍 Cek Detail Toko Belum SO Per AS"):
                list_as = sorted(df_as[df_as['Sudah Input'] < df_as['Target Toko SO']]['AS'].unique())
                if list_as:
                    sel_as = st.selectbox("Pilih Area Supervisor (AS):", list_as, key="sel_as_home")
                    if sel_as:
                        pending_as = df_full[(df_full['AS'] == sel_as) & (df_full['Status'] == 0)]
                        st.warning(f"Terdapat {len(pending_as)} toko di wilayah AS {sel_as} belum SO:")
                        st.table(pending_as[['Kode', 'Nama']])
                else: st.success("Semua AS sudah 100%!")
    else:
        st.info("💡 Menunggu Admin mempublikasikan master data.")
    
    st.divider()
    cl1, cl2, cl3 = st.columns(3)
    if cl1.button("🔑 LOGIN", use_container_width=True, type="primary"): st.session_state.page = "LOGIN"; st.rerun()
    if cl2.button("📝 DAFTAR", use_container_width=True): st.session_state.page = "REGISTER"; st.rerun()
    if cl3.button("🛡️ ADMIN", use_container_width=True): st.session_state.page = "ADMIN"; st.rerun()

# --- LOGIN & REGISTER ---
elif st.session_state.page == "REGISTER":
    st.header("📝 Daftar Akun")
    n_nik = st.text_input("NIK (10 Digit):", max_chars=10); n_pw = st.text_input("Password:", type="password")
    if st.button("Daftar"):
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
    st.link_button("📲 Lupa Password? Hubungi Admin", "https://wa.me/6287725860048?text=Halo%20Admin,%20saya%20lupa%20password", use_container_width=True)

# --- ADMIN PANEL ---
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
                all_files = []
                next_cursor = None
                while True:
                    res_raw = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500, next_cursor=next_cursor)
                    batch = [r for r in res_raw.get('resources', []) if f"_v{m_ver}" in r['public_id']]
                    all_files.extend(batch)
                    next_cursor = res_raw.get('next_cursor')
                    if not next_cursor: break
                
                if st.button(f"🔄 Gabung Data Seluruh Toko ({len(all_files)} Toko)"):
                    with st.spinner("Menggabungkan data..."):
                        m_tk_col = m_df.columns[0]
                        m_prd_col = next((c for c in m_df.columns if 'prdcd' in c.lower()), m_df.columns[4])
                        for r in all_files:
                            try:
                                s_df = pd.read_excel(r['secure_url']); s_df.columns = [str(c).strip() for c in s_df.columns]
                                s_tk_col = s_df.columns[0]
                                s_prd_col = next((c for c in s_df.columns if 'prdcd' in c.lower()), s_df.columns[4])
                                for _, row in s_df.iterrows():
                                    mask = (m_df[m_tk_col].astype(str) == str(row[s_tk_col])) & (m_df[m_prd_col].astype(str) == str(row[s_prd_col]))
                                    if mask.any():
                                        target_cols = [c for c in s_df.columns if any(x in c.lower() for x in ['sales', 'fisik', 'selisih'])]
                                        m_df.loc[mask, target_cols] = row[target_cols].values
                            except: continue
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                        st.download_button("📥 Download Rekap", buf.getvalue(), f"Rekap_SO_{get_indonesia_date()}.xlsx")
            st.divider()
            if st.button("🗑️ Hapus Inputan Lama", use_container_width=True):
                if v_now: confirm_delete_old_data(v_now)

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
    if oc.button("🚪 Logout"): st.session_state.logged_in, st.session_state.user_search_active = False, False; st.session_state.page = "HOME"; st.rerun()
    
    t_in = st.text_input("📍 Kode Toko:", max_chars=4, placeholder="Contoh TQ86").upper()
    if st.button("🔍 Cari"):
        if len(t_in) == 4: st.session_state.active_toko, st.session_state.user_search_active = t_in, True
        else: st.error("Isi 4 Digit!")

    if st.session_state.user_search_active:
        df_m, v_now = get_master_info()
        if df_m is not None:
            m_filt = df_m[df_m[df_m.columns[0]].astype(str) == st.session_state.active_toko].copy()
            if not m_filt.empty:
                n_tk = m_filt.iloc[0, 1]; am_tk = m_filt.iloc[0, 2]; as_tk = m_filt.iloc[0, 3]
                st.success(f"🏠 **{n_tk}** | 👤 AM: **{am_tk}** | 🛡️ AS: **{as_tk}**")
                data_input = load_user_save(st.session_state.active_toko, v_now)
                if data_input is None: 
                    data_input = m_filt
                    c_s = next((c for c in data_input.columns if 'sales' in c.lower()), 'Query Sales')
                    c_f = next((c for c in data_input.columns if 'fisik' in c.lower()), 'Jml Fisik')
                    data_input[c_s], data_input[c_f] = None, None
                c_stok = next((c for c in data_input.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_input.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_input.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_input.columns if 'selisih' in c.lower()), 'Selisih')
                show_user_editor(data_input, c_sales, c_fisik, c_stok, c_selisih, st.session_state.active_toko, v_now)
