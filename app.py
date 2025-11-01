import streamlit as st
import pandas as pd
import re
import time
import json
import os
import requests
import shutil
import hashlib

# ===============================
# ⚙ إعدادات أساسية
# ===============================
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx"
TOKENS_FILE = "tokens.json"
TRIAL_SECONDS = 60
RENEW_HOURS = 24
PASSWORD = "1234"

# ===============================
# 🧠 توليد بصمة (Fingerprint)
# ===============================
def generate_fingerprint_url(base_url):
    timestamp = int(time.time())
    return f"{base_url}?v={timestamp}"

@st.cache_data(ttl=0, show_spinner=False)
def load_all_sheets():
    try:
        local_file = "Machine_Service_Lookup.xlsx"
        fresh_url = generate_fingerprint_url(GITHUB_EXCEL_URL)

        r = requests.get(fresh_url, stream=True, headers={"Cache-Control": "no-cache"})
        if r.status_code != 200:
            raise Exception(f"GitHub returned {r.status_code}")

        with open(local_file, 'wb') as f:
            shutil.copyfileobj(r.raw, f)

        sheets = pd.read_excel(local_file, sheet_name=None)
        for name, df in sheets.items():
            df.columns = df.columns.str.strip()

        with open(local_file, "rb") as f:
            md5 = hashlib.md5(f.read()).hexdigest()

        st.session_state["file_fingerprint"] = md5
        st.session_state["last_update_time"] = time.strftime("%Y-%m-%d %H:%M:%S")

        return sheets

    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الملف من GitHub: {e}")
        st.stop()

# ===============================
# 🔑 نظام التجربة المجانية
# ===============================
def load_tokens():
    if not os.path.exists(TOKENS_FILE):
        with open(TOKENS_FILE, "w") as f:
            json.dump({}, f)
        return {}
    try:
        with open(TOKENS_FILE, "r") as f:
            content = f.read().strip()
            if not content:
                return {}
            return json.loads(content)
    except (json.JSONDecodeError, ValueError):
        with open(TOKENS_FILE, "w") as f:
            json.dump({}, f)
        return {}

def save_tokens(tokens):
    with open(TOKENS_FILE, "w") as f:
        json.dump(tokens, f, indent=4, ensure_ascii=False)

def check_free_trial(user_id="default_user"):
    tokens = load_tokens()
    now_ts = int(time.time())

    if user_id not in tokens:
        tokens[user_id] = {"last_trial": 0}
        save_tokens(tokens)

    last_trial = tokens[user_id]["last_trial"]
    hours_since_last = (now_ts - last_trial) / 3600

    if "trial_start" in st.session_state:
        elapsed = now_ts - st.session_state["trial_start"]
        if elapsed < TRIAL_SECONDS:
            st.info(f"✅ التجربة المجانية مفعّلة — متبقي {TRIAL_SECONDS - elapsed:.0f} ثانية")
            return True
        else:
            st.warning("⏰ انتهت التجربة المجانية. يمكنك إعادة التجربة بعد 24 ساعة أو الدخول بالباسورد.")
            password = st.text_input("أدخل كلمة المرور للوصول:", type="password")
            if password == PASSWORD:
                st.session_state["access_granted"] = True
                st.success("✅ تم تسجيل الدخول بالباسورد.")
                return True
            return False

    if hours_since_last >= RENEW_HOURS:
        if st.button("تفعيل التجربة المجانية 60 ثانية"):
            tokens[user_id]["last_trial"] = now_ts
            save_tokens(tokens)
            st.session_state["trial_start"] = now_ts
            st.experimental_rerun()
        return False

    remaining_hours = max(0, RENEW_HOURS - hours_since_last)
    st.warning(f"🔒 انتهت التجربة المجانية. يمكنك إعادة التجربة بعد {remaining_hours:.1f} ساعة أو الدخول بالباسورد.")
    password = st.text_input("أدخل كلمة المرور للوصول:", type="password")
    if password == PASSWORD:
        st.session_state["access_granted"] = True
        st.success("✅ تم تسجيل الدخول بالباسورد.")
        return True
    return False

# ===============================
# 🔠 دوال مساعدة
# ===============================
def normalize_name(s):
    if s is None:
        return ""
    s = str(s)
    s = s.replace("\n", "+")
    s = re.sub(r"[^0-9a-zA-Z\u0600-\u06FF\+\s_/.-]", " ", s)
    s = re.sub(r"\s+", " ", s).strip().lower()
    return s

