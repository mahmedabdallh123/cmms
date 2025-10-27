import streamlit as st
import pandas as pd
import requests
import os
from github import Github

# ===============================
# إعدادات
# ===============================
REPO_NAME = "mahmedabdallh123/input-data"
BRANCH = "main"
FILE_PATH = "Machine_Service_Lookup.xlsx"
LOCAL_FILE = "Machine_Service_Lookup.xlsx"


def fetch_excel_if_missing():
    if not os.path.exists(LOCAL_FILE):
        st.info("📥 تحميل الملف من GitHub...")
        try:
            url = f"https://raw.githubusercontent.com/{REPO_NAME}/{BRANCH}/{FILE_PATH}"
            r = requests.get(url)
            r.raise_for_status()
            with open(LOCAL_FILE, "wb") as f:
                f.write(r.content)
            st.success("✅ تم تحميل الملف بنجاح.")
        except Exception as e:
            st.error(f"⚠ فشل تحميل الملف: {e}")
            st.stop()


@st.cache_data
def load_sheets():
    sheets = pd.read_excel(LOCAL_FILE, sheet_name=None, dtype=object)
    for name, df in sheets.items():
        df.columns = df.columns.str.strip()
    return sheets


def save_local_excel_and_push(sheets_dict, commit_message="Update from Streamlit"):
    with pd.ExcelWriter(LOCAL_FILE, engine="openpyxl") as writer:
        for name, sh in sheets_dict.items():
            try:
                sh.to_excel(writer, sheet_name=name, index=False)
            except Exception:
                sh.astype(object).to_excel(writer, sheet_name=name, index=False)

    try:
        token = st.secrets["github"]["token"]
    except Exception:
        st.error("🔒 GitHub token not found in Streamlit secrets. Please set it.")
        return False

    g = Github(token)
    repo = g.get_repo(REPO_NAME)

    with open(LOCAL_FILE, "rb") as f:
        content = f.read()

    try:
        contents = repo.get_contents(FILE_PATH, ref=BRANCH)
        repo.update_file(path=FILE_PATH, message=commit_message, content=content, sha=contents.sha, branch=BRANCH)
    except Exception as e:
        st.error(f"⚠ فشل رفع الملف إلى GitHub: {e}")
        return False

    st.cache_data.clear()
    new_sheets = load_sheets()
    st.success("✅ تم الحفظ والرفع على GitHub بنجاح.")
    return new_sheets


# ==============================================================
# 🧱 دالة واجهة التعديل
# ==============================================================
def show_edit_page():
    st.title("🛠 CMMS - تعديل وإضافة بيانات (GitHub)")

    fetch_excel_if_missing()
    sheets = load_sheets()

    tab1, tab2, tab3, tab4 = st.tabs([
        "عرض وتعديل شيت",
        "إضافة صف جديد (أحداث متتالية)",
        "إضافة عمود جديد",
        "🗑 حذف صف"
    ])

    # ==============================
    # Tab 1: تعديل بيانات
    # ==============================
    with tab1:
        st.subheader("✏ تعديل البيانات")
        sheet_name = st.selectbox("اختر الشيت:", list(sheets.keys()), key="edit_sheet")
        df = sheets[sheet_name].astype(str)
        edited_df = st.data_editor(df, num_rows="dynamic")
        if st.button("💾 حفظ التعديلات", key=f"save_edit_{sheet_name}"):
            sheets[sheet_name] = edited_df.astype(object)
            new_sheets = save_local_excel_and_push(sheets, commit_message=f"Edit sheet {sheet_name}")
            if isinstance(new_sheets, dict):
                sheets = new_sheets
                st.dataframe(sheets[sheet_name])

    # ==============================
    # Tab 2: إضافة صف جديد
    # ==============================
    with tab2:
        st.subheader("➕ إضافة صف جديد")
        sheet_name_add = st.selectbox("اختر الشيت لإضافة صف:", list(sheets.keys()), key="add_sheet")
        df_add = sheets[sheet_name_add].astype(str).reset_index(drop=True)
        new_data = {col: st.text_input(col, key=f"add_{sheet_name_add}_{col}") for col in df_add.columns}
        if st.button("💾 إضافة الصف الجديد", key=f"add_row_{sheet_name_add}"):
            new_row_df = pd.DataFrame([new_data]).astype(str)
            df_new = pd.concat([df_add, new_row_df], ignore_index=True)
            sheets[sheet_name_add] = df_new.astype(object)
            new_sheets = save_local_excel_and_push(sheets, commit_message=f"Add row in {sheet_name_add}")
            if isinstance(new_sheets, dict):
                sheets = new_sheets
                st.success("✅ تم إضافة الصف الجديد.")
                st.dataframe(sheets[sheet_name_add])

    # ==============================
    # Tab 3: إضافة عمود جديد
    # ==============================
    with tab3:
        st.subheader("🆕 إضافة عمود جديد")
        sheet_name_col = st.selectbox("اختر الشيت:", list(sheets.keys()), key="add_col_sheet")
        df_col = sheets[sheet_name_col].astype(str)
        new_col_name = st.text_input("اسم العمود الجديد:")
        default_value = st.text_input("القيمة الافتراضية:")
        if st.button("💾 إضافة العمود", key=f"add_col_{sheet_name_col}"):
            if new_col_name:
                df_col[new_col_name] = default_value
                sheets[sheet_name_col] = df_col.astype(object)
                new_sheets = save_local_excel_and_push(sheets, commit_message=f"Add column {new_col_name}")
                if isinstance(new_sheets, dict):
                    sheets = new_sheets
                    st.success("✅ تم إضافة العمود بنجاح.")
                    st.dataframe(sheets[sheet_name_col])

    # ==============================
    # Tab 4: حذف صف
    # ==============================
    with tab4:
        st.subheader("🗑 حذف صف")
        sheet_name_del = st.selectbox("اختر الشيت:", list(sheets.keys()), key="delete_sheet")
        df_del = sheets[sheet_name_del].astype(str).reset_index(drop=True)
        st.dataframe(df_del)
        rows_to_delete = st.text_input("أدخل أرقام الصفوف (مثلاً: 0,2,5)")
        confirm_delete = st.checkbox("تأكيد الحذف")
        if st.button("🗑 تنفيذ الحذف", key=f"delete_rows_{sheet_name_del}"):
            if confirm_delete and rows_to_delete.strip():
                try:
                    rows_list = [int(x) for x in rows_to_delete.split(",") if x.strip().isdigit()]
                    df_new = df_del.drop(rows_list).reset_index(drop=True)
                    sheets[sheet_name_del] = df_new.astype(object)
                    new_sheets = save_local_excel_and_push(sheets, commit_message=f"Delete rows {rows_list}")
                    if isinstance(new_sheets, dict):
                        sheets = new_sheets
                        st.success("✅ تم الحذف.")
                        st.dataframe(sheets[sheet_name_del])
                except Exception as e:
                    st.error(f"حدث خطأ: {e}")
