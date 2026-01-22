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
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{path}"
        resp = requests.get(url, timeout=10)
        return resp.json() if resp.status_code == 200 else {}
    except:
        return {}

def save_json_db(path, db_dict):
    try:
        json_data = json.dumps(db_dict)
        cloudinary.uploader.upload(
            io.BytesIO(json_data.encode()), 
            resource_type="raw", public_id=path, 
            overwrite=True, invalidate=True
        )
        return True
    except:
        return False

def record_login_hit(nik):
    db_logs = load_json_db(LOG_DB_PATH)
    today = get_now_wita().strftime('%Y-%m-%d')
    if nik not in db_logs:
        db_logs[nik] = {}
    current_hits = db_logs[nik].get(today, 0)
    db_logs[nik][today] = current_hits + 1
    save_json_db(LOG_DB_PATH, db_logs)

# --- 3. FUNGSI EXCEL ---
def get_indonesia_date():
    bulan = ["Januari", "Februari", "Maret", "April", "Mei", "Juni", 
             "Juli", "Agustus", "September", "Oktober", "November", "Desember"]
    now = get_now_wita()
    return f"{now.day}_{bulan[now.month-1]}_{now.year}"

@st.cache_data(ttl=30)
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

# --- 4. DIALOGS ---
@st.dialog("⚠️ Konfirmasi Publish Master")
def confirm_admin_publish(file_obj):
    st.warning("Anda akan Publish Master baru & MENGHAPUS seluruh inputan toko harian.")
    if st.button("IYA, Publish & Reset Sekarang", type="primary", use_container_width=True):
        status_ok = False
        try:
            cloudinary.api.delete_resources_by_prefix("so_rawan_hilang/hasil/", resource_type="raw")
            cloudinary.uploader.upload(file_obj, resource_type="raw", public_id="so_rawan_hilang/master_utama.xlsx", overwrite=True, invalidate=True)
            status_ok = True
        except Exception as e:
            st.error(f"Gagal: {e}")
        if status_ok:
            st.success("✅ Master Terbit!"); time.sleep(2); st.rerun()

