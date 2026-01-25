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
# 1. KONFIGURASI & HIDE UI (ANTI-GITHUB)
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
    return datetime.utcnow() + timedelta(hours=8)

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
# 3. FUNGSI OLAH EXCEL & DASHBOARD
# =================================================================
def get_indonesia_date():
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    now = get_now_wita()
    return f"{now.day}_{bulan[now.month-1]}_{now.year}"

@st.cache_data(ttl=10)
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

def delete_old_reports(current_ver):
    """Fungsi mandiri untuk menghapus data lama."""
    try:
        resources = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500)
        deleted_count = 0
        for res in resources.get('resources', []):
            if f"_v{current_ver}" not in res['public_id']:
                cloudinary.uploader.destroy(res['public_id'], resource_type="raw")
                deleted_count += 1
        return True, deleted_count
    except Exception as e: return False, str(e)

@st.cache_data(ttl=60)
def get_report_status(m_ver, df_master):
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
        all_stores = set(df_master[df_master.columns[0]].astype(str).unique())
        not_submitted = sorted(list(all_stores - submitted_codes))
        return list(submitted_codes), not_submitted
    except: return [], []

# =================================================================
# 4. DIALOGS & FRAGMENTS
# =================================================================
@st.dialog("🗑️ Bersihkan Data Lama")
def confirm_delete_old_data(v_now):
    st.error("⚠️ PERINGATAN: Semua hasil input dari periode SEBELUMNYA akan dihapus permanen.")
    if st.button("IYA, Hapus Data Lama", type="primary", use_container_width=True):
        with st.spinner("Membersihkan..."):
            success, result = delete_old_reports(v_now)
            if success:
                st.success(f"✅ Berhasil menghapus {result} file!"); time.sleep(2); st.rerun()
            else: st.error(f"Gagal: {result}")

