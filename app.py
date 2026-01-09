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

def load_excel_from_cloud(public_id):
    try:
        url = f"https://res.cloudinary.com/{st.secrets['cloud_name']}/raw/upload/v{int(time.time())}/{public_id}"
        resp = requests.get(url, timeout=15)
        if resp.status_code == 200:
            df = pd.read_excel(io.BytesIO(resp.content))
            df.columns = [str(c).strip() for c in df.columns]
            return df
    except:
        return None
    return None

def find_join_key(df):
    possible_keys = ['prdcd', 'plu', 'gab', 'prd cd']
    for col in df.columns:
        if col.lower() in possible_keys: return col
    return df.columns[2]

# --- 3. DIALOG KONFIRMASI ---

@st.dialog("Konfirmasi Simpan")
def confirm_submit_dialog(data_toko, toko_code, date_str):
    st.warning(f"⚠️ Simpan data Toko {toko_code} untuk tanggal {date_str}?")
    if st.button("Ya, Simpan Sekarang"):
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            data_toko.to_excel(writer, index=False)
        buffer.seek(0)
        try:
            p_id = f"so_rawan_hilang/{date_str}_Hasil_{toko_code}.xlsx"
            cloudinary.uploader.upload(buffer, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
            st.success("✅ Berhasil Tersimpan!")
            time.sleep(1.5)
            st.rerun()
        except Exception as e:
            st.error(f"Gagal simpan: {e}")

# --- 4. SISTEM MENU & STATE ---
if 'page' not in st.session_state: st.session_state.page = "HOME"
if 'admin_auth' not in st.session_state: st.session_state.admin_auth = False
if 'search_active' not in st.session_state: st.session_state.search_active = False

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
        tab1, tab2 = st.tabs(["📤 Upload & Download", "🗑️ Hapus Data"])
        
        with tab1:
            st.subheader("Upload Master Baru")
            u_date = st.date_input("Berlaku untuk Tanggal:", datetime.now())
            d_str = u_date.strftime("%Y-%m-%d")
            f_admin = st.file_uploader("Pilih Excel", type=["xlsx"])
            
            if f_admin and st.button("🚀 Publish Master & Reset Semua Input Toko"):
                with st.spinner("Sedang memproses reset harian..."):
                    # Hapus history input lama agar tidak bentrok dengan master baru
                    prefix_del = f"so_rawan_hilang/{d_str}_Hasil_"
                    try: cloudinary.api.delete_resources_by_prefix(prefix_del, resource_type="raw")
                    except: pass
                    
                    p_id = f"so_rawan_hilang/{d_str}_Master.xlsx"
                    cloudinary.uploader.upload(f_admin, resource_type="raw", public_id=p_id, overwrite=True, invalidate=True)
                    st.success(f"✅ Master {d_str} Aktif! Seluruh inputan toko telah di-reset.")

            st.divider()
            st.subheader("Tarik Rekap Gabungan")
            r_date = st.date_input("Tarik Rekap Tanggal:", datetime.now(), key="r_date")
            r_str = r_date.strftime("%Y-%m-%d")
            if st.button("🔄 Gabungkan Data"):
                m_df = load_excel_from_cloud(f"so_rawan_hilang/{r_str}_Master.xlsx")
                if m_df is not None:
                    res = cloudinary.api.resources(resource_type="raw", type="upload", prefix=f"so_rawan_hilang/{r_str}_Hasil_")
                    count = 0
                    for r in res.get('resources', []):
                        s_df = pd.read_excel(r['secure_url'])
                        s_df.columns = [str(c).strip() for c in s_df.columns]
                        m_key, s_key = find_join_key(m_df), find_join_key(s_df)
                        for _, row in s_df.iterrows():
                            mask = (m_df[m_key].astype(str) == str(row[s_key])) & (m_df[m_df.columns[0]].astype(str) == str(row[s_df.columns[0]]))
                            if mask.any():
                                cols = [c for c in s_df.columns if c in m_df.columns]
                                m_df.loc[mask, cols] = row[cols].values
                        count += 1
                    buf = io.BytesIO()
                    with pd.ExcelWriter(buf) as w: m_df.to_excel(w, index=False)
                    st.download_button(f"📥 Download Rekap {r_str} ({count} Toko)", buf.getvalue(), f"so_rawan_hilang_{r_str}.xlsx")
                else: st.error("Master tidak ditemukan.")

        with tab2:
            st.subheader("Manajemen Penghapusan")
            if st.button("🔍 Scan Data"):
                files = cloudinary.api.resources(resource_type="raw", type="upload", prefix="so_rawan_hilang/")
                all_ids = [f['public_id'] for f in files.get('resources', [])]
                dates = sorted(list(set([p.split('/')[1].split('_')[0] for p in all_ids if '_' in p.split('/')[1]])))
                if not dates: st.info("Kosong.")
                else:
                    for d in dates:
                        c_n, c_b = st.columns([3, 1])
                        c_n.write(f"📅 **Data Tanggal: {d}**")
                        if c_b.button("🗑️ Hapus", key=f"del_{d}"):
                            cloudinary.api.delete_resources_by_prefix(f"so_rawan_hilang/{d}_", resource_type="raw", invalidate=True)
                            st.rerun()

# ==========================================
#              HALAMAN USER (TOKO)
# ==========================================
elif st.session_state.page == "USER":
    if st.button("🚪 Logout"):
        st.session_state.page = "HOME"; st.session_state.search_active = False; st.session_state.preview_calc = None; st.rerun()

    st.header("📋 Input Data Toko")
    col_d, col_t, col_b = st.columns([2, 2, 1])
    with col_d: u_date = st.date_input("Pilih Tanggal:", datetime.now())
    with col_t: t_id = st.text_input("📍 Kode Toko:", max_chars=4).upper()
    with col_b:
        st.write("##")
        if st.button("🔍 Cari Data", use_container_width=True):
            if t_id:
                st.session_state.search_active = True
                st.session_state.active_toko = t_id
                st.session_state.active_date = u_date.strftime("%Y-%m-%d")
                st.session_state.preview_calc = None # Reset preview saat cari baru
            else: st.error("Isi kode toko!")

    if st.session_state.search_active:
        d_str = st.session_state.active_date
        t_id = st.session_state.active_toko
        
        df_master = load_excel_from_cloud(f"so_rawan_hilang/{d_str}_Master.xlsx")
        
        if df_master is not None:
            u_id = f"so_rawan_hilang/{d_str}_Hasil_{t_id}.xlsx"
            df_user = load_excel_from_cloud(u_id)
            
            # Filter master untuk toko ini
            master_filtered = df_master[df_master[df_master.columns[0]].astype(str).str.contains(t_id)].copy()
            
            if df_user is not None:
                data_to_edit = df_user
            else:
                # LOGIKA FIX: Reset kolom input dan kalkulasi agar tidak terbawa dari Master Excel
                data_to_edit = master_filtered
                # Cari nama kolom secara fleksibel
                c_sales_init = next((c for c in data_to_edit.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik_init = next((c for c in data_to_edit.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih_init = next((c for c in data_to_edit.columns if 'selisih' in c.lower()), 'Selisih')
                
                # Paksa kolom input menjadi kosong/nol saat pertama kali load dari master
                data_to_edit[c_sales_init] = 0
                data_to_edit[c_fisik_init] = 0
                data_to_edit[c_selisih_init] = 0

            if not data_to_edit.empty:
                st.subheader(f"🏠 Toko: {t_id} | 📅 {d_str}")
                
                # Identifikasi Kolom (Dinamis)
                c_stok = next((c for c in data_to_edit.columns if 'stok' in c.lower()), 'Stok H-1')
                c_sales = next((c for c in data_to_edit.columns if 'sales' in c.lower()), 'Query Sales')
                c_fisik = next((c for c in data_to_edit.columns if 'fisik' in c.lower()), 'Jml Fisik')
                c_selisih = next((c for c in data_to_edit.columns if 'selisih' in c.lower()), 'Selisih')

                # TAMPILAN EDITOR
                edited_df = st.data_editor(
                    data_to_edit,
                    disabled=[c for c in data_to_edit.columns if c not in [c_sales, c_fisik]],
                    hide_index=True, use_container_width=True, key=f"editor_{d_str}_{t_id}"
                )

                c1, c2 = st.columns(2)
                with c1:
                    if st.button("🔄 Update Selisih"):
                        vs = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        vf = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        vh = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (vs + vf) - vh
                        st.session_state.preview_calc = edited_df
                        st.success("Tabel hasil perhitungan muncul di bawah!")

                with c2:
                    if st.button("🚀 Simpan Laporan", type="primary"):
                        # Hitung ulang sekali lagi sebelum simpan untuk akurasi
                        vs = pd.to_numeric(edited_df[c_sales], errors='coerce').fillna(0)
                        vf = pd.to_numeric(edited_df[c_fisik], errors='coerce').fillna(0)
                        vh = pd.to_numeric(edited_df[c_stok], errors='coerce').fillna(0)
                        edited_df[c_selisih] = (vs + vf) - vh
                        confirm_submit_dialog(edited_df, t_id, d_str)

                # Tabel Review Hasil
                if st.session_state.get('preview_calc') is not None:
                    st.divider()
                    st.write("### 📝 Preview Hasil Sebelum Submit:")
                    st.dataframe(st.session_state.preview_calc, use_container_width=True, hide_index=True)
            else: st.error("Data toko tidak ketemu.")
        else: st.error(f"Master untuk tanggal {d_str} belum di-upload.")
