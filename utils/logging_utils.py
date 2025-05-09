import logging
import os
import json
from datetime import datetime
from config.config import CACHE_DIR

logger = logging.getLogger('chronolog.utils.logging')

def save_activities_to_file(activities, filename=None):
    """
    Save activities to a JSON file for analysis or recovery
    
    Args:
        activities: List of activity dicts
        filename: Optional filename (defaults to timestamp)
        
    Returns:
        Path to saved file
    """
    if not filename:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f"activities_{timestamp}.json"
    
    filepath = os.path.join(CACHE_DIR, filename)
    
    try:
        # Convert datetime objects to strings for serialization
        serializable_activities = []
        for activity in activities:
            serializable = {}
            for key, value in activity.items():
                if isinstance(value, datetime):
                    serializable[key] = value.isoformat()
                else:
                    serializable[key] = value
            serializable_activities.append(serializable)
        
        with open(filepath, 'w') as f:
            json.dump(serializable_activities, f, indent=2)
        
        logger.info(f"Saved {len(activities)} activities to {filepath}")
        return filepath
    
    except Exception as e:
        logger.error(f"Error saving activities to file: {e}")
        return None

def load_activities_from_file(filepath):
    """
    Load activities from a JSON file
    
    Args:
        filepath: Path to JSON file
        
    Returns:
        List of activity dicts
    """
    if not os.path.exists(filepath):
        logger.error(f"File not found: {filepath}")
        return []
    
    try:
        with open(filepath, 'r') as f:
            activities = json.load(f)
        
        # Convert string timestamps back to datetime objects
        for activity in activities:
            if isinstance(activity.get('start_time'), str):
                activity['start_time'] = datetime.fromisoformat(activity['start_time'])
            if isinstance(activity.get('end_time'), str):
                activity['end_time'] = datetime.fromisoformat(activity['end_time'])
        
        logger.info(f"Loaded {len(activities)} activities from {filepath}")
        return activities
    
    except Exception as e:
        logger.error(f"Error loading activities from file: {e}")
        return []

def get_saved_activity_files():
    """
    Get list of saved activity files
    
    Returns:
        List of filenames
    """
    try:
        files = [f for f in os.listdir(CACHE_DIR) if f.startswith('activities_') and f.endswith('.json')]
        files.sort(reverse=True)  # Newest first
        return files
    except Exception as e:
        logger.error(f"Error listing saved activity files: {e}")
        return []

def log_activity_summary(activities):
    """
    Log a summary of the activities
    
    Args:
        activities: List of activity dicts
    """
    if not activities:
        logger.info("No activities to summarize")
        return
    
    # Count by source
    sources = {}
    for activity in activities:
        source = activity.get('source', 'unknown')
        sources[source] = sources.get(source, 0) + 1
    
    # Count by task type
    task_types = {}
    for activity in activities:
        task_type = activity.get('task_type', 'Unknown')
        task_types[task_type] = task_types.get(task_type, 0) + 1
    
    # Total duration
    total_minutes = sum(activity.get('duration_minutes', 0) for activity in activities)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    
    # Log summary
    logger.info(f"Activity Summary: {len(activities)} activities, {hours}h {minutes}m total")
    logger.info(f"Sources: {sources}")
    logger.info(f"Task Types: {task_types}")

def log_jira_submission_results(results):
    """
    Log results of Jira submission
    
    Args:
        results: Dict with submission results
    """
    logger.info(f"Jira Submission Results:")
    logger.info(f"  Success: {results.get('success', 0)}")
    logger.info(f"  Errors: {results.get('error', 0)}")
    logger.info(f"  Skipped: {results.get('skipped', 0)}")
    
    if results.get('errors', []):
        logger.warning(f"  Error details:")
        for error in results.get('errors', []):
            entry = error.get('entry', {})
            logger.warning(f"    Issue: {entry.get('jira_issue', 'unknown')}, Error: {error.get('error', 'unknown')}")