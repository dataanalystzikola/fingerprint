import streamlit as st
import pandas as pd
from io import BytesIO

# --- 1. إعداد الصفحة والتطبيق ---
st.set_page_config(
    page_title="Attendance Data Analyzer",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("Attendance Data Analyzer (Check-In/Check-Out) 🕒")
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
        
        # تقسيم البيانات إلى سجلات أولية
        raw_lines = data.strip().split('\n')
        processed_lines = []
        
        COMPANY_PREFIX = "This Company"
        
        for line in raw_lines:
            # تنظيف المسافات المتعددة واستبدالها بمسافة واحدة
            cleaned_line = ' '.join(line.strip().split())
            
            if not cleaned_line.startswith(COMPANY_PREFIX):
                continue
                
            # إزالة بادئة اسم الشركة والمسافات الزائدة
            content = cleaned_line[len(COMPANY_PREFIX):].strip()
            
            # تقسيم المحتوى المتبقي إلى أجزاء
            parts = content.split()
            
            # نتوقع 6 حقول ثابتة في النهاية:
            # [ID, Date_Part, Time_HH:MM:SS, Time_AM/PM, Constant_2, Constant_FP]
            # مثال: 41 9/1/2025 10:10:37 AM 2 FP
            # نحتاج الأجزاء الستة الأخيرة (index -6 إلى -1)
            
            if len(parts) >= 6: 
                # استخراج الأجزاء الثابتة من النهاية
                constant_fp = parts[-1] 
                constant_2 = parts[-2]
                time_ampm = parts[-3]
                time_seconds = parts[-4]
                date_part = parts[-5]
                employee_id = parts[-6]
                
                # تجميع سلسلة التاريخ والوقت
                date_time_str = f"{date_part} {time_seconds} {time_ampm}"
                
                # استخراج اسم الموظف: كل ما تبقى قبل الجزء السادس من النهاية
                employee_name = ' '.join(parts[:-6]).strip()
                
                # التأكد من عدم وجود بيانات مكررة (نظراً لأن السطر قد يمتد)
                if employee_name and employee_id.isdigit():
                    processed_lines.append({
                        'Employee Name': employee_name,
                        'ID': employee_id,
                        'DateTime String': date_time_str
                    })
        
        # في حالة عدم وجود أي سجلات صالحة
        if not processed_lines:
            st.error("لم يتم العثور على سجلات بصمات صالحة في الملف المرفوع. تأكد من تطابق التنسيق.")
            st.stop()
            
        # إنشاء DataFrame
        df = pd.DataFrame(processed_lines)
        
        # تحويل عمود التاريخ والوقت إلى تنسيق datetime
        # نستخدم format='%m/%d/%Y %I:%M:%S %p' لأن التنسيق واضح (شهر/يوم/سنة ساعة:دقيقة:ثانية صباحاً/مساءً)
        df['DateTime'] = pd.to_datetime(df['DateTime String'], format='%m/%d/%Y %I:%M:%S %p', errors='coerce')
        df['Date'] = df['DateTime'].dt.date
        
        # التأكد من أن الـ ID رقمي
        df['ID'] = pd.to_numeric(df['ID'], errors='coerce', downcast='integer')
        
        # إزالة أي سجلات لم يتمكن Pandas من تحليل التاريخ أو الـ ID فيها
        df.dropna(subset=['DateTime', 'ID'], inplace=True)
        
        st.success(f"تمت قراءة وتحليل **{len(df)}** بصمة بنجاح لـ **{df['ID'].nunique()}** موظف.")
        
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
                # إنشاء نقطة مرجعية 2:00 PM لنفس اليوم (14:00:00)
                # نستخدم التاريخ من السجل ونحدد الساعة 14:00:00
                ref_time = pd.Timestamp(row['Date']).replace(hour=14, minute=0, second=0)
                
                # استخدام قيمة first_in للمقارنة
                if row['first_in'] <= ref_time:
                    # بصمة قبل أو عند 2:00 PM: تُعتبر Check-In
                    return pd.Series([row['first_in'].time(), 'No Logout'])
                else:
                    # بصمة بعد 2:00 PM: تُعتبر Check-Out
                    return pd.Series(['No Login', row['first_in'].time()])
            else:
                # في حالة وجود بصمتين أو أكثر (أول بصمة وآخر بصمة)
                return pd.Series([row['first_in'].time(), row['last_out'].time()])

        # تطبيق الدالة على الملخص وتعيين القيم للأعمدة
        # تم إصلاح الخطأ: الآن pd.Series تُرجع قيمتين دائماً
        attendance_summary[['Check-In', 'Check-Out']] = attendance_summary.apply(
            apply_single_punch_logic, axis=1
        )

        # --- 5. تجهيز DataFrame النهائي لملف Excel ---
        final_df = attendance_summary[['ID', 'Employee Name', 'Date', 'Check-In', 'Check-Out']]
        
        # فرز نهائي حسب الـ ID والتاريخ
        final_df.sort_values(by=['ID', 'Date'], inplace=True)

        st.subheader("📊 جدول الحضور والانصراف المعالج")
        st.dataframe(final_df, use_container_width=True)

        # --- 6. عنصر تنزيل الملف (Downloader) ---
        
        # تحويل DataFrame إلى Excel في الذاكرة
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            final_df.to_excel(writer, index=False, sheet_name='Attendance_Summary')
        processed_data = output.getvalue()

        st.download_button(
            label="تنزيل ملف Excel 📥",
            data=processed_data,
            file_name="Processed_Attendance_Summary.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"حدث خطأ أثناء معالجة الملف، ربما بسبب تنسيق غير متوقع في بعض السجلات: {e}")
        # st.exception(e) # يمكنك إزالة علامة التعليق لرؤية الـ Traceback
