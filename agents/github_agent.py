import logging
from datetime import datetime, timedelta
import pytz
from services.auth_service import auth_service
from config.config import TIME_ZONE

logger = logging.getLogger('chronolog.agents.github')

class GitHubAgent:
    """Agent for collecting data from GitHub (commits, PRs, reviews)"""
    
    def __init__(self):
        self.tz = pytz.timezone(TIME_ZONE)
    
    def get_github_activities(self, start_date, end_date):
        """
        Get GitHub activities between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of GitHub activities with relevant details
        """
        # Get GitHub client
        github_client = auth_service.get_github_client()
        
        try:
            # Get authenticated user
            user = github_client.get_user()
            username = user.login
            
            # Get user's events
            activities = []
            
            # Get user's repositories (only owned and collaborated)
            repos = list(user.get_repos())
            owned_repos = [repo for repo in repos if repo.owner.login == username]
            collaborated_repos = [repo for repo in repos if repo.owner.login != username]
            
            all_relevant_repos = owned_repos + collaborated_repos
            
            for repo in all_relevant_repos:
                repo_name = repo.full_name
                
                # Get commits in date range
                try:
                    # Convert to GitHub's expected format
                    since_date = start_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    until_date = end_date.strftime('%Y-%m-%dT%H:%M:%SZ')
                    
                    commits = repo.get_commits(author=username, since=since_date, until=until_date)
                    
                    for commit in commits:
                        commit_time = commit.commit.author.date.replace(tzinfo=pytz.UTC)
                        
                        # For each commit, estimate 15 minutes of work
                        start_time = commit_time - timedelta(minutes=15)
                        end_time = commit_time
                        
                        activities.append({
                            'source': 'github_commit',
                            'title': f"Commit: {commit.commit.message[:50]}",
                            'repository': repo_name,
                            'start_time': start_time,
                            'end_time': end_time,
                            'duration_minutes': 15,
                            'sha': commit.sha,
                            'url': commit.html_url,
                            'message': commit.commit.message,
                            'raw_data': {
                                'sha': commit.sha,
                                'message': commit.commit.message,
                                'url': commit.html_url
                            }
                        })
                except Exception as e:
                    logger.warning(f"Error retrieving commits for repo {repo_name}: {e}")
                
                # Get pull requests in date range (created, updated or closed by user)
                try:
                    # Can't directly filter PRs by date, so get all and filter
                    all_prs = repo.get_pulls(state='all')
                    
                    for pr in all_prs:
                        # Check if PR was created in time range
                        created_at = pr.created_at.replace(tzinfo=pytz.UTC)
                        updated_at = pr.updated_at.replace(tzinfo=pytz.UTC)
                        closed_at = pr.closed_at.replace(tzinfo=pytz.UTC) if pr.closed_at else None
                        
                        # Check if user is the author
                        if pr.user.login == username:
                            # PR creation (estimate 30 minutes)
                            if start_date <= created_at <= end_date:
                                activities.append({
                                    'source': 'github_pr_created',
                                    'title': f"Created PR: {pr.title[:50]}",
                                    'repository': repo_name,
                                    'start_time': created_at - timedelta(minutes=30),
                                    'end_time': created_at,
                                    'duration_minutes': 30,
                                    'pr_number': pr.number,
                                    'url': pr.html_url,
                                    'state': pr.state,
                                    'raw_data': {
                                        'number': pr.number,
                                        'title': pr.title,
                                        'state': pr.state,
                                        'url': pr.html_url
                                    }
                                })
                            
                            # PR updates (not creating or closing) - estimate 15 minutes
                            if start_date <= updated_at <= end_date:
                                # Make sure it's not just the creation or closing time
                                if updated_at != created_at and (not closed_at or updated_at != closed_at):
                                    activities.append({
                                        'source': 'github_pr_updated',
                                        'title': f"Updated PR: {pr.title[:50]}",
                                        'repository': repo_name,
                                        'start_time': updated_at - timedelta(minutes=15),
                                        'end_time': updated_at,
                                        'duration_minutes': 15,
                                        'pr_number': pr.number,
                                        'url': pr.html_url,
                                        'state': pr.state,
                                        'raw_data': {
                                            'number': pr.number,
                                            'title': pr.title,
                                            'state': pr.state,
                                            'url': pr.html_url
                                        }
                                    })
                        
                        # Check PR reviews by user
                        reviews = pr.get_reviews()
                        for review in reviews:
                            if review.user.login == username:
                                review_time = review.submitted_at.replace(tzinfo=pytz.UTC)
                                
                                if start_date <= review_time <= end_date:
                                    # Estimate 20 minutes for a code review
                                    activities.append({
                                        'source': 'github_pr_review',
                                        'title': f"Reviewed PR: {pr.title[:50]}",
                                        'repository': repo_name,
                                        'start_time': review_time - timedelta(minutes=20),
                                        'end_time': review_time,
                                        'duration_minutes': 20,
                                        'pr_number': pr.number,
                                        'review_state': review.state,
                                        'url': review.html_url,
                                        'raw_data': {
                                            'pr_number': pr.number,
                                            'pr_title': pr.title,
                                            'review_state': review.state,
                                            'url': review.html_url
                                        }
                                    })
                except Exception as e:
                    logger.warning(f"Error retrieving pull requests for repo {repo_name}: {e}")
                
                # Get issues activities
                try:
                    # Get issues assigned to user
                    issues = repo.get_issues(assignee=username, state='all')
                    
                    for issue in issues:
                        # Only count issues that were created or updated in our time window
                        created_at = issue.created_at.replace(tzinfo=pytz.UTC)
                        updated_at = issue.updated_at.replace(tzinfo=pytz.UTC)
                        closed_at = issue.closed_at.replace(tzinfo=pytz.UTC) if issue.closed_at else None
                        
                        # Issue creation (estimate 20 minutes)
                        if issue.user.login == username and start_date <= created_at <= end_date:
                            activities.append({
                                'source': 'github_issue_created',
                                'title': f"Created Issue: {issue.title[:50]}",
                                'repository': repo_name,
                                'start_time': created_at - timedelta(minutes=20),
                                'end_time': created_at,
                                'duration_minutes': 20,
                                'issue_number': issue.number,
                                'url': issue.html_url,
                                'state': issue.state,
                                'raw_data': {
                                    'number': issue.number,
                                    'title': issue.title,
                                    'state': issue.state,
                                    'url': issue.html_url
                                }
                            })
                        
                        # Issue closing (estimate 10 minutes)
                        if closed_at and start_date <= closed_at <= end_date:
                            # Check if user closed the issue (via comments or events)
                            issue_events = issue.get_events()
                            closed_by_user = False
                            
                            for event in issue_events:
                                if event.event == 'closed' and event.actor.login == username:
                                    closed_by_user = True
                                    break
                            
                            if closed_by_user:
                                activities.append({
                                    'source': 'github_issue_closed',
                                    'title': f"Closed Issue: {issue.title[:50]}",
                                    'repository': repo_name,
                                    'start_time': closed_at - timedelta(minutes=10),
                                    'end_time': closed_at,
                                    'duration_minutes': 10,
                                    'issue_number': issue.number,
                                    'url': issue.html_url,
                                    'state': issue.state,
                                    'raw_data': {
                                        'number': issue.number,
                                        'title': issue.title,
                                        'state': issue.state,
                                        'url': issue.html_url
                                    }
                                })
                        
                        # Issue comments
                        comments = issue.get_comments()
                        for comment in comments:
                            if comment.user.login == username:
                                comment_time = comment.created_at.replace(tzinfo=pytz.UTC)
                                
                                if start_date <= comment_time <= end_date:
                                    # Estimate 5 minutes for a comment
                                    activities.append({
                                        'source': 'github_issue_comment',
                                        'title': f"Commented on Issue: {issue.title[:50]}",
                                        'repository': repo_name,
                                        'start_time': comment_time - timedelta(minutes=5),
                                        'end_time': comment_time,
                                        'duration_minutes': 5,
                                        'issue_number': issue.number,
                                        'url': comment.html_url,
                                        'raw_data': {
                                            'issue_number': issue.number,
                                            'issue_title': issue.title,
                                            'comment_body': comment.body[:100],
                                            'url': comment.html_url
                                        }
                                    })
                except Exception as e:
                    logger.warning(f"Error retrieving issues for repo {repo_name}: {e}")
            
            # Sort activities by start time
            activities.sort(key=lambda x: x['start_time'])
            
            logger.info(f"Retrieved {len(activities)} GitHub activities")
            return activities
            
        except Exception as e:
            logger.error(f"Error retrieving GitHub activities: {e}")
            return []
    
    def get_activities(self, start_date, end_date):
        """
        Get all GitHub activities between start_date and end_date
        
        Args:
            start_date: datetime object for start of period
            end_date: datetime object for end of period
            
        Returns:
            List of all activities from GitHub
        """
        return self.get_github_activities(start_date, end_date)

# Create a singleton instance
github_agent = GitHubAgent()