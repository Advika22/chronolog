import requests
import logging
from datetime import datetime, timedelta
import pytz
from services.auth_service import auth_service
from config.config import TIME_ZONE

logger = logging.getLogger('chronolog.agents.outlook')

class OutlookAgent:
    """Agent for collecting data from Microsoft Outlook (emails and calendar)"""
    
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
    
    def get_calendar_events(self, start_date, end_date):
        """
        Get calendar events between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of calendar events with relevant details
        """
        # Format dates for Microsoft Graph API
        start_str = start_date.astimezone(self.tz).isoformat()
        end_str = end_date.astimezone(self.tz).isoformat()
        
        # API endpoint
        url = f"{self.graph_base_url}/me/calendarview"
        
        params = {
            'startDateTime': start_str,
            'endDateTime': end_str,
            '$select': 'subject,start,end,organizer,attendees,categories,importance,bodyPreview',
            '$orderby': 'start/dateTime',
            '$top': 100  # Adjust based on expected volume
        }
        
        try:
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            
            events_data = response.json().get('value', [])
            
            # Process events into standardized format
            events = []
            for event in events_data:
                # Calculate duration in minutes
                start_time = datetime.fromisoformat(event['start']['dateTime'].replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(event['end']['dateTime'].replace('Z', '+00:00'))
                duration_minutes = (end_time - start_time).total_seconds() / 60
                
                # Skip very short events (less than 5 minutes)
                if duration_minutes < 5:
                    continue
                
                # Create standardized event object
                events.append({
                    'source': 'outlook_calendar',
                    'title': event['subject'],
                    'start_time': start_time,
                    'end_time': end_time,
                    'duration_minutes': duration_minutes,
                    'organizer': event.get('organizer', {}).get('emailAddress', {}).get('name', 'Unknown'),
                    'attendees_count': len(event.get('attendees', [])),
                    'categories': event.get('categories', []),
                    'importance': event.get('importance', 'normal'),
                    'preview': event.get('bodyPreview', '')[:100],  # First 100 chars of body
                    'raw_data': event
                })
            
            logger.info(f"Retrieved {len(events)} calendar events")
            return events
            
        except Exception as e:
            logger.error(f"Error retrieving calendar events: {e}")
            return []
    
    def get_email_activity(self, start_date, end_date):
        """
        Get email activity between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of email activity periods with relevant details
        """
        # Format dates for Microsoft Graph API
        start_str = start_date.astimezone(self.tz).isoformat()
        end_str = end_date.astimezone(self.tz).isoformat()
        
        # API endpoint for received emails
        url = f"{self.graph_base_url}/me/messages"
        
        params = {
            '$filter': f"receivedDateTime ge {start_str} and receivedDateTime le {end_str}",
            '$select': 'subject,receivedDateTime,from,importance,categories,bodyPreview',
            '$orderby': 'receivedDateTime',
            '$top': 100  # Adjust based on expected volume
        }
        
        try:
            # Get received emails
            response = requests.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            received_emails = response.json().get('value', [])
            
            # Get sent emails
            sent_params = {
                '$filter': f"sentDateTime ge {start_str} and sentDateTime le {end_str}",
                '$select': 'subject,sentDateTime,toRecipients,importance,categories,bodyPreview',
                '$orderby': 'sentDateTime',
                '$top': 100
            }
            sent_url = f"{self.graph_base_url}/me/mailFolders/SentItems/messages"
            sent_response = requests.get(sent_url, headers=self._get_headers(), params=sent_params)
            sent_response.raise_for_status()
            sent_emails = sent_response.json().get('value', [])
            
            # Process emails into time blocks
            # For simplicity, we'll estimate 5 minutes per email read and 10 minutes per email sent
            email_activities = []
            
            for email in received_emails:
                received_time = datetime.fromisoformat(email['receivedDateTime'].replace('Z', '+00:00'))
                end_time = received_time + timedelta(minutes=5)  # Assume 5 min to read
                
                email_activities.append({
                    'source': 'outlook_email_received',
                    'title': f"Read: {email['subject']}",
                    'start_time': received_time,
                    'end_time': end_time,
                    'duration_minutes': 5,
                    'from': email.get('from', {}).get('emailAddress', {}).get('name', 'Unknown'),
                    'importance': email.get('importance', 'normal'),
                    'categories': email.get('categories', []),
                    'preview': email.get('bodyPreview', '')[:100],
                    'raw_data': email
                })
            
            for email in sent_emails:
                sent_time = datetime.fromisoformat(email['sentDateTime'].replace('Z', '+00:00'))
                start_time = sent_time - timedelta(minutes=10)  # Assume 10 min to write
                
                email_activities.append({
                    'source': 'outlook_email_sent',
                    'title': f"Wrote: {email['subject']}",
                    'start_time': start_time,
                    'end_time': sent_time,
                    'duration_minutes': 10,
                    'to_count': len(email.get('toRecipients', [])),
                    'importance': email.get('importance', 'normal'),
                    'categories': email.get('categories', []),
                    'preview': email.get('bodyPreview', '')[:100],
                    'raw_data': email
                })
            
            logger.info(f"Retrieved activity for {len(received_emails)} received and {len(sent_emails)} sent emails")
            return email_activities
            
        except Exception as e:
            logger.error(f"Error retrieving email activity: {e}")
            return []
    
    def get_activities(self, start_date, end_date):
        """
        Get all Outlook activities between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of all activities from Outlook
        """
        calendar_events = self.get_calendar_events(start_date, end_date)
        email_activities = self.get_email_activity(start_date, end_date)
        
        all_activities = calendar_events + email_activities
        
        # Sort by start time
        all_activities.sort(key=lambda x: x['start_time'])
        
        return all_activities

# Create a singleton instance
outlook_agent = OutlookAgent()