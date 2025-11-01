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
SESSION_DURATION = timedelta(minutes=10)  # مدة الجلسة 10 دقائق
MAX_ACTIVE_USERS = 2  # أقصى عدد مستخدمين مسموح

# إعدادات GitHub (مسارات الملف والريبو)
REPO_NAME = "mahmedabdallh123/cmms"  # عدل إذا لزم
BRANCH = "main"
FILE_PATH = "Machine_Service_Lookup.xlsx"
LOCAL_FILE = "Machine_Service_Lookup.xlsx"
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx"

# -------------------------------
# 🔁 دالة آمنة لإعادة التشغيل (تتعامل مع اختلاف إصدارات Streamlit)
# -------------------------------
def safe_rerun():
    """
    استدعاء آمن لإعادة تشغيل Streamlit.
    يحاول استدعاء st.rerun() أولًا، ثم st.experimental_rerun() كبديل،
    ثم يتجاهل إن لم تكن متوفرة (مع تجربة إنهاء التنفيذ الحالي).
    """
    try:
        # استدعاء st.rerun إن كانت متاحة (نسخ أحدث)
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
    # كحل أخير، نوقف تنفيذ الصفحة بهدوء عبر استدعاء stop
    try:
        st.stop()
    except Exception:
        return

# -------------------------------
# 🆕 نظام البصمة الفريدة للتحديثات
# -------------------------------
def get_file_fingerprint():
    """إنشاء بصمة فريدة للملف بناءً على وقت التعديل والمحتوى"""
    if not os.path.exists(LOCAL_FILE):
        return "initial"
    
    try:
        # استخدام وقت التعديل وحجم الملف لإنشاء بصمة
        stat = os.stat(LOCAL_FILE)
        file_info = f"{stat.st_mtime}_{stat.st_size}"
        
        # إضافة هاش للمحتوى لزيادة الدقة (اختياري لأداء أفضل)
        with open(LOCAL_FILE, "rb") as f:
            file_hash = hashlib.md5(f.read()).hexdigest()[:8]
        
        return f"{file_info}_{file_hash}"
    except Exception:
        return str(datetime.now().timestamp())

def update_fingerprint():
    """تحديث البصمة في حالة الجلسة"""
    st.session_state["file_fingerprint"] = get_file_fingerprint()

def get_current_fingerprint():
    """الحصول على البصمة الحالية أو إنشاء واحدة جديدة"""
    if "file_fingerprint" not in st.session_state:
        st.session_state["file_fingerprint"] = get_file_fingerprint()
    return st.session_state["file_fingerprint"]

# -------------------------------
# 🧩 دوال مساعدة للملفات والحالة
# -------------------------------
def load_users():
    if not os.path.exists(USERS_FILE):
        # انشئ ملف افتراضي اذا مش موجود (يوجد admin بكلمة مرور افتراضية "admin" — غيرها فورًا)
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

# -------------------------------
# 🔐 تسجيل الخروج (مصحح وآمن)
# -------------------------------
def logout_action():
    state = load_state()
    username = st.session_state.get("username")
    if username and username in state:
        state[username]["active"] = False
        state[username].pop("login_time", None)
        save_state(state)
    # احذف متغيرات الجلسة بطريقة آمنة (ننسخ المفاتيح أولاً)
    try:
        keys = list(st.session_state.keys())
        for k in keys:
            try:
                st.session_state.pop(k, None)
            except Exception:
                pass
    except Exception:
        pass
    # إعادة تشغيل العرض بطريقة آمنة
    safe_rerun()
    return

# -------------------------------
# 🧠 واجهة تسجيل الدخول (مأخوذ وموسع)
# -------------------------------
def login_ui():
    users = load_users()
    state = cleanup_sessions(load_state())
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None

    st.title("🔐 تسجيل الدخول - Bail Yarn (CMMS)")

    # اختيار المستخدم
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

# -------------------------------
# 🔄 طرق جلب الملف من GitHub
# -------------------------------
def fetch_from_github_requests():
    """تحميل بإستخدام رابط RAW (requests)"""
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=20)
        response.raise_for_status()
        with open(LOCAL_FILE, "wb") as f:
            shutil.copyfileobj(response.raw, f)
        # تحديث البصمة بدلاً من مسح الكاش
        update_fingerprint()
        st.success("✅ تم تحديث البيانات من GitHub بنجاح وتم تحديث البصمة.")
        safe_rerun()
    except Exception as e:
        st.error(f"⚠ فشل التحديث من GitHub (requests): {e}")

