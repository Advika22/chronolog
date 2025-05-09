import logging
from datetime import datetime, timedelta, time
import pytz
from config.config import TIME_ZONE, MINIMUM_ACTIVITY_DURATION, ACTIVITY_MERGE_THRESHOLD, DEFAULT_WORKING_HOURS

logger = logging.getLogger('chronolog.utils.time')

def get_yesterday():
    """Get yesterday's date range (from midnight to midnight)"""
    tz = pytz.timezone(TIME_ZONE)
    today = datetime.now(tz).replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday = today - timedelta(days=1)
    return yesterday, today

def get_date_range(date_str=None, days=1):
    """
    Get date range for a specific date or date range
    
    Args:
        date_str: Date string in format 'YYYY-MM-DD' or 'YYYY-MM-DD:YYYY-MM-DD'
        days: Number of days if only start date is provided
        
    Returns:
        Tuple of (start_date, end_date) as datetime objects
    """
    tz = pytz.timezone(TIME_ZONE)
    
    if not date_str:
        # Default to yesterday
        return get_yesterday()
    
    if ':' in date_str:
        # Date range format: 'YYYY-MM-DD:YYYY-MM-DD'
        start_str, end_str = date_str.split(':')
        start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=tz)
        end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(tzinfo=tz)
        # Set end date to end of day
        end_date = end_date.replace(hour=23, minute=59, second=59)
    else:
        # Single date format: 'YYYY-MM-DD'
        start_date = datetime.strptime(date_str, '%Y-%m-%d').replace(tzinfo=tz)
        end_date = start_date + timedelta(days=days)
        # Set end date to end of day
        end_date = end_date.replace(hour=23, minute=59, second=59)
    
    return start_date, end_date

def filter_activities_by_date(activities, start_date, end_date):
    """Filter activities to only include those within the date range"""
    return [
        activity for activity in activities 
        if activity['start_time'] >= start_date and activity['end_time'] <= end_date
    ]

def merge_overlapping_activities(activities):
    """
    Merge activities that overlap in time
    
    When activities overlap, they are merged with the following rules:
    - The merged activity gets the earliest start time of all merged activities
    - The merged activity gets the latest end time of all merged activities
    - The merged activity source becomes a comma-separated list of all sources
    - The merged activity title combines the titles with a semicolon
    - Other fields use the values from the activity with the longest duration
    
    Args:
        activities: List of activity dicts
        
    Returns:
        List of merged activities
    """
    if not activities:
        return []
    
    # Sort activities by start time
    sorted_activities = sorted(activities, key=lambda x: x['start_time'])
    
    merged = []
    current = sorted_activities[0]
    
    for next_activity in sorted_activities[1:]:
        # Check if activities overlap
        if next_activity['start_time'] <= current['end_time'] or \
           (next_activity['start_time'] - current['end_time']).total_seconds() / 60 <= ACTIVITY_MERGE_THRESHOLD:
            
            # Merge activities
            merged_activity = {
                'source': f"{current['source']},{next_activity['source']}",
                'title': f"{current['title']}; {next_activity['title']}",
                'start_time': min(current['start_time'], next_activity['start_time']),
                'end_time': max(current['end_time'], next_activity['end_time'])
            }
            
            # Calculate durations
            current_duration = (current['end_time'] - current['start_time']).total_seconds()
            next_duration = (next_activity['end_time'] - next_activity['start_time']).total_seconds()
            
            # Keep other fields from the longer activity
            donor = current if current_duration > next_duration else next_activity
            
            for key, value in donor.items():
                if key not in ['source', 'title', 'start_time', 'end_time']:
                    merged_activity[key] = value
            
            # Update duration_minutes
            merged_activity['duration_minutes'] = (merged_activity['end_time'] - merged_activity['start_time']).total_seconds() / 60
            
            current = merged_activity
        else:
            merged.append(current)
            current = next_activity
    
    # Add the last activity
    merged.append(current)
    
    logger.info(f"Merged {len(activities)} activities into {len(merged)} activities")
    return merged

