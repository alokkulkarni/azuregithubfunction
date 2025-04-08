import azure.functions as func
import logging
import os
import requests
from datetime import datetime, UTC
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()
logging.info("Environment variables loaded")

# GitHub API configuration
GITHUB_TOKEN = os.getenv('GITHUB_TOKEN')
GITHUB_ORG = os.getenv('GITHUB_ORG')
GITHUB_REPOS = os.getenv('GITHUB_REPOS', '').split(',')
HEADERS = {
    'Authorization': f'token {GITHUB_TOKEN}',
    'Accept': 'application/vnd.github.v3+json'
}

logging.info(f"Configured to monitor organization: {GITHUB_ORG}")
logging.info(f"Configured repositories: {GITHUB_REPOS}")

def format_cycle_time(hours):
    """Format cycle time in hours or days based on duration."""
    if hours > 100:
        days = hours / 24
        return f"{days:.1f} days"
    return f"{hours:.1f} hours"

def get_pr_timeline(repo, pr_number):
    """Fetch timeline events for a pull request."""
    url = f'https://api.github.com/repos/{GITHUB_ORG}/{repo}/issues/{pr_number}/timeline'
    try:
        response = requests.get(url, headers=HEADERS)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching timeline for PR #{pr_number} in {repo}: {str(e)}")
        return []

def calculate_pr_cycle_time(pr):
    """Calculate the time from PR creation to close/current date."""
    created_at = datetime.fromisoformat(pr['created_at'].replace('Z', '+00:00'))
    
    # Use closed_at if available, otherwise use current time
    if pr['state'] == 'closed' and pr.get('closed_at'):
        end_time = datetime.fromisoformat(pr['closed_at'].replace('Z', '+00:00'))
    else:
        end_time = datetime.now(UTC)
    
    cycle_time = end_time - created_at
    return cycle_time.total_seconds() / 3600  # Convert to hours

def get_pull_requests(repo):
    """Fetch pull requests for a given repository."""
    url = f'https://api.github.com/repos/{GITHUB_ORG}/{repo}/pulls'
    params = {'state': 'all'}  # Get both open and closed PRs
    logging.info(f"Fetching pull requests from: {url}")
    try:
        response = requests.get(url, headers=HEADERS, params=params)
        response.raise_for_status()
        prs = response.json()
        logging.info(f"Found {len(prs)} pull requests in {repo}")
        return prs
    except requests.exceptions.RequestException as e:
        logging.error(f"Error fetching pull requests for {repo}: {str(e)}")
        return []

def main(mytimer: func.TimerRequest = None) -> None:
    utc_timestamp = datetime.now(UTC).isoformat()
    logging.info("Function execution started")

    if mytimer is not None and mytimer.past_due:
        logging.warning('The timer is past due!')

    logging.info('Python timer trigger function ran at %s', utc_timestamp)

    # Validate required environment variables
    if not all([GITHUB_TOKEN, GITHUB_ORG, GITHUB_REPOS]):
        logging.error("Missing required environment variables")
        logging.error(f"GITHUB_TOKEN present: {bool(GITHUB_TOKEN)}")
        logging.error(f"GITHUB_ORG present: {bool(GITHUB_ORG)}")
        logging.error(f"GITHUB_REPOS present: {bool(GITHUB_REPOS)}")
        return

    # Process each repository
    for repo in GITHUB_REPOS:
        if not repo.strip():
            logging.warning("Skipping empty repository name")
            continue
            
        logging.info(f"Processing repository: {repo}")
        pull_requests = get_pull_requests(repo)
        
        if not pull_requests:
            logging.info(f"No pull requests found in {repo}")
            continue

        # Initialize cycle time tracking
        total_cycle_time = 0
        total_prs = len(pull_requests)
        
        # Separate tracking for open and closed PRs
        open_prs = []
        closed_prs = []
        open_cycle_time = 0
        closed_cycle_time = 0
        
        # Process each PR
        for pr in pull_requests:
            logging.info(f"PR #{pr['number']}: {pr['title']} - State: {pr['state']}")
            logging.info(f"Created by: {pr['user']['login']}")
            logging.info(f"URL: {pr['html_url']}")
            
            cycle_time = calculate_pr_cycle_time(pr)
            total_cycle_time += cycle_time
            
            # Track PR by state
            if pr['state'] == 'closed':
                closed_prs.append(pr)
                closed_cycle_time += cycle_time
            else:
                open_prs.append(pr)
                open_cycle_time += cycle_time
            
            status = "Closed" if pr['state'] == 'closed' else "Open"
            formatted_time = format_cycle_time(cycle_time)
            logging.info(f"Cycle time: {formatted_time} ({status})")
            logging.info("---")

        # Log average cycle times
        if total_prs > 0:
            # All PRs average
            avg_cycle_time = total_cycle_time / total_prs
            formatted_avg_time = format_cycle_time(avg_cycle_time)
            logging.info(f"Repository {repo} - Average PR cycle time (All PRs): {formatted_avg_time}")
            logging.info(f"Total PRs analyzed: {total_prs}")
            
            # Closed PRs average
            if closed_prs:
                avg_closed_cycle_time = closed_cycle_time / len(closed_prs)
                formatted_closed_time = format_cycle_time(avg_closed_cycle_time)
                logging.info(f"Repository {repo} - Average PR cycle time (Closed PRs): {formatted_closed_time}")
                logging.info(f"Closed PRs: {len(closed_prs)}")
            
            # Open PRs average
            if open_prs:
                avg_open_cycle_time = open_cycle_time / len(open_prs)
                formatted_open_time = format_cycle_time(avg_open_cycle_time)
                logging.info(f"Repository {repo} - Average PR cycle time (Open PRs): {formatted_open_time}")
                logging.info(f"Open PRs: {len(open_prs)}")
        else:
            logging.info(f"Repository {repo} - No PRs found for cycle time calculation")

    logging.info("Function execution completed")

if __name__ == "__main__":
    logging.info("Starting function in local mode")
    main()