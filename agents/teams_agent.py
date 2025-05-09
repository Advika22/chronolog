import requests
import logging
from datetime import datetime, timedelta
import pytz
from services.auth_service import auth_service
from config.config import TIME_ZONE

logger = logging.getLogger('chronolog.agents.teams')

class TeamsAgent:
    """Agent for collecting data from Microsoft Teams (meetings and chats)"""
    
    def __init__(self):
        self.graph_base_url = 'https://graph.microsoft.com/v1.0'
        self.tz = pytz.timezone(TIME_ZONE)
    
    def _get_headers(self):
        """Get headers for Microsoft Graph API requests"""
        token = auth_service.get_microsoft_token()
        return {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json'
        }
    
    def get_teams_meetings(self, start_date, end_date):
        """
        Get Teams meetings between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of Teams meetings with relevant details
        """
        # NOTE: Teams meetings are also available in the calendar
        # This method can be used to get additional Teams-specific details
        
        # Format dates for Microsoft Graph API
        start_str = start_date.astimezone(self.tz).isoformat()
        end_str = end_date.astimezone(self.tz).isoformat()
        
        # API endpoint for online meetings
        url = f"{self.graph_base_url}/me/onlineMeetings"
        
        # NOTE: Unfortunately, Graph API doesn't support filtering onlineMeetings by date
        # So we'll get all and filter client-side
        
        try:
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            all_meetings = response.json().get('value', [])
            
            # Filter meetings within our date range
            filtered_meetings = []
            for meeting in all_meetings:
                if 'startDateTime' in meeting:
                    start_time = datetime.fromisoformat(meeting['startDateTime'].replace('Z', '+00:00'))
                    end_time = datetime.fromisoformat(meeting['endDateTime'].replace('Z', '+00:00'))
                    
                    # Check if meeting is within our date range
                    if start_time >= start_date and end_time <= end_date:
                        duration_minutes = (end_time - start_time).total_seconds() / 60
                        
                        filtered_meetings.append({
                            'source': 'teams_meeting',
                            'title': meeting.get('subject', 'Teams Meeting'),
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration_minutes': duration_minutes,
                            'participants_count': len(meeting.get('participants', {}).get('attendees', [])),
                            'join_url': meeting.get('joinUrl', ''),
                            'raw_data': meeting
                        })
            
            logger.info(f"Retrieved {len(filtered_meetings)} Teams meetings")
            return filtered_meetings
            
        except Exception as e:
            logger.error(f"Error retrieving Teams meetings: {e}")
            return []
    
    def get_teams_chat_activity(self, start_date, end_date):
        """
        Get Teams chat activity between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of Teams chat activity periods with relevant details
        """
        # Format dates for Microsoft Graph API
        start_str = start_date.astimezone(self.tz).isoformat()
        end_str = end_date.astimezone(self.tz).isoformat()
        
        # API endpoint for chats
        url = f"{self.graph_base_url}/me/chats"
        
        try:
            # Get list of chats
            response = requests.get(url, headers=self._get_headers())
            response.raise_for_status()
            
            chats = response.json().get('value', [])
            
            chat_activities = []
            
            # For each chat, get recent messages
            for chat in chats:
                chat_id = chat['id']
                messages_url = f"{self.graph_base_url}/me/chats/{chat_id}/messages"
                
                # Filter by date
                messages_params = {
                    '$filter': f"lastModifiedDateTime ge {start_str} and lastModifiedDateTime le {end_str}",
                    '$orderby': 'lastModifiedDateTime asc',
                    '$top': 50  # Adjust based on expected volume
                }
                
                try:
                    messages_response = requests.get(
                        messages_url, 
                        headers=self._get_headers(), 
                        params=messages_params
                    )
                    messages_response.raise_for_status()
                    
                    messages = messages_response.json().get('value', [])
                    
                    # Group messages by time periods (if messages are within 5 minutes, consider as one activity)
                    if messages:
                        current_group = {
                            'start_time': datetime.fromisoformat(messages[0]['lastModifiedDateTime'].replace('Z', '+00:00')),
                            'end_time': datetime.fromisoformat(messages[0]['lastModifiedDateTime'].replace('Z', '+00:00')),
                            'message_count': 1,
                            'chat_name': chat.get('topic', 'Chat'),
                            'chat_type': chat.get('chatType', 'unknown'),
                            'messages': [messages[0]]
                        }
                        
                        for i in range(1, len(messages)):
                            msg_time = datetime.fromisoformat(messages[i]['lastModifiedDateTime'].replace('Z', '+00:00'))
                            
                            # If message is within 5 minutes of current group's end time, add to group
                            if (msg_time - current_group['end_time']).total_seconds() <= 300:  # 5 minutes
                                current_group['end_time'] = msg_time
                                current_group['message_count'] += 1
                                current_group['messages'].append(messages[i])
                            else:
                                # Add current group to activities and start a new one
                                duration = (current_group['end_time'] - current_group['start_time']).total_seconds() / 60
                                
                                chat_activities.append({
                                    'source': 'teams_chat',
                                    'title': f"Chat in {current_group['chat_name']}",
                                    'start_time': current_group['start_time'],
                                    'end_time': current_group['end_time'],
                                    'duration_minutes': max(duration, 1),  # Minimum 1 minute
                                    'message_count': current_group['message_count'],
                                    'chat_type': current_group['chat_type'],
                                    'chat_name': current_group['chat_name'],
                                    'raw_data': {
                                        'chat': chat,
                                        'first_message_preview': current_group['messages'][0].get('body', {}).get('content', '')[:100]
                                    }
                                })
                                
                                # Start new group
                                current_group = {
                                    'start_time': msg_time,
                                    'end_time': msg_time,
                                    'message_count': 1,
                                    'chat_name': chat.get('topic', 'Chat'),
                                    'chat_type': chat.get('chatType', 'unknown'),
                                    'messages': [messages[i]]
                                }
                        
                        # Add the last group
                        duration = (current_group['end_time'] - current_group['start_time']).total_seconds() / 60
                        
                        chat_activities.append({
                            'source': 'teams_chat',
                            'title': f"Chat in {current_group['chat_name']}",
                            'start_time': current_group['start_time'],
                            'end_time': current_group['end_time'],
                            'duration_minutes': max(duration, 1),  # Minimum 1 minute
                            'message_count': current_group['message_count'],
                            'chat_type': current_group['chat_type'],
                            'chat_name': current_group['chat_name'],
                            'raw_data': {
                                'chat': chat,
                                'first_message_preview': current_group['messages'][0].get('body', {}).get('content', '')[:100]
                            }
                        })
                
                except Exception as e:
                    logger.warning(f"Error retrieving messages for chat {chat_id}: {e}")
                    continue
            
            logger.info(f"Retrieved {len(chat_activities)} Teams chat activities")
            return chat_activities
            
        except Exception as e:
            logger.error(f"Error retrieving Teams chat activities: {e}")
            return []
    
    def get_activities(self, start_date, end_date):
        """
        Get all Teams activities between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of all activities from Teams
        """
        meetings = self.get_teams_meetings(start_date, end_date)
        chat_activities = self.get_teams_chat_activity(start_date, end_date)
        
        all_activities = meetings + chat_activities
        
        # Sort by start time
        all_activities.sort(key=lambda x: x['start_time'])
        
        return all_activities

# Create a singleton instance
teams_agent = TeamsAgent()