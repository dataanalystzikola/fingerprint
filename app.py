import streamlit as st
import pandas as pd
import numpy as np
import io
from datetime import datetime

# Display logo and title
st.image("black.jpeg", width=200)
st.title("Finger Print App")

# Upload CSV file
uploaded_file = st.file_uploader("Upload your file", type=["txt", "csv"])

if uploaded_file is not None:
    # Read the file
    # We'll handle the case where the uploaded file is a .txt with no header
    # and use the headers we defined previously.
    df = pd.read_csv(uploaded_file, sep='\t', header=None,
                     names=['id', 'Time', 'test_1', 'test_2', 'Name', 'test_3', 'test_4', 'test_5'])

    # Data cleaning
    df['id'] = df['id'].astype(int)

    # Check if the 'Name' column has a trailing whitespace and remove it
    df['Name'] = df['Name'].str.strip()

    # Drop unnecessary columns
    df = df.drop(columns=['test_1', 'test_2', 'test_3', 'test_4', 'test_5'])

    # Split Date and Time
    df[['Date', 'Time']] = df['Time'].str.split(' ', expand=True)
    df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
    df['Time'] = pd.to_datetime(df['Time'], format='%H:%M:%S').dt.time

    # Sort data by Person ID, Date, and Time
    df = df.sort_values(by=['id', 'Date', 'Time'])

    # Group data by employee and date
    grouped = df.groupby(['id', 'Name', 'Date'])['Time'].agg(list).reset_index()


    # Function to assign Check In and Check Out intelligently
    def assign_check_in_out(times):
        # A helper function to safely find min and max times
        if not times:
            return None, None

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
    grouped[['Check In', 'Check Out']] = grouped['Time'].apply(lambda x: pd.Series(assign_check_in_out(x)))

    # Drop the original 'Time' column
    grouped = grouped.drop(columns=['Time'])

    # Replace missing values
    grouped['Check In'] = grouped['Check In'].astype(str).replace('None', 'no login')
    grouped['Check Out'] = grouped['Check Out'].astype(str).replace('None', 'no logout')

    # Show processed data
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
