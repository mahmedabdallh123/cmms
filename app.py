import streamlit as st
import pandas as pd
import json
import os
import io
import requests
import shutil
import re
from datetime import datetime, timedelta
import time

# ===============================
# 🔐 إدارة المستخدمين والجلسات
import streamlit as st
import json, os
from datetime import datetime, timedelta

import streamlit as st
import json, os
from datetime import datetime, timedelta

# ===============================
# 🔐 إعدادات الدخول والجلسات
# ===============================
USERS_FILE = "users.json"
STATE_FILE = "state.json"
SESSION_DURATION = timedelta(minutes=10)  # مدة الجلسة 10 دقائق
MAX_ACTIVE_USERS = 2  # أقصى عدد مستخدمين مسموح

# -------------------------------
# 🧩 دوال مساعدة
# -------------------------------
def load_users():
    """تحميل المستخدمين من users.json"""
    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        st.error("❌ ملف users.json غير موجود!")
        st.stop()
    except json.JSONDecodeError:
        st.error("⚠ ملف users.json غير صالح JSON.")
        st.stop()

def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=4, ensure_ascii=False)

def load_state():
    """قراءة ملف state.json أو إنشاءه"""
    if not os.path.exists(STATE_FILE):
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump({}, f, indent=4, ensure_ascii=False)
        return {}
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {}

def save_state(state):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4, ensure_ascii=False)

def cleanup_sessions(state):
    """إغلاق الجلسات المنتهية"""
    now = datetime.now()
    changed = False
    for user, info in state.items():
        if info.get("active") and "login_time" in info:
            try:
                login_time = datetime.fromisoformat(info["login_time"])
                if now - login_time > SESSION_DURATION:
                    info["active"] = False
                    info.pop("login_time", None)
                    changed = True
            except:
                info["active"] = False
                changed = True
    if changed:
        save_state(state)
    return state

def remaining_time(state, username):
    """إرجاع الوقت المتبقي في الجلسة"""
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
    except:
        return None

# -------------------------------
# 🚪 تسجيل الخروج
# -------------------------------
def logout_action():
    state = load_state()
    username = st.session_state.get("username")
    if username and username in state:
        state[username]["active"] = False
        state[username].pop("login_time", None)
        save_state(state)
    st.session_state.clear()
    st.rerun()

# -------------------------------
# 🧠 واجهة تسجيل الدخول
# -------------------------------
def login_ui():
    users = load_users()
    state = cleanup_sessions(load_state())

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
        st.session_state.username = None

    st.title("🔐 تسجيل الدخول - Bail Yarn")

    username_input = st.selectbox("👤 اختر المستخدم", list(users.keys()))
    password = st.text_input("🔑 كلمة المرور", type="password")

    active_users = [u for u, v in state.items() if v.get("active")]
    active_count = len(active_users)
    st.caption(f"🔒 المستخدمون النشطون الآن: {active_count} / {MAX_ACTIVE_USERS}")

    if not st.session_state.logged_in:
        if st.button("تسجيل الدخول"):
            if username_input in users and users[username_input]["password"] == password:
                if username_input == "admin":  # 👑 الأدمن له أولوية الدخول
                    pass
                elif username_input in active_users:
                    st.warning("⚠ هذا المستخدم مسجل دخول بالفعل.")
                    return False
                elif active_count >= MAX_ACTIVE_USERS:
                    st.error("🚫 الحد الأقصى للمستخدمين المتصلين حالياً.")
                    return False

                # ✅ تسجيل الدخول
                state[username_input] = {"active": True, "login_time": datetime.now().isoformat()}
                save_state(state)
                st.session_state.logged_in = True
                st.session_state.username = username_input
                st.success(f"✅ تم تسجيل الدخول: {username_input}")
                st.rerun()
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
        if st.button("🚪 تسجيل الخروج"):
            logout_action()
        return True

# -------------------------------
# 🧭 تنفيذ النظام
# -------------------------------
if not st.session_state.get("logged_in"):
    if not login_ui():
        st.stop()
else:
    state = load_state()
    state = cleanup_sessions(state)
    username = st.session_state.username
    rem = remaining_time(state, username)
    if rem:
        mins, secs = divmod(int(rem.total_seconds()), 60)
        st.sidebar.success(f"👋 {username} | ⏳ {mins:02d}:{secs:02d}")
    else:
        logout_action()
# ⚙ إعدادات أساسية
# ===============================
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/NEW-CMMS/raw/refs/heads/main/Machine_Service_Lookup.xlsx"
PASSWORD = "1224"
LOCAL_FILE = "Machine_Service_Lookup.xlsx"

