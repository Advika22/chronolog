import os
import json
import msal
import boto3
import requests
from datetime import datetime, timedelta
import logging
from github import Github
from jira import JIRA

from config.config import (
    MS_CLIENT_ID, MS_CLIENT_SECRET, MS_AUTHORITY, MS_SCOPE,
    GITHUB_TOKEN, WAKATIME_API_KEY, JIRA_URL, JIRA_EMAIL,
    JIRA_API_TOKEN, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY,
    AWS_REGION, CACHE_DIR
)

logger = logging.getLogger('chronolog.auth')

class AuthService:
    """Service for handling authentication with various platforms"""
    
    def __init__(self):
        self.ms_app = None
        self.ms_token = None
        self.ms_token_expires = None
        self.github_client = None
        self.jira_client = None
        self.aws_session = None
        self.bedrock_client = None
        
        # Token cache paths
        self.token_cache_file = os.path.join(CACHE_DIR, 'token_cache.json')
        
        # Load cached tokens if available
        self._load_cached_tokens()
    
    def _load_cached_tokens(self):
        """Load cached tokens from file if available"""
        if os.path.exists(self.token_cache_file):
            try:
                with open(self.token_cache_file, 'r') as f:
                    cache = json.load(f)
                    
                # Check if MS token is cached and not expired
                if 'ms_token' in cache and 'ms_expires' in cache:
                    expires = datetime.fromisoformat(cache['ms_expires'])
                    if expires > datetime.now() + timedelta(minutes=5):
                        self.ms_token = cache['ms_token']
                        self.ms_token_expires = expires
                        logger.info("Loaded cached Microsoft token")
            except Exception as e:
                logger.warning(f"Error loading cached tokens: {e}")
    
    def _save_cached_tokens(self):
        """Save tokens to cache file"""
        cache = {}
        
        if self.ms_token and self.ms_token_expires:
            cache['ms_token'] = self.ms_token
            cache['ms_expires'] = self.ms_token_expires.isoformat()
        
        try:
            with open(self.token_cache_file, 'w') as f:
                json.dump(cache, f)
            logger.info("Saved tokens to cache")
        except Exception as e:
            logger.warning(f"Error saving cached tokens: {e}")
    
    def get_microsoft_token(self):
        """Get Microsoft Graph API access token"""
        # Return cached token if valid
        if self.ms_token and self.ms_token_expires and self.ms_token_expires > datetime.now() + timedelta(minutes=5):
            return self.ms_token
        
        # Initialize MSAL app if not already done
        if not self.ms_app:
            self.ms_app = msal.ConfidentialClientApplication(
                MS_CLIENT_ID,
                authority=MS_AUTHORITY,
                client_credential=MS_CLIENT_SECRET
            )
        
        # Acquire token
        result = self.ms_app.acquire_token_for_client(scopes=MS_SCOPE)
        
        if "access_token" in result:
            self.ms_token = result['access_token']
            self.ms_token_expires = datetime.now() + timedelta(seconds=result.get('expires_in', 3600))
            self._save_cached_tokens()
            logger.info("Acquired new Microsoft token")
            return self.ms_token
        else:
            logger.error(f"Failed to acquire Microsoft token: {result.get('error_description', 'Unknown error')}")
            raise Exception(f"Failed to authenticate with Microsoft: {result.get('error_description', 'Unknown error')}")
    
    def get_github_client(self):
        """Get authenticated GitHub client"""
        if not self.github_client:
            self.github_client = Github(GITHUB_TOKEN)
            # Test the connection
            try:
                _ = self.github_client.get_user().login
                logger.info("GitHub client authenticated successfully")
            except Exception as e:
                logger.error(f"Failed to authenticate with GitHub: {e}")
                raise Exception(f"Failed to authenticate with GitHub: {e}")
        
        return self.github_client
    
    def get_wakatime_headers(self):
        """Get headers for WakaTime API requests"""
        import base64
        auth_string = base64.b64encode(f"{WAKATIME_API_KEY}".encode()).decode()
        return {
            'Authorization': f'Basic {auth_string}'
        }
    
    def get_jira_client(self):
        """Get authenticated Jira client"""
        if not self.jira_client:
            try:
                self.jira_client = JIRA(
                    server=JIRA_URL,
                    basic_auth=(JIRA_EMAIL, JIRA_API_TOKEN)
                )
                # Test the connection
                _ = self.jira_client.myself()
                logger.info("Jira client authenticated successfully")
            except Exception as e:
                logger.error(f"Failed to authenticate with Jira: {e}")
                raise Exception(f"Failed to authenticate with Jira: {e}")
        
        return self.jira_client
    
    def get_bedrock_client(self):
        """Get authenticated AWS Bedrock client"""
        if not self.bedrock_client:
            try:
                # Create a session with AWS credentials
                self.aws_session = boto3.Session(
                    aws_access_key_id=AWS_ACCESS_KEY_ID,
                    aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
                    region_name=AWS_REGION
                )
                
                # Create a Bedrock Runtime client
                self.bedrock_client = self.aws_session.client(
                    service_name='bedrock-runtime'
                )
                
                # Test the connection (can't easily test without making an actual call)
                logger.info("AWS Bedrock client initialized")
            except Exception as e:
                logger.error(f"Failed to initialize AWS Bedrock client: {e}")
                raise Exception(f"Failed to initialize AWS Bedrock client: {e}")
        
        return self.bedrock_client

# Create a singleton instance
auth_service = AuthService()