@st.dialog("⚠️ Konfirmasi Publish Master")
def confirm_admin_publish(file_obj):
    st.warning("Anda akan Publish Master baru & mereset progres toko hari ini.")
    if st.button("IYA, Publish Sekarang", type="primary", use_container_width=True):
        msg = st.empty()
        try:
            cloudinary.uploader.upload(file_obj, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
            msg.success("✅ Master Berhasil Terbit!"); time.sleep(2); st.rerun()
        except Exception as e: msg.error(f"Gagal Upload: {e}")

@st.dialog("Konfirmasi Simpan")
def confirm_user_submit(data_toko, toko_code, v_id):
    if st.button("Ya, Simpan ke Cloud", use_container_width=True):
        msg = st.empty()
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: data_toko.to_excel(w, index=False)
        try:
            p_id = f"so_rawan_hilang/hasil/Hasil_{toko_code}_v{v_id}.xlsx"
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            msg.success("✅ Tersimpan!"); time.sleep(1.5); st.rerun()
        except Exception as e: msg.error(f"Gagal: {e}")

@st.fragment
def show_user_editor(df_in, c_sales, c_fisik, c_stok, c_selisih, toko_id, v_now):
    df_in[c_sales] = pd.to_numeric(df_in[c_sales], errors='coerce')
    df_in[c_fisik] = pd.to_numeric(df_in[c_fisik], errors='coerce')
    edited = st.data_editor(df_in, column_config={
            c_sales: st.column_config.NumberColumn(f"📥 {c_sales}", format="%d", min_value=0),
            c_fisik: st.column_config.NumberColumn(f"📥 {c_fisik}", format="%d", min_value=0),
            c_selisih: st.column_config.NumberColumn(c_selisih, format="%d"),
            c_stok: st.column_config.NumberColumn(c_stok, format="%d"),
        }, disabled=[c for c in df_in.columns if c not in [c_sales, c_fisik]], hide_index=True, use_container_width=True, key=f"ed_{toko_id}")
    if st.button("🚀 Simpan Laporan", type="primary", use_container_width=True):
        if edited[c_sales].isnull().any() or edited[c_fisik].isnull().any(): st.error("⚠️ Masih Ada Kolom Yang Kosong!")
        else:
            vs, vf, vh = edited[c_sales].fillna(0).astype(int), edited[c_fisik].fillna(0).astype(int), edited[c_stok].fillna(0).astype(int)
            edited[c_selisih] = (vs + vf) - vh
            confirm_user_submit(edited, toko_id, v_now)

# =================================================================
# 5. SISTEM STATE & ROUTING
# =================================================================
for key in ['page', 'logged_in', 'user_nik', 'admin_auth', 'user_search_active']:
    if key not in st.session_state: st.session_state[key] = False if 'auth' in key or 'in' in key or 'active' in key else "HOME"

if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    df_m, v_now = get_master_info()
    if v_now:
        with st.spinner("Loading..."):
            list_masuk, list_belum = get_report_status(v_now, df_m)
            total_toko = len(df_m[df_m.columns[0]].unique())
            st.subheader("📊 Progres Real-Time")
            m1, m2, m3 = st.columns(3)
            m1.metric("Total Toko", total_toko)
            m2.metric("Jml Toko Sudah Input", len(list_masuk), delta=f"{len(list_masuk)/total_toko:.1%}")
            m3.metric("Jml Toko Belum Input", len(list_belum), delta=f"-{len(list_belum)}", delta_color="inverse")
            st.progress(len(list_masuk) / total_toko if total_toko > 0 else 0)
            with st.expander(f"🚩 Lihat {len(list_belum)} Toko Belum Kirim"):
                if list_belum:
                    cols = st.columns(5)
                    for idx, t_code in enumerate(list_belum): cols[idx % 5].write(f"• {t_code}")
                else: st.success("🎉 Selesai!")
    else: st.warning("⚠️ Master data belum terbit.")
    st.divider()
    col1, col2, col3 = st.columns(3)
    if col1.button("🔑 LOGIN", use_container_width=True, type="primary"): st.session_state.page = "LOGIN"; st.rerun()
    if col2.button("📝 DAFTAR", use_container_width=True): st.session_state.page = "REGISTER"; st.rerun()
    if col3.button("🛡️ ADMIN", use_container_width=True): st.session_state.page = "ADMIN"; st.rerun()

elif st.session_state.page == "REGISTER":
    st.header("📝 Daftar Akun")
    n_nik = st.text_input("NIK (10 Digit):", max_chars=10)
    n_pw = st.text_input("Password:", type="password")
    if st.button("Daftar"):
        if len(n_nik) == 10 and n_nik.isdigit():
            db = load_json_db(USER_DB_PATH)
            if n_nik not in db:
                db[n_nik] = n_pw
                if save_json_db(USER_DB_PATH, db): st.success("✅ Berhasil!"); time.sleep(2); st.session_state.page = "LOGIN"; st.rerun()
            else: st.error("NIK ada!")
        else: st.error("NIK salah!")
    if st.button("⬅️ Kembali"): st.session_state.page = "HOME"; st.rerun()

elif st.session_state.page == "LOGIN":
    st.header("🔑 Login")
    l_nik = st.text_input("NIK:", max_chars=10)
    l_pw = st.text_input("Password:", type="password")
    if st.button("Masuk", type="primary"):
        db = load_json_db(USER_DB_PATH)
        if l_nik in db and db[l_nik] == l_pw:
            record_login_hit(l_nik)
            st.session_state.logged_in, st.session_state.user_nik, st.session_state.page = True, l_nik, "USER_INPUT"; st.rerun()
        else: st.error("Salah!")
    if st.button("⬅️ Kembali"): st.session_state.page = "HOME"; st.rerun()

elif st.session_state.page == "ADMIN":
    hc, oc = st.columns([5, 1])
    hc.header("🛡️ Admin Panel")
    if oc.button("🚪 Logout"): st.session_state.admin_auth, st.session_state.page = False, "HOME"; st.rerun()
    if not st.session_state.admin_auth:
        pw = st.text_input("Password Admin:", type="password")
        if st.button("Buka"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
            else: st.error("Salah!")
    else:
        t1, t2, t3 = st.tabs(["📤 Master & Rekap", "📊 Monitoring", "🔐 Reset"])
        with t1:
            st.subheader("Update Master")
            f_adm = st.file_uploader("Upload Excel", type=["xlsx"])
            if f_adm and st.button("🚀 Publish Master"): confirm_admin_publish(f_adm)
            st.divider()
            st.subheader("📥 Penarikan Data")
            m_df, m_ver = get_master_info()
            if m_df is not None:
                with st.spinner("Checking..."):
                    all_f = []
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500)
                    all_f = [r for r in res.get('resources', []) if f"_v{m_ver}" in r['public_id']]
                if all_f:
                    st.info(f"📊 Ada {len(all_f)} laporan.")
                    if st.button("🔄 Gabung & Download"):
                        for r in all_f:
                            s_df = pd.read_excel(r['secure_url'])
                            s_df.columns = [str(c).strip() for c in s_df.columns]
                            for _, row in s_df.iterrows():
                                mask = (m_df[m_df.columns[2]] == row[s_df.columns[2]]) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                                if mask.any(): m_df.loc[mask, s_df.columns] = row.values
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                        st.download_button("📥 Download Rekap", buf.getvalue(), f"Rekap_{get_indonesia_date()}.xlsx")
                else: st.warning("Belum ada laporan.")
            st.divider()
            st.subheader("🧹 Pembersihan")
            if st.button("🗑️ Hapus Inputan Lama", use_container_width=True):
                if m_ver: confirm_delete_old_data(m_ver)
                else: st.error("Master missing.")
        with t2:
            logs = load_json_db(LOG_DB_PATH)
            if logs:
                flat = [{"NIK": k, "Tanggal": t, "Hits": h} for k, d in logs.items() for t, h in d.items()]
                st.dataframe(pd.DataFrame(flat).sort_values(by="Tanggal", ascending=False), hide_index=True)
        with t3:
            r_nik = st.text_input("NIK:"); r_pw = st.text_input("New PW:", type="password")
            if st.button("Reset"):
                db = load_json_db(USER_DB_PATH)
                if r_nik in db: db[r_nik] = r_pw; save_json_db(USER_DB_PATH, db); st.success("OK!")

elif st.session_state.page == "USER_INPUT":
    if not st.session_state.logged_in: st.session_state.page = "HOME"; st.rerun()
    hc, oc = st.columns([5, 1]); hc.header(f"📋 Input SO ({st.session_state.user_nik})")
    if oc.button("🚪 Logout"): st.session_state.logged_in = False; st.session_state.user_search_active = False; st.session_state.active_toko = ""; st.session_state.page = "HOME"; st.rerun()
    t_id = st.text_input("📍 Kode Toko:", max_chars=4, placeholder="Contoh: TQ86").upper()
    if st.button("🔍 Cari"):
        if len(t_id) == 4: st.session_state.active_toko, st.session_state.user_search_active = t_id, True
        else: st.error("Isi 4 digit!")
    if st.session_state.user_search_active:
        df_m, v_now = get_master_info()
        if df_m is not None:
            m_filt = df_m[df_m[df_m.columns[0]].astype(str) == st.session_state.active_toko].copy()
            if not m_filt.empty:
                data_show = load_user_save(st.session_state.active_toko, v_now)
                if data_show is None: data_show = m_filt
                c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), 'Stok')
                c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Sales')
                c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Fisik')
                c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')
                show_user_editor(data_show, c_sales, c_fisik, c_stok, c_selisih, st.session_state.active_toko, v_now)
            else: st.error("Toko tidak ada.")





