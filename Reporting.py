import os
import requests
from datetime import datetime, timedelta
import pandas as pd
import streamlit as st

class AttendanceAnalyzer:
    def __init__(self):
        self.api_base = st.secrets["SLING_API_BASE"]
        self.headers = {'Authorization': st.secrets["SLING_API_KEY"]}
        self.late_threshold = 15
        self.early_threshold = 15  # Consider early if leaving 15 minutes before shift end
        self.break_threshold = 60  # Maximum allowed break duration in minutes
        self.start_date = datetime(2025, 1, 1)
        self.end_date = datetime(2025, 1, 26)
        self.output_dir = 'attendance_reports'
        os.makedirs(self.output_dir, exist_ok=True)

    def fetch_user_data(self) -> dict:
        """Fetch all users from Sling API"""
        url = f"{self.api_base}/{st.secrets['SLING_ORG_ID']}/users"
        try:
            response = requests.get(url, headers=self.headers)
            if response.status_code == 200:
                data = response.json()
                user_map = {
                    str(user['id']): {
                        'email': user.get('email'),
                        'name': f"{user.get('firstname', '')} {user.get('lastname', '')}".strip()
                    }
                    for user in data
                    if user.get('email')
                }
                return user_map
            return {}
        except Exception as e:
            print(f"Error fetching user data: {e}")
            return {}

    def fetch_timesheet_data(self, date: datetime) -> list:
        """Fetch timesheet data from Sling API"""
        date_str = date.strftime('%Y-%m-%d')
        date_range = f"{date_str}/{date_str}"
        nonce = int(datetime.now().timestamp() * 1000)
        
        url = f"{self.api_base}/{st.secrets['SLING_ORG_ID']}/reports/timesheets"
        try:
            response = requests.get(
                url,
                headers=self.headers,
                params={
                    'dates': date_range,
                    'nonce': nonce
                }
            )
            return response.json() if response.status_code == 200 else []
        except Exception:
            return []

    def analyze_attendance(self) -> pd.DataFrame:
        """Analyze attendance focusing on shifts and late arrivals"""
        user_map = self.fetch_user_data()
        if not user_map:
            print("No users found!")
            return pd.DataFrame()

        # Initialize tracking for each user
        attendance_records = {
            user_id: {
                'name': info['name'],
                'total_scheduled_shifts': 0,
                'days_present': 0,
                'late_arrivals': 0,
                'early_clock_outs': 0,
                'extended_breaks': 0,
                'absent_dates': [],  # Track specific dates of absence
                'late_arrival_dates': [],  # Track dates of late arrivals
                'early_clock_out_dates': [],  # Track dates of early clock-outs
                'extended_break_details': []  # Track dates and durations of extended breaks
            }
            for user_id, info in user_map.items()
        }

        # Process each date
        current_date = self.start_date
        while current_date <= self.end_date:
            timesheet_data = self.fetch_timesheet_data(current_date)
            
            # Track scheduled shifts and clock-ins for each user for this day
            daily_scheduled = set()  # Track users who had shifts this day
            daily_present = set()    # Track users who clocked in this day
            daily_late = set()       # Track users who were late this day
            daily_early_out = set()  # Track users who left early this day
            
            for entry in timesheet_data:
                try:
                    user_info = entry.get('user', {})
                    user_id = str(user_info.get('id'))
                    
                    if user_id not in user_map:
                        continue

                    # Count scheduled shift
                    if user_id not in daily_scheduled:
                        daily_scheduled.add(user_id)
                        attendance_records[user_id]['total_scheduled_shifts'] += 1

                    shift_start = datetime.fromisoformat(entry['dtstart'].replace('Z', '+00:00'))
                    shift_end = datetime.fromisoformat(entry['dtend'].replace('Z', '+00:00'))
                    entries = entry.get('timesheetEntries', [])
                    
                    # Sort entries by timestamp for proper break calculation
                    sorted_entries = sorted(entries, key=lambda x: x['timestamp'])
                    
                    # Look for clock-in, clock-out, and breaks
                    clock_in = None
                    clock_out = None
                    current_break_start = None
                    breaks = []  # To store all break periods
                    total_break = timedelta(minutes=0)
                    
                    for record in sorted_entries:
                        entry_type = record.get('type')
                        timestamp = datetime.fromisoformat(record['timestamp'].replace('Z', '+00:00'))

                        if entry_type == 'clock_in':
                            if not clock_in:
                                clock_in = timestamp
                            if current_break_start:
                                # End of a break period
                                break_duration = timestamp - current_break_start
                                breaks.append((current_break_start, timestamp, break_duration))
                                total_break += break_duration
                                current_break_start = None
                                
                        elif entry_type in ['clock_out', 'auto_clock_out']:
                            clock_out = timestamp
                            if not current_break_start:
                                current_break_start = timestamp
                        
                        elif entry_type == 'break_start':
                            current_break_start = timestamp
                        elif entry_type == 'break_end' and current_break_start:
                            break_duration = timestamp - current_break_start
                            breaks.append((current_break_start, timestamp, break_duration))
                            total_break += break_duration
                            current_break_start = None
                    
                    # Process extended breaks
                    for break_start, break_end, duration in breaks:
                        break_minutes = duration.total_seconds() / 60
                        if break_minutes > self.break_threshold:
                            attendance_records[user_id]['extended_breaks'] += 1
                            attendance_records[user_id]['extended_break_details'].append({
                                'date': current_date.strftime('%Y-%m-%d'),
                                'start_time': break_start.strftime('%H:%M'),
                                'end_time': break_end.strftime('%H:%M'),
                                'duration': round(break_minutes)
                            })
                    
                    if clock_in:
                        # Mark as present
                        if user_id not in daily_present:
                            daily_present.add(user_id)
                        
                        # Check for late arrival
                        if user_id not in daily_late:  # Only check if not already marked late today
                            minutes_late = (clock_in - shift_start).total_seconds() / 60
                            if minutes_late > self.late_threshold:
                                daily_late.add(user_id)
                                attendance_records[user_id]['late_arrival_dates'].append(current_date.strftime('%Y-%m-%d'))
                    
                    # Check for early clock-out
                    if clock_out and user_id not in daily_early_out:
                        minutes_early = (shift_end - clock_out).total_seconds() / 60
                        if minutes_early > self.early_threshold:
                            daily_early_out.add(user_id)
                            attendance_records[user_id]['early_clock_out_dates'].append(current_date.strftime('%Y-%m-%d'))

                except Exception as e:
                    print(f"Error processing entry: {str(e)}")
                    continue
            
            # Update attendance records for this day
            for user_id in daily_present:
                attendance_records[user_id]['days_present'] += 1
            
            # Record absences for scheduled but not present
            for user_id in daily_scheduled:
                if user_id not in daily_present:
                    attendance_records[user_id]['absent_dates'].append(current_date.strftime('%Y-%m-%d'))
            
            for user_id in daily_late:
                attendance_records[user_id]['late_arrivals'] += 1
                
            for user_id in daily_early_out:
                attendance_records[user_id]['early_clock_outs'] += 1

            current_date += timedelta(days=1)

        # Create summary records
        summary_records = []
        for user_id, record in attendance_records.items():
            if record['total_scheduled_shifts'] > 0:
                # Format extended break details
                extended_break_info = []
                for break_detail in record['extended_break_details']:
                    extended_break_info.append(
                        f"{break_detail['date']} ({break_detail['start_time']}-{break_detail['end_time']}, {break_detail['duration']} mins)"
                    )
                
                summary_records.append({
                    'Full Name': record['name'],
                    'Total Scheduled Shifts': record['total_scheduled_shifts'],
                    'Days Present': record['days_present'],
                    'Days Absent': record['total_scheduled_shifts'] - record['days_present'],
                    'Absent Dates': ', '.join(record['absent_dates']) if record['absent_dates'] else 'None',
                    'Late Arrivals': record['late_arrivals'],
                    'Late Arrival Dates': ', '.join(record['late_arrival_dates']) if record['late_arrival_dates'] else 'None',
                    'Early Clock-outs': record['early_clock_outs'],
                    'Early Clock-out Dates': ', '.join(record['early_clock_out_dates']) if record['early_clock_out_dates'] else 'None',
                    'Extended Breaks': record['extended_breaks'],
                    'Extended Break Details': ', '.join(extended_break_info) if extended_break_info else 'None'
                    
                })

        return pd.DataFrame(summary_records)

def main():
    try:
        analyzer = AttendanceAnalyzer()
        print("Analyzing attendance data...")
        summary_df = analyzer.analyze_attendance()
        
        if summary_df.empty:
            print("No attendance data was generated.")
            return
        
        # Save to CSV
        output_file = os.path.join(analyzer.output_dir, 'attendance_summary_jan2025.csv')
        summary_df.to_csv(output_file, index=False)
        print(f"\nAttendance summary has been saved to {output_file}")
        
        # Display summary
        print("\nAttendance Summary:")
        print(summary_df.to_string(index=False))
        
    except Exception as e:
        print(f"An unexpected error occurred: {str(e)}")
        raise

# if __name__ == "__main__":
#     main()
