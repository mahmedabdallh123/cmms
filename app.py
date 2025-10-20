import streamlit as st
import pandas as pd

# ===============================
# 📦 رابط ملف Excel على GitHub
# ===============================
GITHUB_EXCEL_URL = "https://github.com/mahmedabdallh123/cmms/raw/refs/heads/main/Machine_Service_Lookup.xlsx"

# ===============================
# ⚙️ تحميل جميع الشيتات من GitHub
# ===============================
@st.cache_data(ttl=3600)
def load_all_sheets():
    try:
        all_sheets = pd.read_excel(GITHUB_EXCEL_URL, sheet_name=None)
        return all_sheets
    except Exception as e:
        st.error(f"❌ خطأ أثناء تحميل الملف من GitHub:\n{e}")
        return None

# ===============================
# 🔍 تحديد الصيانة المطلوبة من ServicePlan
# ===============================
def get_required_service(service_df, tones):
    for _, row in service_df.iterrows():
        if row['Min_Tones'] <= tones <= row['Max_Tones']:
            return str(row['Service'])
    return "❌ لا توجد صيانة محددة لهذا النطاق"

# ===============================
# 🧮 مقارنة المطلوب مع المنفذ في شيت الماكينة
# ===============================
def compare_services(required_service, machine_df):
    # استخراج الخدمات المطلوبة من النص
    required_list = [x.strip() for x in str(required_service).split("+")]

    # الأعمدة اللي فيها علامة ✔ تعتبر منفذة
    done_services = []
    for col in machine_df.columns:
        if machine_df[col].astype(str).str.contains("✔").any():
            done_services.append(col)

    # مقارنة المطلوب مع المنفذ
    done = [s for s in required_list if any(d in s for d in done_services)]
    not_done = [s for s in required_list if s not in done]
    return done, not_done

# ===============================
# 🚀 واجهة Streamlit
# ===============================
st.set_page_config(page_title="CMMS - Mini System", layout="wide")
st.title("🧰 Mini CMMS - نظام الصيانة المصغر")

all_sheets = load_all_sheets()
if not all_sheets:
    st.stop()

# تحديد الجداول الثابتة
service_plan = all_sheets.get("ServicePlan")
machine_table = all_sheets.get("Machine")

if not all([service_plan is not None, machine_table is not None]):
    st.error("❌ تأكد أن الشيتات داخل الملف فيها 'ServicePlan' و 'Machine'")
    st.stop()

# إدخال المستخدم
machine_id = st.number_input("🆔 أدخل رقم الماكينة:", min_value=1, max_value=24, step=1)
tones = st.number_input("⚙️ أدخل عدد الأطنان الحالية:", min_value=0, step=10)

if st.button("🔍 تحليل الصيانة"):
    required_service = get_required_service(service_plan, tones)
    st.subheader("📋 الصيانة المطلوبة عند هذا العدد من الأطنان:")
    st.write(required_service)

    # تحديد شيت الماكينة بناءً على الرقم
    machine_sheet_name = str(machine_id)
    if machine_sheet_name in all_sheets:
        machine_df = all_sheets[machine_sheet_name]

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
        st.error(f"❌ لم يتم العثور على شيت باسم {machine_sheet_name} في الملف.")

