import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from Reporting import AttendanceAnalyzer

def main():
    st.title("Attendance Analysis Dashboard")
    
    # Date selection
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Start Date",
            datetime(2025, 1, 1),
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2030, 12, 31)
        )
    with col2:
        end_date = st.date_input(
            "End Date",
            datetime(2025, 1, 26),
            min_value=datetime(2024, 1, 1),
            max_value=datetime(2030, 12, 31)
        )
    
    if st.button("Generate Report"):
        if start_date <= end_date:
            with st.spinner("Analyzing attendance data..."):
                # Initialize analyzer with custom dates
                analyzer = AttendanceAnalyzer()
                analyzer.start_date = datetime.combine(start_date, datetime.min.time())
                analyzer.end_date = datetime.combine(end_date, datetime.min.time())
                
                # Get attendance data
                summary_df = analyzer.analyze_attendance()
                
                if not summary_df.empty:
                    # Display summary statistics
                    st.subheader("Summary Statistics")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Employees", len(summary_df))
                    with col2:
                        avg_attendance = (summary_df['Days Present'].sum() / summary_df['Total Scheduled Shifts'].sum() * 100)
                        st.metric("Average Attendance Rate", f"{avg_attendance:.1f}%")
                    with col3:
                        total_late = summary_df['Late Arrivals'].sum()
                        st.metric("Total Late Arrivals", total_late)
                    
                    # Display detailed table
                    st.subheader("Detailed Attendance Report")
                    st.dataframe(summary_df, use_container_width=True)
                    
                    # Download summary button
                    csv = summary_df.to_csv(index=False)
                    st.download_button(
                        "Download Summary Report",
                        csv,
                        f"attendance_summary_{start_date.strftime('%Y%m')}_{end_date.strftime('%Y%m')}.csv",
                        "text/csv",
                        key='download-summary-csv'
                    )
                else:
                    st.warning("No attendance data was found for the selected date range.")
        else:
            st.error("End date must be after start date.")

# if __name__ == "__main__":
#     main() 