import json
import logging
from datetime import datetime, timedelta
import pytz
from services.auth_service import auth_service
from config.config import TIME_ZONE, AWS_BEDROCK_MODEL_ID

logger = logging.getLogger('chronolog.agents.bedrock')

class BedrockAgent:
    """Agent for analyzing and categorizing activities using AWS Bedrock (Claude)"""
    
    def __init__(self):
        self.tz = pytz.timezone(TIME_ZONE)
    
    def _get_client(self):
        """Get authenticated AWS Bedrock client"""
        return auth_service.get_bedrock_client()
    
    def analyze_activities(self, activities):
        """
        Analyze activities using AWS Bedrock (Claude)
        
        Args:
            activities: List of activity dicts
            
        Returns:
            List of activities with analysis data added
        """
        if not activities:
            logger.warning("No activities to analyze")
            return []
        
        client = self._get_client()
        
        # Group activities into batches to avoid model context limits
        batches = []
        current_batch = []
        batch_size = 0
        
        for activity in activities:
            # Estimate token count (rough approximation)
            activity_size = len(json.dumps(activity)) // 4  # ~4 chars per token
            
            # If adding this activity would exceed batch size, create a new batch
            if batch_size + activity_size > 4000:  # Keep well under model context limit
                batches.append(current_batch)
                current_batch = [activity]
                batch_size = activity_size
            else:
                current_batch.append(activity)
                batch_size += activity_size
        
        # Add the last batch if not empty
        if current_batch:
            batches.append(current_batch)
        
        all_analyzed_activities = []
        
        for batch in batches:
            try:
                # Create a prompt for the batch
                prompt = self._create_analysis_prompt(batch)
                
                # Call Bedrock with Claude model
                response = client.invoke_model(
                    modelId=AWS_BEDROCK_MODEL_ID,
                    body=json.dumps({
                        "anthropic_version": "bedrock-2023-05-31",
                        "max_tokens": 4000,
                        "messages": [
                            {
                                "role": "user",
                                "content": prompt
                            }
                        ]
                    }).encode('utf-8'),
                    contentType='application/json',
                    accept='application/json'
                )
                
                response_body = json.loads(response['body'].read().decode('utf-8'))
                analysis_text = response_body['content'][0]['text']
                
                # Parse the analysis
                analyzed_activities = self._parse_analysis_response(batch, analysis_text)
                all_analyzed_activities.extend(analyzed_activities)
                
                logger.info(f"Successfully analyzed batch of {len(batch)} activities")
                
            except Exception as e:
                logger.error(f"Error analyzing activities with Bedrock: {e}")
                # On error, return the original activities without analysis
                all_analyzed_activities.extend(batch)
        
        # Sort by start time
        all_analyzed_activities.sort(key=lambda x: x['start_time'])
        
        return all_analyzed_activities
    
    def _create_analysis_prompt(self, activities):
        """Create prompt for AWS Bedrock (Claude) to analyze activities"""
        prompt = """
You are an advanced AI system that helps categorize and analyze work activities for time tracking.
Your task is to analyze a list of work activities and:
1. Categorize each activity into a specific task type (e.g., "Development", "Documentation", "Meeting", "Code Review", "Communication", "Research", etc.)
2. Determine which Jira issue each activity is likely related to, using the available context clues
3. Provide a concise description of each activity suitable for a time tracking system

For each activity, return a JSON object with the following fields:
- id: A unique identifier (use the index in the list)
- task_type: The category of the activity
- jira_issue: The most likely Jira issue ID (if determinable, otherwise "unknown")
- description: A concise description of the activity for time tracking
- billable: Boolean indicating if the activity is billable work (true for development, meetings, etc., false for personal activities)

Here's the list of activities to analyze:
"""
        prompt += json.dumps(activities, default=str, indent=2)
        
        prompt += """
Format your response as a valid JSON array where each object represents the analysis of one activity.
Start your response with "ANALYSIS_RESULTS:" followed by the JSON array.
"""
        return prompt
    
    def _parse_analysis_response(self, original_activities, analysis_text):
        """Parse the response from AWS Bedrock (Claude) analysis"""
        try:
            # Extract the JSON part
            if "ANALYSIS_RESULTS:" in analysis_text:
                json_str = analysis_text.split("ANALYSIS_RESULTS:")[1].strip()
            else:
                # Try to find JSON array in the response
                start_idx = analysis_text.find('[')
                end_idx = analysis_text.rfind(']')
                if start_idx != -1 and end_idx != -1:
                    json_str = analysis_text[start_idx:end_idx+1]
                else:
                    raise ValueError("Could not find JSON array in response")
            
            # Parse the JSON
            analysis_results = json.loads(json_str)
            
            # Match analysis results with original activities
            analyzed_activities = []
            
            for i, activity in enumerate(original_activities):
                # Find matching analysis (if any)
                matching_analysis = None
                for result in analysis_results:
                    if result.get('id') == i:
                        matching_analysis = result
                        break
                
                # If no matching analysis found, try to match by other means
                if not matching_analysis and i < len(analysis_results):
                    matching_analysis = analysis_results[i]
                
                # Create a copy of the original activity and add analysis data
                analyzed_activity = activity.copy()
                
                if matching_analysis:
                    analyzed_activity['task_type'] = matching_analysis.get('task_type', 'Unknown')
                    analyzed_activity['jira_issue'] = matching_analysis.get('jira_issue', 'unknown')
                    analyzed_activity['description'] = matching_analysis.get('description', activity.get('title', 'Unknown Activity'))
                    analyzed_activity['billable'] = matching_analysis.get('billable', True)
                else:
                    # If no analysis was found, use defaults
                    analyzed_activity['task_type'] = 'Unknown'
                    analyzed_activity['jira_issue'] = 'unknown'
                    analyzed_activity['description'] = activity.get('title', 'Unknown Activity')
                    analyzed_activity['billable'] = True
                
                analyzed_activities.append(analyzed_activity)
            
            return analyzed_activities
            
        except Exception as e:
            logger.error(f"Error parsing analysis response: {e}")
            # On error, return original activities without analysis
            for activity in original_activities:
                activity['task_type'] = 'Unknown'
                activity['jira_issue'] = 'unknown'
                activity['description'] = activity.get('title', 'Unknown Activity')
                activity['billable'] = True
            
            return original_activities
    
    def categorize_activities(self, activities):
        """
        Categorize activities using AWS Bedrock (Claude)
        
        Args:
            activities: List of activities to categorize
            
        Returns:
            List of categorized activities
        """
        return self.analyze_activities(activities)

# Create a singleton instance
bedrock_agent = BedrockAgent()