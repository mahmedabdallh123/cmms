import pandas as pd
import requests
import os
from github import Github
from base64 import b64decode

# ===============================
# إعدادات
# ===============================
REPO_NAME = "mahmedabdallh123/input-data"
BRANCH = "main"
FILE_PATH = "Machine_Service_Lookup.xlsx"
LOCAL_FILE = "Machine_Service_Lookup.xlsx"

# ===============================
# تحميل Excel من GitHub (مرة واحدة لو مش موجود محلياً)
# ===============================
def fetch_excel_if_missing():
    """📥 تحميل ملف Excel من GitHub (بجميع الشيتات) إذا لم يكن موجوداً محلياً"""
    if not os.path.exists(LOCAL_FILE):
        st.info("📥 تحميل الملف من GitHub عبر API...")
        try:
            # 🔒 قراءة التوكين من Streamlit secrets
            token = st.secrets["github"]["token"]
            g = Github(token)
            repo = g.get_repo(REPO_NAME)

            # 📦 جلب المحتوى من GitHub بالفرع المحدد
            file_content = repo.get_contents(FILE_PATH, ref=BRANCH)
            content = b64decode(file_content.content)  # فك الترميز Base64

            # 💾 حفظ الملف محلياً كما هو (بصيغة Excel أصلية)
            with open(LOCAL_FILE, "wb") as f:
                f.write(content)

            st.success("✅ تم تحميل الملف من GitHub بنجاح (بجميع الشيتات).")

        except Exception as e:
            st.error(f"⚠ فشل تحميل الملف من GitHub: {e}")
            st.stop()
    else:
        st.info("📄 الملف موجود محلياً بالفعل.")

# ===============================
# تحميل الشيتات (كل الأعمدة نصوص لتسهيل الكتابة)
# ===============================
@st.cache_data
def load_sheets():
    sheets = pd.read_excel(LOCAL_FILE, sheet_name=None, dtype=object)
    for name, df in sheets.items():
        df.columns = df.columns.str.strip()
    return sheets

# ===============================
# دالة حفظ محلي + رفع على GitHub + مسح الكاش + إعادة تحميل
# ===============================
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

# ===============================
# واجهة المستخدم
# ===============================
st.title("🛠 CMMS - تعديل وإضافة بيانات (GitHub)")

# تأكد من وجود الملف المحلي (تنزيله لو مكنش موجود)
fetch_excel_if_missing()

# نحمل الشيتات (مخبأة)
sheets = load_sheets()

tab1, tab2, tab3, tab4 = st.tabs([
    "عرض وتعديل شيت",
    "إضافة صف جديد (أحداث متتالية)",
    "إضافة عمود جديد",
    "🗑 حذف صف"
])


# -------------------------------
# Tab 1: تعديل بيانات وعرض
# -------------------------------
with tab1:
    st.subheader("✏ تعديل البيانات")

    sheet_name = st.selectbox("اختر الشيت:", list(sheets.keys()), key="edit_sheet")
    df = sheets[sheet_name].astype(str)

    edited_df = st.data_editor(df, num_rows="dynamic")

    if st.button("💾 حفظ التعديلات", key=f"save_edit_{sheet_name}"):
        sheets[sheet_name] = edited_df.astype(object)
        new_sheets = save_local_excel_and_push(
            sheets,
            commit_message=f"Edit sheet {sheet_name}"
        )
        if isinstance(new_sheets, dict):
            sheets = new_sheets
        st.dataframe(sheets[sheet_name])