@st.dialog("Konfirmasi Simpan")
def confirm_user_submit(data_toko, toko_code, v_id):
    st.info(f"Menyimpan data Toko {toko_code}...")
    if st.button("Ya, Simpan ke Cloud", use_container_width=True):
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine='openpyxl') as w: 
            data_toko.to_excel(w, index=False)
        status_ok = False
        try:
            p_id = f"so_rawan_hilang/hasil/Hasil_{toko_code}_v{v_id}.xlsx"
            cloudinary.uploader.upload(buf.getvalue(), resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            status_ok = True
        except Exception as e:
            st.error(f"Gagal menyimpan ke Cloud: {e}")
        if status_ok:
            st.success("✅ Berhasil Tersimpan!"); time.sleep(1.5); st.rerun()

# --- 5. FRAGMENT EDITOR ---
@st.fragment
def show_user_editor(df_in, c_sales, c_fisik, c_stok, c_selisih, toko_id, v_now):
    df_in[c_sales] = pd.to_numeric(df_in[c_sales], errors='coerce')
    df_in[c_fisik] = pd.to_numeric(df_in[c_fisik], errors='coerce')
    edited = st.data_editor(
        df_in,
        column_config={
            c_sales: st.column_config.NumberColumn(f"📥 {c_sales}", format="%d", min_value=0),
            c_fisik: st.column_config.NumberColumn(f"📥 {c_fisik}", format="%d", min_value=0),
            c_selisih: st.column_config.NumberColumn(c_selisih, format="%d"),
            c_stok: st.column_config.NumberColumn(c_stok, format="%d"),
        },
        disabled=[c for c in df_in.columns if c not in [c_sales, c_fisik]],
        hide_index=True, use_container_width=True, key=f"ed_{toko_id}"
    )
    if st.button("🚀 Simpan Laporan", type="primary", use_container_width=True):
        if edited[c_sales].isnull().any() or edited[c_fisik].isnull().any():
            st.error("⚠️ Ada kolom yang belum diisi (blank)!")
        else:
            vs = edited[c_sales].fillna(0).astype(int)
            vf = edited[c_fisik].fillna(0).astype(int)
            vh = edited[c_stok].fillna(0).astype(int)
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
    st.divider()
    col1, col2, col3 = st.columns(3)
    if col1.button("🔑 LOGIN KARYAWAN", use_container_width=True, type="primary"):
        st.session_state.page = "LOGIN"; st.rerun()
    if col2.button("📝 DAFTAR AKUN", use_container_width=True):
        st.session_state.page = "REGISTER"; st.rerun()
    if col3.button("🛡️ ADMIN PANEL", use_container_width=True):
        st.session_state.page = "ADMIN"; st.rerun()

# ==========================================
#              HALAMAN DAFTAR
# ==========================================
elif st.session_state.page == "REGISTER":
    st.header("📝 Daftar Akun Baru")
    new_nik = st.text_input("NIK (10 Digit):", max_chars=10)
    new_pw = st.text_input("Buat Password:", type="password")
    st.info("ℹ️ Password minimal 4 digit")
    if st.button("Daftar Sekarang", use_container_width=True):
        if len(new_nik) != 10 or not new_nik.isdigit(): st.error("NIK harus 10 digit!")
        elif len(new_pw) < 4: st.error("Password minimal 4 karakter!")
        else:
            db = load_json_db(USER_DB_PATH)
            if new_nik in db: st.error("NIK sudah terdaftar!")
            else:
                db[new_nik] = new_pw
                if save_json_db(USER_DB_PATH, db):
                    st.success("✅ Terdaftar!"); time.sleep(1); st.session_state.page = "LOGIN"; st.rerun()
    if st.button("⬅️ Kembali"): st.session_state.page = "HOME"; st.rerun()

# ==========================================
#              HALAMAN LOGIN
# ==========================================
elif st.session_state.page == "LOGIN":
    st.header("🔑 Login Karyawan")
    log_nik = st.text_input("Masukkan NIK:", max_chars=10)
    log_pw = st.text_input("Masukkan Password:", type="password")
    if st.button("Masuk Sekarang", use_container_width=True, type="primary"):
        db = load_json_db(USER_DB_PATH)
        if log_nik in db and db[log_nik] == log_pw:
            record_login_hit(log_nik)
            st.session_state.logged_in, st.session_state.user_nik, st.session_state.page = True, log_nik, "USER_INPUT"
            st.rerun()
        else: st.error("NIK atau Password salah!")
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
            if m_df is not None:
                with st.spinner("Mengecek jumlah toko..."):
                    # FIX: Menambahkan max_results=500 agar bisa menarik lebih dari 10 data
                    res = cloudinary.api.resources(
                        resource_type="raw", 
                        type="upload", 
                        prefix="so_rawan_hilang/hasil/Hasil_",
                        max_results=500 
                    )
                    submitted_files = [r for r in res.get('resources', []) if f"_v{m_ver}" in r['public_id']]
                    toko_count = len(submitted_files)
                
                if toko_count > 0:
                    st.info(f"📊 **Informasi:** Terdapat **{toko_count}** toko yang sudah mengirimkan laporan.")
                else:
                    st.warning("ℹ️ Belum ada toko yang mengirimkan laporan.")

                if st.button("🔄 Gabung Data Seluruh Toko", use_container_width=True):
                    with st.spinner("Sedang menggabungkan data..."):
                        for r in submitted_files:
                            s_df = pd.read_excel(r['secure_url'])
                            s_df.columns = [str(c).strip() for c in s_df.columns]
                            for _, row in s_df.iterrows():
                                mask = (m_df[m_df.columns[2]] == row[s_df.columns[2]]) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                                if mask.any(): m_df.loc[mask, s_df.columns] = row.values
                        buf = io.BytesIO()
                        with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                        st.session_state.final_excel = buf.getvalue()
                        st.session_state.final_count = toko_count
                if 'final_excel' in st.session_state:
                    st.download_button(label=f"📥 Download Hasil Rekap ({st.session_state.final_count} Toko)", 
                                       data=st.session_state.final_excel, file_name=f"Rekap_{get_indonesia_date()}.xlsx", use_container_width=True)
            else: st.info("💡 Belum ada Master Data.")

        with tab2:
            st.subheader("📊 Monitoring Aktivitas")
            logs = load_json_db(LOG_DB_PATH)
            if logs:
                flat_data = []
                for nik, dates in logs.items():
                    for tgl, hit in dates.items():
                        flat_data.append({"NIK Karyawan": nik, "Tanggal Akses": tgl, "Jumlah Log In": hit})
                st.dataframe(pd.DataFrame(flat_data).sort_values(by="Tanggal Akses", ascending=False), use_container_width=True, hide_index=True)
        
        with tab3:
            st.subheader("🔐 Reset / Ubah Password User")
            target_nik = st.text_input("Masukkan NIK karyawan:", key="reset_nik")
            new_custom_pw = st.text_input("Masukkan Password Baru:", type="password", key="reset_pw")
            if st.button("Simpan Password Baru", use_container_width=True, type="primary"):
                if not target_nik or len(new_custom_pw) < 4: st.error("Lengkapi data!")
                else:
                    db = load_json_db(USER_DB_PATH)
                    if target_nik in db:
                        db[target_nik] = new_custom_pw
                        if save_json_db(USER_DB_PATH, db): st.success(f"✅ Berhasil diubah!")
                    else: st.error("NIK tidak ditemukan!")

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER_INPUT":
    if not st.session_state.logged_in: st.session_state.page = "HOME"; st.rerun()
    hc, oc = st.columns([5, 1])
    hc.header(f"📋 Menu Input ({st.session_state.user_nik})")
    if oc.button("🚪 Logout"): st.session_state.logged_in, st.session_state.user_search_active = False, False; st.session_state.page = "HOME"; st.rerun()

    t_col, b_col = st.columns([3, 1])
    with t_col: t_id = st.text_input("📍 Kode Toko:", max_chars=4).upper()
    with b_col:
        st.write("##")
        if st.button("🔍 Cari Data", use_container_width=True):
            if t_id: st.session_state.active_toko, st.session_state.user_search_active = t_id, True
            else: st.error("Isi Kode!")

    if st.session_state.user_search_active:
        df_m, v_now = get_master_info()
        if df_m is not None:
            df_u = load_user_save(st.session_state.active_toko, v_now)
            m_filt = df_m[df_m[df_m.columns[0]].astype(str).str.contains(st.session_state.active_toko)].copy()
            data_show = df_u if df_u is not None else m_filt
            if not data_show.empty:
                st.subheader(f"🏠 Toko: {st.session_state.active_toko}")
                c_stok = next((c for c in data_show.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_show.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_show.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_show.columns if 'selisih' in c.lower()), 'Selisih')
                data_show[c_sales] = pd.to_numeric(data_show[c_sales], errors='coerce')
                data_show[c_fisik] = pd.to_numeric(data_show[c_fisik], errors='coerce')
                show_user_editor(data_show, c_sales, c_fisik, c_stok, c_selisih, st.session_state.active_toko, v_now)
            else: st.error("Toko tidak ditemukan.")
