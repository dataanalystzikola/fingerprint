import streamlit as st
import pandas as pd
from io import BytesIO

# --- 1. إعداد الصفحة والتطبيق ---
st.set_page_config(
    page_title="Attendance Data Analyzer",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("Attendance Data Analyzer (Check-In/Check-Out)")
st.markdown("يرجى رفع ملف البصمات النصي (`.txt`) بالصيغة المحددة لتحويله إلى جدول حضور وانصراف.")

# --- 2. عنصر رفع الملف (Uploader) ---
uploaded_file = st.file_uploader(
    "ارفع ملف البصمات (بصمه 222.txt أو أي ملف بنفس التنسيق)",
    type=["txt"]
)

if uploaded_file is not None:
    try:
        # --- 3. قراءة البيانات الأولية والمعالجة (Data Preprocessing) ---
        
        # قراءة الملف كوظيفة
        data = uploaded_file.getvalue().decode("utf-8")
        
        # تقسيم السطور وتنظيف المسافات البيضاء المتعددة واستبدال الفراغات بعلامة جدولة
        lines = data.strip().split('\n')
        processed_lines = []
        for line in lines:
            # تنظيف السطر من مسافات البداية/النهاية واستبدال المسافات المتعددة بمسافة واحدة
            cleaned_line = ' '.join(line.split())
            
            # محاولة تقسيم الحقول. البنية هي (اسم الشركة، اسم الموظف، الرقم، التاريخ، الوقت، ثابت 1، ثابت 2)
            parts = cleaned_line.split()
            
            # التحقق من الحد الأدنى المتوقع للحقول قبل محاولة تحليلها
            if len(parts) >= 7:
                company_name = ' '.join(parts[:2]) # This Company
                employee_name = ' '.join(parts[2:-5]) # الاسم الكامل للموظف
                
                # التعامل مع الأعمدة المتبقية
                rest_of_parts = parts[-5:]
                
                employee_id = rest_of_parts[0]
                date_time_str = rest_of_parts[1] + ' ' + rest_of_parts[2] + ' ' + rest_of_parts[3]
                constant_1 = rest_of_parts[4]
                # constant_2 = rest_of_parts[5] # FP
                
                processed_lines.append({
                    'Company': company_name,
                    'Employee Name': employee_name,
                    'ID': employee_id,
                    'DateTime String': date_time_str
                })

        # إنشاء DataFrame
        df = pd.DataFrame(processed_lines)
        
        # تحويل عمود التاريخ والوقت إلى تنسيق datetime
        df['DateTime'] = pd.to_datetime(df['DateTime String'], format='%m/%d/%Y %I:%M:%S %p', errors='coerce')
        df['Date'] = df['DateTime'].dt.date
        df['Time'] = df['DateTime'].dt.time
        
        # التأكد من أن الـ ID رقمي (مهم لعملية التجميع)
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce', downcast='integer')
        
        # إزالة أي سجلات لم يتمكن Pandas من تحليل التاريخ أو الـ ID فيها
        df.dropna(subset=['DateTime', 'ID'], inplace=True)
        
        st.success(f"تمت قراءة وتحليل {len(df)} بصمة بنجاح.")
        
        # --- 4. تطبيق منطق الحضور والانصراف (Grouping & Logic) ---
        
        # فرز البيانات لضمان أن أول بصمة هي Check-In وآخر بصمة هي Check-Out
        df.sort_values(by=['ID', 'Date', 'DateTime'], inplace=True)
        
        # تجميع البيانات حسب الموظف واليوم
        attendance_summary = df.groupby(['ID', 'Employee Name', 'Date']).agg(
            first_in=('DateTime', 'first'),
            last_out=('DateTime', 'last'),
            count=('DateTime', 'size')
        ).reset_index()

        # دالة تطبيق منطق البصمة الواحدة
        def apply_single_punch_logic(row):
            if row['count'] == 1:
                # التحقق من أن البصمة قبل أو بعد 2:00 PM (14:00)
                limit_time = pd.to_datetime(f"{row['Date']} 14:00:00")
                
                if row['first_in'] <= limit_time:
                    # بصمة قبل أو عند 2:00 PM: تُعتبر Check-In
                    return pd.Series([row['first_in'].time(), 'No Logout'])
                else:
                    # بصمة بعد 2:00 PM: تُعتبر Check-Out
                    return pd.Series(['No Login', row['first_in'].time()])
            else:
                # في حالة وجود بصمتين أو أكثر، نأخذ الأولى كـ Check-In والأخيرة كـ Check-Out
                return pd.Series([row['first_in'].time(), row['last_out'].time()])

        # تطبيق الدالة على الملخص
        attendance_summary[['Check-In', 'Check-Out']] = attendance_summary.apply(
            apply_single_punch_logic, axis=1
        )

        # --- 5. تجهيز DataFrame النهائي لملف Excel ---
        final_df = attendance_summary[['ID', 'Employee Name', 'Date', 'Check-In', 'Check-Out']]
        
        # ترتيب الأعمدة حسب طلبك
        final_df.columns = ['ID', 'Employee Name', 'Date', 'Check-In', 'Check-Out']
        
        # فرز نهائي حسب الـ ID والتاريخ
        final_df.sort_values(by=['ID', 'Date'], inplace=True)

        st.subheader("جدول الحضور والانصراف المعالج")
        st.dataframe(final_df, use_container_width=True)

        # --- 6. عنصر تنزيل الملف (Downloader) ---
        
        # تحويل DataFrame إلى Excel في الذاكرة
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Attendance_Summary')
        processed_data = output.getvalue()

        st.download_button(
            label="تنزيل ملف Excel",
            data=processed_data,
            file_name="Processed_Attendance_Summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملف: {e}")
        st.exception(e)

# --- 7. دليل الاستخدام (اختياري) ---
st.markdown("---")
with st.expander("كيفية عمل التحليل"):
    st.markdown("""
    يقوم التطبيق بتحليل بيانات البصمات يوميًا لكل موظف وفقًا للقواعد التالية:
    1.  **بصمتان أو أكثر في اليوم (مثل 2, 3, 4):** يتم اعتماد **أول بصمة** كـ **Check-In** وأخيرة بصمة كـ **Check-Out**.
    2.  **بصمة واحدة في اليوم (مفردة):**
        * إذا كانت البصمة في الساعة **2:00:00 PM وما قبلها**، تعتبر **Check-In** ويتم تسجيل **Check-Out** كـ "**No Logout**".
        * إذا كانت البصمة في الساعة **2:00:01 PM وما بعدها**، تعتبر **Check-Out** ويتم تسجيل **Check-In** كـ "**No Login**".
    """)