def fetch_from_github_api():
    """تحميل عبر GitHub API (باستخدام PyGithub token في secrets)"""
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
        # تحديث البصمة بدلاً من مسح الكاش
        update_fingerprint()
        st.success("✅ تم تحميل الملف من GitHub API بنجاح.")
        safe_rerun()
    except Exception as e:
        st.error(f"⚠ فشل تحميل الملف من GitHub API: {e}")

# -------------------------------
# 📂 تحميل الشيتات (مخبأ مع البصمة)
# -------------------------------
@st.cache_data(show_spinner=False)
def load_all_sheets(_fingerprint):
    """
    تحميل جميع الشيتات مع استخدام البصمة كمفتاح كاش
    البصمة تضمن أن أي تحديث جديد سيؤدي لتحميل جديد
    """
    if not os.path.exists(LOCAL_FILE):
        return None
    sheets = pd.read_excel(LOCAL_FILE, sheet_name=None)
    for name, df in sheets.items():
        df.columns = df.columns.str.strip()
    return sheets

# نسخة مع dtype=object لواجهة التحرير
@st.cache_data(show_spinner=False)
def load_sheets_for_edit(_fingerprint):
    """
    تحميل الشيتات للتحرير مع استخدام البصمة كمفتاح كاش
    """
    if not os.path.exists(LOCAL_FILE):
        return None
    sheets = pd.read_excel(LOCAL_FILE, sheet_name=None, dtype=object)
    for name, df in sheets.items():
        df.columns = df.columns.str.strip()
    return sheets

# -------------------------------
# 🔁 حفظ محلي + رفع على GitHub + تحديث البصمة + إعادة تحميل
# -------------------------------
def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
    # احفظ محلياً
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

    # تحديث البصمة بدلاً من مسح الكاش
    update_fingerprint()

    # حاول الرفع عبر PyGithub token في secrets
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
            # حاول رفع كملف جديد أو إنشاء
            try:
                repo.create_file(path=FILE_PATH, message=commit_message, content=content, branch=BRANCH)
            except Exception as e2:
                st.error(f"⚠ فشل رفع الملف إلى GitHub: {e2}")
                return load_sheets_for_edit(get_current_fingerprint())

        st.success("✅ تم الحفظ والرفع على GitHub بنجاح.")
        # إعادة تحميل النسخة المعدّلة للواجهة باستخدام البصمة الجديدة
        safe_rerun()
        return load_sheets_for_edit(get_current_fingerprint())
    except Exception as e:
        st.error(f"⚠ فشل الاتصال بـ GitHub: {e}")
        return load_sheets_for_edit(get_current_fingerprint())

# -------------------------------
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

