import streamlit as st
import pandas as pd
import re
import time
import json
import os
import streamlit.components.v1 as components

# ===============================
# 📂 تحميل البيانات من GitHub
# ===============================
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx"

@st.cache_data
def load_all_sheets():
    try:
        return pd.read_excel(GITHUB_EXCEL_URL, sheet_name=None)
    except FileNotFoundError:
        st.error("❌ لم يتم العثور على ملف Machine_Service_Lookup.xlsx.")
        st.stop()
    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الملف من GitHub: {e}")
        st.stop()

# ===============================
# 🔑 نظام التجربة المجانية مع باسورد
# ===============================
TOKENS_FILE = "tokens.json"
TRIAL_SECONDS = 60
RENEW_HOURS = 24
PASSWORD = "1234"

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

def render_countdown(start_ts, seconds=TRIAL_SECONDS):
    html = f"""
    <div id="countdown" style="font-family:Segoe UI, Tahoma, Geneva, Verdana, sans-serif; margin-top:10px;">
      <h4>⏳ التجربة المجانية متبقي: <span id='secs'>--</span> ثانية</h4>
      <div style="width:100%; background:#eee; border-radius:6px; height:12px; margin-top:6px;">
        <div id="bar" style="height:12px; width:100%; background:#4caf50; border-radius:6px; transition:width 1s linear;"></div>
      </div>
    </div>

    <script>
    const start_ts = {int(start_ts)} * 1000;
    const total = {int(seconds)};
    function update(){{
      const now = Date.now();
      let elapsed = Math.floor((now - start_ts)/1000);
      if(elapsed < 0) elapsed = 0;
      let remaining = total - elapsed;
      if(remaining < 0) remaining = 0;
      document.getElementById('secs').innerText = remaining;
      document.getElementById('bar').style.width = (remaining/total*100) + '%';
      setTimeout(update, 1000);
    }}
    update();
    </script>
    """
    components.html(html, height=120)

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
            render_countdown(st.session_state["trial_start"], TRIAL_SECONDS)
            st.info("✅ التجربة المجانية مفعّلة — استخدم التطبيق الآن")
            return True
        else:
            st.warning("⏰ انتهت التجربة المجانية. يمكنك إعادة التجربة بعد مرور 24 ساعة أو الدخول بالباسورد.")
            password = st.text_input("أدخل كلمة المرور للوصول:", type="password")
            if password == PASSWORD:
                st.success("✅ تم تسجيل الدخول بنجاح بالباسورد.")
                st.session_state["access_granted"] = True
                return True
            return False

    if hours_since_last >= RENEW_HOURS:
        if st.button("تفعيل التجربة المجانية 60 ثانية"):
            tokens[user_id]["last_trial"] = now_ts
            save_tokens(tokens)
            st.session_state["trial_start"] = now_ts
            st.success("🎁 تم تفعيل التجربة المجانية لمدة 60 ثانية ⏳")
            st.experimental_rerun()
        return False

    remaining_hours = max(0, RENEW_HOURS - hours_since_last)
    st.warning(f"🔒 انتهت التجربة المجانية. يمكنك إعادة التجربة بعد {remaining_hours:.1f} ساعة أو الدخول بالباسورد.")
    password = st.text_input("أدخل كلمة المرور للوصول:", type="password")
    if password == PASSWORD:
        st.success("✅ تم تسجيل الدخول بنجاح بالباسورد.")
        st.session_state["access_granted"] = True
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
    s = re.sub(r"👦.*?👦", "", s)
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
        return None

    service_plan_df = all_sheets["ServicePlan"]
    card_sheet_name = f"Card{card_num}"
    if card_sheet_name not in all_sheets:
        st.warning(f"⚠ لا يوجد شيت باسم {card_sheet_name}")
        return None

    # ✅ تم التصحيح هنا (Min_Tones بدل Min_Tons)
    current_slice = service_plan_df[
        (service_plan_df["Min_Tones"] <= current_tons) &
        (service_plan_df["Max_Tones"] >= current_tons)
    ]

    if current_slice.empty:
        st.warning("⚠ لم يتم العثور على شريحة تناسب عدد الأطنان الحالي.")
        return None

    min_tons = current_slice["Min_Tones"].values[0]
    max_tons = current_slice["Max_Tones"].values[0]
    needed_service_raw = current_slice["Service"].values[0]
    needed_parts = split_needed_services(needed_service_raw)
    needed_norm = [normalize_name(p) for p in needed_parts]

    card_df = all_sheets[card_sheet_name]
    slice_df = card_df[
        (card_df["Min_Tones"] == min_tons) &
        (card_df["Max_Tones"] == max_tons)
    ]

    done_services, last_date, last_tons = [], "-", "-"
    status = "❌ لم يتم تنفيذ صيانة في هذه الشريحة"

    if not slice_df.empty:
        last_row = slice_df.iloc[-1]
        last_date = last_row.get("Date", "-")
        last_tons = last_row.get("Tones", "-")

        ignore_cols = ["card", "Tones", "Date", "Min_Tones", "Max_Tones"]
        for col in card_df.columns:
            if col not in ignore_cols:
                val = str(last_row.get(col, "")).strip().lower()
                if val and val not in ["nan", "none", ""]:
                    done_services.append(col)
        if done_services:
            status = "✅ تم تنفيذ صيانة في هذه الشريحة"

    done_norm = [normalize_name(c) for c in done_services]
    not_done = [orig for orig, n in zip(needed_parts, needed_norm) if n not in done_norm]

    result = {
        "Card": card_num,
        "Current_Tons": current_tons,
        "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
        "Done Services": ", ".join(done_services) if done_services else "-",
        "Not Done Services": ", ".join(not_done) if not_done else "-",
        "Date": last_date,
        "Tones": last_tons,
        "Status": status,
    }

    result_df = pd.DataFrame([result])

    def highlight_cell(val, col_name):
        if col_name == "Service Needed":
            return "background-color: #fff3cd; color:#856404; font-weight:bold;"
        elif col_name == "Done Services":
            return "background-color: #d4edda; color:#155724; font-weight:bold;"
        elif col_name == "Not Done Services":
            return "background-color: #f8d7da; color:#721c24; font-weight:bold;"
        elif col_name == "Status":
            if "✅" in val:
                return "background-color:#c3e6cb; color:#155724;"
            else:
                return "background-color:#f5c6cb; color:#721c24;"
        return ""

    def style_table(row):
        return [highlight_cell(row[col], col) for col in row.index]

    styled_df = result_df.style.apply(style_table, axis=1)
    st.dataframe(styled_df, use_container_width=True)

# ===============================
# 🖥 واجهة Streamlit
# ===============================
st.title("🔧 نظام متابعة الصيانة التنبؤية")

if check_free_trial(user_id="default_user") or st.session_state.get("access_granted", False):
    all_sheets = load_all_sheets()
    st.write("أدخل رقم الماكينة وعدد الأطنان الحالية لمعرفة حالة الصيانة")
    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1)
    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100)
    if st.button("عرض الحالة"):
        check_machine_status(card_num, current_tons, all_sheets)
