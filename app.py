import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

# Inject custom CSS for styling (نفس الستايل بتاعك، مش هنغيره)
st.markdown("""
<style>
    body {
        font-family: 'Inter', Arial, sans-serif;
        background-color: #f4f4f4;
        color: #333333;
    }
    #header-container {
        background-color: #F37626;
        color: white;
        padding: 24px;
        text-align: center;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    #header-container img {
        max-width: 150px;
        height: auto;
    }
    #header-container h1 {
        color: white;
        font-weight: bold;
        text-align: center;
    }
    #main-container {
        background-color: #ffffff;
        border-radius: 8px;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        padding: 24px;
        margin-top: 20px;
    }
    #main-container h3 {
        color: #F37626;
        font-weight: 600;
    }
    .stDataFrame {
        width: 100%;
    }
    .stDataFrame table {
        border-collapse: collapse;
        width: 100%;
        margin-top: 20px;
        margin-bottom: 20px;
    }
    .stDataFrame th, 
    .stDataFrame td {
        padding: 12px;
        border: 1px solid #dddddd;
        text-align: left;
        font-size: 14px;
    }
    .stDataFrame th {
        background-color: #f9f9f9;
        font-weight: 600;
        color: #555555;
    }
    .stDataFrame tbody tr:nth-child(odd) {
        background-color: #f9f9f9;
    }
    .stDataFrame tbody tr:hover {
        background-color: #f1f1f1;
    }
</style>
""", unsafe_allow_html=True)

# Main application logic
with st.container():
    st.image("black.jpeg", width=200)
    st.title("Finger Print App")

# File uploader
uploaded_file = st.file_uploader("Upload your file", type=["txt", "csv"])

if uploaded_file is not None:
    try:
        # Try different encodings
        encodings = ['utf-16', 'windows-1256', 'utf-8']
        df = None
        for encoding in encodings:
            try:
                df = pd.read_csv(uploaded_file, sep='\s+', header=0, encoding=encoding)
                break
            except:
                uploaded_file.seek(0)  # Reset file pointer to beginning
                continue
        
        if df is None:
            st.error("Could not read the file with any supported encoding. Please check the file format.")
            st.stop()

        # Rename columns to English for easier processing
        df.columns = ['Department', 'Name', 'ID', 'DateTime', 'Location', 'Number', 'RegistrationMethod', 'CardNumber']

        # Data cleaning
        df['ID'] = df['ID'].astype(int)
        df['Name'] = df['Name'].str.strip()

        # Drop unnecessary columns
        df = df.drop(columns=['Department', 'Location', 'Number', 'RegistrationMethod', 'CardNumber'])

        # Split Date and Time
        df[['Date', 'Time']] = df['DateTime'].str.split(' ', n=1, expand=True)
        df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
        df['Time'] = pd.to_datetime(df['Time'], format='%I:%M:%S %p', errors='coerce').dt.time

        # Sort data by ID, Date, and Time
        df = df.sort_values(by=['ID', 'Date', 'Time'])

        # Function to assign Check In and Check Out intelligently
        def assign_check_in_out(times):
            if not times:
                return None, None
            
            first_entry = min(times)
            last_entry = max(times)
            
            if len(times) == 1:
                check_in_threshold = datetime.strptime("14:00:00", "%H:%M:%S").time()
                if first_entry <= check_in_threshold:
                    return first_entry, None
                else:
                    return None, first_entry
            else:
                return first_entry, last_entry

        # Apply the function to the data
        grouped = df.groupby(['ID', 'Name', 'Date'])['Time'].agg(list).reset_index()
        grouped[['Check In', 'Check Out']] = grouped['Time'].apply(lambda x: pd.Series(assign_check_in_out(x)))

        # Drop the original 'Time' column
        grouped = grouped.drop(columns=['Time'])

        # Replace missing values
        grouped['Check In'] = grouped['Check In'].astype(str).replace('None', 'no login')
        grouped['Check Out'] = grouped['Check Out'].astype(str).replace('None', 'no logout')

        # Show processed data
        with st.container():
            st.subheader("Processed Data")
            st.write(grouped)

        # Convert DataFrame to Excel
        @st.cache_data
        def convert_df_to_excel(df):
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Sheet1')
            return output.getvalue()

        # Button to download the file
        excel_data = convert_df_to_excel(grouped)
        st.download_button(
            label="Download Processed Excel File",
            data=excel_data,
            file_name="processed_attendance.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        st.error(f"An error occurred: {str(e)}")
