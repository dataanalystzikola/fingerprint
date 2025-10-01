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
    # Read the file using regex for multiple spaces separator and the correct encoding
    # We define custom names to map the required columns correctly based on the new file structure.
    # The columns we care about are Name (col 2), ID (col 3), and Time/Date (col 4).
    try:
        df = pd.read_csv(
            uploaded_file, 
            sep='\s+', 
            encoding='Windows-1256', 
            header=None, 
            skiprows=[0], # Skip the header row (row 0) that contains Arabic names
            names=[
                'Extra1', 'Company', 'Name', 'id', 'Date_Time_Raw', 
                'Extra2', 'Extra3', 'Extra4', 'Extra5'
            ],
            engine='python' # Using python engine for complex regex separator
        )
    except Exception as e:
        st.error(f"Error reading file: {e}. Ensure the file is tab-separated and the format is correct.")
        return

    # Data cleaning and column renaming to match the required format
    
    # 1. Safely convert 'id' to numeric and drop invalid rows (if any remaining)
    df['id'] = pd.to_numeric(df['id'], errors='coerce')
    df = df.dropna(subset=['id']).copy()
    df['id'] = df['id'].astype(int)
    
    # 2. Ensure 'Name' column is string type before stripping
    df['Name'] = df['Name'].astype(str).str.strip()

    # Drop unnecessary columns (the ones we mapped as Extra/Company)
    df = df.drop(columns=['Extra1', 'Company', 'Extra2', 'Extra3', 'Extra4', 'Extra5'])

    # Rename the raw column to 'Time' temporarily for consistency
    df = df.rename(columns={'Date_Time_Raw': 'Time'})

    # Split Date and Time - Date and Time are separated by a single space in the column
    # Example: '9/1/2025 10:10:37 AM' -> '9/1/2025' and '10:10:37 AM'
    df[['Date', 'Time_With_AMPM']] = df['Time'].str.split(' ', n=1, expand=True)
    
    # Re-assemble Date and Time properly for sorting and conversion
    # We must use datetime.strptime to handle the full format including AM/PM
    
    # Convert 'Date' to proper datetime object
    df['Date'] = pd.to_datetime(df['Date'], format='%m/%d/%Y', errors='coerce')

    # Combine Date and Time_With_AMPM string columns into a single datetime column for accurate sorting
    df['DateTime'] = df['Date'].dt.strftime('%m/%d/%Y') + ' ' + df['Time_With_AMPM']
    
    # Convert to datetime objects, including the AM/PM part
    # Format: 9/1/2025 10:10:37 AM -> %m/%d/%Y %I:%M:%S %p
    df['DateTime'] = pd.to_datetime(df['DateTime'], format='%m/%d/%Y %I:%M:%S %p', errors='coerce')
    
    # Extract only the time part as datetime.time object
    df['Time'] = df['DateTime'].dt.time
    
    # Drop intermediate columns
    df = df.drop(columns=['Time_With_AMPM', 'DateTime'])


    # Sort data by Person ID, Date, and Time
    df = df.sort_values(by=['id', 'Date', 'Time'])

    # Function to assign Check In and Check Out intelligently
    def assign_check_in_out(times):
        # A helper function to safely find min and max times
        if not times:
            return None, None
        
        # We must rely on min/max functions to find the first/last time
        first_entry = min(times)
        last_entry = max(times)
        
        # If there is only one entry for the day
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
