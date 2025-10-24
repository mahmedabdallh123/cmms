import streamlit as st
import pandas as pd
import re
import requests
import shutil

# ===============================
# ⚙️ إعدادات أساسية
# ===============================
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx"
PASSWORD = "1234"

# ===============================
# 📂 تحميل البيانات من GitHub
# ===============================
@st.cache_data(show_spinner=False)
def load_all_sheets():
    try:
        local_file = "Machine_Service_Lookup.xlsx"
        r = requests.get(GITHUB_EXCEL_URL, stream=True)
        with open(local_file, 'wb') as f:
            shutil.copyfileobj(r.raw, f)
        sheets = pd.read_excel(local_file, sheet_name=None)
        for name, df in sheets.items():
            df.columns = df.columns.str.strip()
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الملف من GitHub: {e}")
        st.stop()

# ===============================
# 🎨 واجهة تسجيل الدخول بالباسورد فقط
# ===============================
def check_access():
    if st.session_state.get("access_granted", False):
        return True

    # تصميم الكارت
    st.markdown(
        """
        <style>
        .login-box {
            background-color: #f9f9f9;
            padding: 40px;
            border-radius: 20px;
            box-shadow: 0 0 15px rgba(0,0,0,0.1);
            width: 380px;
            margin: 120px auto;
            text-align: center;
        }
        .login-title {
            font-size: 26px;
            color: #333;
            margin-bottom: 20px;
            font-weight: bold;
        }
        </style>
        """,
        unsafe_allow_html=True
    )

    st.markdown('<div class="login-box"><div class="login-title">🔒 تسجيل الدخول</div>', unsafe_allow_html=True)

    password = st.text_input("أدخل كلمة المرور للوصول:", type="password")

    if st.button("تأكيد الدخول"):
        if password == PASSWORD:
            st.session_state["access_granted"] = True
            st.success("✅ تم تسجيل الدخول بنجاح.")
            st.rerun()
        else:
            st.error("❌ كلمة المرور غير صحيحة.")
    
    st.markdown("</div>", unsafe_allow_html=True)
    return False

# ===============================
# 🧰 دوال النظام
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
    current_slice = service_plan_df[
        (service_plan_df["Min_Tones"] <= current_tons) &
        (service_plan_df["Max_Tones"] >= current_tons)
    ]

    if current_slice.empty:
        st.warning("⚠ لم يتم العثور على شريحة تناسب عدد الأطنان الحالي.")
        return

    needed_service_raw = current_slice["Service"].values[0]
    needed_parts = split_needed_services(needed_service_raw)
    needed_norm = [normalize_name(p) for p in needed_parts]

    done_services, last_date, last_tons = [], "-", "-"
    for idx, row in card_df.iterrows():
        row_min = row.get("Min_Tones", 0)
        row_max = row.get("Max_Tones", 0)
        if row_min <= current_tons <= row_max:
            row_done = []
            ignore_cols = ["card", "Tones", "Min_Tones", "Max_Tones", "Date"]
            for col in card_df.columns:
                if col not in ignore_cols:
                    val = str(row.get(col, "")).strip()
                    if val and val.lower() not in ["nan", "none", ""]:
                        row_done.append(col)
            done_services.extend(row_done)
            last_date = row.get("Date", "-")
            last_tons = row.get("Tones", "-")

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
    }

    result_df = pd.DataFrame([result])

    def highlight_cell(val, col_name):
        if col_name == "Service Needed":
            return "background-color: #fff3cd; color:#856404; font-weight:bold;"
        elif col_name == "Done Services":
            return "background-color: #d4edda; color:#155724; font-weight:bold;"
        elif col_name == "Not Done Services":
            return "background-color: #f8d7da; color:#721c24; font-weight:bold;"
        elif col_name in ["Date", "Tones"]:
            return "background-color: #e7f1ff; color:#004085;"
        return ""

    def style_table(row):
        return [highlight_cell(row[col], col) for col in row.index]

    styled_df = result_df.style.apply(style_table, axis=1)
    st.dataframe(styled_df, use_container_width=True)

    if st.button("💾 حفظ النتيجة في Excel"):
        result_df.to_excel("Machine_Result.xlsx", index=False)
        st.success("✅ تم حفظ النتيجة في ملف 'Machine_Result.xlsx' بنجاح.")

# ===============================
# 🖥 واجهة البرنامج الرئيسية
# ===============================
st.title("🔧 سيرفيس تحضيرات بيل يارن 1")

if "refresh_data" not in st.session_state:
    st.session_state["refresh_data"] = False

if st.button("refresh data "):
    st.session_state["refresh_data"] = True

if check_access():
    if st.session_state["refresh_data"]:
        load_all_sheets.clear()
        st.session_state["refresh_data"] = False

    all_sheets = load_all_sheets()
    st.write("أدخل رقم الماكينة وعدد الأطنان الحالية لمعرفة حالة الصيانة")
    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1)
    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100)
    if st.button("عرض الحالة"):
        check_machine_status(card_num, current_tons, all_sheets)