# ===============================
# 🔄 تحديث الملف من GitHub
# ===============================
def fetch_from_github():
    """تحميل الملف من GitHub وتحديث النسخة المحلية"""
    try:
        response = requests.get(GITHUB_EXCEL_URL, stream=True, timeout=10)
        response.raise_for_status()
        with open(LOCAL_FILE, "wb") as f:
            shutil.copyfileobj(response.raw, f)

        # ✅ تنظيف الكاش بعد التحديث
        st.cache_data.clear()
        st.session_state["last_update"] = pd.Timestamp.now().strftime("%Y-%m-%d %H:%M:%S")

        st.success("✅ تم تحديث البيانات من GitHub بنجاح وتم مسح الكاش.")
    except Exception as e:
        st.error(f"⚠ فشل التحديث من GitHub: {e}")

# ===============================
# 📂 تحميل البيانات (من الملف المحلي فقط)
# ===============================
@st.cache_data(show_spinner=False)
def load_all_sheets():
    """تحميل كل الشيتات من الملف المحلي"""
    if not os.path.exists(LOCAL_FILE):
        st.error("❌ الملف المحلي غير موجود. برجاء الضغط على زر التحديث أولًا.")
        return None

    sheets = pd.read_excel(LOCAL_FILE, sheet_name=None)
    for name, df in sheets.items():
        df.columns = df.columns.str.strip()
    return sheets

