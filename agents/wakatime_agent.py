import requests
import logging
from datetime import datetime, timedelta
import pytz
from services.auth_service import auth_service
from config.config import TIME_ZONE, WAKATIME_BASE_URL

logger = logging.getLogger('chronolog.agents.wakatime')

class WakaTimeAgent:
    """Agent for collecting coding activity data from WakaTime"""
    
    def __init__(self):
        self.tz = pytz.timezone(TIME_ZONE)
    
    def get_coding_activity(self, start_date, end_date):
        """
        Get coding activity between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of coding activity periods with relevant details
        """
        # Format dates for WakaTime API
        start_str = start_date.strftime('%Y-%m-%d')
        end_str = end_date.strftime('%Y-%m-%d')
        
        # Get headers with authentication
        headers = auth_service.get_wakatime_headers()
        
        # API endpoint for summaries
        url = f"{WAKATIME_BASE_URL}/users/current/summaries"
        
        params = {
            'start': start_str,
            'end': end_str
        }
        
        try:
            response = requests.get(url, headers=headers, params=params)
            response.raise_for_status()
            
            days_data = response.json().get('data', [])
            
            activities = []
            
            for day in days_data:
                day_date = datetime.fromisoformat(day['range']['date']).replace(tzinfo=self.tz)
                
                # Process project summaries
                for project in day.get('projects', []):
                    project_name = project['name']
                    total_seconds = project['total_seconds']
                    
                    # If less than 5 minutes, skip
                    if total_seconds < 300:  # 5 minutes
                        continue
                    
                    # For each project, create an activity
                    # Since WakaTime doesn't provide exact start/end times for projects,
                    # we'll create time blocks based on the project's duration
                    
                    # Start at 9 AM if no better info available
                    project_start = day_date.replace(hour=9, minute=0, second=0)
                    project_end = project_start + timedelta(seconds=total_seconds)
                    
                    activities.append({
                        'source': 'wakatime_project',
                        'title': f"Coding: {project_name}",
                        'start_time': project_start,
                        'end_time': project_end,
                        'duration_minutes': total_seconds / 60,
                        'project': project_name,
                        'language': ", ".join([lang['name'] for lang in project.get('languages', [])[:3]]),
                        'editor': ", ".join([editor['name'] for editor in project.get('editors', [])[:2]]),
                        'raw_data': project
                    })
            
            # Get more detailed data
            # For each day, get the heartbeats/durations to get more accurate time info
            for single_date in (start_date + timedelta(days=n) for n in range((end_date - start_date).days + 1)):
                date_str = single_date.strftime('%Y-%m-%d')
                
                # API endpoint for durations
                durations_url = f"{WAKATIME_BASE_URL}/users/current/durations"
                durations_params = {
                    'date': date_str
                }
                
                try:
                    durations_response = requests.get(durations_url, headers=headers, params=durations_params)
                    durations_response.raise_for_status()
                    
                    durations_data = durations_response.json().get('data', [])
                    
                    # Process durations to get more accurate timings
                    for duration in durations_data:
                        start_time = datetime.fromisoformat(duration['time']).replace(tzinfo=pytz.UTC)
                        end_time = start_time + timedelta(seconds=duration['duration'])
                        
                        # If duration is less than 5 minutes, skip
                        if duration['duration'] < 300:  # 5 minutes
                            continue
                        
                        activities.append({
                            'source': 'wakatime_duration',
                            'title': f"Coding: {duration.get('project', 'Unknown Project')}",
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration_minutes': duration['duration'] / 60,
                            'project': duration.get('project', 'Unknown Project'),
                            'language': duration.get('language', 'Unknown'),
                            'editor': duration.get('editor', 'Unknown'),
                            'raw_data': duration
                        })
                
                except Exception as e:
                    logger.warning(f"Error retrieving WakaTime durations for date {date_str}: {e}")
            
            # Remove duplicate activities (prefer durations over projects)
            filtered_activities = [act for act in activities if act['source'] == 'wakatime_duration']
            
            # If we didn't get any duration data, use the project summary data
            if not filtered_activities:
                filtered_activities = [act for act in activities if act['source'] == 'wakatime_project']
            
            # Sort by start time
            filtered_activities.sort(key=lambda x: x['start_time'])
            
            logger.info(f"Retrieved {len(filtered_activities)} WakaTime activities")
            return filtered_activities
            
        except Exception as e:
            logger.error(f"Error retrieving WakaTime activities: {e}")
            return []
    
    def get_activities(self, start_date, end_date):
        """
        Get all WakaTime activities between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of all activities from WakaTime
        """
        return self.get_coding_activity(start_date, end_date)

# Create a singleton instance
wakatime_agent = WakaTimeAgent()