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
# 1. KONFIGURASI UTAMA
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

# SET PAGE CONFIG HANYA SEKALI DI SINI (WAJIB PALING ATAS)
st.set_page_config(page_title="Sistem SO Rawan Hilang", layout="wide")

# Link GIF Maintenance (Silakan ganti URL ini jika punya link GIF lain)
GIF_MAINTENANCE = "https://res.cloudinary.com/ddtgzywhh/image/upload/v1771046500/download_lwj6f1.gif"

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
CONFIG_PATH = "so_rawan_hilang/config/project_config.json"

def get_now_wita():
    return datetime.utcnow() + timedelta(hours=8)

def get_session_date():
    return get_now_wita().strftime('%Y-%m-%d')

def get_indonesia_date():
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    now = get_now_wita()
    return f"{now.day}_{bulan[now.month-1]}_{now.year}"

def load_json_db(path):
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{path}"
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
    today = get_session_date()
    if nik not in db_logs: db_logs[nik] = {}
    db_logs[nik][today] = db_logs[nik].get(today, 0) + 1
    save_json_db(LOG_DB_PATH, db_logs)

def is_maintenance_mode():
    config = load_json_db(CONFIG_PATH)
    return config.get("maintenance_mode", False)

def set_maintenance_mode(status: bool):
    config = load_json_db(CONFIG_PATH)
    config["maintenance_mode"] = status
    save_json_db(CONFIG_PATH, config)

# =================================================================
# 3. FUNGSI OLAH DATA
# =================================================================

def get_active_project_id():
    config = load_json_db(CONFIG_PATH)
    return config.get("active_id", "default_v1")

@st.cache_data(ttl=60)
def get_master_info():
    try:
        p_id = "so_rawan_hilang/master_utama.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{p_id}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except: return None

def load_user_save(toko_id, project_id):
    try:
        path_file = f"so_rawan_hilang/hasil/Hasil_{toko_id}_{project_id}.xlsx"
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{path_file}"
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except: return None

@st.cache_data(ttl=60)
def get_progress_rankings(df_master):
    try:
        p_id_active = get_active_project_id()
        submitted_codes = set()
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"so_rawan_hilang/hasil/Hasil_", max_results=500)
        for r in res.get("resources", []):
            if f"_{p_id_active}" in r["public_id"]:
                code = r["public_id"].split("Hasil_")[-1].split(f"_{p_id_active}")[0]
                submitted_codes.add(code)
        
        df_temp = df_master.iloc[:, [0, 1, 2, 3]].copy()
        df_temp.columns = ["Kode", "Nama", "AM", "AS"]
        df_temp = df_temp.drop_duplicates()
        df_temp['Status'] = df_temp['Kode'].astype(str).str.strip().apply(lambda x: 1 if x in submitted_codes else 0)
        
        am_sum = df_temp.groupby("AM").agg(Target=("Kode", "count"), Sudah=("Status", "sum")).reset_index()
        am_sum['Belum SO'] = am_sum['Target'] - am_sum['Sudah']
        am_sum['Progres'] = (am_sum['Sudah'] / am_sum['Target']) * 100
        am_sum.columns = ["AM", "Target Toko SO", "Sudah SO", "Belum SO", "Progres"]
        am_sum = am_sum.sort_values(by=["Progres", "Target Toko SO"], ascending=[True, False])

        as_sum = df_temp.groupby("AS").agg(Target=("Kode", "count"), Sudah=("Status", "sum")).reset_index()
        as_sum['Belum SO'] = as_sum['Target'] - as_sum['Sudah']
        as_sum['Progres'] = (as_sum['Sudah'] / as_sum['Target']) * 100
        as_sum.columns = ["AS", "Target Toko SO", "Sudah SO", "Belum SO", "Progres"]
        as_sum = as_sum.sort_values(by=["Progres", "Target Toko SO"], ascending=[True, False])
        
        return df_temp, am_sum, as_sum
    except: return pd.DataFrame(), pd.DataFrame(), pd.DataFrame()

def delete_old_reports(active_id):
    try:
        res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500)
        deleted = 0
        for r in res.get("resources", []):
            if f"_{active_id}" not in r["public_id"]:
                cloudinary.uploader.destroy(r["public_id"], resource_type="raw")
                deleted += 1
        return True, deleted
    except Exception as e: return False, str(e)

# =================================================================
# 4. DIALOGS, FRAGMENTS & MAINTENANCE
# =================================================================

