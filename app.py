import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

# Inject custom CSS for styling
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
    # Use the local file for the image
    st.image("black.jpeg", width=200) 
    st.title("Finger Print App")

uploaded_file = st.file_uploader("Upload your file", type=["txt", "csv"])

if uploaded_file is not None:
    # --- SECURE FILE READING (Using regex '\s+' for variable multiple spaces separator) ---
    try:
        # We use '\s+' to read any number of spaces/tabs as one separator.
        # We include extra columns in names=['...'] to avoid 'saw X fields' error.
        df = pd.read_csv(
            uploaded_file, 
            sep='\s+', 
            encoding='Windows-1256', 
            header=None, 
            skiprows=[0], # Skip the main Arabic header row only (line 0 from Test222.txt)
            names=['Extra0', 'Company', 'Name', 'id', 'Time_Raw', 'Extra1', 'Extra2', 'Extra3', 'Extra4', 'Extra5', 'Extra6', 'Extra7'],
            engine='python' # Using python engine for robust regex splitting
        ).iloc[1:] # Drop the empty row after the header (line 1 from Test222.txt)
        
    except Exception as e:
        st.error(f"Error reading file: {e}. يرجى التأكد من أن الملف ليس فارغًا وأن هيكل الأعمدة صحيح.")
        st.stop() 

    # --- DATA CLEANING ---
    
    # 1. Safely convert 'id' to integer
    # We must drop rows where 'id' is NaN *before* converting to int, to prevent IntCastingNaNError
    df['id'] = pd.to_numeric(df['id'], errors='coerce')
    df = df.dropna(subset=['id']).copy()
    df['id'] = df['id'].astype(int)
    
    # 2. Ensure 'Name' column is string type before stripping (Fixes AttributeError)
    df['Name'] = df['Name'].astype(str).str.strip()
    
    # 3. Final cleanup: Drop unnecessary columns 
    df = df.drop(columns=['Extra0', 'Company', 'Extra1', 'Extra2', 'Extra3', 'Extra4', 'Extra5', 'Extra6', 'Extra7'], errors='ignore')

    # Rename the raw column to 'Time' temporarily
    df = df.rename(columns={'Time_Raw': 'Time'})

    # 4. Safely Split Date and Time_Raw (Example: '9/1/2025 10:10:37 AM')
    
    # Convert 'Time_Raw' to string, replacing NaN with an empty string ('')
    time_series = df['Time'].astype(str).replace('nan', '') 
    
    # Split the series safely
    split_result = time_series.str.split(' ', n=1, expand=True)

    # Assign the split results
    df[['Date_Part', 'Time_With_AMPM']] = split_result
    
    # 5. Process Date and Time for final use
    
    # Convert 'Date_Part' to proper datetime object
    df['Date'] = pd.to_datetime(df['Date_Part'], format='%m/%d/%Y', errors='coerce')

    # Combine Date and Time_With_AMPM strings into a single datetime column for sorting
    df['DateTime'] = pd.to_datetime(
        df['Date_Part'].astype(str) + ' ' + df['Time_With_AMPM'].astype(str), 
        format='%m/%d/%Y %I:%M:%S %p', 
        errors='coerce'
    )
    
    # Extract only the final time part
    df['Time'] = df['DateTime'].dt.time
    
    # Drop intermediate and original raw columns
    df = df.drop(columns=['Date_Part', 'Time_With_AMPM', 'DateTime'])


    # Sort data by Person ID, Date, and Time
    df = df.sort_values(by=['id', 'Date', 'Time'])

    # Function to assign Check In and Check Out intelligently
    def assign_check_in_out(times):
        if not times:
            return None, None
        
        # We must rely on min/max functions to find the first/last time
        first_entry = min(times)
        last_entry = max(times)
        
        # Logic for single entry
        if len(times) == 1:
            check_in_threshold = datetime.strptime("14:00:00", "%H:%M:%S").time()
            if first_entry <= check_in_threshold:
                return first_entry, None
            else:
                return None, first_entry
        else:
            return first_entry, last_entry

    # Apply the function to the data
    grouped = df.groupby(['id', 'Name', 'Date'])['Time'].agg(list).reset_index()
    grouped[['Check In', 'Check Out']] = grouped['Time'].apply(lambda x: pd.Series(assign_check_in_out(x)))

    # Drop the original 'Time' column (list of times)
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
