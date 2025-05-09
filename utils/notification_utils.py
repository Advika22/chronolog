"""
Notification utilities for ChronoLog
"""

import os
import smtplib
import logging
import requests
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config.config import (
    NOTIFICATIONS_ENABLED, NOTIFICATION_METHOD, 
    EMAIL_HOST, EMAIL_PORT, EMAIL_USE_TLS, 
    EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_RECIPIENT,
    SLACK_WEBHOOK_URL, TEAMS_WEBHOOK_URL
)

logger = logging.getLogger('chronolog.utils.notifications')

def send_email_notification(subject, message):
    """
    Send an email notification
    
    Args:
        subject: Email subject
        message: Email message body
        
    Returns:
        Boolean indicating success
    """
    if not all([EMAIL_HOST, EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_RECIPIENT]):
        logger.error("Email notification settings incomplete")
        return False
    
    try:
        # Create message
        msg = MIMEMultipart()
        msg['From'] = EMAIL_USERNAME
        msg['To'] = EMAIL_RECIPIENT
        msg['Subject'] = subject
        
        # Add body
        msg.attach(MIMEText(message, 'plain'))
        
        # Connect to server
        if EMAIL_USE_TLS:
            server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
            server.starttls()
        else:
            server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        
        # Login and send
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        
        logger.info(f"Email notification sent to {EMAIL_RECIPIENT}")
        return True
    
    except Exception as e:
        logger.error(f"Error sending email notification: {e}")
        return False

def send_slack_notification(message):
    """
    Send a Slack notification
    
    Args:
        message: Message to send
        
    Returns:
        Boolean indicating success
    """
    if not SLACK_WEBHOOK_URL:
        logger.error("Slack webhook URL not configured")
        return False
    
    try:
        # Prepare payload
        payload = {
            "text": message
        }
        
        # Send request
        response = requests.post(
            SLACK_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            logger.info("Slack notification sent successfully")
            return True
        else:
            logger.error(f"Error sending Slack notification: {response.status_code} {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending Slack notification: {e}")
        return False

def send_teams_notification(message):
    """
    Send a Microsoft Teams notification
    
    Args:
        message: Message to send
        
    Returns:
        Boolean indicating success
    """
    if not TEAMS_WEBHOOK_URL:
        logger.error("Teams webhook URL not configured")
        return False
    
    try:
        # Prepare payload
        payload = {
            "text": message
        }
        
        # Send request
        response = requests.post(
            TEAMS_WEBHOOK_URL,
            data=json.dumps(payload),
            headers={'Content-Type': 'application/json'}
        )
        
        if response.status_code == 200:
            logger.info("Teams notification sent successfully")
            return True
        else:
            logger.error(f"Error sending Teams notification: {response.status_code} {response.text}")
            return False
    
    except Exception as e:
        logger.error(f"Error sending Teams notification: {e}")
        return False

def send_notification(subject, message):
    """
    Send a notification using the configured method
    
    Args:
        subject: Notification subject
        message: Notification message
        
    Returns:
        Boolean indicating success
    """
    if not NOTIFICATIONS_ENABLED:
        logger.info("Notifications are disabled")
        return False
    
    # Format date for subject
    date_str = datetime.now().strftime('%Y-%m-%d')
    full_subject = f"{subject} - {date_str}"
    
    # Send via configured method
    if NOTIFICATION_METHOD.lower() == 'email':
        return send_email_notification(full_subject, message)
    elif NOTIFICATION_METHOD.lower() == 'slack':
        return send_slack_notification(f"*{full_subject}*\n\n{message}")
    elif NOTIFICATION_METHOD.lower() == 'teams':
        return send_teams_notification(f"## {full_subject}\n\n{message}")
    else:
        logger.error(f"Unknown notification method: {NOTIFICATION_METHOD}")
        return False

def format_jira_update_notification(date_str, results, activities):
    """
    Format a notification message for Jira updates
    
    Args:
        date_str: Date string (YYYY-MM-DD)
        results: Jira submission results
        activities: List of processed activities
        
    Returns:
        Formatted notification message
    """
    # Calculate total time logged
    total_minutes = sum(activity.get('duration_minutes', 0) 
                        for activity in activities 
                        if activity.get('jira_issue') and activity.get('jira_issue') != 'unknown')
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    # Group by Jira issue
    issues = {}
    for activity in activities:
        jira_issue = activity.get('jira_issue')
        if jira_issue and jira_issue != 'unknown':
            if jira_issue not in issues:
                issues[jira_issue] = 0
            issues[jira_issue] += activity.get('duration_minutes', 0)
    
    # Format message
    message = f"ChronoLog Automated Time Tracking Summary for {date_str}\n\n"
    
    message += f"Total Time Tracked: {hours}h {minutes}m\n"
    message += f"Number of Activities: {len(activities)}\n\n"
    
    message += "Time Tracked by Issue:\n"
    for issue, mins in issues.items():
        issue_hours = mins // 60
        issue_minutes = mins % 60
        message += f"- {issue}: {issue_hours}h {issue_minutes}m\n"
    
    message += "\nPlease review these activities in the ChronoLog dashboard before submitting to Jira."
    
    return message