# -------------------------------
# Tab 2: إضافة صف جديد (أحداث متعددة بنفس الرينج)
# -------------------------------
with tab2:
    st.subheader("➕ إضافة صف جديد (سجل حدث جديد داخل نفس الرينج)")

    sheet_name_add = st.selectbox(
        "اختر الشيت لإضافة صف:",
        list(sheets.keys()),
        key="add_sheet"
    )

    df_add = sheets[sheet_name_add].astype(str).reset_index(drop=True)
    st.markdown("أدخل بيانات الحدث (يمكنك إدخال أي نص/أرقام/تواريخ)")

    new_data = {}
    for col in df_add.columns:
        new_data[col] = st.text_input(f"{col}", key=f"add_{sheet_name_add}_{col}")

    if st.button("💾 إضافة الصف الجديد", key=f"add_row_{sheet_name_add}"):

        # تحويل الإدخال إلى DataFrame
        new_row_df = pd.DataFrame([new_data]).astype(str)

        # البحث عن أعمدة الرينج
        min_col, max_col, card_col = None, None, None
        for c in df_add.columns:
            c_low = c.strip().lower()
            if c_low in ("min_tones", "min_tone", "min tones", "min"):
                min_col = c
            if c_low in ("max_tones", "max_tone", "max tones", "max"):
                max_col = c
            if c_low in ("card", "machine", "machine_no", "machine id"):
                card_col = c

        if not min_col or not max_col:
            st.error("⚠ لم يتم العثور على أعمدة Min_Tones و/أو Max_Tones في الشيت.")
        else:
            def to_num_or_none(x):
                try:
                    return float(x)
                except:
                    return None

            new_min_raw = str(new_data.get(min_col, "")).strip()
            new_max_raw = str(new_data.get(max_col, "")).strip()
            new_min_num = to_num_or_none(new_min_raw)
            new_max_num = to_num_or_none(new_max_raw)

            # البحث عن موضع الإدراج
            insert_pos = len(df_add)
            mask = pd.Series([False] * len(df_add))

            if card_col:
                new_card = str(new_data.get(card_col, "")).strip()
                if new_card != "":
                    if new_min_num is not None and new_max_num is not None:
                        mask = (
                            (df_add[card_col].astype(str).str.strip() == new_card) &
                            (pd.to_numeric(df_add[min_col], errors='coerce') == new_min_num) &
                            (pd.to_numeric(df_add[max_col], errors='coerce') == new_max_num)
                        )
                    else:
                        mask = (
                            (df_add[card_col].astype(str).str.strip() == new_card) &
                            (df_add[min_col].astype(str).str.strip() == new_min_raw) &
                            (df_add[max_col].astype(str).str.strip() == new_max_raw)
                        )
            else:
                if new_min_num is not None and new_max_num is not None:
                    mask = (
                        (pd.to_numeric(df_add[min_col], errors='coerce') == new_min_num) &
                        (pd.to_numeric(df_add[max_col], errors='coerce') == new_max_num)
                    )
                else:
                    mask = (
                        (df_add[min_col].astype(str).str.strip() == new_min_raw) &
                        (df_add[max_col].astype(str).str.strip() == new_max_raw)
                    )

            st.write("DEBUG: new_min_raw, new_max_raw:", new_min_raw, new_max_raw)
            st.write("DEBUG: Found match count:", mask.sum())

            if mask.any():
                insert_pos = mask[mask].index[-1] + 1
            else:
                try:
                    df_add["_min_num"] = pd.to_numeric(df_add[min_col], errors='coerce').fillna(-1)
                    if new_min_num is not None:
                        insert_pos = int((df_add["_min_num"] < new_min_num).sum())
                    else:
                        insert_pos = len(df_add)
                    df_add = df_add.drop(columns=["_min_num"])
                except Exception:
                    insert_pos = len(df_add)

            df_top = df_add.iloc[:insert_pos].reset_index(drop=True)
            df_bottom = df_add.iloc[insert_pos:].reset_index(drop=True)
            df_new = pd.concat(
                [df_top, new_row_df.reset_index(drop=True), df_bottom],
                ignore_index=True
            )

            sheets[sheet_name_add] = df_new.astype(object)
            new_sheets = save_local_excel_and_push(
                sheets,
                commit_message=f"Add new row under range {new_min_raw}-{new_max_raw} in {sheet_name_add}"
            )

            if isinstance(new_sheets, dict):
                sheets = new_sheets

            st.success("✅ تم الإضافة — تم إدراج الصف في الموقع المناسب.")
            st.dataframe(sheets[sheet_name_add])


# -------------------------------
# Tab 3: إضافة عمود جديد
# -------------------------------
with tab3:
    st.subheader("🆕 إضافة عمود جديد")

    sheet_name_col = st.selectbox(
        "اختر الشيت لإضافة عمود:",
        list(sheets.keys()),
        key="add_col_sheet"
    )

    df_col = sheets[sheet_name_col].astype(str)
    new_col_name = st.text_input("اسم العمود الجديد:")
    default_value = st.text_input("القيمة الافتراضية لكل الصفوف (اختياري):", "")

    if st.button("💾 إضافة العمود الجديد", key=f"add_col_{sheet_name_col}"):
        if new_col_name:
            df_col[new_col_name] = default_value
            sheets[sheet_name_col] = df_col.astype(object)
            new_sheets = save_local_excel_and_push(
                sheets,
                commit_message=f"Add new column '{new_col_name}' to {sheet_name_col}"
            )
            if isinstance(new_sheets, dict):
                sheets = new_sheets
            st.success("✅ تم إضافة العمود الجديد بنجاح!")
            st.dataframe(sheets[sheet_name_col])
        else:
            st.warning("⚠ الرجاء إدخال اسم العمود الجديد.")
# -------------------------------
# Tab 4: حذف صف
# -------------------------------
with tab4:
    st.subheader("🗑 حذف صف من الشيت")

    sheet_name_del = st.selectbox("اختر الشيت:", list(sheets.keys()), key="delete_sheet")
    df_del = sheets[sheet_name_del].astype(str).reset_index(drop=True)

    st.markdown("### 📋 بيانات الشيت الحالية")
    st.dataframe(df_del)

    st.markdown("### ✏ اختر الصفوف التي تريد حذفها (برقم الصف):")
    st.write("💡 ملاحظة: رقم الصف يبدأ من 0 (أول صف = 0)")

    rows_to_delete = st.text_input("أدخل أرقام الصفوف مفصولة بفاصلة (مثلاً: 0,2,5):")

    confirm_delete = st.checkbox("✅ أؤكد أني أريد حذف هذه الصفوف بشكل نهائي")

    if st.button("🗑 تنفيذ الحذف", key=f"delete_rows_{sheet_name_del}"):
        if rows_to_delete.strip() == "":
            st.warning("⚠ الرجاء إدخال رقم الصف أو أكثر.")
        elif not confirm_delete:
            st.warning("⚠ برجاء تأكيد الحذف أولاً بوضع علامة ✅ قبل التنفيذ.")
        else:
            try:
                # تحويل الإدخالات إلى أرقام صحيحة
                rows_list = [int(x.strip()) for x in rows_to_delete.split(",") if x.strip().isdigit()]
                rows_list = [r for r in rows_list if 0 <= r < len(df_del)]
                
                if not rows_list:
                    st.warning("⚠ لم يتم العثور على صفوف صحيحة.")
                else:
                    df_new = df_del.drop(rows_list).reset_index(drop=True)
                    sheets[sheet_name_del] = df_new.astype(object)

                    new_sheets = save_local_excel_and_push(sheets, commit_message=f"Delete rows {rows_list} from {sheet_name_del}")
                    if isinstance(new_sheets, dict):
                        sheets = new_sheets
                        st.success(f"✅ تم حذف الصفوف التالية بنجاح: {rows_list}")
                        st.dataframe(sheets[sheet_name_del])
            except Exception as e:
                st.error(f"حدث خطأ أثناء الحذف: {e}")
