import streamlit as st
import pandas as pd
import re
import requests
import shutil

# ===============================
# ⚙️ إعدادات أساسية
# ===============================
GITHUB_EXCEL_URL = ""https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx""
PASSWORD = "1234"

# ===============================
# 📂 تحميل البيانات من GitHub
# ===============================
@st.cache_data(show_spinner=False)
def load_all_sheets():
    local_file = "Machine_Service_Lookup.xlsx"
    r = requests.get(GITHUB_EXCEL_URL, stream=True)
    with open(local_file, 'wb') as f:
        shutil.copyfileobj(r.raw, f)
    sheets = pd.read_excel(local_file, sheet_name=None)
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
# 🔍 تحليل حالة الماكينة
# ===============================
def check_machine_status(card_num, current_tons, all_sheets):
    if "ServicePlan" not in all_sheets:
        st.error("❌ الملف لازم يحتوي على شيت 'ServicePlan'")
        return

    service_plan_df = all_sheets["ServicePlan"]
    card_sheet_name = f"Card{card_num}"
    if card_sheet_name not in all_sheets:
        st.warning(f"⚠ لا يوجد شيت باسم {card_sheet_name}")
        return
    card_df = all_sheets[card_sheet_name]

    # حفظ اختيار النطاق في session
    if "view_option" not in st.session_state:
        st.session_state.view_option = "الشريحة الحالية فقط"

    # ===============================
    # ⚙️ إدخال نطاق العرض
    # ===============================
    st.subheader("⚙️ نطاق العرض")
    view_option = st.radio(
        "اختر نطاق العرض:",
        ("الشريحة الحالية فقط", "كل الشرائح الأقل", "كل الشرائح الأعلى", "نطاق مخصص", "كل الشرائح"),
        horizontal=True,
        key="view_option"
    )

    # النطاق المخصص (يتخزن كمان)
    min_range = st.session_state.get("min_range", max(0, current_tons - 500))
    max_range = st.session_state.get("max_range", current_tons + 500)

    if view_option == "نطاق مخصص":
        st.markdown("#### 🔢 أدخل النطاق المخصص")
        col1, col2 = st.columns(2)
        with col1:
            min_range = st.number_input("من (طن):", min_value=0, step=100, value=min_range, key="min_range")
        with col2:
            max_range = st.number_input("إلى (طن):", min_value=min_range, step=100, value=max_range, key="max_range")

    # ===============================
    # 🎯 تحديد النطاق حسب الاختيار
    # ===============================
    if view_option == "الشريحة الحالية فقط":
        selected_slices = service_plan_df[
            (service_plan_df["Min_Tones"] <= current_tons) &
            (service_plan_df["Max_Tones"] >= current_tons)
        ]
    elif view_option == "كل الشرائح الأقل":
        selected_slices = service_plan_df[service_plan_df["Max_Tones"] <= current_tons]
    elif view_option == "كل الشرائح الأعلى":
        selected_slices = service_plan_df[service_plan_df["Min_Tones"] >= current_tons]
    elif view_option == "نطاق مخصص":
        selected_slices = service_plan_df[
            (service_plan_df["Min_Tones"] >= min_range) &
            (service_plan_df["Max_Tones"] <= max_range)
        ]
    else:
        selected_slices = service_plan_df.copy()

    if selected_slices.empty:
        st.warning("⚠ لا توجد شرائح مطابقة حسب النطاق المحدد.")
        return

    # ===============================
    # 🧮 تحليل البيانات
    # ===============================
    all_results = []
    for _, current_slice in selected_slices.iterrows():
        needed_service_raw = current_slice["Service"]
        needed_parts = split_needed_services(needed_service_raw)
        needed_norm = [normalize_name(p) for p in needed_parts]

        done_services, last_date, last_tons = [], "-", "-"
        for _, row in card_df.iterrows():
            if row.get("Min_Tones", 0) <= current_tons <= row.get("Max_Tones", 0):
                for col in card_df.columns:
                    if col not in ["card", "Tones", "Min_Tones", "Max_Tones", "Date"]:
                        val = str(row.get(col, "")).strip()
                        if val and val.lower() not in ["nan", "none", ""]:
                            done_services.append(col)
                last_date = row.get("Date", "-")
                last_tons = row.get("Tones", "-")

        done_norm = [normalize_name(c) for c in done_services]
        not_done = [orig for orig, n in zip(needed_parts, needed_norm) if n not in done_norm]

        all_results.append({
            "Min_Tons": current_slice["Min_Tones"],
            "Max_Tons": current_slice["Max_Tones"],
            "Service Needed": " + ".join(needed_parts) if needed_parts else "-",
            "Done Services": ", ".join(done_services) if done_services else "-",
            "Not Done Services": ", ".join(not_done) if not_done else "-",
            "Last Date": last_date,
            "Last Tones": last_tons,
        })

    result_df = pd.DataFrame(all_results)

    # ===============================
    # 🎨 عرض الجدول
    # ===============================
    def highlight_cell(val, col_name):
        if col_name == "Service Needed":
            return "background-color: #fff3cd; color:#856404; font-weight:bold;"
        elif col_name == "Done Services":
            return "background-color: #d4edda; color:#155724; font-weight:bold;"
        elif col_name == "Not Done Services":
            return "background-color: #f8d7da; color:#721c24; font-weight:bold;"
        elif col_name in ["Last Date", "Last Tones"]:
            return "background-color: #e7f1ff; color:#004085;"
        return ""

    def style_table(row):
        return [highlight_cell(row[col], col) for col in row.index]

    st.dataframe(result_df.style.apply(style_table, axis=1), use_container_width=True)

# ===============================
# 🖥 الواجهة الرئيسية
# ===============================
st.title("🏭 سيرفيس تحضيرات Bail Yarn")

all_sheets = load_all_sheets()

col1, col2 = st.columns(2)
with col1:
    card_num = st.number_input("رقم الماكينة:", min_value=1, step=1, key="card_num")
with col2:
    current_tons = st.number_input("عدد الأطنان الحالية:", min_value=0, step=100, key="current_tons")

if st.button("عرض الحالة"):
    st.session_state["show_results"] = True

# حفظ عرض النتائج بعد الضغط
if st.session_state.get("show_results", False):
    check_machine_status(st.session_state.card_num, st.session_state.current_tons, all_sheets)
