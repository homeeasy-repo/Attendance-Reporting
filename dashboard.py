import streamlit as st
from Reporting import AttendanceAnalyzer
from datetime import datetime, timedelta

st.set_page_config(
    page_title="Attendance Dashboard",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Attendance Analysis Dashboard")

# Initialize the analyzer
analyzer = AttendanceAnalyzer()

# Add date range selector
col1, col2 = st.columns(2)
with col1:
    start_date = st.date_input(
        "Start Date",
        value=datetime(2025, 1, 1).date(),
        min_value=datetime(2024, 1, 1).date(),
        max_value=datetime.now().date()
    )
with col2:
    end_date = st.date_input(
        "End Date",
        value=datetime(2025, 1, 26).date(),
        min_value=start_date,
        max_value=datetime.now().date()
    )

# Update analyzer dates
analyzer.start_date = datetime.combine(start_date, datetime.min.time())
analyzer.end_date = datetime.combine(end_date, datetime.min.time())

if st.button("Generate Report"):
    with st.spinner("Analyzing attendance data..."):
        try:
            df = analyzer.analyze_attendance()
            
            if df.empty:
                st.error("No attendance data found for the selected period.")
            else:
                # Display summary metrics
                st.subheader("Summary Metrics")
                metric_cols = st.columns(4)
                
                with metric_cols[0]:
                    total_employees = len(df)
                    st.metric("Total Employees", total_employees)
                
                with metric_cols[1]:
                    avg_attendance = round(df['Days Present'].mean(), 1)
                    st.metric("Avg Days Present", avg_attendance)
                
                with metric_cols[2]:
                    total_lates = df['Late Arrivals'].sum()
                    st.metric("Total Late Arrivals", total_lates)
                
                with metric_cols[3]:
                    total_early_outs = df['Early Clock-outs'].sum()
                    st.metric("Total Early Clock-outs", total_early_outs)

                # Display detailed table
                st.subheader("Detailed Attendance Report")
                st.dataframe(
                    df,
                    use_container_width=True,
                    hide_index=True
                )

                # Download button for CSV
                csv = df.to_csv(index=False).encode('utf-8')
                st.download_button(
                    "Download Report as CSV",
                    csv,
                    "attendance_report.csv",
                    "text/csv",
                    key='download-csv'
                )

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")

# if __name__ == "__main__":
#     main() 