@st.dialog("🗑️ Bersihkan Data Lama")
def confirm_delete_old_data(active_id):
    st.error(f"Semua hasil input yang BUKAN ID {active_id} akan dihapus.")
    if st.button("IYA, Hapus Sekarang", type="primary", use_container_width=True):
        ok, res = delete_old_reports(active_id)
        if ok:
            st.success(f"✅ Terhapus {res} file!"); time.sleep(2.5); st.rerun()
        else: st.error(f"Gagal: {res}")

@st.dialog("⚠️ Konfirmasi Publish Master Baru")
def confirm_admin_publish(file_obj):
    st.error("Tindakan ini akan MENGHAPUS SEMUA progres (ID Baru).")
    if st.button("IYA, Reset & Publish", type="primary", use_container_width=True):
        try:
            new_id = f"ID{int(time.time())}"
            save_json_db(CONFIG_PATH, {"active_id": new_id, "maintenance_mode": is_maintenance_mode()})
            cloudinary.api.delete_resources_by_prefix("so_rawan_hilang/hasil/", resource_type="raw")
            cloudinary.uploader.upload(file_obj, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
            st.cache_data.clear()
            st.success(f"✅ Master Terbit! (ID: {new_id})"); time.sleep(2.5); st.rerun()
        except: st.error("Gagal!")

@st.dialog("⚙️ Update Master Aktif")
def confirm_admin_update_aktif(file_obj):
    if st.button("IYA, Update File Master", use_container_width=True):
        try:
            cloudinary.uploader.upload(file_obj, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
            st.cache_data.clear()
            st.success("✅ Master Diperbarui!"); time.sleep(2.5); st.rerun()
        except: st.error("Gagal!")

@st.dialog("Konfirmasi Simpan")
def confirm_user_submit(data_full, toko_code, p_id):
    if st.button("Ya, Simpan ke Cloud", use_container_width=True):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: data_full.to_excel(w, index=False)
        try:
            p_id_file = f"so_rawan_hilang/hasil/Hasil_{toko_code}_{p_id}.xlsx"
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id_file, overwrite=True, invalidate=True)
            st.success("✅ Berhasil Tersimpan!"); time.sleep(2.5); st.rerun()
        except: st.error("Gagal!")

@st.fragment
def show_user_editor(df_full, c_sales, c_fisik, c_stok, c_selisih, toko_id, p_id):
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
            st.error("⚠️ Ada kolom yang belum diisi!")
        else:
            for col_idx in [0, 1, 2, 3]:
                col_name = df_full.columns[col_idx]
                edited_display.insert(col_idx, col_name, df_full[col_name].values)
            vs, vf, vh = edited_display[c_sales].fillna(0).astype(int), edited_display[c_fisik].fillna(0).astype(int), edited_display[c_stok].fillna(0).astype(int)
            edited_display[c_selisih] = (vs + vf) - vh
            confirm_user_submit(edited_display, toko_id, p_id)

@st.dialog("⚙️ Pengaturan Maintenance")
def maintenance_dialog():
    current_status = is_maintenance_mode()
    st.warning(f"Status Maintenance: {'AKTIF' if current_status else 'TIDAK AKTIF'}")
    if st.button("Ubah Status Maintenance", use_container_width=True):
        set_maintenance_mode(not current_status)
        st.success("✅ Status Berhasil Diubah!"); time.sleep(2.5); st.rerun()

def show_maintenance_page():
    st.markdown("<br><br>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        # Menampilkan GIF Animasi
        st.image(GIF_MAINTENANCE, use_container_width=True)
        st.markdown("<h1 style='text-align: center; color: #FF4B4B;'>Web Sedang Maintenance</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Kami sedang melakukan pembaruan sistem untuk kenyamanan Anda.</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Mohon coba kembali beberapa saat lagi.</p>", unsafe_allow_html=True)
        if st.button("Masuk sebagai Admin", use_container_width=True):
            st.session_state.page = "ADMIN"
            st.rerun()

# =================================================================
# 5. ROUTING & LOGIKA UTAMA
# =================================================================
for key in ['page', 'logged_in', 'user_nik', 'admin_auth', 'user_search_active', 'active_toko']:
    if key not in st.session_state: st.session_state[key] = False if 'auth' in key or 'in' in key or 'active' in key else "HOME"

# CEK MAINTENANCE
if is_maintenance_mode() and st.session_state.page != "ADMIN":
    show_maintenance_page()
else:
    if st.session_state.page == "HOME":
        st.title("📑 Sistem SO Rawan Hilang")
        df_m = get_master_info()
        if df_m is not None:
            df_full, df_am, df_as = get_progress_rankings(df_m)
            if not df_am.empty:
                t_t = df_am['Target Toko SO'].sum(); s_t = df_am['Sudah SO'].sum()
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Toko SO", t_t)
                c2.metric("Sudah SO", s_t, f"{(s_t/t_t):.1%}" if t_t > 0 else "0%")
                c3.metric("Belum SO", t_t-s_t, delta=f"-({t_t-s_t})", delta_color="inverse")
                st.progress(s_t/t_t if t_t > 0 else 0)
                st.subheader("📊 Progres AM (Urutan Terendah di Atas)")
                st.dataframe(df_am, column_config={'Progres': st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                st.subheader("📊 Progres AS (Urutan Terendah di Atas)")
                st.dataframe(df_as, column_config={'Progres': st.column_config.ProgressColumn(format="%d%%", min_value=0, max_value=100)}, hide_index=True, use_container_width=True)
                with st.expander("🔍 Detail Toko Belum SO Per AM"):
                    list_am = sorted(df_am[df_am['Sudah SO'] < df_am['Target Toko SO']]['AM'].unique())
                    if list_am:
                        sel_am = st.selectbox("Pilih AM:", list_am, key="sel_am_home")
                        if sel_am:
                            pending_am = df_full[(df_full['AM'] == sel_am) & (df_full['Status'] == 0)]
                            st.dataframe(pending_am[["Kode", "Nama"]], hide_index=True, use_container_width=True)
                with st.expander("🔍 Detail Toko Belum SO Per AS"):
                    list_as = sorted(df_as[df_as['Sudah SO'] < df_as['Target Toko SO']]['AS'].unique())
                    if list_as:
                        sel_as = st.selectbox("Pilih AS:", list_as, key="sel_as_home")
                        if sel_as:
                            pending_as = df_full[(df_full['AS'] == sel_as) & (df_full['Status'] == 0)]
                            st.dataframe(pending_as[["Kode", "Nama"]], hide_index=True, use_container_width=True)
        st.divider()
        cl1, cl2, cl3 = st.columns(3)
        if cl1.button("🔑 LOGIN", use_container_width=True, type="primary"): st.session_state.page = "LOGIN"; st.rerun()
        if cl2.button("📝 DAFTAR", use_container_width=True): st.session_state.page = "REGISTER"; st.rerun()
        if cl3.button("🛡️ ADMIN", use_container_width=True): st.session_state.page = "ADMIN"; st.rerun()

    elif st.session_state.page == "ADMIN":
        hc, oc = st.columns([5, 1]); hc.header("🛡️ Admin Panel")
        if oc.button("🚪 Logout"): st.session_state.admin_auth, st.session_state.page = False, "HOME"; st.rerun()
        if not st.session_state.admin_auth:
            pw = st.text_input("Admin Password:", type="password")
            if st.button("Masuk Panel"):
                if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
        else:
            t1, t2, t3 = st.tabs(["📤 Master & Rekap", "📊 Monitoring", "🔐 Reset PW"])
            with t1:
                col_u1, col_u2 = st.columns(2)
                with col_u1:
                    st.subheader("1. Publish Baru")
                    f_new = st.file_uploader("Upload reset harian", type=["xlsx"], key="up_new")
                    if f_new and st.button("🚀 Reset & Publish"): confirm_admin_publish(f_new)
                with col_u2:
                    st.subheader("2. Update Aktif")
                    f_update = st.file_uploader("Upload revisi master", type=["xlsx"], key="up_active")
                    if f_update and st.button("🔄 Update Revisi"): confirm_admin_update_aktif(f_update)
                st.divider()
                m_df = get_master_info()
                if m_df is not None:
                    p_id_act = get_active_project_id()
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/hasil/Hasil_", max_results=500)
                    all_f = [r for r in res.get("resources", []) if f"_{p_id_act}" in r["public_id"]]
                    if st.button(f"🔄 Gabung & Download ({len(all_f)} Toko)"):
                        m_tk_col, m_prd_col = m_df.columns[0], next((c for c in m_df.columns if 'prdcd' in c.lower()), m_df.columns[4])
                        for r in all_f:
                            try:
                                s_df = pd.read_excel(r['secure_url']); s_df.columns = [str(c).strip() for c in s_df.columns]
                                s_tk_col, s_prd_col = s_df.columns[0], next((c for c in s_df.columns if 'prdcd' in c.lower()), s_df.columns[4])
                                for _, row in s_df.iterrows():
                                    mask = (m_df[m_tk_col].astype(str).str.strip() == str(row[s_tk_col]).strip()) & (m_df[m_prd_col].astype(str).str.strip() == str(row[s_prd_col]).strip())
                                    if mask.any():
                                        target_cols = [c for c in s_df.columns if any(x in c.lower() for x in ['sales', 'fisik', 'selisih'])]
                                        m_df.loc[mask, target_cols] = row[target_cols].values
                            except: continue
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                        st.download_button("📥 Download Rekap", buf.getvalue(), f"Rekap_SO_{get_indonesia_date()}.xlsx")
                st.divider()
                if st.button("🧹 Hapus Data Lama"): confirm_delete_old_data(get_active_project_id())
                if st.button("🛠️ PENGATURAN MAINTENANCE", use_container_width=True): maintenance_dialog()

            with t2:
                logs = load_json_db(LOG_DB_PATH)
                if logs:
                    flat = [{"NIK": k, "Tanggal": t, "Hits": h} for k, d in logs.items() for t, h in d.items()]
                    st.dataframe(pd.DataFrame(flat).sort_values(by="Tanggal", ascending=False), hide_index=True, use_container_width=True)
            with t3:
                r_nik = st.text_input("NIK reset:"); r_pw = st.text_input("Password Baru:", type="password")
                if st.button("Reset Sekarang"):
                    db = load_json_db(USER_DB_PATH)
                    if r_nik in db: db[r_nik] = r_pw; save_json_db(USER_DB_PATH, db); st.success("Password Berhasil Di Reset!"); time.sleep(2)

    elif st.session_state.page == "REGISTER":
        st.header("📝 Daftar Akun")
        n_nik = st.text_input("NIK (10 Digit):", max_chars=10); n_pw = st.text_input("Password Baru:", type="password")
        if st.button("Daftar"):
            if len(n_nik) == 10:
                db = load_json_db(USER_DB_PATH); db[n_nik] = n_pw; save_json_db(USER_DB_PATH, db); st.success("User Terdaftar!"); time.sleep(2); st.session_state.page = "LOGIN"; st.rerun()
        if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()

    elif st.session_state.page == "LOGIN":
        st.header("🔑 Login Karyawan")
        l_nik = st.text_input("NIK:", max_chars=10); l_pw = st.text_input("Password:", type="password")
        if st.button("Masuk"):
            db = load_json_db(USER_DB_PATH)
            if l_nik in db and db[l_nik] == l_pw:
                record_login_hit(l_nik); st.session_state.logged_in, st.session_state.user_nik, st.session_state.page = True, l_nik, "USER_INPUT"; st.rerun()
        if st.button("Kembali"): st.session_state.page = "HOME"; st.rerun()
        st.link_button("📲 Lupa Password? Hubungi Admin", "https://wa.me/6287725860048?text=Lupa%20Password", use_container_width=True)

    elif st.session_state.page == "USER_INPUT":
        if not st.session_state.logged_in: st.session_state.page = "HOME"; st.rerun()
        hc, oc = st.columns([5, 1]); hc.header(f"📋 Menu Input ({st.session_state.user_nik})")
        if oc.button("🚪 Logout"): st.session_state.logged_in = False; st.session_state.user_search_active = False; st.session_state.page = "HOME"; st.rerun()
        t_in = st.text_input("📍 Kode Toko:", max_chars=4, placeholder="Contoh TQ86").upper()
        if st.button("🔍 Cari Data"):
            if len(t_in) == 4: st.session_state.active_toko, st.session_state.user_search_active = t_in, True
        if st.session_state.user_search_active:
            df_m = get_master_info()
            if df_m is not None:
                m_filt = df_m[df_m[df_m.columns[0]].astype(str).str.strip() == st.session_state.active_toko].copy()
                if not m_filt.empty:
                    # LABEL IDENTITAS LENGKAP
                    st.success(f"🏠 **{m_filt.iloc[0,1]}** | 👤 AM: **{m_filt.iloc[0,2]}** | 🛡️ AS: **{m_filt.iloc[0,3]}**")
                    p_id_act = get_active_project_id()
                    data_input = load_user_save(st.session_state.active_toko, p_id_act)
                    if data_input is None:
                        data_input = m_filt
                        c_s, c_f = next((c for c in data_input.columns if 'sales' in c.lower()), 'Query Sales'), next((c for c in data_input.columns if 'fisik' in c.lower()), 'Jml Fisik')
                        data_input[c_s], data_input[c_f] = None, None
                    c_st = next((c for c in data_input.columns if 'stok' in c.lower()), 'Stok H-1')
                    c_sl = next((c for c in data_input.columns if 'sales' in c.lower()), 'Query Sales')
                    c_fi = next((c for c in data_input.columns if 'fisik' in c.lower()), 'Jml Fisik')
                    c_se = next((c for c in data_input.columns if 'selisih' in c.lower()), 'Selisih')
                    show_user_editor(data_input, c_sl, c_fi, c_st, c_se, st.session_state.active_toko, p_id_act)
                else: st.error("Toko tidak ditemukan di master data.")
