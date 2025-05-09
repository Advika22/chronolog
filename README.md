# ChronoLog: Smart Time Tracker

ChronoLog is an intelligent time tracking application that integrates with multiple platforms to automatically track your work activities and log time to Jira.

## Features

- **Multi-platform Integration**: Automatically collects activity data from:
  - Microsoft Outlook (calendar events and email activity)
  - Microsoft Teams (meetings and chats)
  - GitHub (commits, pull requests, and reviews)
  - PyCharm via WakaTime (coding activity)
  
- **AI-Powered Categorization**: Uses AWS Bedrock with Claude to analyze activities and categorize them by task type.

- **Review & Edit**: Daily UI summary of activities before submission to Jira.

- **Automated Jira Updates**: Automatically logs time entries to Jira.

- **Notifications**: Email, Slack, or Microsoft Teams notifications for automated updates.

## Prerequisites

- Python 3.9+
- AWS account with Bedrock access
- Microsoft account with appropriate API permissions
- GitHub account with Personal Access Token
- WakaTime account and API key
- Jira account with API token

## Installation

1. Clone the repository:
   ```
   git clone https://github.com/yourusername/chronolog.git
   cd chronolog
   ```

2. Create a virtual environment:
   ```
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```
   pip install -r requirements.txt
   ```

4. Create a `.env` file based on `.env.example` and fill in your credentials.

## Usage

1. Run the Streamlit app:
   ```
   python -m streamlit run main.py
   ```

2. The dashboard will open in your browser.

3. By default, the app aggregates data from the previous day and presents it for review.

4. Review the categorized time entries, make any necessary adjustments, and approve for submission to Jira.

## Automated Activity Collection

ChronoLog can automatically collect and analyze activities without the UI:

```
python main.py --auto-run --date 2025-05-01:2025-05-07 --notify
```

This will:
1. Fetch activities from all configured sources for the specified date range
2. Analyze and categorize them using AWS Bedrock
3. Save the analyzed activities for later review
4. Send a notification that activities are ready for review

**Important**: ChronoLog **never** submits time entries to Jira without explicit user approval through the UI. The activities are prepared and saved, but the user must review and approve them before submission.

### Date Selection Options

ChronoLog supports various date specifications:

- Single day: `--date 2025-05-08`
- Date range: `--date 2025-05-01:2025-05-07`
- Yesterday (default if no date specified)

Within the UI, more options are available:
- Yesterday
- Today
- Custom date
- Date range
- This week
- Last week
- This month

### Notification Options

When running in auto-run mode, you can enable notifications to alert you when activities are ready for review:

```
python main.py --auto-run --date yesterday --notify
```

## Proxy Configuration

If your organization uses proxies for internet access, ensure you've set the appropriate environment variables in the `.env` file:

```
HTTP_PROXY=http://proxy.example.com:port
HTTPS_PROXY=https://proxy.example.com:port
```

For additional proxy settings in specific libraries, refer to their documentation.

## Authentication Notes

- **Microsoft APIs**: Uses MSAL (Microsoft Authentication Library) for authentication with Microsoft Graph API
- **GitHub**: Uses Personal Access Token with appropriate scopes
- **WakaTime**: Uses API Key
- **Jira**: Uses Email + API Token
- **AWS Bedrock**: Uses standard AWS credentials (access key and secret)

## Scheduled Operations

You can configure a scheduled task to run ChronoLog regularly:

```
0 7 * * * cd /path/to/chronolog && /path/to/venv/bin/python main.py --auto-run --date yesterday --notify >> /path/to/chronolog/logs/chronolog.log 2>&1
```

This cron job will run at 7:00 AM daily to process the previous day's activities. The system will:
1. Collect and analyze your activities
2. Send you a notification that they're ready for review
3. You then open the ChronoLog UI and:
   - Load the saved activities
   - Review and edit them as needed
   - Submit them to Jira only after your approval

This ensures you always have the final say on what gets logged to Jira while still automating the tedious data collection and analysis steps.

## Development

The project is structured as follows:
- `main.py`: Application entry point
- `agents/`: Integration with external platforms
- `services/`: Core services for authentication and Jira communication
- `utils/`: Utility functions for time calculations, logging, and notifications
- `ui/`: Streamlit UI components