def split_needed_services(needed_service_str):
    if not isinstance(needed_service_str, str) or needed_service_str.strip() == "":
        return []
    parts = re.split(r"\+|,|\n|;", needed_service_str)
    return [p.strip() for p in parts if p.strip() != ""]

# ===============================
# ⚙ دالة مقارنة الصيانة
# ===============================
def check_machine_status(card_num, current_tons, all_sheets):
    if "ServicePlan" not in all_sheets or "Machine" not in all_sheets:
        st.error("❌ الملف لازم يحتوي على شيتين: 'Machine' و 'ServicePlan'")
        return

    service_plan_df = all_sheets["ServicePlan"]
    card_sheet_name = f"Card{card_num}"
    if card_sheet_name not in all_sheets:
        st.warning(f"⚠ لا يوجد شيت باسم {card_sheet_name}")
        return

    card_df = all_sheets[card_sheet_name]

    # الرنج الحالي
    current_slice = service_plan_df[
        (service_plan_df["Min_Tones"] <= current_tons) &
        (service_plan_df["Max_Tones"] >= current_tons)
    ]

    if current_slice.empty:
        st.warning("⚠ لم يتم العثور على شريحة تناسب عدد الأطنان الحالي.")
        return

    min_tons = current_slice["Min_Tones"].values[0]
    max_tons = current_slice["Max_Tones"].values[0]
    needed_service_raw = current_slice["Service"].values[0]
    needed_parts = split_needed_services(needed_service_raw)
    needed_norm = [normalize_name(p) for p in needed_parts]

    # الأعمدة الخاصة بالصيانة
    ignore_cols = ["card", "Tones", "Date", "Min_Tones", "Max_Tones"]

    done_services, last_date, last_tons = [], "-", "-"
    all_done_services_norm = []

    for _, row in card_df.iterrows():
        row_services = []
        for col in card_df.columns:
            if col not in ignore_cols:
                val = str(row.get(col, "")).strip().lower()
                if val and val not in ["nan", "none", ""]:
                    row_services.append(col)
        row_norm = [normalize_name(c) for c in row_services]
        all_done_services_norm.extend(row_norm)

        if min_tons <= row.get("Tones", 0) <= max_tons:
            done_services.extend(row_services)
            last_date = row.get("Date", "-")
            last_tons = row.get("Tones", "-")

    done_norm = [normalize_name(c) for c in done_services]
    not_done = [orig for orig, n in zip(needed_parts, needed_norm) if n not in done_norm]

    # ✅ تجميع كل الأعمدة الأخرى الجديدة وإظهارها
    extra_cols = [c for c in card_df.columns if c not in ignore_cols and normalize_name(c) not in needed_norm]
    last_row = card_df.iloc[-1] if not card_df.empty else {}

    extra_data = {col: last_row.get(col, "-") for col in extra_cols}

    # ✅ دمج النتيجة النهائية
    result = {
        "Card": card_num,
        "Current_Tons": current_tons,
        "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
        "Done Services": ", ".join(done_services) if done_services else "-",
        "Not Done Services": ", ".join(not_done) if not_done else "-",
        "Date": last_date,
        "Tones": last_tons,
    }
    result.update(extra_data)

    result_df = pd.DataFrame([result])
    st.dataframe(result_df, use_container_width=True)

    if st.button("💾 حفظ النتيجة في Excel"):
        result_df.to_excel("Machine_Result.xlsx", index=False)
        st.success("✅ تم حفظ النتيجة في ملف 'Machine_Result.xlsx' بنجاح.")

# ===============================
# 🖥 واجهة Streamlit
# ===============================
st.title("🔧 نظام متابعة الصيانة التنبؤية")

if st.button("🔄 تحديث البيانات من GitHub"):
    st.cache_data.clear()
    all_sheets = load_all_sheets()
    st.success("✅ تم تحديث البيانات من GitHub بنجاح.")
else:
    if check_free_trial(user_id="default_user") or st.session_state.get("access_granted", False):
        all_sheets = load_all_sheets()

if "file_fingerprint" in st.session_state:
    st.info(f"🧾 بصمة الملف: {st.session_state['file_fingerprint']}")
if "last_update_time" in st.session_state:
    st.caption(f"🕒 آخر تحديث: {st.session_state['last_update_time']}")

if 'all_sheets' in locals():
    st.write("أدخل رقم الماكينة وعدد الأطنان الحالية لمعرفة حالة الصيانة")
    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1)
    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100)
    if st.button("عرض الحالة"):
        check_machine_status(card_num, current_tons, all_sheets)
        
