import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta, time
import pytz
import logging
import os
import json

from agents.outlook_agent import outlook_agent
from agents.teams_agent import teams_agent
from agents.github_agent import github_agent
from agents.wakatime_agent import wakatime_agent
from agents.bedrock_agent import bedrock_agent
from services.jira_service import jira_service
from utils.time_utils import (
    get_yesterday, get_date_range, merge_overlapping_activities,
    fill_time_gaps, calculate_daily_totals, format_duration,
    group_activities_by_day
)
from utils.logging_utils import (
    save_activities_to_file, load_activities_from_file,
    get_saved_activity_files, log_activity_summary,
    log_jira_submission_results
)
from config.config import TIME_ZONE

logger = logging.getLogger('chronolog.ui')

def run_app():
    """Run the Streamlit app"""
    st.set_page_config(
        page_title="ChronoLog - Smart Time Tracker",
        page_icon="⏱️",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Custom CSS
    st.markdown("""
    <style>
    .main {
        padding: 1rem;
    }
    .time-block {
        border-radius: 5px;
        padding: 10px;
        margin: 5px 0;
    }
    .stButton button {
        width: 100%;
    }
    </style>
    """, unsafe_allow_html=True)
    
    # Sidebar
    with st.sidebar:
        st.title("⏱️ ChronoLog")
        st.markdown("---")
        
        # Date selection
        st.subheader("Select Date Range")
        today = datetime.now().date()
        yesterday = (today - timedelta(days=1))
        default_date = yesterday
        
        date_selection = st.radio(
            "Period",
            [
                "Yesterday",
                "Today",
                "Custom Date",
                "Date Range",
                "This Week",
                "Last Week", 
                "This Month"
            ],
            index=0
        )
        
        if date_selection == "Yesterday":
            start_date, end_date = get_yesterday()
            date_range_display = f"{start_date.strftime('%Y-%m-%d')}"
        elif date_selection == "Today":
            tz = pytz.timezone(TIME_ZONE)
            start_date = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = datetime.now(tz)
            date_range_display = f"{start_date.strftime('%Y-%m-%d')}"
        elif date_selection == "Custom Date":
            selected_date = st.date_input("Date", default_date)
            tz = pytz.timezone(TIME_ZONE)
            start_date = datetime.combine(selected_date, time.min).replace(tzinfo=tz)
            end_date = datetime.combine(selected_date, time.max).replace(tzinfo=tz)
            date_range_display = f"{start_date.strftime('%Y-%m-%d')}"
        elif date_selection == "Date Range":
            col1, col2 = st.columns(2)
            start_date_input = col1.date_input("Start Date", default_date)
            end_date_input = col2.date_input("End Date", default_date)
            
            tz = pytz.timezone(TIME_ZONE)
            start_date = datetime.combine(start_date_input, time.min).replace(tzinfo=tz)
            end_date = datetime.combine(end_date_input, time.max).replace(tzinfo=tz)
            date_range_display = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        elif date_selection == "This Week":
            tz = pytz.timezone(TIME_ZONE)
            # Get start of current week (Monday)
            today = datetime.now(tz).date()
            start_of_week = today - timedelta(days=today.weekday())
            start_date = datetime.combine(start_of_week, time.min).replace(tzinfo=tz)
            end_date = datetime.now(tz)
            date_range_display = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        elif date_selection == "Last Week":
            tz = pytz.timezone(TIME_ZONE)
            # Get start of previous week (Monday)
            today = datetime.now(tz).date()
            start_of_last_week = today - timedelta(days=today.weekday() + 7)
            end_of_last_week = start_of_last_week + timedelta(days=6)
            start_date = datetime.combine(start_of_last_week, time.min).replace(tzinfo=tz)
            end_date = datetime.combine(end_of_last_week, time.max).replace(tzinfo=tz)
            date_range_display = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        elif date_selection == "This Month":
            tz = pytz.timezone(TIME_ZONE)
            # Get start of current month
            today = datetime.now(tz).date()
            start_of_month = today.replace(day=1)
            start_date = datetime.combine(start_of_month, time.min).replace(tzinfo=tz)
            end_date = datetime.now(tz)
            date_range_display = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
        
        st.markdown(f"**Selected Period**: {date_range_display}")
        st.markdown("---")
        
        # Data sources selection
        st.subheader("Data Sources")
        use_outlook = st.checkbox("Microsoft Outlook", value=True)
        use_teams = st.checkbox("Microsoft Teams", value=True)
        use_github = st.checkbox("GitHub", value=True)
        use_wakatime = st.checkbox("WakaTime", value=True)
        
        st.markdown("---")
        
        # Actions
        st.subheader("Actions")
        fetch_button = st.button("Fetch Activities", use_container_width=True)
        
        # Cached activities
        st.markdown("---")
        st.subheader("Saved Activities")
        saved_files = get_saved_activity_files()
        if saved_files:
            selected_file = st.selectbox("Load from file", saved_files)
            load_button = st.button("Load Selected", use_container_width=True)
        else:
            st.info("No saved activity files found")
            load_button = False
    
    # Main content
    st.title("ChronoLog - Smart Time Tracker")
    st.subheader(f"Activities for {date_range_display}")
    
    # Initialize session state
    if 'activities' not in st.session_state:
        st.session_state.activities = []
    if 'analyzed_activities' not in st.session_state:
        st.session_state.analyzed_activities = []
    if 'jira_issues' not in st.session_state:
        st.session_state.jira_issues = []
    if 'daily_totals' not in st.session_state:
        st.session_state.daily_totals = {}
    if 'fetching_data' not in st.session_state:
        st.session_state.fetching_data = False
    if 'analyzing_data' not in st.session_state:
        st.session_state.analyzing_data = False
    if 'submitting_data' not in st.session_state:
        st.session_state.submitting_data = False
    
    # Handle button actions
    if fetch_button:
        st.session_state.fetching_data = True
    
    if load_button and 'selected_file' in locals():
        filepath = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache', selected_file)
        st.session_state.analyzed_activities = load_activities_from_file(filepath)
        if st.session_state.analyzed_activities:
            # Calculate daily totals
            st.session_state.daily_totals = calculate_daily_totals(st.session_state.analyzed_activities)
            # Fetch Jira issues for reference
            st.session_state.jira_issues = jira_service.get_user_issues()
            st.success(f"Loaded {len(st.session_state.analyzed_activities)} activities from file.")
        else:
            st.error("Failed to load activities from file.")
    
    # Fetch data if requested
    if st.session_state.fetching_data:
        st.session_state.fetching_data = False
        
        with st.spinner("Fetching activities..."):
            all_activities = []
            
            try:
                # Fetch data from selected sources
                if use_outlook:
                    with st.status("Fetching Outlook activities...", state="running"):
                        outlook_activities = outlook_agent.get_activities(start_date, end_date)
                        all_activities.extend(outlook_activities)
                        st.write(f"Found {len(outlook_activities)} Outlook activities")
                
                if use_teams:
                    with st.status("Fetching Teams activities...", state="running"):
                        teams_activities = teams_agent.get_activities(start_date, end_date)
                        all_activities.extend(teams_activities)
                        st.write(f"Found {len(teams_activities)} Teams activities")
                
                if use_github:
                    with st.status("Fetching GitHub activities...", state="running"):
                        github_activities = github_agent.get_activities(start_date, end_date)
                        all_activities.extend(github_activities)
                        st.write(f"Found {len(github_activities)} GitHub activities")
                
                if use_wakatime:
                    with st.status("Fetching WakaTime activities...", state="running"):
                        wakatime_activities = wakatime_agent.get_activities(start_date, end_date)
                        all_activities.extend(wakatime_activities)
                        st.write(f"Found {len(wakatime_activities)} WakaTime activities")
                
                # Process activities
                st.session_state.activities = all_activities
                
                # Merge overlapping activities
                merged_activities = merge_overlapping_activities(all_activities)
                
                # Fill gaps
                filled_activities = fill_time_gaps(merged_activities)
                
                # Save activities
                if filled_activities:
                    save_activities_to_file(filled_activities, f"activities_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
                
                # Now we need to analyze activities using Bedrock
                st.session_state.analyzing_data = True
                
            except Exception as e:
                st.error(f"Error fetching activities: {e}")
                logger.error(f"Error fetching activities: {e}", exc_info=True)
    
    # Analyze data if needed
    if st.session_state.analyzing_data:
        st.session_state.analyzing_data = False
        
        with st.spinner("Analyzing activities with AWS Bedrock..."):
            try:
                # Analyze activities
                analyzed_activities = bedrock_agent.categorize_activities(st.session_state.activities)
                
                # Save analyzed activities
                if analyzed_activities:
                    save_activities_to_file(analyzed_activities)
                
                # Update session state
                st.session_state.analyzed_activities = analyzed_activities
                
                # Calculate daily totals
                st.session_state.daily_totals = calculate_daily_totals(analyzed_activities)
                
                # Fetch Jira issues for reference
                st.session_state.jira_issues = jira_service.get_user_issues()
                
                st.success(f"Successfully analyzed {len(analyzed_activities)} activities.")
                
            except Exception as e:
                st.error(f"Error analyzing activities: {e}")
                logger.error(f"Error analyzing activities: {e}", exc_info=True)
    
    # Display activities if available
    if st.session_state.analyzed_activities:
        # Create tabs for different views
        tab1, tab2, tab3, tab4 = st.tabs(["Timeline", "Summary", "Jira Time Entries", "Raw Data"])
        
        with tab1:
            st.subheader("Activity Timeline")
            
            # Group activities by day
            activities_by_day = group_activities_by_day(st.session_state.analyzed_activities)
            
            for day_str, day_activities in activities_by_day.items():
                st.write(f"### {day_str}")
                
                # Create Gantt chart with plotly
                fig = px.timeline(
                    pd.DataFrame([
                        {
                            'Task': f"{activity.get('title', 'Unknown')} ({activity.get('source', 'unknown')})",
                            'Start': activity['start_time'],
                            'Finish': activity['end_time'],
                            'Source': activity.get('source', 'unknown'),
                            'TaskType': activity.get('task_type', 'Unknown'),
                            'JiraIssue': activity.get('jira_issue', 'unknown'),
                            'Duration': format_duration(activity.get('duration_minutes', 0))
                        }
                        for activity in day_activities
                    ]),
                    x_start="Start",
                    x_end="Finish",
                    y="Task",
                    color="TaskType",
                    hover_data=["Source", "JiraIssue", "Duration"]
                )
                
                # Update layout
                fig.update_layout(
                    height=min(60 * len(day_activities), 800),
                    xaxis_title="Time",
                    yaxis_title=None,
                    title=None
                )
                
                st.plotly_chart(fig, use_container_width=True)
        
        with tab2:
            st.subheader("Daily Summary")
            
            for day_str, totals in st.session_state.daily_totals.items():
                st.write(f"### {day_str}")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.metric("Total Hours", f"{totals['total_minutes'] / 60:.1f}h")
                    
                    # Create pie chart for task types
                    if totals['task_types']:
                        task_types_df = pd.DataFrame({
                            'Task Type': list(totals['task_types'].keys()),
                            'Minutes': list(totals['task_types'].values())
                        })
                        fig = px.pie(
                            task_types_df,
                            values='Minutes',
                            names='Task Type',
                            title="Time by Task Type"
                        )
                        st.plotly_chart(fig, use_container_width=True)
                
                with col2:
                    st.metric("Billable Hours", f"{totals['billable_minutes'] / 60:.1f}h")
                    
                    # Create pie chart for Jira issues
                    if totals['jira_issues']:
                        # Filter out 'unknown' issue if it exists
                        jira_issues = {k: v for k, v in totals['jira_issues'].items() if k != 'unknown'}
                        
                        if jira_issues:
                            jira_issues_df = pd.DataFrame({
                                'Jira Issue': list(jira_issues.keys()),
                                'Minutes': list(jira_issues.values())
                            })
                            fig = px.pie(
                                jira_issues_df,
                                values='Minutes',
                                names='Jira Issue',
                                title="Time by Jira Issue"
                            )
                            st.plotly_chart(fig, use_container_width=True)
        
        with tab3:
            st.subheader("Jira Time Entries")
            
            # Create dataframe for time entries
            time_entries_data = []
            
            for activity in st.session_state.analyzed_activities:
                # Skip activities with no Jira issue or 'unknown' issue
                if not activity.get('jira_issue') or activity.get('jira_issue') == 'unknown':
                    continue
                
                time_entries_data.append({
                    'Jira Issue': activity.get('jira_issue', 'unknown'),
                    'Description': activity.get('description', 'Unknown Activity'),
                    'Duration': format_duration(activity.get('duration_minutes', 0)),
                    'Start Time': activity.get('start_time', '').strftime('%Y-%m-%d %H:%M'),
                    'Task Type': activity.get('task_type', 'Unknown'),
                    'Source': activity.get('source', 'unknown'),
                    'Duration Minutes': activity.get('duration_minutes', 0),
                    'Activity ID': id(activity)  # Use object ID as a unique identifier
                })
            
            if time_entries_data:
                time_entries_df = pd.DataFrame(time_entries_data)
                
                # Allow user to edit the entries
                edited_df = st.data_editor(
                    time_entries_df,
                    column_config={
                        "Jira Issue": st.column_config.TextColumn(
                            "Jira Issue",
                            width="medium",
                            required=True
                        ),
                        "Description": st.column_config.TextColumn(
                            "Description",
                            width="large",
                            required=True
                        ),
                        "Duration": st.column_config.TextColumn(
                            "Duration",
                            width="small",
                            disabled=True
                        ),
                        "Start Time": st.column_config.TextColumn(
                            "Start Time",
                            width="medium",
                            disabled=True
                        ),
                        "Task Type": st.column_config.SelectboxColumn(
                            "Task Type",
                            width="medium",
                            options=[
                                "Development",
                                "Documentation",
                                "Meeting",
                                "Code Review",
                                "Research",
                                "Communication",
                                "Planning",
                                "Testing",
                                "Bugfix",
                                "Design",
                                "Other"
                            ]
                        ),
                        "Source": st.column_config.TextColumn(
                            "Source",
                            width="medium",
                            disabled=True
                        ),
                        "Duration Minutes": st.column_config.NumberColumn(
                            "Duration Minutes",
                            width="small",
                            format="%d min",
                            disabled=True
                        ),
                        "Activity ID": st.column_config.Column(
                            "Activity ID",
                            width="small",
                            disabled=True,
                            required=True,
                            visibility="hidden"
                        )
                    },
                    hide_index=True,
                    num_rows="dynamic"
                )
                
                # Submit to Jira button
                if st.button("Submit to Jira", use_container_width=True):
                    # Show preview of what will be submitted
                    st.subheader("Preview of Jira Submissions")
                    st.write("The following time entries will be submitted to Jira:")
                    
                    # Create a preview dataframe
                    preview_data = []
                    total_time = 0
                    
                    for _, row in edited_df.iterrows():
                        # Find the original activity to get accurate duration
                        original_activity = None
                        for activity in st.session_state.analyzed_activities:
                            if id(activity) == row['Activity ID']:
                                original_activity = activity
                                break
                        
                        if original_activity:
                            duration_minutes = original_activity.get('duration_minutes', 0)
                            total_time += duration_minutes
                            
                            # Format for preview
                            preview_data.append({
                                'Jira Issue': row['Jira Issue'],
                                'Description': row['Description'],
                                'Duration': format_duration(duration_minutes),
                                'Start Time': original_activity.get('start_time').strftime('%Y-%m-%d %H:%M'),
                                'Task Type': row['Task Type']
                            })
                    
                    # Show preview table
                    preview_df = pd.DataFrame(preview_data)
                    st.dataframe(preview_df, use_container_width=True)
                    
                    # Show total time being logged
                    st.metric("Total Time to be Logged", format_duration(total_time))
                    
                    # Final confirmation
                    if st.button("Confirm and Submit to Jira", key="final_confirm", type="primary"):
                        st.session_state.submitting_data = True
                        
                        # Convert edited dataframe back to entries format
                        entries_to_submit = []
                        
                        for _, row in edited_df.iterrows():
                            # Find the original activity
                            original_activity = None
                            for activity in st.session_state.analyzed_activities:
                                if id(activity) == row['Activity ID']:
                                    original_activity = activity
                                    break
                            
                            if original_activity:
                                entries_to_submit.append({
                                    'jira_issue': row['Jira Issue'],
                                    'description': row['Description'],
                                    'duration_minutes': original_activity.get('duration_minutes', 0),
                                    'start_time': original_activity.get('start_time'),
                                    'task_type': row['Task Type'],
                                    'source': original_activity.get('source', 'unknown')
                                })
                        
                        # Submit to Jira
                        with st.spinner("Submitting time entries to Jira..."):
                            results = jira_service.submit_time_entries(entries_to_submit)
                            log_jira_submission_results(results)
                            
                            st.success(f"Submitted {results['success']} time entries to Jira successfully.")
                            if results['error'] > 0:
                                st.warning(f"Failed to submit {results['error']} time entries.")
                            if results['skipped'] > 0:
                                st.info(f"Skipped {results['skipped']} time entries.")
                        
                        st.session_state.submitting_data = False
            else:
                st.info("No Jira time entries to display.")
        
        with tab4:
            st.subheader("Raw Activity Data")
            
            # Show raw data
            activities_df = pd.DataFrame([
                {
                    'Source': activity.get('source', 'unknown'),
                    'Title': activity.get('title', 'Unknown'),
                    'Start Time': activity.get('start_time', '').strftime('%Y-%m-%d %H:%M'),
                    'End Time': activity.get('end_time', '').strftime('%Y-%m-%d %H:%M'),
                    'Duration': format_duration(activity.get('duration_minutes', 0)),
                    'Task Type': activity.get('task_type', 'Unknown'),
                    'Jira Issue': activity.get('jira_issue', 'unknown'),
                    'Description': activity.get('description', ''),
                    'Billable': activity.get('billable', False)
                }
                for activity in st.session_state.analyzed_activities
            ])
            
            st.dataframe(activities_df, use_container_width=True, height=600)
            
            # Allow downloading as CSV
            @st.cache_data
            def convert_df_to_csv(df):
                return df.to_csv(index=False).encode('utf-8')
            
            csv = convert_df_to_csv(activities_df)
            st.download_button(
                "Download CSV",
                csv,
                f"chronolog_activities_{datetime.now().strftime('%Y%m%d')}.csv",
                "text/csv",
                key='download-csv'
            )
    
    else:
        # No activities yet
        st.info("No activities loaded. Use the sidebar to fetch or load activities.")

if __name__ == "__main__":
    run_app()