# ================================
# 🔍 الفحص الديناميكي الكامل
# ================================
def check_machine_status(card_num, current_tons, all_sheets):
    if not all_sheets or "ServicePlan" not in all_sheets:
        st.error("❌ الملف لا يحتوي على شيت ServicePlan.")
        return

    service_plan_df = all_sheets["ServicePlan"]
    card_sheet_name = f"Card{card_num}"

    if card_sheet_name not in all_sheets:
        st.warning(f"⚠ لا يوجد شيت باسم {card_sheet_name}")
        return

    card_df = all_sheets[card_sheet_name]

    # تحديد الشريحة المناسبة في ServicePlan حسب الـ Current Tons
    selected_slice = service_plan_df[
        (service_plan_df["Min_Tones"] <= current_tons) &
        (service_plan_df["Max_Tones"] >= current_tons)
    ]

    if selected_slice.empty:
        st.warning("⚠ لا توجد شريحة مطابقة للـ Current Tons.")
        return

    results = []

    for _, row in selected_slice.iterrows():
        slice_min = row["Min_Tones"]
        slice_max = row["Max_Tones"]

        needed_raw = row.get("Service", "")
        needed_parts = split_needed_services(needed_raw)
        needed_norm = [normalize_name(x) for x in needed_parts]

        # نطاق الشريحة في كارت الماكينة
        mask = (card_df.get("Min_Tones", 0).fillna(0) <= slice_max) & \
               (card_df.get("Max_Tones", 0).fillna(0) >= slice_min)
        card_rows = card_df[mask]

        if card_rows.empty:
            result_row = {
                "Machine": card_num,
                "Min_Tons": slice_min,
                "Max_Tons": slice_max,
                "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
                "Done Services": "-",
                "Not Done Services": " + ".join(needed_parts) if needed_parts else "-",
                "Tones": "-"
            }
            results.append(result_row)
            continue

        # تحديد الأعمدة الأساسية التي ليست خدمات
        base_cols = ["card", "tones", "min_tones", "max_tones"]
        # كل الأعمدة الأخرى تعتبر إما خدمات أو معلومات إضافية
        all_cols = list(card_df.columns)
        service_cols = []
        extra_cols = []

        for c in all_cols:
            c_low = str(c).strip().lower()
            if c_low in base_cols:
                continue
            if c_low in ["date", "other", "servised by"]:
                extra_cols.append(c)
            else:
                # نعتبره خدمة إلا إذا كانت قيمه كلها فاضية
                if card_df[c].notna().any():
                    service_cols.append(c)
                else:
                    extra_cols.append(c)

        done_services = set()
        extra_info = {col: "" for col in extra_cols}
        tone_val = "-"

        # تحليل الصفوف في نفس الشريحة
        for _, r in card_rows.iterrows():
            # الخدمات المنفذة
            for col in service_cols:
                val = str(r.get(col, "")).strip()
                if val and val.lower() not in ["nan", "none", ""]:
                    done_services.add(col)
                    tone_val = r.get("Tones", tone_val)
            # الأعمدة الإضافية
            for col in extra_cols:
                val = str(r.get(col, "")).strip()
                if val:
                    extra_info[col] = val

        done_norm = [normalize_name(x) for x in done_services]
        not_done = []

        for orig, n in zip(needed_parts, needed_norm):
            found = any(n in dn or dn in n for dn in done_norm)
            if not found:
                not_done.append(orig)

        result_row = {
            "Machine": card_num,
            "Min_Tons": slice_min,
            "Max_Tons": slice_max,
            "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
            "Done Services": ", ".join(done_services) if done_services else "-",
            "Not Done Services": ", ".join(not_done) if not_done else "-",
            "Tones": tone_val
        }

        # دمج الأعمدة الديناميكية
        result_row.update(extra_info)
        results.append(result_row)

    # إنشاء الداتا فريم النهائي
    result_df = pd.DataFrame(results).reset_index(drop=True)
    st.markdown("### 📋 نتائج الفحص الديناميكية")
    st.dataframe(result_df, use_container_width=True)

    # تنزيل النتائج كـ Excel
    buffer = io.BytesIO()
    result_df.to_excel(buffer, index=False, engine="openpyxl")
    st.download_button(
        label="💾 تحميل النتيجة كـ Excel",
        data=buffer.getvalue(),
        file_name=f"Machine_{card_num}_Service_Check.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
# -------------------------------
# 🖥 الواجهة الرئيسية المدمجة
# -------------------------------
# إعداد الصفحة
st.set_page_config(page_title="CMMS - Bail Yarn", layout="wide")

# شريط تسجيل الدخول / معلومات الجلسة في الشريط الجانبي
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
    
    # 🆕 عرض معلومات البصمة الحالية
    current_fingerprint = get_current_fingerprint()
    st.markdown(f"🆔 بصمة الملف الحالية:")
    st.caption(f"{current_fingerprint[:20]}...")
    
    st.markdown("---")
    # زر لإعادة تسجيل الخروج
    if st.button("🚪 تسجيل الخروج"):
        logout_action()

# 🆕 تحميل الشيتات باستخدام البصمة الحالية
current_fingerprint = get_current_fingerprint()
all_sheets = load_all_sheets(current_fingerprint)
sheets_edit = load_sheets_for_edit(current_fingerprint)

# واجهة التبويبات الرئيسية
st.title("🏭 CMMS - Bail Yarn")

tabs = st.tabs(["📊 عرض وفحص الماكينات", "🛠 تعديل وإدارة البيانات","⚙ إدارة المستخدمين"])

# -------------------------------
# Tab: عرض وفحص الماكينات
# -------------------------------
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
            check_machine_status(st.session_state.card_num_main, st.session_state.current_tons_main, all_sheets)

# -------------------------------
# Tab: تعديل وإدارة البيانات
# -------------------------------
with tabs[1]:
    st.header("🛠 تعديل وإدارة البيانات")

    # تحقق صلاحية الرفع: إما admin أو يوجد توكين في secrets وPyGithub متاح
    username = st.session_state.get("username")
    token_exists = bool(st.secrets.get("github", {}).get("token", None))
    can_push = (username == "admin") or (token_exists and GITHUB_AVAILABLE)

    if sheets_edit is None:
        st.warning("❗ الملف المحلي غير موجود. اضغط تحديث من cloud في الشريط الجانبي أولًا.")
    else:
        tab1, tab2, tab3, tab4 = st.tabs([
            "عرض وتعديل شيت",
            "إضافة صف جديد (أحداث متتالية)",
            "إضافة عمود جديد",
            "🗑 حذف صف"
        ])

        # Tab1: تعديل بيانات وعرض
        with tab1:
            st.subheader("✏ تعديل البيانات")
            sheet_name = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="edit_sheet")
            df = sheets_edit[sheet_name].astype(str)
            edited_df = st.data_editor(df, num_rows="dynamic")
            if st.button("💾 حفظ التعديلات", key=f"save_edit_{sheet_name}"):
                if not can_push:
                    st.warning("🚫 لا تملك صلاحية الرفع إلى GitHub من هذه الجلسة.")
                sheets_edit[sheet_name] = edited_df.astype(object)
                new_sheets = save_local_excel_and_push(
                    sheets_edit,
                    commit_message=f"Edit sheet {sheet_name} by {st.session_state.get('username')}"
                )
                if isinstance(new_sheets, dict):
                    sheets_edit = new_sheets
                st.dataframe(sheets_edit[sheet_name])

        # Tab2: إضافة صف جديد
        with tab2:
            st.subheader("➕ إضافة صف جديد (سجل حدث جديد داخل نفس الرينج)")
            sheet_name_add = st.selectbox("اختر الشيت لإضافة صف:", list(sheets_edit.keys()), key="add_sheet")
            df_add = sheets_edit[sheet_name_add].astype(str).reset_index(drop=True)
            st.markdown("أدخل بيانات الحدث (يمكنك إدخال أي نص/أرقام/تواريخ)")
            new_data = {}
            for col in df_add.columns:
                new_data[col] = st.text_input(f"{col}", key=f"add_{sheet_name_add}_{col}")
            if st.button("💾 إضافة الصف الجديد", key=f"add_row_{sheet_name_add}"):
                new_row_df = pd.DataFrame([new_data]).astype(str)
                # البحث عن أعمدة الرينج
                min_col, max_col, card_col = None, None, None
                for c in df_add.columns:
                    c_low = c.strip().lower()
                    if c_low in ("min_tones", "min_tone", "min tones", "min"):
                        min_col = c
                    if c_low in ("max_tones", "max_tone", "max tones", "max"):
                        max_col = c
                    if c_low in ("card", "machine", "machine_no", "machine id"):
                        card_col = c
                if not min_col or not max_col:
                    st.error("⚠ لم يتم العثور على أعمدة Min_Tones و/أو Max_Tones في الشيت.")
                else:
                    def to_num_or_none(x):
                        try:
                            return float(x)
                        except Exception:
                            return None
                    new_min_raw = str(new_data.get(min_col, "")).strip()
                    new_max_raw = str(new_data.get(max_col, "")).strip()
                    new_min_num = to_num_or_none(new_min_raw)
                    new_max_num = to_num_or_none(new_max_raw)
                    # العثور على موضع الإدراج
                    insert_pos = len(df_add)
                    mask = pd.Series([False] * len(df_add))
                    if card_col:
                        new_card = str(new_data.get(card_col, "")).strip()
                        if new_card != "":
                            if new_min_num is not None and new_max_num is not None:
                                mask = (
                                    (df_add[card_col].astype(str).str.strip() == new_card) &
                                    (pd.to_numeric(df_add[min_col], errors='coerce') == new_min_num) &
                                    (pd.to_numeric(df_add[max_col], errors='coerce') == new_max_num)
                                )
                            else:
                                mask = (
                                    (df_add[card_col].astype(str).str.strip() == new_card) &
                                    (df_add[min_col].astype(str).str.strip() == new_min_raw) &
                                    (df_add[max_col].astype(str).str.strip() == new_max_raw)
                                )
                    else:
                        if new_min_num is not None and new_max_num is not None:
                            mask = (
                                (pd.to_numeric(df_add[min_col], errors='coerce') == new_min_num) &
                                (pd.to_numeric(df_add[max_col], errors='coerce') == new_max_num)
                            )
                        else:
                            mask = (
                                (df_add[min_col].astype(str).str.strip() == new_min_raw) &
                                (df_add[max_col].astype(str).str.strip() == new_max_raw)
                            )
                    if mask.any():
                        insert_pos = mask[mask].index[-1] + 1
                    else:
                        try:
                            df_add["_min_num"] = pd.to_numeric(df_add[min_col], errors='coerce').fillna(-1)
                            if new_min_num is not None:
                                insert_pos = int((df_add["_min_num"] < new_min_num).sum())
                            else:
                                insert_pos = len(df_add)
                            df_add = df_add.drop(columns=["_min_num"])
                        except Exception:
                            insert_pos = len(df_add)
                    df_top = df_add.iloc[:insert_pos].reset_index(drop=True)
                    df_bottom = df_add.iloc[insert_pos:].reset_index(drop=True)
                    df_new = pd.concat([df_top, new_row_df.reset_index(drop=True), df_bottom], ignore_index=True)
                    sheets_edit[sheet_name_add] = df_new.astype(object)
                    if not can_push:
                        st.warning("🚫 لا تملك صلاحية الرفع (التغييرات ستبقى محلياً).")
                        # حفظ محلياً
                        try:
                            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                                for name, sh in sheets_edit.items():
                                    try:
                                        sh.to_excel(writer, sheet_name=name, index=False)
                                    except Exception:
                                        sh.astype(object).to_excel(writer, sheet_name=name, index=False)
                            # تحديث البصمة بعد الحفظ المحلي
                            update_fingerprint()
                            st.success("✅ تم إدراج الصف محليًا (لم يتم رفعه إلى GitHub).")
                            st.dataframe(sheets_edit[sheet_name_add])
                        except Exception as e:
                            st.error(f"⚠ خطأ أثناء الحفظ المحلي: {e}")
                    else:
                        new_sheets = save_local_excel_and_push(
                            sheets_edit,
                            commit_message=f"Add new row under range {new_min_raw}-{new_max_raw} in {sheet_name_add} by {st.session_state.get('username')}"
                        )
                        if isinstance(new_sheets, dict):
                            sheets_edit = new_sheets
                        st.success("✅ تم الإضافة — تم إدراج الصف في الموقع المناسب.")
                        st.dataframe(sheets_edit[sheet_name_add])

        # Tab3: إضافة عمود جديد
        with tab3:
            st.subheader("🆕 إضافة عمود جديد")
            sheet_name_col = st.selectbox("اختر الشيت لإضافة عمود:", list(sheets_edit.keys()), key="add_col_sheet")
            df_col = sheets_edit[sheet_name_col].astype(str)
            new_col_name = st.text_input("اسم العمود الجديد:")
            default_value = st.text_input("القيمة الافتراضية لكل الصفوف (اختياري):", "")
            if st.button("💾 إضافة العمود الجديد", key=f"add_col_{sheet_name_col}"):
                if new_col_name:
                    df_col[new_col_name] = default_value
                    sheets_edit[sheet_name_col] = df_col.astype(object)
                    if not can_push:
                        try:
                            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                                for name, sh in sheets_edit.items():
                                    try:
                                        sh.to_excel(writer, sheet_name=name, index=False)
                                    except Exception:
                                        sh.astype(object).to_excel(writer, sheet_name=name, index=False)
                            # تحديث البصمة بعد الحفظ المحلي
                            update_fingerprint()
                            st.success("✅ تم إضافة العمود محليًا (لم يتم رفعه إلى GitHub).")
                            st.dataframe(sheets_edit[sheet_name_col])
                        except Exception as e:
                            st.error(f"⚠ خطأ أثناء الحفظ المحلي: {e}")
                    else:
                        new_sheets = save_local_excel_and_push(
                            sheets_edit,
                            commit_message=f"Add new column '{new_col_name}' to {sheet_name_col} by {st.session_state.get('username')}"
                        )
                        if isinstance(new_sheets, dict):
                            sheets_edit = new_sheets
                        st.success("✅ تم إضافة العمود الجديد بنجاح!")
                        st.dataframe(sheets_edit[sheet_name_col])
                else:
                    st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")

        # Tab4: حذف صف
        with tab4:
            st.subheader("🗑 حذف صف من الشيت")
            sheet_name_del = st.selectbox("اختر الشيت:", list(sheets_edit.keys()), key="delete_sheet")
            df_del = sheets_edit[sheet_name_del].astype(str).reset_index(drop=True)

            st.markdown("### 📋 بيانات الشيت الحالية")
            st.dataframe(df_del)

            st.markdown("### ✏ اختر الصفوف التي تريد حذفها (برقم الصف):")
            st.write("💡 ملاحظة: رقم الصف يبدأ من 0 (أول صف = 0)")

            rows_to_delete = st.text_input("أدخل أرقام الصفوف مفصولة بفاصلة (مثلاً: 0,2,5):")
            confirm_delete = st.checkbox("✅ أؤكد أني أريد حذف هذه الصفوف بشكل نهائي")

            if st.button("🗑 تنفيذ الحذف", key=f"delete_rows_{sheet_name_del}"):
                if rows_to_delete.strip() == "":
                    st.warning("⚠ الرجاء إدخال رقم الصف أو أكثر.")
                elif not confirm_delete:
                    st.warning("⚠ برجاء تأكيد الحذف أولاً بوضع علامة ✅ قبل التنفيذ.")
                else:
                    try:
                        rows_list = [int(x.strip()) for x in rows_to_delete.split(",") if x.strip().isdigit()]
                        rows_list = [r for r in rows_list if 0 <= r < len(df_del)]
                        if not rows_list:
                            st.warning("⚠ لم يتم العثور على صفوف صحيحة.")
                        else:
                            df_new = df_del.drop(rows_list).reset_index(drop=True)
                            sheets_edit[sheet_name_del] = df_new.astype(object)
                            if not can_push:
                                try:
                                    with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
                                        for name, sh in sheets_edit.items():
                                            try:
                                                sh.to_excel(writer, sheet_name=name, index=False)
                                            except Exception:
                                                sh.astype(object).to_excel(writer, sheet_name=name, index=False)
                                    # تحديث البصمة بعد الحفظ المحلي
                                    update_fingerprint()
                                    st.success(f"✅ تم حذف الصفوف التالية محليًا: {rows_list}")
                                    st.dataframe(sheets_edit[sheet_name_del])
                                except Exception as e:
                                    st.error(f"⚠ خطأ أثناء الحفظ المحلي: {e}")
                            else:
                                new_sheets = save_local_excel_and_push(sheets_edit, commit_message=f"Delete rows {rows_list} from {sheet_name_del} by {st.session_state.get('username')}")
                                if isinstance(new_sheets, dict):
                                    sheets_edit = new_sheets
                                st.success(f"✅ تم حذف الصفوف التالية بنجاح: {rows_list}")
                                st.dataframe(sheets_edit[sheet_name_del])
                    except Exception as e:
                        st.error(f"حدث خطأ أثناء الحذف: {e}")

