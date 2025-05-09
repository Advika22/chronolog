import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()

# Configure logging
log_level = os.getenv('LOG_LEVEL', 'INFO').upper()
logging.basicConfig(
    level=getattr(logging, log_level),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('chronolog')

# Microsoft Graph API settings
MS_CLIENT_ID = os.getenv('MS_CLIENT_ID')
MS_CLIENT_SECRET = os.getenv('MS_CLIENT_SECRET')
MS_TENANT_ID = os.getenv('MS_TENANT_ID')
MS_AUTHORITY = f"https://login.microsoftonline.com/{MS_TENANT_ID}"
MS_SCOPE = ['User.Read', 'Calendars.Read', 'Mail.Read', 'Chat.Read']

# GitHub API settings
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')

# WakaTime API settings
WAKATIME_API_KEY = os.getenv('WAKATIME_API_KEY')
WAKATIME_BASE_URL = 'https://wakatime.com/api/v1'

# Jira API settings
JIRA_URL = os.getenv('JIRA_URL')
JIRA_EMAIL = os.getenv('JIRA_EMAIL')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')

# AWS Bedrock settings
AWS_ACCESS_KEY_ID = os.getenv('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.getenv('AWS_SECRET_ACCESS_KEY')
AWS_REGION = os.getenv('AWS_REGION', 'us-west-2')
AWS_BEDROCK_MODEL_ID = 'anthropic.claude-3-sonnet-20240229-v1:0'  # Update to latest model as needed

# Proxy settings
HTTP_PROXY = os.getenv('HTTP_PROXY')
HTTPS_PROXY = os.getenv('HTTPS_PROXY')

if HTTP_PROXY or HTTPS_PROXY:
    os.environ['HTTP_PROXY'] = HTTP_PROXY if HTTP_PROXY else ''
    os.environ['HTTPS_PROXY'] = HTTPS_PROXY if HTTPS_PROXY else ''
    logger.info("Proxy settings applied to environment variables")

# Application settings
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't')
AUTO_SUBMIT = os.getenv('AUTO_SUBMIT', 'False').lower() in ('true', '1', 't')  # This setting is now only used for notifications

# Time tracking settings
DEFAULT_WORKING_HOURS = (9, 17)  # 9 AM to 5 PM
TIME_ZONE = 'UTC'  # Set to your timezone
MINIMUM_ACTIVITY_DURATION = 5  # minutes
ACTIVITY_MERGE_THRESHOLD = 2  # minutes - merge activities if gap is less than this

# Jira specific settings
JIRA_DEFAULT_ISSUE_TYPE = 'Task'
JIRA_TIME_FORMAT = '{duration}h {description}'  # Format for time log entries

# Cache settings
CACHE_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'cache')
if not os.path.exists(CACHE_DIR):
    os.makedirs(CACHE_DIR)

# Notification settings
NOTIFICATIONS_ENABLED = os.getenv('NOTIFICATIONS_ENABLED', 'False').lower() in ('true', '1', 't')
NOTIFICATION_METHOD = os.getenv('NOTIFICATION_METHOD', 'email')  # email, slack, or teams

# Email notification settings
EMAIL_HOST = os.getenv('EMAIL_HOST')
EMAIL_PORT = int(os.getenv('EMAIL_PORT', '587'))
EMAIL_USE_TLS = os.getenv('EMAIL_USE_TLS', 'True').lower() in ('true', '1', 't')
EMAIL_USERNAME = os.getenv('EMAIL_USERNAME')
EMAIL_PASSWORD = os.getenv('EMAIL_PASSWORD')
EMAIL_RECIPIENT = os.getenv('EMAIL_RECIPIENT')

# Slack notification settings
SLACK_WEBHOOK_URL = os.getenv('SLACK_WEBHOOK_URL')

# Teams notification settings
TEAMS_WEBHOOK_URL = os.getenv('TEAMS_WEBHOOK_URL')