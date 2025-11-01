import streamlit as st
import pandas as pd
import json
import os
import io
import requests
import shutil
import re
import hashlib
from datetime import datetime, timedelta
from base64 import b64decode

# محاولة استيراد PyGithub (لرفع التعديلات)
try:
    from github import Github
    GITHUB_AVAILABLE = True
except Exception:
    GITHUB_AVAILABLE = False

# ===============================
# إعدادات عامة
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=10)
MAX_ACTIVE_USERS = 2

REPO_NAME = "mahmedabdallh123/cmms"
BRANCH = "main"
FILE_PATH = "Machine_Service_Lookup.xlsx"
LOCAL_FILE = "Machine_Service_Lookup.xlsx"
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx"

# ===============================
# 🆕 نظام اكتشاف الأعمدة الديناميكي
# ===============================
def detect_columns(df):
    """اكتشاف أسماء الأعمدة المختلفة بناءً على الأنماط الشائعة"""
    detected = {}
    all_cols = [str(col).strip().lower() for col in df.columns]
    
    # أنماط البحث لكل نوع عمود
    patterns = {
        'min_tones': ['min_tones', 'min tones', 'min', 'min tone', 'start', 'from'],
        'max_tones': ['max_tones', 'max tones', 'max', 'max tone', 'end', 'to'],
        'tones': ['tones', 'tone', 'current tones', 'current'],
        'date': ['date', 'time', 'timestamp', 'تاريخ'],
        'service': ['service', 'service needed', 'needed service', 'service_needed'],
        'event': ['other', 'notes', 'remarks', 'ملاحظات'],
        'servised_by': ['servised by', 'serviced by', 'technician', 'فني'],
        'card': ['card', 'machine', 'machine_no', 'machine id', 'card_no']
    }
    
    for col_type, patterns_list in patterns.items():
        for pattern in patterns_list:
            for i, col_name in enumerate(all_cols):
                if pattern in col_name:
                    detected[col_type] = df.columns[i]  # العمود الأصلي مع الحالة
                    break
            if col_type in detected:
                break
    
    return detected

# ===============================
# 🔁 نظام البصمة المحسن
# ===============================
def get_enhanced_fingerprint():
    """بصمة محسنة تعتمد على وقت التعديل والمحتوى"""
    if not os.path.exists(LOCAL_FILE):
        return f"initial_{datetime.now().timestamp()}"
    
    try:
        # استخدام وقت التعديل وحجم الملف
        stat = os.stat(LOCAL_FILE)
        file_info = f"{stat.st_mtime}_{stat.st_size}"
        
        # هاش للمحتوى (لزيادة الدقة)
        with open(LOCAL_FILE, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:12]
        
        return f"{file_info}_{file_hash}"
    except Exception:
        return str(datetime.now().timestamp())

def update_fingerprint():
    """تحديث البصمة في حالة الجلسة"""
    st.session_state["file_fingerprint"] = get_enhanced_fingerprint()
    st.session_state["last_update_time"] = datetime.now().isoformat()

def get_current_fingerprint():
    """الحصول على البصمة الحالية أو إنشاء واحدة جديدة"""
    if "file_fingerprint" not in st.session_state:
        st.session_state["file_fingerprint"] = get_enhanced_fingerprint()
    return st.session_state["file_fingerprint"]

# ===============================
# 🔁 دوال مساعدة (بدون تغيير)
# ===============================
def safe_rerun():
    try:
        if hasattr(st, "rerun"):
            st.rerun()
            return
    except Exception:
        pass
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
            return
    except Exception:
        pass
    try:
        st.stop()
    except Exception:
        return

def load_users():
    if not os.path.exists(USERS_FILE):
        default = {"admin": {"password": "admin"}}
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(default, f, indent=4, ensure_ascii=False)
        return default
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        st.error(f"❌ خطأ في ملف users.json: {e}")
        st.stop()

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def load_state():
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def cleanup_sessions(state):
    now = datetime.now()
    changed = False
    for user, info in list(state.items()):
        if info.get("active") and "login_time" in info:
            try:
                login_time = datetime.fromisoformat(info["login_time"])
                if now - login_time > SESSION_DURATION:
                    info["active"] = False
                    info.pop("login_time", None)
                    changed = True
            except Exception:
                info["active"] = False
                changed = True
    if changed:
        save_state(state)
    return state

