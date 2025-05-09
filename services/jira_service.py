import logging
from datetime import datetime
import pytz
from services.auth_service import auth_service
from config.config import TIME_ZONE, JIRA_TIME_FORMAT

logger = logging.getLogger('chronolog.services.jira')

class JiraService:
    """Service for interacting with Jira"""
    
    def __init__(self):
        self.tz = pytz.timezone(TIME_ZONE)
    
    def _get_client(self):
        """Get authenticated Jira client"""
        return auth_service.get_jira_client()
    
    def get_user_issues(self, status=None):
        """
        Get issues assigned to the current user
        
        Args:
            status: Optional status filter (e.g., 'In Progress', 'Open')
            
        Returns:
            List of Jira issues
        """
        jira = self._get_client()
        
        try:
            # Get current user
            myself = jira.myself()
            username = myself['name']
            
            # JQL query for issues assigned to user
            jql = f"assignee = '{username}'"
            
            # Add status filter if provided
            if status:
                jql += f" AND status = '{status}'"
            
            # Execute query
            issues = jira.search_issues(jql, maxResults=100)
            
            # Format issues
            formatted_issues = []
            for issue in issues:
                formatted_issues.append({
                    'key': issue.key,
                    'summary': issue.fields.summary,
                    'status': issue.fields.status.name,
                    'issue_type': issue.fields.issuetype.name,
                    'priority': issue.fields.priority.name if hasattr(issue.fields, 'priority') and issue.fields.priority else 'N/A',
                    'url': f"{jira.server_url}/browse/{issue.key}"
                })
            
            logger.info(f"Retrieved {len(formatted_issues)} Jira issues")
            return formatted_issues
            
        except Exception as e:
            logger.error(f"Error retrieving Jira issues: {e}")
            return []
    
    def search_issues(self, query, max_results=10):
        """
        Search for Jira issues
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of matching Jira issues
        """
        jira = self._get_client()
        
        try:
            # JQL query for text search
            jql = f'text ~ "{query}"'
            
            # Execute query
            issues = jira.search_issues(jql, maxResults=max_results)
            
            # Format issues
            formatted_issues = []
            for issue in issues:
                formatted_issues.append({
                    'key': issue.key,
                    'summary': issue.fields.summary,
                    'status': issue.fields.status.name,
                    'issue_type': issue.fields.issuetype.name,
                    'url': f"{jira.server_url}/browse/{issue.key}"
                })
            
            logger.info(f"Found {len(formatted_issues)} Jira issues matching query '{query}'")
            return formatted_issues
            
        except Exception as e:
            logger.error(f"Error searching Jira issues: {e}")
            return []
    
    def log_work(self, issue_key, time_spent_seconds, description, start_time=None):
        """
        Log work to a Jira issue
        
        Args:
            issue_key: Jira issue key (e.g., 'PROJ-123')
            time_spent_seconds: Time spent in seconds
            description: Work description
            start_time: Optional start time (datetime object)
            
        Returns:
            Boolean indicating success
        """
        jira = self._get_client()
        
        try:
            # Convert seconds to a format Jira understands
            # Jira accepts time in format like "2h 30m"
            hours = time_spent_seconds // 3600
            minutes = (time_spent_seconds % 3600) // 60
            
            time_spent = ""
            if hours > 0:
                time_spent += f"{hours}h "
            if minutes > 0:
                time_spent += f"{minutes}m"
            
            time_spent = time_spent.strip()
            
            # If time is less than 1 minute, use 1m
            if not time_spent:
                time_spent = "1m"
            
            # Format start time if provided
            started = None
            if start_time:
                # Convert to Jira expected format
                started = start_time.strftime('%Y-%m-%dT%H:%M:%S.000%z')
            
            # Log work
            worklog = jira.add_worklog(
                issue=issue_key,
                timeSpent=time_spent,
                comment=description,
                started=started
            )
            
            logger.info(f"Logged {time_spent} to issue {issue_key}")
            return True
            
        except Exception as e:
            logger.error(f"Error logging work to Jira issue {issue_key}: {e}")
            return False
    
    def submit_time_entries(self, entries):
        """
        Submit multiple time entries to Jira
        
        Args:
            entries: List of time entry dicts with keys:
                - jira_issue: Jira issue key
                - duration_minutes: Duration in minutes
                - description: Work description
                - start_time: Start time (datetime object)
            
        Returns:
            Dict with success and error counts
        """
        results = {
            'success': 0,
            'error': 0,
            'skipped': 0,
            'errors': []
        }
        
        for entry in entries:
            # Skip entries with no Jira issue or with 'unknown' issue
            if not entry.get('jira_issue') or entry.get('jira_issue') == 'unknown':
                results['skipped'] += 1
                continue
            
            # Convert duration to seconds
            duration_seconds = int(entry.get('duration_minutes', 0) * 60)
            
            # Skip very short entries (less than 1 minute)
            if duration_seconds < 60:
                results['skipped'] += 1
                continue
            
            # Get description
            description = entry.get('description', 'Work logged by ChronoLog')
            
            # Submit entry
            success = self.log_work(
                issue_key=entry['jira_issue'],
                time_spent_seconds=duration_seconds,
                description=description,
                start_time=entry.get('start_time')
            )
            
            if success:
                results['success'] += 1
            else:
                results['error'] += 1
                results['errors'].append({
                    'entry': entry,
                    'error': f"Failed to log work to issue {entry['jira_issue']}"
                })
        
        logger.info(f"Submitted time entries: {results['success']} successful, {results['error']} errors, {results['skipped']} skipped")
        return results

# Create a singleton instance
jira_service = JiraService()