import streamlit as st
import pandas as pd
import requests
import io
import os
import time
import hashlib
import json
import shutil
from datetime import datetime
from github import Github

# ===============================
# ⚙ إعدادات أساسية
# ===============================
REPO_NAME = "mahmedabdallh123/cmms"
FILE_PATH = "Machine_Service_Lookup.xlsx"
LOCAL_FILE = "Machine_Service_Lookup.xlsx"
GITHUB_RAW_URL = f"https://github.com/{REPO_NAME}/raw/main/{FILE_PATH}"

PASSWORD = "1234"
TRIAL_SECONDS = 60
RENEW_HOURS = 24
TOKENS_FILE = "tokens.json"

# ===============================
# 🧠 تحميل الملف من GitHub
# ===============================
def generate_fingerprint_url(base_url):
    timestamp = int(time.time())
    return f"{base_url}?v={timestamp}"

@st.cache_data(ttl=0, show_spinner=False)
def load_excel_with_fingerprint():
    """تحميل ملف Excel من GitHub وتحديث البصمة"""
    try:
        url = generate_fingerprint_url(GITHUB_RAW_URL)
        r = requests.get(url, headers={"Cache-Control": "no-cache"})
        if r.status_code != 200:
            raise Exception(f"فشل التحميل من GitHub: {r.status_code}")
        with open(LOCAL_FILE, "wb") as f:
            f.write(r.content)

        with open(LOCAL_FILE, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()

        sheets = pd.read_excel(LOCAL_FILE, sheet_name=None)
        st.session_state["file_fingerprint"] = md5
        st.session_state["last_update_time"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الملف: {e}")
        st.stop()

# ===============================
# 💾 رفع الملف إلى GitHub
# ===============================
def upload_to_github(local_path, repo_name, target_path):
    """رفع الملف المحدث تلقائيًا إلى GitHub"""
    try:
        token = st.secrets["GITHUB_TOKEN"]
        g = Github(token)
        repo = g.get_repo(repo_name)

        with open(local_path, "rb") as f:
            content = f.read()

        try:
            contents = repo.get_contents(target_path)
            repo.update_file(contents.path, "تحديث تلقائي من Streamlit", content, contents.sha, branch="main")
            st.success("✅ تم رفع الملف بنجاح إلى GitHub (تحديث تلقائي)")
        except Exception:
            repo.create_file(target_path, "رفع أولي من Streamlit", content, branch="main")
            st.success("✅ تم رفع الملف لأول مرة إلى GitHub")

    except Exception as e:
        st.error(f"❌ فشل الرفع إلى GitHub: {e}")

# ===============================
# 🔑 نظام التجربة المجانية / الباسورد
# ===============================
def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "w") as f:
            json.dump({}, f)
    with open(TOKENS_FILE, "r") as f:
        return json.load(f)

def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=4)

def check_access(user_id="default_user"):
    tokens = load_tokens()
    now = time.time()

    if user_id not in tokens:
        tokens[user_id] = {"last_trial": 0}
        save_tokens(tokens)

    last_trial = tokens[user_id]["last_trial"]
    if now - last_trial < RENEW_HOURS * 3600 and "trial_start" not in st.session_state:
        password = st.text_input("أدخل كلمة المرور للوصول:", type="password")
        if password == PASSWORD:
            st.session_state["access_granted"] = True
            return True
        st.warning("⏰ التجربة غير متاحة حاليًا. أعد المحاولة لاحقًا أو استخدم الباسورد.")
        return False

    if "trial_start" in st.session_state:
        if now - st.session_state["trial_start"] < TRIAL_SECONDS:
            return True
        else:
            st.warning("انتهت التجربة المؤقتة.")
            return False

    if st.button("تفعيل تجربة مجانية لمدة 60 ثانية"):
        tokens[user_id]["last_trial"] = now
        save_tokens(tokens)
        st.session_state["trial_start"] = now
        st.experimental_rerun()

    return False

# ===============================
# 🔧 وظائف التطبيق
# ===============================
def show_machine_status(card_num, tons, sheets):
    if "ServicePlan" not in sheets or f"Card{card_num}" not in sheets:
        st.error("❌ الملف لا يحتوي على الشيتات المطلوبة.")
        return

    plan = sheets["ServicePlan"]
    card_df = sheets[f"Card{card_num}"]

    current_plan = plan[(plan["Min_Tones"] <= tons) & (plan["Max_Tones"] >= tons)]
    if current_plan.empty:
        st.warning("⚠ لم يتم العثور على خطة صيانة مناسبة.")
        return

    row = current_plan.iloc[0]
    needed = str(row["Service"]).split("+")
    done = card_df[(card_df["Tones"] >= row["Min_Tones"]) & (card_df["Tones"] <= row["Max_Tones"])]

    done_cols = [c for c in card_df.columns if c not in ["Tones", "Date", "Card"]]
    completed = [c for c in done_cols if done[c].notna().any()]

    not_done = [s for s in needed if s.strip().lower() not in [c.lower() for c in completed]]

    result = pd.DataFrame([{
        "Card": card_num,
        "Current_Tons": tons,
        "Service Needed": " + ".join(needed),
        "Done": ", ".join(completed),
        "Not Done": ", ".join(not_done)
    }])

    st.dataframe(result, use_container_width=True)

    if st.button("💾 حفظ النتيجة"):
        result.to_excel("Machine_Result.xlsx", index=False)
        st.success("✅ تم حفظ النتيجة محليًا.")


# ===============================
# 🖥 واجهة Streamlit
# ===============================
st.title("🏭 CMMS - Bail Yarn")

if st.button("🔄 تحديث البيانات من GitHub"):
    st.cache_data.clear()
    sheets = load_excel_with_fingerprint()
    st.success("✅ تم تحديث البيانات من GitHub")
else:
    if check_access() or st.session_state.get("access_granted", False):
        sheets = load_excel_with_fingerprint()
    else:
        st.stop()

# عرض البصمة وآخر تحديث
if "file_fingerprint" in st.session_state:
    st.info(f"🧾 بصمة الملف: {st.session_state['file_fingerprint']}")
if "last_update_time" in st.session_state:
    st.caption(f"🕒 آخر تحديث: {st.session_state['last_update_time']}")

# قسم التعديل / الإضافة
st.subheader("🛠 تعديل البيانات")
sheet_name = st.selectbox("اختر الشيت:", list(sheets.keys()))
df = sheets[sheet_name]
st.dataframe(df, use_container_width=True)

if st.button("💾 حفظ التعديلات ورفعها إلى GitHub"):
    df.to_excel(LOCAL_FILE, index=False)
    upload_to_github(LOCAL_FILE, REPO_NAME, FILE_PATH)

# قسم فحص الماكينة
st.subheader("📊 فحص حالة الماكينة")
card_num = st.number_input("رقم الماكينة:", min_value=1, step=1)
tons = st.number_input("عدد الأطنان:", min_value=0, step=100)
if st.button("عرض الحالة"):
    show_machine_status(card_num, tons, sheets)