def remaining_time(state, username):
    if not username or username not in state:
        return None
    info = state.get(username)
    if not info or not info.get("active"):
        return None
    try:
        lt = datetime.fromisoformat(info["login_time"])
        remaining = SESSION_DURATION - (datetime.now() - lt)
        if remaining.total_seconds() <= 0:
            return None
        return remaining
    except Exception:
        return None

def logout_action():
    state = load_state()
    username = st.session_state.get("username")
    if username and username in state:
        state[username]["active"] = False
        state[username].pop("login_time", None)
        save_state(state)
    try:
        keys = list(st.session_state.keys())
        for k in keys:
            try:
                st.session_state.pop(k, None)
            except Exception:
                pass
    except Exception:
        pass
    safe_rerun()

def login_ui():
    users = load_users()
    state = cleanup_sessions(load_state())
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None

    st.title("🔐 تسجيل الدخول - Bail Yarn (CMMS)")

    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            if username_input in users and users[username_input]["password"] == password:
                if username_input == "admin":
                    pass
                elif username_input in active_users:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS:
                    st.error("🚫 الحد الأقصى للمستخدمين المتصلين حالياً.")
                    return False
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.success(f"✅ تم تسجيل الدخول: {username_input}")
                safe_rerun()
                return True
            else:
                st.error("❌ كلمة المرور غير صحيحة.")
        return False
    else:
        username = st.session_state.username
        st.success(f"✅ مسجل الدخول كـ: {username}")
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.info(f"⏳ الوقت المتبقي: {mins:02d}:{secs:02d}")
        else:
            st.warning("⏰ انتهت الجلسة، سيتم تسجيل الخروج.")
            logout_action()
            return False
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
            return False
        return True

# ===============================
# 🔄 طرق جلب الملف من GitHub
# ===============================
def fetch_from_github_requests():
    """تحميل بإستخدام رابط RAW (requests)"""
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=20)
        response.raise_for_status()
        with open(LOCAL_FILE, "wb") as f:
            shutil.copyfileobj(response.raw, f)
        # تحديث البصمة ومسح الكاش
        st.cache_data.clear()
        update_fingerprint()
        st.success("✅ تم تحديث البيانات من GitHub بنجاح وتم تحديث البصمة ومسح الكاش.")
        safe_rerun()
    except Exception as e:
        st.error(f"⚠ فشل التحديث من GitHub (requests): {e}")

def fetch_from_github_api():
    """تحميل عبر GitHub API"""
    if not GITHUB_AVAILABLE:
        st.warning("PyGithub غير متوفر، سيتم المحاولة عبر رابط RAW.")
        fetch_from_github_requests()
        return
    try:
        token = st.secrets.get("github", {}).get("token", None)
        if not token:
            st.warning("توكين GitHub غير موجود في secrets، سيتم التحميل عبر رابط RAW.")
            fetch_from_github_requests()
            return
        g = Github(token)
        repo = g.get_repo(REPO_NAME)
        file_content = repo.get_contents(FILE_PATH, ref=BRANCH)
        content = b64decode(file_content.content)
        with open(LOCAL_FILE, "wb") as f:
            f.write(content)
        # تحديث البصمة ومسح الكاش
        st.cache_data.clear()
        update_fingerprint()
        st.success("✅ تم تحميل الملف من GitHub API بنجاح وتم مسح الكاش.")
        safe_rerun()
    except Exception as e:
        st.error(f"⚠ فشل تحميل الملف من GitHub API: {e}")

# ===============================
# 📂 تحميل الشيتات (مع البصمة)
# ===============================
@st.cache_data(show_spinner=False)
def load_all_sheets(_fingerprint):
    if not os.path.exists(LOCAL_FILE):
        return None
    sheets = pd.read_excel(LOCAL_FILE, sheet_name=None)
    for name, df in sheets.items():
        df.columns = df.columns.str.strip()
    return sheets

@st.cache_data(show_spinner=False)
def load_sheets_for_edit(_fingerprint):
    if not os.path.exists(LOCAL_FILE):
        return None
    sheets = pd.read_excel(LOCAL_FILE, sheet_name=None, dtype=object)
    for name, df in sheets.items():
        df.columns = df.columns.str.strip()
    return sheets