# Tab: إدارة المستخدمين
with tabs[2]:
    st.header("⚙ إدارة المستخدمين")
    users = load_users()
    username = st.session_state.get("username")

    # فقط admin يستطيع إدارة المستخدمين عبر الواجهة
    if username != "admin":
        st.info("🛑 فقط المستخدم 'admin' يمكنه إدارة المستخدمين عبر هذه الواجهة. تواصل مع المدير لإجراء تغييرات.")
        st.markdown("المستخدمين الحاليين:")
        st.write(list(users.keys()))
    else:
        st.subheader("🔐 المستخدمين الموجودين")
        st.dataframe(pd.DataFrame([{"username": k, "password": v.get("password","")} for k,v in users.items()]))
        st.markdown("### ➕ إضافة مستخدم جديد")
        new_user = st.text_input("اسم المستخدم الجديد:")
        new_pass = st.text_input("كلمة المرور:", type="password")
        if st.button("إضافة مستخدم"):
            if new_user.strip() == "" or new_pass.strip() == "":
                st.warning("الرجاء إدخال اسم وكلمة مرور.")
            else:
                if new_user in users:
                    st.warning("هذا المستخدم موجود بالفعل.")
                else:
                    users[new_user] = {"password": new_pass}
                    save_users(users)
                    st.success("✅ تم إضافة المستخدم.")
                    safe_rerun()

        st.markdown("### 🗑 حذف مستخدم")
        del_user = st.selectbox("اختر مستخدم للحذف:", [u for u in users.keys() if u != "admin"])
        if st.button("حذف المستخدم"):
            if del_user in users:
                users.pop(del_user, None)
                save_users(users)
                st.success("✅ تم الحذف.")
                safe_rerun()
