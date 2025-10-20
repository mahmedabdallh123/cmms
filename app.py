import streamlit as st
import pandas as pd

# =====================================
# 📂 رابط Excel على GitHub
# =====================================
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx"

# =====================================
# ⚙️ تحميل جميع الشيتات
# =====================================
@st.cache_data(ttl=3600)
def load_all_sheets():
    try:
        sheets = pd.read_excel(GITHUB_EXCEL_URL, sheet_name=None)
        return sheets
    except Exception as e:
        st.error(f"❌ خطأ في تحميل الملف: {e}")
        return None

# =====================================
# 🔍 تحديد الصيانة المطلوبة من ServicePlan
# =====================================
def get_required_service(service_plan_df, tones):
    match = service_plan_df[
        (service_plan_df["Min_Tons"] <= tones) &
        (service_plan_df["Max_Tons"] >= tones)
    ]
    if not match.empty:
        return match.iloc[0]["Service"]
    return "❌ لا توجد صيانة مطلوبة في هذا النطاق."

# =====================================
# 🧮 مقارنة المطلوب مع المنفذ في شيت الماكينة
# =====================================
def compare_services(required_service, machine_df):
    required_list = [x.strip() for x in str(required_service).replace("\n", "").split("+")]
    done_cols = [
        col for col in machine_df.columns
        if machine_df[col].astype(str).str.contains("✔").any()
    ]
    done = [s for s in required_list if any(d.lower() in s.lower() for d in done_cols)]
    not_done = [s for s in required_list if s not in done]
    return done, not_done

# =====================================
# 🚀 واجهة Streamlit
# =====================================
st.set_page_config(page_title="Mini CMMS", layout="wide")
st.title("🧰 Mini CMMS - نظام الصيانة المصغر")

all_sheets = load_all_sheets()
if not all_sheets:
    st.stop()

service_plan = all_sheets.get("ServicePlan")
machine_table = all_sheets.get("Machine")

if not all([service_plan is not None, machine_table is not None]):
    st.error("❌ تأكد أن الشيتات موجودة: ServicePlan و Machine")
    st.stop()

# =====================================
# 🧩 إدخال المستخدم
# =====================================
machine_id = st.number_input("🆔 رقم الماكينة:", min_value=1, max_value=24, step=1)
tones = st.number_input("⚙️ عدد الأطنان الحالية:", min_value=0, step=10)

if st.button("🔍 تحليل الصيانة"):
    required_service = get_required_service(service_plan, tones)
    st.subheader("📋 الصيانة المطلوبة:")
    st.write(required_service)

    sheet_name = f"Card{machine_id}"
    if sheet_name in all_sheets:
        machine_df = all_sheets[sheet_name]

        done, not_done = compare_services(required_service, machine_df)

        st.subheader("✅ الصيانات المنفذة:")
        if done:
            st.success(", ".join(done))
        else:
            st.info("لا توجد صيانات منفذة مطابقة.")

        st.subheader("❌ الصيانات غير المنفذة:")
        if not_done:
            st.warning(", ".join(not_done))
        else:
            st.success("كل الصيانات المطلوبة تم تنفيذها ✅")

        with st.expander("📄 عرض سجل الماكينة"):
            st.dataframe(machine_df)
    else:
        st.error(f"❌ لم يتم العثور على شيت باسم {sheet_name}.")