def fill_time_gaps(activities, min_gap_minutes=30, working_hours=DEFAULT_WORKING_HOURS):
    """
    Fill gaps between activities with 'Unknown' activities
    
    Args:
        activities: List of activity dicts
        min_gap_minutes: Minimum gap size to fill (in minutes)
        working_hours: Tuple of (start_hour, end_hour) for working day
        
    Returns:
        List of activities with gaps filled
    """
    if not activities or len(activities) < 2:
        return activities
    
    # Sort activities by start time
    sorted_activities = sorted(activities, key=lambda x: x['start_time'])
    
    # Get time zone
    tz = pytz.timezone(TIME_ZONE)
    work_start_hour, work_end_hour = working_hours
    
    result = [sorted_activities[0]]
    
    for i in range(1, len(sorted_activities)):
        prev_end = sorted_activities[i-1]['end_time']
        curr_start = sorted_activities[i]['start_time']
        
        # Calculate gap in minutes
        gap_minutes = (curr_start - prev_end).total_seconds() / 60
        
        # Only fill gaps that are larger than min_gap_minutes
        # and are within working hours
        if gap_minutes >= min_gap_minutes:
            # Check if gap is within working hours
            # Get the day's working hours start and end times
            day_start = prev_end.replace(hour=work_start_hour, minute=0, second=0, microsecond=0)
            day_end = prev_end.replace(hour=work_end_hour, minute=0, second=0, microsecond=0)
            
            # If the gap extends past working hours, adjust the times
            gap_start = max(prev_end, day_start)
            gap_end = min(curr_start, day_end)
            
            # Only create a gap activity if there's still a meaningful gap
            gap_minutes = (gap_end - gap_start).total_seconds() / 60
            if gap_minutes >= min_gap_minutes:
                gap_activity = {
                    'source': 'time_gap',
                    'title': 'Unknown Activity',
                    'start_time': gap_start,
                    'end_time': gap_end,
                    'duration_minutes': gap_minutes,
                    'task_type': 'Unknown',
                    'jira_issue': 'unknown',
                    'description': 'Untracked time',
                    'billable': False
                }
                result.append(gap_activity)
        
        # Add the current activity
        result.append(sorted_activities[i])
    
    logger.info(f"Added {len(result) - len(sorted_activities)} gap activities")
    return result

def group_activities_by_day(activities):
    """Group activities by day"""
    days = {}
    
    for activity in activities:
        # Get the day as a string
        day_str = activity['start_time'].strftime('%Y-%m-%d')
        
        if day_str not in days:
            days[day_str] = []
        
        days[day_str].append(activity)
    
    # Sort each day's activities by start time
    for day_str in days:
        days[day_str].sort(key=lambda x: x['start_time'])
    
    return days

def calculate_daily_totals(activities):
    """
    Calculate daily total time for each task type and Jira issue
    
    Args:
        activities: List of activity dicts
        
    Returns:
        Dict with daily totals
    """
    days = group_activities_by_day(activities)
    
    daily_totals = {}
    
    for day_str, day_activities in days.items():
        # Initialize totals for this day
        daily_totals[day_str] = {
            'total_minutes': 0,
            'billable_minutes': 0,
            'task_types': {},
            'jira_issues': {}
        }
        
        # Calculate totals
        for activity in day_activities:
            duration_minutes = activity.get('duration_minutes', 0)
            task_type = activity.get('task_type', 'Unknown')
            jira_issue = activity.get('jira_issue', 'unknown')
            billable = activity.get('billable', False)
            
            # Add to total minutes
            daily_totals[day_str]['total_minutes'] += duration_minutes
            
            # Add to billable minutes if applicable
            if billable:
                daily_totals[day_str]['billable_minutes'] += duration_minutes
            
            # Add to task type totals
            if task_type not in daily_totals[day_str]['task_types']:
                daily_totals[day_str]['task_types'][task_type] = 0
            daily_totals[day_str]['task_types'][task_type] += duration_minutes
            
            # Add to Jira issue totals
            if jira_issue not in daily_totals[day_str]['jira_issues']:
                daily_totals[day_str]['jira_issues'][jira_issue] = 0
            daily_totals[day_str]['jira_issues'][jira_issue] += duration_minutes
    
    return daily_totals

def format_duration(minutes):
    """Format duration in minutes to a human-readable string"""
    hours = minutes // 60
    mins = minutes % 60
    
    if hours > 0 and mins > 0:
        return f"{hours}h {mins}m"
    elif hours > 0:
        return f"{hours}h"
    else:
        return f"{mins}m"