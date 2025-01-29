import streamlit as st

st.set_page_config(
    page_title="Homeeasy Sales Dashboard",
    layout="wide"
)

from Reporting import AttendanceAnalyzer
import shifts
import pandas as pd

def show_reporting():
    st.title("Attendance Reporting Dashboard")
    
    analyzer = AttendanceAnalyzer()
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input("Start Date", analyzer.start_date)
    with col2:
        end_date = st.date_input("End Date", analyzer.end_date)
    
    if st.button("Generate Report"):
        with st.spinner("Analyzing attendance data..."):
            analyzer.start_date = start_date
            analyzer.end_date = end_date
            

            summary_df = analyzer.analyze_attendance()
            
            if not summary_df.empty:
                st.success("Report generated successfully!")
                

                st.dataframe(
                    summary_df,
                    use_container_width=True,
                    hide_index=True
                )
                
                # Add download button
                csv = summary_df.to_csv(index=False)
                st.download_button(
                    "Download Report",
                    csv,
                    "attendance_report.csv",
                    "text/csv",
                    key='download-csv'
                )
            else:
                st.warning("No attendance data found for the selected date range.")

def main():
    try:
        st.sidebar.image("homeeasylogo.png", width=200)
    except:
        st.sidebar.title("Homeeasy")
    
    page = st.sidebar.selectbox(
        "Select Dashboard",
        ["Shift Management", "Attendance Reporting"],
        format_func=lambda x: f"📊 {x}" if x == "Attendance Reporting" else f"📅 {x}"
    )
    
    if page == "Shift Management":
        shifts.main()
    else:
        show_reporting()
    
    st.sidebar.markdown("---")
    st.sidebar.markdown("### About")
    st.sidebar.info(
        """
        This dashboard provides tools for managing employee shifts 
        and monitoring attendance patterns.
        """
    )

if __name__ == "__main__":
    main() 