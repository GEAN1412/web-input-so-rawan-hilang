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

# --- 2. FUNGSI DATABASE (JSON) ---
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

# --- 3. FUNGSI EXCEL ---
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

# --- 4. DIALOGS ---
@st.dialog("⚠️ Konfirmasi Publish Master")
def confirm_admin_publish(file_obj):
    st.warning("Anda akan Publish Master baru & mereset inputan toko.")
    if st.button("IYA, Publish Sekarang", type="primary", use_container_width=True):
        msg = st.empty()
        is_ok = False
        try:
            cloudinary.uploader.upload(file_obj, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
            msg.success("✅ Master Terbit!")
            is_ok = True
        except Exception as e:
            msg.error(f"Gagal! {e}")
        
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
            msg.success("✅ Berhasil Tersimpan!")
            is_ok = True
        except Exception as e:
            msg.error(f"Gagal! {e}")
        
        if is_ok:
            time.sleep(1.5); st.rerun()

# --- 5. FRAGMENT EDITOR ---
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
        if edited[c_sales].isnull().any() or edited[c_fisik].isnull().any():
            st.error("⚠️ Ada kolom yang belum diisi (blank)!")
        else:
            vs, vf, vh = edited[c_sales].fillna(0).astype(int), edited[c_fisik].fillna(0).astype(int), edited[c_stok].fillna(0).astype(int)
            edited[c_selisih] = (vs + vf) - vh
            confirm_user_submit(edited, toko_id, v_now)

# --- 6. SISTEM STATE ---
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'logged_in' not in st.session_state: st.session_state.logged_in = False
if 'user_nik' not in st.session_state: st.session_state.user_nik = ""
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'user_search_active' not in st.session_state: st.session_state.user_search_active = False

# ==========================================
#              HALAMAN UTAMA
# ==========================================
if st.session_state.page == "HOME":
    st.title("📑 Sistem SO Rawan Hilang")
    
    # --- PROGRES BAR & METRIC ---
    df_m, v_now = get_master_info()
    if v_now:
        with st.spinner("Menghitung progres toko..."):
            list_masuk, list_belum = get_report_status(v_now, df_m)
            total_toko = len(df_m[df_m.columns[0]].unique())
            jumlah_masuk = len(list_masuk)
            jumlah_belum = len(list_belum)

        # Tampilan Ringkasan Atas
        st.subheader("📊 Progres Real-Time")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Toko", total_toko)
        m2.metric("Sudah Kirim", jumlah_masuk, delta=f"{jumlah_masuk/total_toko:.1%}")
        m3.metric("Belum Kirim", jumlah_belum, delta=f"-{jumlah_belum}", delta_color="inverse")
        
        # Progres Bar Visual
        st.progress(jumlah_masuk / total_toko if total_toko > 0 else 0)

        # Daftar Toko yang Belum Kirim (Dibuat Lipatan agar tidak memenuhi layar)
        with st.expander(f"🚩 Lihat {jumlah_belum} Toko yang BELUM Kirim"):
            if jumlah_belum > 0:
                # Tampilkan dalam 5 kolom agar ringkas
                cols = st.columns(5)
                for idx, t_code in enumerate(list_belum):
                    cols[idx % 5].write(f"• {t_code}")
            else:
                st.success("🎉 Semua toko sudah menyelesaikan laporan!")
    else:
        st.warning("⚠️ Master data belum tersedia.")

    st.divider()
    # Tombol menu tetap di bawah
    col1, col2, col3 = st.columns(3)
    if col1.button("🔑 LOGIN KARYAWAN", use_container_width=True, type="primary"): 
        st.session_state.page = "LOGIN"; st.rerun()
    if col2.button("📝 DAFTAR AKUN", use_container_width=True): 
        st.session_state.page = "REGISTER"; st.rerun()
    if col3.button("🛡️ ADMIN PANEL", use_container_width=True): 
        st.session_state.page = "ADMIN"; st.rerun()

# ==========================================
#              LOGIN & REGISTER
# ==========================================
elif st.session_state.page == "REGISTER":
    st.header("📝 Daftar Akun Baru")
    new_nik = st.text_input("NIK (10 Digit):", max_chars=10)
    new_pw = st.text_input("Password:", type="password")
    st.caption("Password minimal 4 digit (huruf/angka)")
    if st.button("Daftar Sekarang", use_container_width=True):
        if len(new_nik) != 10 or not new_nik.isdigit(): st.error("NIK harus 10 digit!")
        else:
            db = load_json_db(USER_DB_PATH)
            if new_nik in db: st.error("NIK sudah ada!")
            else:
                db[new_nik] = new_pw
                if save_json_db(USER_DB_PATH, db):
                    st.success("✅ Berhasil!"); time.sleep(1); st.session_state.page = "LOGIN"; st.rerun()
    if st.button("⬅️ Kembali"): st.session_state.page = "HOME"; st.rerun()

elif st.session_state.page == "LOGIN":
    st.header("🔑 Login Karyawan")
    log_nik = st.text_input("Masukkan NIK:", max_chars=10)
    log_pw = st.text_input("Masukkan Password:", type="password")
    if st.button("Masuk Sekarang", use_container_width=True, type="primary"):
        db = load_json_db(USER_DB_PATH)
        if log_nik in db and db[log_nik] == log_pw:
            record_login_hit(log_nik)
            st.session_state.logged_in, st.session_state.user_nik, st.session_state.page = True, log_nik, "USER_INPUT"; st.rerun()
        else: st.error("Salah NIK/Password!")
    if st.button("⬅️ Kembali", use_container_width=True): st.session_state.page = "HOME"; st.rerun()
    st.link_button("📲 Lupa Password? Hubungi Admin", "https://wa.me/6287725860048?text=Halo%20Admin,%20saya%20lupa%20password", use_container_width=True)

# ==========================================
#              HALAMAN ADMIN
# ==========================================
elif st.session_state.page == "ADMIN":
    hc, oc = st.columns([5, 1])
    hc.header("🛡️ Admin Panel")
    if oc.button("🚪 Logout"): st.session_state.admin_auth, st.session_state.page = False, "HOME"; st.rerun()
    if not st.session_state.admin_auth:
        pw = st.text_input("Password Admin:", type="password")
        if st.button("Buka Panel"):
            if pw == "icnkl034": st.session_state.admin_auth = True; st.rerun()
            else: st.error("Salah!")
    else:
        tab1, tab2, tab3 = st.tabs(["📤 Master & Rekap", "📊 Monitoring", "🔐 Reset Password"])
        with tab1:
            st.subheader("Update Master Data")
            f_adm = st.file_uploader("Upload Excel", type=["xlsx"])
            if f_adm and st.button("🚀 Publish Master"): confirm_admin_publish(f_adm)
            
            st.divider()
            st.subheader("📥 Penarikan Data")
            m_df, m_ver = get_master_info()
            @st.cache_data(ttl=60)
def get_report_status(m_ver, df_master):
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
                    # Ambil kode toko dari nama file (misal: Hasil_1001_v1...)
                    code = r['public_id'].split('Hasil_')[-1].split('_v')[0]
                    submitted_codes.add(code)
            next_cursor = res.get('next_cursor')
            if not next_cursor: break
            
        # 2. Ambil daftar unik seluruh toko dari kolom pertama Master Excel
        all_stores = set(df_master[df_master.columns[0]].astype(str).unique())
        
        # 3. Cari selisihnya (Toko yang ada di master tapi belum ada di Cloudinary)
        not_submitted = sorted(list(all_stores - submitted_codes))
        
        return list(submitted_codes), not_submitted
    except:
        return [], []
            if m_df is not None:
                # --- LOGIKA FETCH SEMUA TOKO DENGAN PAGINATION (FIX LIMIT 10) ---
                with st.spinner("Mengecek seluruh toko di Cloudinary..."):
                    all_submitted_files = []
                    next_cursor = None
                    while True:
                        # max_results diset 500 (maksimal Cloudinary)
                        res = cloudinary.api.resources(
                            resource_type="raw", type="upload", 
                            prefix="so_rawan_hilang/hasil/Hasil_", 
                            max_results=500, next_cursor=next_cursor
                        )
                        # Filter hanya versi yang cocok dengan Master Aktif
                        batch = [r for r in res.get('resources', []) if f"_v{m_ver}" in r['public_id']]
                        all_submitted_files.extend(batch)
                        
                        next_cursor = res.get('next_cursor')
                        if not next_cursor: break
                    
                    toko_count = len(all_submitted_files)
                
                if toko_count > 0:
                    st.info(f"📊 **Informasi:** Terdapat **{toko_count}** toko yang sudah mengirimkan laporan (Versi: {m_ver}).")
                else:
                    st.warning("ℹ️ Belum ada toko yang mengirim laporan untuk versi ini.")

                if st.button("🔄 Gabung Data Seluruh Toko", use_container_width=True):
                    with st.spinner(f"Sedang menggabungkan {toko_count} toko..."):
                        for r in all_submitted_files:
                            s_df = pd.read_excel(r['secure_url'])
                            s_df.columns = [str(c).strip() for c in s_df.columns]
                            for _, row in s_df.iterrows():
                                # Join menggunakan Prdcd (kolom ke-3) dan Toko (kolom pertama)
                                mask = (m_df[m_df.columns[2]] == row[s_df.columns[2]]) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                                if mask.any(): m_df.loc[mask, s_df.columns] = row.values
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                        st.download_button(f"📥 Download Rekap ({toko_count} Toko)", buf.getvalue(), f"Rekap_{get_indonesia_date()}.xlsx", use_container_width=True)

        with tab2:
            logs = load_json_db(LOG_DB_PATH)
            if logs:
                flat = [{"NIK": k, "Tanggal": t, "Hits": h} for k, d in logs.items() for t, h in d.items()]
                st.dataframe(pd.DataFrame(flat).sort_values(by="Tanggal", ascending=False), use_container_width=True, hide_index=True)
        with tab3:
            t_nik = st.text_input("NIK:"); n_pw = st.text_input("Pass Baru:", type="password")
            if st.button("Simpan"):
                db = load_json_db(USER_DB_PATH)
                if t_nik in db: db[t_nik] = n_pw; save_json_db(USER_DB_PATH, db); st.success("✅ Berhasil!")
                else: st.error("NIK tdk ada.")

# ==========================================
#              HALAMAN USER
# ==========================================
elif st.session_state.page == "USER_INPUT":
    if not st.session_state.logged_in: st.session_state.page = "HOME"; st.rerun()
    
    hc, oc = st.columns([5, 1])
    hc.header(f"📋 Menu Input ({st.session_state.user_nik})")
    if oc.button("🚪 Logout"): 
        st.session_state.logged_in, st.session_state.user_search_active = False, False
        st.session_state.page = "HOME"; st.rerun()

    # --- Bagian Input & Validasi ---
    t_col, b_col = st.columns([3, 1])
    with t_col: 
        t_id = st.text_input("📍 Kode Toko:", max_chars=4, placeholder="Contoh: TQ86").upper()
    
    with b_col:
        st.write("##") # Spacer agar tombol sejajar dengan input
        btn_cari = st.button("🔍 Cari Data", use_container_width=True)

    # --- Logika Validasi ---
    if t_id:
        if len(t_id) < 4:
            st.error(f"⚠️ Kode Toko harus **4 digit**! (Anda baru mengetik {len(t_id)})")
            st.session_state.user_search_active = False
        elif btn_cari:
            st.session_state.active_toko, st.session_state.user_search_active = t_id, True

    st.divider()

    # --- Bagian Menampilkan Editor ---
    if st.session_state.user_search_active:
        df_m, v_now = get_master_info()
        if df_m is not None:
            # GUNAKAN PERBANDINGAN == (EXACT MATCH)
            # Kolom 0 diasumsikan berisi Kode Toko
            m_filt = df_m[df_m[df_m.columns[0]].astype(str) == st.session_state.active_toko].copy()
            
            if not m_filt.empty:
                df_u = load_user_save(st.session_state.active_toko, v_now)
                data_show = df_u if df_u is not None else m_filt
                
                st.subheader(f"🏠 Toko: {st.session_state.active_toko}")
                
                # Deteksi Nama Kolom
                c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')
                
                show_user_editor(data_show, c_sales, c_fisik, c_stok, c_selisih, st.session_state.active_toko, v_now)
            else:
                st.error(f"❌ Toko **{st.session_state.active_toko}** tidak ditemukan dalam Master Utama!")
                st.session_state.user_search_active = False





