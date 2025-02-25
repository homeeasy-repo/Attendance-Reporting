import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta
import time

def fetch_users():
    """Fetch users from Sling API with concise information"""
    url = f'{st.secrets["SLING_API_BASE"]}/{st.secrets["SLING_ORG_ID"]}/users/concise'
    params = {
        'nonce': '1738160741741',
        'user-fields': 'full'
    }
    headers = {
        "Authorization": st.secrets["SLING_API_KEY"]
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching users: {str(e)}")
        return []

# Define day mappings
DAY_MAPPINGS = {
    'Monday': 'MO',
    'Tuesday': 'TU',
    'Wednesday': 'WE',
    'Thursday': 'TH',
    'Friday': 'FR',
    'Saturday': 'SA',
    'Sunday': 'SU'
}

def get_position_from_groups(group_ids, groups):
    """Helper function to determine position from group IDs"""
    position_priority = {
        22292139: 'Head of People and Operations', 
        21678700: 'Manager',
        22207072: 'Senior Sales Agent',
        21678699: 'Sales Agent',
        21678698: 'AI Engineer',  
        21982629: 'HR'
    }
    
    # Check groups in priority order
    for group_id in position_priority:
        if group_id in group_ids:
            return position_priority[group_id], group_id
    
    return 'Sales Agent', 21678699

def create_shift(user_id, position_id, start_date, selected_days, interval, shift_type):
    """Create shift for a user"""
    url = f'{st.secrets["SLING_API_BASE"]}/{st.secrets["SLING_ORG_ID"]}/shifts/bulk'
    headers = {
        "Authorization": st.secrets["SLING_API_KEY"],
        "Content-Type": "application/json"
    }
    
    # Convert selected days to RRULE format
    byday = ','.join([DAY_MAPPINGS[day] for day, selected in selected_days.items() if selected])
    
    # Calculate until date based on interval
    until_date = start_date + timedelta(days=(7 * interval - 1))
    until_str = f"{until_date.strftime('%Y-%m-%d')}T23:59:59.000Z"
    
    # Set shift times based on shift type (Pakistan time UTC+5)
    if shift_type == "8-hour":
        # 8 PM PKT = 15:00 UTC
        shift_start = "15:00:00.000"  # 8 PM PKT
        # For 8-hour shift ending at 4 AM PKT next day = 23:00 UTC same day
        shift_end = "23:00:00.000"    # 4 AM PKT next day
        summary = "8-Hour Night Shift (8 PM - 4 AM PKT)"
        # For 8-hour shift, end time is on the same UTC day
        next_day = start_date
    elif shift_type == "10-hour-late":
        # 10 PM PKT = 17:00 UTC
        shift_start = "17:00:00.000"  # 10 PM PKT
        shift_end = "03:00:00.000"    # 8 AM PKT next day
        summary = "10-Hour Night Shift (10 PM - 8 AM PKT)"
        next_day = start_date + timedelta(days=1)
    elif shift_type == "10-hour-early":
        # 8 PM PKT = 15:00 UTC
        shift_start = "15:00:00.000"  # 8 PM PKT
        shift_end = "01:00:00.000"    # 6 AM PKT next day
        summary = "10-Hour Night Shift (8 PM - 6 AM PKT)"
        next_day = start_date + timedelta(days=1)
    else:  # 12-hour
        # 8 PM PKT = 15:00 UTC
        shift_start = "15:00:00.000"  # 8 PM PKT
        shift_end = "03:00:00.000"    # 8 AM PKT next day
        summary = "12-Hour Night Shift (8 PM - 8 AM PKT)"
        next_day = start_date + timedelta(days=1)
    
    # Create shift start and end time strings
    shift_start_str = f"{start_date.strftime('%Y-%m-%d')}T{shift_start}Z"
    shift_end_str = f"{next_day.strftime('%Y-%m-%d')}T{shift_end}Z"
    
    # Create shift data
    shift_data = [{
        "user": {"id": user_id},
        "summary": summary,
        "location": {"id": 22425442},
        "position": {"id": position_id},
        "dtstart": shift_start_str,
        "dtend": shift_end_str,
        "breakduration": 60,
        "status": "published",
        "rrule": {
            "freq": "WEEKLY",
            "byday": byday,
            "interval": 1,
            "until": until_str
        }
    }]
    
    try:
        # st.write("Sending shift data:", shift_data)  # Debug print
        response = requests.post(url, headers=headers, json=shift_data)
        if response.status_code != 200:
            st.error(f"API Response: {response.text}")  # Debug print
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as e:
        st.error(f"Error creating shift: {str(e)}")
        return False

def fetch_shifts(start_date, end_date):
    """Fetch shifts from Sling API for given date range"""
    url = f'{st.secrets["SLING_API_BASE"]}/{st.secrets["SLING_ORG_ID"]}/reports/timesheets'
    params = {
        'dates': f"{start_date}/{end_date}"
    }
    headers = {
        "Authorization": st.secrets["SLING_API_KEY"]
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        st.error(f"Error fetching shifts: {str(e)}")
        return []

def process_shifts_view(shifts_data, start_date, end_date, users_data):
    """Process shifts data and create a display table"""
    # Create date range
    date_range = pd.date_range(start=start_date, end=end_date)
    
    # Create user lookup dictionary
    all_users = {}
    if users_data and 'users' in users_data:
        for user in users_data['users']:
            # Skip AI Engineers, Head of People and Operations, and Mukund Chopra
            position = get_position_from_groups(user['groupIds'], {})[0]
            if (position not in ['AI Engineer', 'Head of People and Operations'] and
                f"{user['legalName']} {user['lastname']}" != "Mukund Chopra"):
                all_users[str(user['id'])] = {
                    'name': f"{user['legalName']} {user['lastname']}",
                    'shifts': {date.date(): [] for date in date_range}
                }
    
    # Process each shift
    for shift in shifts_data:
        if 'user' in shift and shift['user']:
            user_id = str(shift['user']['id'])
            if user_id in all_users:
                try:
                    # Parse shift times
                    dtstart = shift['dtstart']
                    dtend = shift['dtend']
                    shift_start = datetime.strptime(dtstart.split('+')[0], "%Y-%m-%dT%H:%M:%S")
                    shift_end = datetime.strptime(dtend.split('+')[0], "%Y-%m-%dT%H:%M:%S")
                    
                    # Get all dates this shift covers
                    shift_dates = set()
                    
                    # Add initial shift dates
                    shift_dates.add(shift_start.date())
                    if shift_end.date() != shift_start.date():
                        shift_dates.add(shift_end.date())
                    
                    # Handle recurring shifts
                    if 'rrule' in shift:
                        rrule = shift['rrule']
                        byday = rrule.get('byday', '').split(',')
                        until = datetime.strptime(rrule['until'].split('+')[0], "%Y-%m-%dT%H:%M:%S")
                        
                        # Add all recurring dates
                        current_date = shift_start.date()
                        while current_date <= min(until.date(), end_date):
                            weekday = current_date.strftime('%a').upper()[:2]
                            if weekday in byday:
                                shift_dates.add(current_date)
                            current_date += timedelta(days=1)
                    
                    # Mark shifts in user's data
                    for date in shift_dates:
                        if date in all_users[user_id]['shifts']:
                            all_users[user_id]['shifts'][date].append(shift.get('summary', 'Night Shift'))
                
                except Exception as e:
                    st.error(f"Error processing shift for {all_users[user_id]['name']}: {str(e)}")
    
    # Create display rows
    shift_rows = []
    for user_id, user_data in all_users.items():
        row = {'Employee': user_data['name']}
        for date in date_range:
            date_str = date.strftime("%Y-%m-%d")
            has_shift = bool(user_data['shifts'][date.date()])
            row[date_str] = "✅" if has_shift else "❌"
        shift_rows.append(row)
    
    return pd.DataFrame(shift_rows), date_range

def main():
    st.title("Shift Management Dashboard")
    
    st.write("### View Shifts")
    col1, col2 = st.columns(2)
    with col1:
        start_view_date = st.date_input("Select Start Date", value=datetime.now().date())
    with col2:
        end_view_date = st.date_input("Select End Date", value=(datetime.now().date() + timedelta(days=30)))
    
    shifts_data = fetch_shifts(start_view_date.strftime("%Y-%m-%d"), end_view_date.strftime("%Y-%m-%d"))
    users_data = fetch_users()
    
    if shifts_data and users_data:
        # Process shifts and create display table
        shifts_df, date_range = process_shifts_view(shifts_data, start_view_date, end_view_date, users_data)
        
        # Display legend
        st.markdown("#### Shift Legend:")
        st.markdown("✅ = Scheduled Shift")
        st.markdown("❌ = No Shift")
        
        # Display shifts table
        st.dataframe(
            shifts_df,
            hide_index=True,
            column_config={
                'Employee': st.column_config.Column(
                    'Employee',
                    width='medium'
                ),
                **{
                    date.strftime("%Y-%m-%d"): st.column_config.Column(
                        f"{date.strftime('%a')} ({date.strftime('%d').lstrip('0')} {date.strftime('%b')})",
                        width='small'
                    )
                    for date in date_range
                }
            },
            use_container_width=True
        )
    
    st.markdown("---") 
    
    # Initialize session state variables if they don't exist
    if 'selected_employees' not in st.session_state:
        st.session_state.selected_employees = []
    if 'shift_type_key' not in st.session_state:
        st.session_state.shift_type_key = 0
    if 'start_date_key' not in st.session_state:
        st.session_state.start_date_key = 0
    if 'interval_key' not in st.session_state:
        st.session_state.interval_key = 0
    if 'selected_employees_key' not in st.session_state:
        st.session_state.selected_employees_key = 0
    
    st.write("### Create Shifts")
    
    # Add shift type selection with both 10-hour options
    shift_type = st.radio(
        "Select Shift Type",
        ["8-hour", "10-hour-early", "10-hour-late", "12-hour"],
        format_func=lambda x: "8-Hour Night Shift (8 PM - 4 AM PKT)" if x == "8-hour"
                            else "10-Hour Night Shift (8 PM - 6 AM PKT)" if x == "10-hour-early"
                            else "10-Hour Night Shift (10 PM - 8 AM PKT)" if x == "10-hour-late"
                            else "12-Hour Night Shift (8 PM - 8 AM PKT)",
        horizontal=True,
        key=f"shift_type_{st.session_state.shift_type_key}"
    )
    
    col1, col2 = st.columns(2)
    with col1:
        start_date = st.date_input(
            "Select Start Date", 
            min_value=datetime.now().date(),
            key=f"start_date_{st.session_state.start_date_key}"
        )
    with col2:
        interval = st.selectbox(
            "Select Interval (weeks)", 
            options=[1, 2, 3, 4],
            key=f"interval_{st.session_state.interval_key}"
        )
    
    response_data = fetch_users()
    
    if response_data and 'users' in response_data and 'groups' in response_data:
        all_employees = []
        available_employees = []
        
        for user in response_data['users']:
            position, position_id = get_position_from_groups(user['groupIds'], response_data['groups'])
            # Exclude Head of People and Operations, AI Engineers, and Mukund Chopra
            if (position != 'Head of People and Operations' and 
                position != 'AI Engineer' and 
                f"{user['legalName']} {user['lastname']}" != "Mukund Chopra"):
                employee_data = {
                        'id': user['id'],
                        'full_name': f"{user['legalName']} {user['lastname']}",
                        'position': position,
                        'position_id': position_id,
                        'display_name': f"{user['legalName']} {user['lastname']} ({position})"
                }
                all_employees.append(employee_data)
                available_employees.append(employee_data)
        
        if available_employees:
            # Create employee options dictionary
            employee_options = {emp['display_name']: emp for emp in available_employees}
            
            # Create the multiselect without any session state dependency
            if 'selected_employees_key' not in st.session_state:
                st.session_state.selected_employees_key = 0
            
            selected_names = st.multiselect(
                "Select Employees for Shift Creation",
                options=list(employee_options.keys()),
                key=f"employee_multiselect_{st.session_state.selected_employees_key}"
            )
            
            if selected_names:
                # Initialize shift selections
                if 'shift_selections' not in st.session_state:
                    st.session_state.shift_selections = {}
                
                # Create date range for the interval
                dates = []
                current_date = start_date
                for _ in range(7 * interval):
                    dates.append(current_date)
                    current_date += timedelta(days=1)
                
                # Create the shift selection table
                shift_selection_data = []
                
                for name in selected_names:
                    employee = employee_options[name]
                    emp_id = employee['id']
                    
                    # Initialize shift selections for this employee if not exists
                    if emp_id not in st.session_state.shift_selections:
                        st.session_state.shift_selections[emp_id] = {}
                    
                    # Update shift selections with any new dates
                    for date in dates:
                        date_str = date.strftime("%Y-%m-%d")
                        if date_str not in st.session_state.shift_selections[emp_id]:
                            st.session_state.shift_selections[emp_id][date_str] = False
                    
                    row = {'Employee': employee['display_name']}
                    
                    # Add date columns
                    for date in dates:
                        date_str = date.strftime("%Y-%m-%d")
                        row[date_str] = st.session_state.shift_selections[emp_id][date_str]
                    
                    shift_selection_data.append(row)
                
                # Create DataFrame
                selection_df = pd.DataFrame(shift_selection_data)
                
                # Create the interactive table
                edited_df = st.data_editor(
                    selection_df,
                    hide_index=True,
                    column_config={
                        'Employee': st.column_config.Column(
                            'Employee',
                            width='medium',
                            required=True
                        ),
                        **{
                            date.strftime("%Y-%m-%d"): st.column_config.CheckboxColumn(
                                f"{date.strftime('%a')} ({date.strftime('%d').lstrip('0')} {date.strftime('%b')})",
                                default=False,
                                width='small'
                            )
                            for date in dates
                        }
                    },
                    key="shift_selection_table"
                )

                # Add a single Create Shifts button for all employees
                if st.button("Create Shifts for All Selected Employees"):
                    message_container = st.empty()
                    progress_container = st.empty()
                    
                    with progress_container:
                                progress_text = "Creating shifts for all employees..."
                                progress_bar = st.progress(0)
                                st.markdown(f"<p style='color: #666;'>{progress_text}</p>", unsafe_allow_html=True)
                                
                                total_employees = len(selected_names)
                    success_count = 0
                    messages = []
                    
                    employees_to_process = selected_names.copy()
                    
                    for index, name in enumerate(employees_to_process):
                        employee = employee_options[name]
                        selected_days = {}
                        
                        employee_row = edited_df[edited_df['Employee'] == employee['display_name']]
                        
                        if not employee_row.empty:
                            for date in dates:
                                day_name = date.strftime("%A")
                                date_str = date.strftime("%Y-%m-%d")
                                selected_days[day_name] = employee_row[date_str].iloc[0]
                            
                            if any(selected_days.values()):
                                try:
                                    if create_shift(employee['id'], employee['position_id'], start_date, selected_days, interval, shift_type):
                                        messages.append(("success", f"✅ Shift created successfully for {employee['full_name']}"))
                                        success_count += 1
                                except Exception as e:
                                    messages.append(("error", f"❌ Error creating shift for {employee['full_name']}: {str(e)}"))
                            else:
                                messages.append(("warning", f"⚠️ Please select at least one day for {employee['full_name']}"))
                        else:
                            messages.append(("error", f"❌ Could not find data for {employee['full_name']}"))
                        
                        progress_bar.progress((index + 1) / total_employees)
                        
                        with message_container:
                            for msg_type, msg in messages:
                                if msg_type == "success":
                                    st.success(msg)
                                elif msg_type == "warning":
                                    st.warning(msg)
                                else:
                                    st.error(msg)
                    
                    if success_count > 0:
                        st.info(f"✨ Successfully created shifts for {success_count} out of {total_employees} employees")
                        # Reset all session state variables
                        st.session_state.shift_selections = {}
                        st.session_state.shift_type_key += 1
                        st.session_state.start_date_key += 1
                        st.session_state.interval_key += 1
                        st.session_state.selected_employees_key += 1
                        # Clear the selection table key
                        if "shift_selection_table" in st.session_state:
                            del st.session_state["shift_selection_table"]
                        time.sleep(2)
                        st.rerun()
                    else:
                        st.error("No shifts were created. Please select days for at least one employee.")

if __name__ == "__main__":
    main()