# ===============================
# 🔁 حفظ محلي + رفع على GitHub
# ===============================
def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
    try:
        with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
            for name, sh in sheets_dict.items():
                try:
                    sh.to_excel(writer, sheet_name=name, index=False)
                except Exception:
                    sh.astype(object).to_excel(writer, sheet_name=name, index=False)
    except Exception as e:
        st.error(f"⚠ خطأ أثناء الحفظ المحلي: {e}")
        return load_sheets_for_edit(get_current_fingerprint())

    # تحديث البصمة ومسح الكاش
    st.cache_data.clear()
    update_fingerprint()

    token = st.secrets.get("github", {}).get("token", None)
    if not token:
        st.warning("🔒 GitHub token not found in Streamlit secrets. لن يتم الرفع إلى الريبو.")
        return load_sheets_for_edit(get_current_fingerprint())

    if not GITHUB_AVAILABLE:
        st.error("PyGithub غير مثبت على بيئتك. تثبيته مطلوب للرفع التلقائي.")
        return load_sheets_for_edit(get_current_fingerprint())

    try:
        g = Github(token)
        repo = g.get_repo(REPO_NAME)
        with open(LOCAL_FILE, "rb") as f:
            content = f.read()

        try:
            contents = repo.get_contents(FILE_PATH, ref=BRANCH)
            repo.update_file(path=FILE_PATH, message=commit_message, content=content, sha=contents.sha, branch=BRANCH)
        except Exception:
            try:
                repo.create_file(path=FILE_PATH, message=commit_message, content=content, branch=BRANCH)
            except Exception as e2:
                st.error(f"⚠ فشل رفع الملف إلى GitHub: {e2}")
                return load_sheets_for_edit(get_current_fingerprint())

        st.success("✅ تم الحفظ والرفع على GitHub بنجاح وتم مسح الكاش.")
        safe_rerun()
        return load_sheets_for_edit(get_current_fingerprint())
    except Exception as e:
        st.error(f"⚠ فشل الاتصال بـ GitHub: {e}")
        return load_sheets_for_edit(get_current_fingerprint())

