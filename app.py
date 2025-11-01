import streamlit as st
import pandas as pd
import requests
import os
import io
import hashlib
import shutil
import time
from github import Github
from base64 import b64decode, b64encode

# ===============================
# ⚙ إعدادات
# ===============================
REPO_NAME = "mahmedabdallh123/cmms"
BRANCH = "main"
FILE_PATH = "Machine_Service_Lookup.xlsx"
LOCAL_FILE = "Machine_Service_Lookup.xlsx"
RAW_URL = f"https://github.com/{REPO_NAME}/raw/{BRANCH}/{FILE_PATH}"

# ===============================
# 📦 تحميل الملف من GitHub
# ===============================
def fetch_excel_from_github():
    """تحميل أحدث نسخة من الملف من GitHub بدون كاش"""
    try:
        timestamp = int(time.time())
        url = f"{RAW_URL}?v={timestamp}"
        r = requests.get(url, stream=True, headers={"Cache-Control": "no-cache"})
        r.raise_for_status()
        with open(LOCAL_FILE, "wb") as f:
            shutil.copyfileobj(r.raw, f)
        st.success("✅ تم تحميل أحدث نسخة من GitHub.")
        return True
    except Exception as e:
        st.error(f"⚠ فشل التحميل من GitHub: {e}")
        return False


# ===============================
# 💾 رفع التعديلات إلى GitHub
# ===============================
def push_excel_to_github():
    """رفع التعديلات إلى GitHub باستخدام التوكين"""
    try:
        token = st.secrets["github"]["token"]
        g = Github(token)
        repo = g.get_repo(REPO_NAME)

        with open(LOCAL_FILE, "rb") as f:
            content = f.read()

        sha = None
        try:
            existing_file = repo.get_contents(FILE_PATH, ref=BRANCH)
            sha = existing_file.sha
        except Exception:
            pass  # الملف جديد

        repo.update_file(
            path=FILE_PATH,
            message="Auto update from Streamlit app",
            content=content,
            sha=sha,
            branch=BRANCH,
        )
        st.success("🚀 تم رفع التعديلات إلى GitHub بنجاح.")
    except Exception as e:
        st.error(f"❌ فشل رفع الملف إلى GitHub: {e}")


# ===============================
# 🧠 تحميل كل الشيتات
# ===============================
@st.cache_data(ttl=0, show_spinner=False)
def load_all_sheets():
    """تحميل كل الشيتات من ملف Excel"""
    try:
        fetch_excel_from_github()
        sheets = pd.read_excel(LOCAL_FILE, sheet_name=None)
        for name, df in sheets.items():
            df.columns = df.columns.str.strip()
        # بصمة الملف
        with open(LOCAL_FILE, "rb") as f:
            st.session_state["file_fingerprint"] = hashlib.md5(f.read()).hexdigest()
        st.session_state["last_update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ أثناء قراءة الملف: {e}")
        return {}


# ===============================
# 🧾 مقارنة الصيانة
# ===============================
def normalize_name(s):
    if s is None:
        return ""
    import re
    s = str(s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s


def split_needed_services(needed_service_str):
    import re
    if not isinstance(needed_service_str, str) or not needed_service_str.strip():
        return []
    parts = re.split(r"\+|,|\n|;", needed_service_str)
    return [p.strip() for p in parts if p.strip()]


def check_machine_status(card_num, current_tons, all_sheets):
    if "ServicePlan" not in all_sheets or f"Card{card_num}" not in all_sheets:
        st.warning("⚠ لم يتم العثور على شيت الماكينة أو خطة الخدمة.")
        return

    service_plan_df = all_sheets["ServicePlan"]
    card_df = all_sheets[f"Card{card_num}"]

    # الحصول على الرنج المناسب
    current_slice = service_plan_df[
        (service_plan_df["Min_Tones"] <= current_tons)
        & (service_plan_df["Max_Tones"] >= current_tons)
    ]
    if current_slice.empty:
        st.warning("⚠ لا يوجد نطاق خدمة مناسب للأطنان الحالية.")
        return

    min_tons = current_slice["Min_Tones"].values[0]
    max_tons = current_slice["Max_Tones"].values[0]
    needed_parts = split_needed_services(current_slice["Service"].values[0])

    # الأعمدة غير التابعة للخدمة (مثل Date, Event...)
    ignore_cols = ["card", "Tones", "Date", "Min_Tones", "Max_Tones"]

    done_services = []
    other_data = {}

    for idx, row in card_df.iterrows():
        row_services = []
        for col in card_df.columns:
            val = str(row.get(col, "")).strip()
            if col in ignore_cols and val:
                other_data[col] = val
            elif val not in ["", "nan", "none"]:
                row_services.append(col)
        done_services.extend(row_services)

    done_norm = [normalize_name(c) for c in done_services]
    needed_norm = [normalize_name(p) for p in needed_parts]
    not_done = [orig for orig, n in zip(needed_parts, needed_norm) if n not in done_norm]

    result = {
        "Card": card_num,
        "Current_Tons": current_tons,
        "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
        "Done Services": ", ".join(done_services) if done_services else "-",
        "Not Done Services": ", ".join(not_done) if not_done else "-",
    }

    # ضم الأعمدة الجديدة المكتشفة
    result.update(other_data)

    result_df = pd.DataFrame([result])
    st.dataframe(result_df, use_container_width=True)

    if st.button("💾 حفظ التعديلات ورفعها"):
        result_df.to_excel(LOCAL_FILE, index=False)
        push_excel_to_github()


# ===============================
# 🖥 واجهة Streamlit
# ===============================
st.set_page_config(page_title="CMMS - Bail Yarn", layout="wide")
st.title("🏭 CMMS - Bail Yarn")

# تحديث يدوي
if st.button("🔄 تحديث الملف من GitHub"):
    st.cache_data.clear()
    all_sheets = load_all_sheets()
    st.success("✅ تم التحديث بنجاح من GitHub.")
else:
    all_sheets = load_all_sheets()

# عرض معلومات
if "file_fingerprint" in st.session_state:
    st.caption(f"🧾 بصمة الملف: {st.session_state['file_fingerprint']}")
if "last_update_time" in st.session_state:
    st.caption(f"🕒 آخر تحديث: {st.session_state['last_update_time']}")

# اختيار الماكينة
if all_sheets:
    st.header("🔍 فحص حالة الماكينة")
    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1)
    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100)
    if st.button("عرض الحالة"):
        check_machine_status(card_num, current_tons, all_sheets)
