import streamlit as st
import pandas as pd
import requests
import os
import io
import time
import hashlib
import shutil
from github import Github
from base64 import b64encode

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
# 🧾 تعديل البيانات داخل Streamlit
# ===============================
def edit_excel_sheet(sheet_name, sheets):
    """عرض وتعديل شيت محدد"""
    st.subheader(f"✏ تعديل الشيت: {sheet_name}")

    df = sheets[sheet_name]
    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)

    if st.button(f"💾 حفظ التعديلات في {sheet_name}"):
        try:
            with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl", mode="a", if_sheet_exists="replace") as writer:
                for name, sheet in sheets.items():
                    if name == sheet_name:
                        edited_df.to_excel(writer, index=False, sheet_name=name)
                    else:
                        sheet.to_excel(writer, index=False, sheet_name=name)
            st.success(f"✅ تم حفظ التعديلات في {sheet_name}.")
            push_excel_to_github()
        except Exception as e:
            st.error(f"❌ خطأ أثناء حفظ التعديلات: {e}")


# ===============================
# ⚙ واجهة Streamlit
# ===============================
st.set_page_config(page_title="CMMS - Bail Yarn", layout="wide")
st.title("🏭 CMMS - Bail Yarn")

# تحديث يدوي
if st.button("🔄 تحديث الملف من GitHub"):
    st.cache_data.clear()
    all_sheets = load_all_sheets()
else:
    all_sheets = load_all_sheets()

# عرض معلومات
if "file_fingerprint" in st.session_state:
    st.caption(f"🧾 بصمة الملف: {st.session_state['file_fingerprint']}")
if "last_update_time" in st.session_state:
    st.caption(f"🕒 آخر تحديث: {st.session_state['last_update_time']}")

# اختيار الشيت للتعديل أو العرض
if all_sheets:
    st.header("📊 إدارة البيانات")
    sheet_choice = st.selectbox("اختر الشيت:", list(all_sheets.keys()))

    if sheet_choice:
        edit_excel_sheet(sheet_choice, all_sheets)