# ===============================
# 🧰 دوال مساعدة للمعالجة والنصوص
# ===============================
def normalize_name(s):
    if s is None: return ""
    s = str(s).replace("\n", "+")
    s = re.sub(r"[^0-9a-zA-Z\u0600-\u06FF\+\s_/.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def split_needed_services(needed_service_str):
    if not isinstance(needed_service_str, str) or needed_service_str.strip() == "":
        return []
    parts = re.split(r"\+|,|\n|;", needed_service_str)
    return [p.strip() for p in parts if p.strip() != ""]

def highlight_cell(val, col_name):
    color_map = {
        "Service Needed": "background-color: #fff3cd; color:#856404; font-weight:bold;",
        "Done Services": "background-color: #d4edda; color:#155724; font-weight:bold;",
        "Not Done Services": "background-color: #f8d7da; color:#721c24; font-weight:bold;",
        "Date": "background-color: #e7f1ff; color:#004085; font-weight:bold;",
        "Last Tones": "background-color: #f0f0f0; color:#333; font-weight:bold;",
        "Event": "background-color: #e2f0d9; color:#2e6f32; font-weight:bold;",
        "Servised by": "background-color: #fdebd0; color:#7d6608; font-weight:bold;",
        "Min_Tons": "background-color: #ebf5fb; color:#154360; font-weight:bold;",
        "Max_Tons": "background-color: #f9ebea; color:#641e16; font-weight:bold;",
    }
    return color_map.get(col_name, "")

def style_table(row):
    return [highlight_cell(row[col], col) for col in row.index]

# ===============================
# 🖥 دالة فحص الماكينة المحسنة
# ===============================
def check_machine_status_enhanced(card_num, current_tons, all_sheets):
    """نسخة محسنة من دالة فحص الماكينة مع اكتشاف الأعمدة الديناميكي"""
    if not all_sheets or "ServicePlan" not in all_sheets:
        st.error("❌ الملف لا يحتوي على شيت ServicePlan.")
        return
    
    service_plan_df = all_sheets["ServicePlan"]
    card_sheet_name = f"Card{card_num}"
    
    if card_sheet_name not in all_sheets:
        st.warning(f"⚠ لا يوجد شيت باسم {card_sheet_name}")
        return
    
    card_df = all_sheets[card_sheet_name]
    
    # 🆕 اكتشاف الأعمدة تلقائياً
    service_plan_cols = detect_columns(service_plan_df)
    card_cols = detect_columns(card_df)
    
    # عرض الأعمدة المكتشفة للمستخدم
    with st.expander("🔍 الأعمدة المكتشفة", expanded=False):
        col1, col2 = st.columns(2)
        with col1:
            st.write("*ServicePlan:*")
            for col_type, col_name in service_plan_cols.items():
                st.write(f"- {col_type}: {col_name}")
        with col2:
            st.write(f"{card_sheet_name}:")
            for col_type, col_name in card_cols.items():
                st.write(f"- {col_type}: {col_name}")
    
    # التحقق من الأعمدة الضرورية
    if 'min_tones' not in service_plan_cols or 'max_tones' not in service_plan_cols:
        st.error("❌ لم يتم العثور على أعمدة Min_Tones و/أو Max_Tones في ServicePlan")
        st.info("الأعمدة المتاحة في ServicePlan:")
        st.write(list(service_plan_df.columns))
        return
    
    if 'min_tones' not in card_cols or 'max_tones' not in card_cols:
        st.error(f"❌ لم يتم العثور على أعمدة Min_Tones و/أو Max_Tones في {card_sheet_name}")
        st.info(f"الأعمدة المتاحة في {card_sheet_name}:")
        st.write(list(card_df.columns))
        return

    # نطاق العرض
    if "view_option" not in st.session_state:
        st.session_state.view_option = "الشريحة الحالية فقط"

    st.subheader("⚙ نطاق العرض")
    view_option = st.radio(
        "اختر نطاق العرض:",
        ("الشريحة الحالية فقط", "كل الشرائح الأقل", "كل الشرائح الأعلى", "نطاق مخصص", "كل الشرائح"),
        horizontal=True,
        key="view_option"
    )

    min_range = st.session_state.get("min_range", max(0, current_tons - 500))
    max_range = st.session_state.get("max_range", current_tons + 500)
    if view_option == "نطاق مخصص":
        col1, col2 = st.columns(2)
        with col1:
            min_range = st.number_input("من (طن):", min_value=0, step=100, value=min_range, key="min_range")
        with col2:
            max_range = st.number_input("إلى (طن):", min_value=min_range, step=100, value=max_range, key="max_range")

    # 🆕 استخدام الأعمدة المكتشفة بدلاً من الثابتة
    min_col = service_plan_cols['min_tones']
    max_col = service_plan_cols['max_tones']
    service_col = service_plan_cols.get('service', service_plan_df.columns[2] if len(service_plan_df.columns) > 2 else "Service")
    
    card_min_col = card_cols['min_tones']
    card_max_col = card_cols['max_tones']
    date_col = card_cols.get('date', None)
    tones_col = card_cols.get('tones', None)
    other_col = card_cols.get('other', None)
    servised_col = card_cols.get('servised_by', None)

    # اختيار الشرائح باستخدام الأعمدة المكتشفة
    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[
            (pd.to_numeric(service_plan_df[min_col], errors='coerce') <= current_tons) & 
            (pd.to_numeric(service_plan_df[max_col], errors='coerce') >= current_tons)
        ]
    elif view_option == "كل الشرائح الأقل":
        selected_slices = service_plan_df[
            pd.to_numeric(service_plan_df[max_col], errors='coerce') <= current_tons
        ]
    elif view_option == "كل الشرائح الأعلى":
        selected_slices = service_plan_df[
            pd.to_numeric(service_plan_df[min_col], errors='coerce') >= current_tons
        ]
    elif view_option == "نطاق مخصص":
        selected_slices = service_plan_df[
            (pd.to_numeric(service_plan_df[min_col], errors='coerce') >= min_range) & 
            (pd.to_numeric(service_plan_df[max_col], errors='coerce') <= max_range)
        ]
    else:
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة حسب النطاق المحدد.")
        return

    all_results = []
    for _, current_slice in selected_slices.iterrows():
        slice_min = pd.to_numeric(current_slice[min_col], errors='coerce')
        slice_max = pd.to_numeric(current_slice[max_col], errors='coerce')
        needed_service_raw = current_slice.get(service_col, "")
        needed_parts = split_needed_services(str(needed_service_raw))
        needed_norm = [normalize_name(p) for p in needed_parts]

        # البحث في كارد الماكينة باستخدام الأعمدة المكتشفة
        mask = (
            (pd.to_numeric(card_df[card_min_col], errors='coerce') <= slice_max) & 
            (pd.to_numeric(card_df[card_max_col], errors='coerce') >= slice_min)
        )
        matching_rows = card_df[mask]

        done_services_set = set()
        last_date = "-"
        last_tons = "-"
        last_other = "-"
        last_servised_by = "-"

        if not matching_rows.empty:
            # 🆕 تحديد الأعمدة التي تمثل الخدمات (ليست بيانات نظامية)
            ignore_cols = {
                card_min_col.lower(), card_max_col.lower(), 
                'card', 'machine', 'date', 'tones', 'Event', 'servised by', 'servised_by'
            }
            if date_col: ignore_cols.add(date_col.lower())
            if tones_col: ignore_cols.add(tones_col.lower())
            if event_col: ignore_cols.add(event_col.lower())
            if servised_col: ignore_cols.add(servised_col.lower())

            for _, r in matching_rows.iterrows():
                for col in card_df.columns:
                    col_lower = str(col).lower()
                    if col_lower not in ignore_cols:
                        val = str(r.get(col, "")).strip()
                        if val and val.lower() not in ["nan", "none", ""]:
                            done_services_set.add(col)

            # قراءة البيانات الأخرى باستخدام الأعمدة المكتشفة
            if date_col and date_col in card_df.columns:
                try:
                    cleaned_dates = card_df[date_col].astype(str).str.replace("\\", "/", regex=False)
                    dates = pd.to_datetime(cleaned_dates, errors="coerce", dayfirst=True)
                    if dates.notna().any():
                        idx = dates.idxmax()
                        last_date = dates.loc[idx].strftime("%d/%m/%Y")
                except Exception:
                    last_date = "-"

            if tones_col and tones_col in card_df.columns:
                tons_vals = pd.to_numeric(card_df[tones_col], errors="coerce")
                if tons_vals.notna().any():
                    last_tons = int(tons_vals.max())

            if other_col and other_col in card_df.columns:
                last_other = str(card_df[other_col].dropna().iloc[-1]) if card_df[other_col].notna().any() else "-"

            if servised_col and servised_col in card_df.columns:
                last_servised_by = str(card_df[servised_col].dropna().iloc[-1]) if card_df[servised_col].notna().any() else "-"

        done_services = sorted(list(done_services_set))
        done_norm = [normalize_name(c) for c in done_services]
        not_done = [orig for orig, n in zip(needed_parts, needed_norm) if n not in done_norm]

        all_results.append({
            "Min_Tons": slice_min,
            "Max_Tons": slice_max,
            "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
            "Done Services": ", ".join(done_services) if done_services else "-",
            "Not Done Services": ", ".join(not_done) if not_done else "-",
            "Date": date,
            "Last Tones": last_tons,
            "Event": event,
            "Servised by": last_servised_by
        })

    result_df = pd.DataFrame(all_results).dropna(how="all").reset_index(drop=True)

    st.markdown("### 📋 نتائج الفحص")
    st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)

    # تنزيل النتائج
    buffer = io.BytesIO()
    result_df.to_excel(buffer, index=False, engine="openpyxl")
    st.download_button(
        label="💾 حفظ النتائج كـ Excel",
        data=buffer.getvalue(),
        file_name=f"Service_Report_Card{card_num}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ===============================
# 🖥 الواجهة الرئيسية المدمجة
# ===============================
st.set_page_config(page_title="CMMS - Bail Yarn", layout="wide")

# شريط تسجيل الدخول
with st.sidebar:
    st.header("👤 الجلسة")
    if not st.session_state.get("logged_in"):
        if not login_ui():
            st.stop()
    else:
        state = cleanup_sessions(load_state())
        username = st.session_state.username
        rem = remaining_time(state, username)
        if rem:
            mins, secs = divmod(int(rem.total_seconds()), 60)
            st.success(f"👋 {username} | ⏳ {mins:02d}:{secs:02d}")
        else:
            logout_action()

    st.markdown("---")
    st.write("🔧 أدوات:")
    if st.button("🔄 تحديث الملف من GitHub (RAW)"):
        fetch_from_github_requests()
    if st.button("🔄 تحديث الملف من GitHub (API)"):
        fetch_from_github_api()

    # 🆕 إضافة زرار مسح الكاش
    if st.button("🗑 مسح الكاش وإعادة التحميل"):
        st.cache_data.clear()
        update_fingerprint()  # تحديث البصمة
        st.success("✅ تم مسح الكاش وتحديث البصمة")
        safe_rerun()
    
    # عرض معلومات البصمة
    current_fingerprint = get_current_fingerprint()
    st.markdown(f"🆔 بصمة الملف الحالية:")
    st.caption(f"{current_fingerprint[:20]}...")
    
    if "last_update_time" in st.session_state:
        last_update = datetime.fromisoformat(st.session_state.last_update_time)
        st.caption(f"🕒 آخر تحديث: {last_update.strftime('%H:%M:%S')}")
    
    st.markdown("---")
    if st.button("🚪 تسجيل الخروج"):
        logout_action()

# تحميل الشيتات باستخدام البصمة
current_fingerprint = get_current_fingerprint()
all_sheets = load_all_sheets(current_fingerprint)
sheets_edit = load_sheets_for_edit(current_fingerprint)

# واجهة التبويبات الرئيسية
st.title("🏭 CMMS - Bail Yarn")

tabs = st.tabs(["📊 عرض وفحص الماكينات", "🛠 تعديل وإدارة البيانات","⚙ إدارة المستخدمين"])

# Tab: عرض وفحص الماكينات (باستخدام الدالة المحسنة)
with tabs[0]:
    st.header("📊 عرض وفحص الماكينات")
    if all_sheets is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم أحد أزرار التحديث في الشريط الجانبي لتحميل الملف من cloud.")
    else:
        col1, col2 = st.columns(2)
        with col1:
            card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num_main")
        with col2:
            current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons_main")

        if st.button("عرض الحالة"):
            st.session_state["show_results"] = True

        if st.session_state.get("show_results", False):
            # 🆕 استخدام الدالة المحسنة
            check_machine_status_enhanced(st.session_state.card_num_main, st.session_state.current_tons_main, all_sheets)

# Tab: تعديل وإدارة البيانات
with tabs[1]:
    st.header("🛠 تعديل وإدارة البيانات")
    if sheets_edit is None:
        st.warning("❗ الملف المحلي غير موجود. استخدم أحد أزرار التحديث في الشريط الجانبي لتحميل الملف من cloud.")
    else:
        sheet_names = list(sheets_edit.keys())
        selected_sheet = st.selectbox("اختر الشيت:", sheet_names)
        
        if selected_sheet:
            df = sheets_edit[selected_sheet].copy()
            st.subheader(f"بيانات الشيت: {selected_sheet}")
            
            # عرض البيانات القابلة للتعديل
            edited_df = st.data_editor(df, use_container_width=True, num_rows="dynamic")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("💾 حفظ التعديلات"):
                    sheets_edit[selected_sheet] = edited_df
                    sheets_edit = save_local_excel_and_push(sheets_edit, f"Updated {selected_sheet}")
                    st.success("تم حفظ التعديلات بنجاح!")
            
            with col2:
                if st.button("🔄 إعادة تحميل البيانات"):
                    st.cache_data.clear()
                    update_fingerprint()
                    st.rerun()

# Tab: إدارة المستخدمين (للمسؤول فقط)
with tabs[2]:
    st.header("⚙ إدارة المستخدمين")
    if st.session_state.get("username") != "admin":
        st.warning("⛔ هذه الصفحة متاحة فقط للمسؤول.")
    else:
        users = load_users()
        
        st.subheader("المستخدمون الحاليون")
        for username, info in users.items():
            st.write(f"- *{username}*")
        
        st.subheader("إضافة مستخدم جديد")
        new_user = st.text_input("اسم المستخدم الجديد")
        new_password = st.text_input("كلمة المرور", type="password")
        
        if st.button("➕ إضافة مستخدم"):
            if new_user and new_password:
                if new_user in users:
                    st.error("المستخدم موجود بالفعل!")
                else:
                    users[new_user] = {"password": new_password}
                    save_users(users)
                    st.success(f"تم إضافة المستخدم {new_user} بنجاح!")
                    st.rerun()
            else:
                st.error("يرجى إدخال اسم المستخدم وكلمة المرور!")
        
        st.subheader("حذف مستخدم")
        user_to_delete = st.selectbox("اختر المستخدم للحذف", [u for u in users.keys() if u != "admin"])
        
        if st.button("🗑 حذف المستخدم"):
            if user_to_delete and user_to_delete != "admin":
                del users[user_to_delete]
                save_users(users)
                st.success(f"تم حذف المستخدم {user_to_delete} بنجاح!")
                st.rerun()
            else:
                st.error("لا يمكن حذف المسؤول!")