# ===============================
# 🧰 دوال مساعدة
# ===============================
def normalize_name(s):
    if s is None:
        return ""
    s = str(s).replace("\n", "+")
    s = re.sub(r"[^0-9a-zA-Z\u0600-\u06FF\+\s_/.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def split_needed_services(needed_service_str):
    if not isinstance(needed_service_str, str) or needed_service_str.strip() == "":
        return []
    parts = re.split(r"\+|,|\n|;", needed_service_str)
    return [p.strip() for p in parts if p.strip() != ""]

# ===============================
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

    # حفظ اختيار النطاق
    if "view_option" not in st.session_state:
        st.session_state.view_option = "الشريحة الحالية فقط"

    st.subheader("⚙ نطاق العرض")
    view_option = st.radio(
        "اختر نطاق العرض:",
        ("الشريحة الحالية فقط", "كل الشرائح الأقل", "كل الشرائح الأعلى", "نطاق مخصص", "كل الشرائح"),
        horizontal=True,
        key="view_option"
    )

    # نطاق مخصص
    min_range = st.session_state.get("min_range", max(0, current_tons - 500))
    max_range = st.session_state.get("max_range", current_tons + 500)

    if view_option == "نطاق مخصص":
        st.markdown("#### 🔢 أدخل النطاق المخصص")
        col1, col2 = st.columns(2)
        with col1:
            min_range = st.number_input("من (طن):", min_value=0, step=100, value=min_range, key="min_range")
        with col2:
            max_range = st.number_input("إلى (طن):", min_value=min_range, step=100, value=max_range, key="max_range")

    # تحديد الشرائح المطلوبة
    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[(service_plan_df["Min_Tones"] <= current_tons) & (service_plan_df["Max_Tones"] >= current_tons)]
    elif view_option == "كل الشرائح الأقل":
        selected_slices = service_plan_df[service_plan_df["Max_Tones"] <= current_tons]
    elif view_option == "كل الشرائح الأعلى":
        selected_slices = service_plan_df[service_plan_df["Min_Tones"] >= current_tons]
    elif view_option == "نطاق مخصص":
        selected_slices = service_plan_df[(service_plan_df["Min_Tones"] >= min_range) & (service_plan_df["Max_Tones"] <= max_range)]
    else:
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة حسب النطاق المحدد.")
        return

    all_results = []
    for _, current_slice in selected_slices.iterrows():
        slice_min = current_slice["Min_Tones"]
        slice_max = current_slice["Max_Tones"]
        needed_service_raw = current_slice.get("Service", "")
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]

        mask = (card_df.get("Min_Tones", 0).fillna(0) <= slice_max) & (card_df.get("Max_Tones", 0).fillna(0) >= slice_min)
        matching_rows = card_df[mask]

        done_services_set = set()
        last_date = "-"
        last_tons = "-"
        last_other = "-"
        last_servised_by = "-"

        if not matching_rows.empty:
            ignore_cols = {"card", "Tones", "Min_Tones", "Max_Tones", "Date", "Other", "Servised by"}
            for _, r in matching_rows.iterrows():
                for col in matching_rows.columns:
                    if col not in ignore_cols:
                        val = str(r.get(col, "")).strip()
                        if val and val.lower() not in ["nan", "none", ""]:
                            done_services_set.add(col)

            # ✅ قراءة آخر تاريخ
            if "Date" in matching_rows.columns:
                try:
                    cleaned_dates = matching_rows["Date"].astype(str).str.replace("\\", "/", regex=False)
                    dates = pd.to_datetime(cleaned_dates, errors="coerce", dayfirst=True)
                    if dates.notna().any():
                        idx = dates.idxmax()
                        parsed_date = dates.loc[idx]
                        last_date = parsed_date.strftime("%d/%m/%Y") if pd.notna(parsed_date) else "-"
                except Exception:
                    last_date = "-"

            # ✅ قراءة آخر طن
            if "Tones" in matching_rows.columns:
                tons_vals = pd.to_numeric(matching_rows["Tones"], errors="coerce")
                if tons_vals.notna().any():
                    last_tons = int(tons_vals.max())

            # ✅ قراءة عمود Other
            if "Other" in matching_rows.columns:
                last_other = str(matching_rows["Other"].dropna().iloc[-1]) if matching_rows["Other"].notna().any() else "-"

            # ✅ قراءة عمود Servised by
            if "Servised by" in matching_rows.columns:
                last_servised_by = str(matching_rows["Servised by"].dropna().iloc[-1]) if matching_rows["Servised by"].notna().any() else "-"

        done_services = sorted(list(done_services_set))
        done_norm = [normalize_name(c) for c in done_services]
        not_done = [orig for orig, n in zip(needed_parts, needed_norm) if n not in done_norm]

        all_results.append({
            "Min_Tons": slice_min,
            "Max_Tons": slice_max,
            "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
            "Done Services": ", ".join(done_services) if done_services else "-",
            "Not Done Services": ", ".join(not_done) if not_done else "-",
            "Last Date": last_date,
            "Last Tones": last_tons,
            "Other": last_other,
            "Servised by": last_servised_by
        })

    result_df = pd.DataFrame(all_results)

    # ✅ إزالة الصفوف الفارغة وإعادة الفهرسة
    result_df = result_df.dropna(how="all").reset_index(drop=True)

    # 🎨 تنسيق الجدول - كل عمود بلون مختلف لتمييز البيانات
    def highlight_cell(val, col_name):
        color_map = {
            "Service Needed": "background-color: #fff3cd; color:#856404; font-weight:bold;",   # أصفر فاتح
            "Done Services": "background-color: #d4edda; color:#155724; font-weight:bold;",     # أخضر فاتح
            "Not Done Services": "background-color: #f8d7da; color:#721c24; font-weight:bold;", # أحمر فاتح
            "Last Date": "background-color: #e7f1ff; color:#004085; font-weight:bold;",         # أزرق فاتح
            "Last Tones": "background-color: #f0f0f0; color:#333; font-weight:bold;",           # رمادي فاتح
            "Other": "background-color: #e2f0d9; color:#2e6f32; font-weight:bold;",             # أخضر باهت
            "Servised by": "background-color: #fdebd0; color:#7d6608; font-weight:bold;",       # بيج
            "Min_Tons": "background-color: #ebf5fb; color:#154360; font-weight:bold;",          # أزرق باهت
            "Max_Tons": "background-color: #f9ebea; color:#641e16; font-weight:bold;",          # وردي باهت
        }
        return color_map.get(col_name, "")

    def style_table(row):
        return [highlight_cell(row[col], col) for col in row.index]

    st.markdown("### 📋 نتائج الفحص")
    st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)

    # ✅ تحميل النتائج كملف Excel
    import io
    buffer = io.BytesIO()
    result_df.to_excel(buffer, index=False, engine="openpyxl")
    st.download_button(
        label="💾 حفظ النتائج كـ Excel",
        data=buffer.getvalue(),
        file_name=f"Service_Report_Card{card_num}.xlsx",
        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

# ===============================
# 🖥 الواجهة الرئيسية
# ===============================
st.title("🏭 سيرفيس تحضيرات Bail Yarn")

# 🔄 زر التحديث من GitHub
if st.button("🔄 تحديث البيانات من GitHub"):
    fetch_from_github()

if "last_update" in st.session_state:
    st.caption(f"🕒 آخر تحديث: {st.session_state['last_update']}")

all_sheets = load_all_sheets()

col1, col2 = st.columns(2)
with col1:
    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num")
with col2:
    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons")

if st.button("عرض الحالة"):
    st.session_state["show_results"] = True

if st.session_state.get("show_results", False) and all_sheets:
    check_machine_status(st.session_state.card_num, st.session_state.current_tons, all_sheets)










