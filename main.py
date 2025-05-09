#!/usr/bin/env python3
"""
ChronoLog - Smart Time Tracker

Main entry point for the application.
"""

import os
import sys
import argparse
import logging
from datetime import datetime, timedelta
import pytz

# Add the parent directory to path to allow imports
parent_dir = os.path.dirname(os.path.abspath(__file__))
if parent_dir not in sys.path:
    sys.path.append(parent_dir)

# Import configuration and setup logging
from config.config import TIME_ZONE, DEBUG
from ui.streamlit_app import run_app

from agents.outlook_agent import outlook_agent
from agents.teams_agent import teams_agent
from agents.github_agent import github_agent
from agents.wakatime_agent import wakatime_agent
from agents.bedrock_agent import bedrock_agent
from services.jira_service import jira_service
from utils.time_utils import (
    get_yesterday, merge_overlapping_activities,
    fill_time_gaps, calculate_daily_totals, group_activities_by_day
)
from utils.logging_utils import (
    save_activities_to_file, log_activity_summary,
    log_jira_submission_results
)
from utils.notification_utils import (
    send_notification, format_jira_update_notification
)

# Configure root logger
logger = logging.getLogger('chronolog')

def parse_args():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(description='ChronoLog - Smart Time Tracker')
    
    parser.add_argument(
        '--auto-run',
        action='store_true',
        help='Automatically process activities without UI (but still requires manual review for Jira submission)'
    )
    
    parser.add_argument(
        '--date',
        type=str,
        help='Date to process (YYYY-MM-DD or YYYY-MM-DD:YYYY-MM-DD for date range)'
    )
    
    parser.add_argument(
        '--sources',
        type=str,
        default='outlook,teams,github,wakatime',
        help='Comma-separated list of data sources to use'
    )
    
    parser.add_argument(
        '--notify',
        action='store_true',
        help='Send notification when activities are ready for review'
    )
    
    return parser.parse_args()

def auto_run(args):
    """Run the time tracking pipeline automatically without UI"""
    logger.info("Starting ChronoLog in auto-run mode")
    
    # Parse sources
    sources = args.sources.lower().split(',')
    
    # Determine date range
    if args.date:
        if ':' in args.date:
            # Date range format: 'YYYY-MM-DD:YYYY-MM-DD'
            start_str, end_str = args.date.split(':')
            tz = pytz.timezone(TIME_ZONE)
            start_date = datetime.strptime(start_str, '%Y-%m-%d').replace(tzinfo=tz)
            end_date = datetime.strptime(end_str, '%Y-%m-%d').replace(hour=23, minute=59, second=59, tzinfo=tz)
        else:
            # Single date format: 'YYYY-MM-DD'
            tz = pytz.timezone(TIME_ZONE)
            start_date = datetime.strptime(args.date, '%Y-%m-%d').replace(tzinfo=tz)
            end_date = start_date.replace(hour=23, minute=59, second=59)
    else:
        # Default to yesterday
        start_date, end_date = get_yesterday()
    
    date_str = start_date.strftime('%Y-%m-%d')
    logger.info(f"Processing date range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    # Collect activities from all sources
    all_activities = []
    
    if 'outlook' in sources:
        logger.info("Fetching Outlook activities...")
        outlook_activities = outlook_agent.get_activities(start_date, end_date)
        all_activities.extend(outlook_activities)
        logger.info(f"Found {len(outlook_activities)} Outlook activities")
    
    if 'teams' in sources:
        logger.info("Fetching Teams activities...")
        teams_activities = teams_agent.get_activities(start_date, end_date)
        all_activities.extend(teams_activities)
        logger.info(f"Found {len(teams_activities)} Teams activities")
    
    if 'github' in sources:
        logger.info("Fetching GitHub activities...")
        github_activities = github_agent.get_activities(start_date, end_date)
        all_activities.extend(github_activities)
        logger.info(f"Found {len(github_activities)} GitHub activities")
    
    if 'wakatime' in sources:
        logger.info("Fetching WakaTime activities...")
        wakatime_activities = wakatime_agent.get_activities(start_date, end_date)
        all_activities.extend(wakatime_activities)
        logger.info(f"Found {len(wakatime_activities)} WakaTime activities")
    
    # Process activities
    logger.info(f"Processing {len(all_activities)} activities...")
    
    # Merge overlapping activities
    merged_activities = merge_overlapping_activities(all_activities)
    
    # Fill gaps
    filled_activities = fill_time_gaps(merged_activities)
    
    # Save raw activities
    if filled_activities:
        save_activities_to_file(filled_activities, f"activities_raw_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    
    # Analyze activities
    logger.info("Analyzing activities with AWS Bedrock...")
    analyzed_activities = bedrock_agent.categorize_activities(filled_activities)
    
    # Save analyzed activities
    if analyzed_activities:
        activities_file = save_activities_to_file(analyzed_activities)
        logger.info(f"Activities saved to {activities_file}")
        
        # Send notification about pending activities
        if args.notify:
            notification_subject = "ChronoLog Time Tracking Ready for Review"
            
            # Format notification message
            total_minutes = sum(activity.get('duration_minutes', 0) for activity in analyzed_activities)
            hours = total_minutes // 60
            minutes = total_minutes % 60
            
            notification_message = (
                f"ChronoLog has analyzed your activities for {date_str}.\n\n"
                f"Total time tracked: {hours}h {minutes}m\n"
                f"Number of activities: {len(analyzed_activities)}\n\n"
                f"Please review and approve these time entries in the ChronoLog dashboard before they're submitted to Jira.\n"
                f"Run ChronoLog and select 'Load from file' to review these activities."
            )
            
            success = send_notification(notification_subject, notification_message)
            if success:
                logger.info("Notification sent successfully")
            else:
                logger.error("Failed to send notification")
    
    # Log summary
    log_activity_summary(analyzed_activities)
    
    # IMPORTANT: Never submit to Jira automatically - always require user review
    logger.info("Activities processed and saved. Please review in the ChronoLog dashboard before submitting to Jira.")
    
    logger.info("ChronoLog auto-run completed")

def main():
    """Main entry point"""
    args = parse_args()
    
    if args.auto_run:
        # Run automatically without UI
        auto_run(args)
    else:
        # Run the Streamlit UI
        run_app()

if __name__ == "__main__":
    main()