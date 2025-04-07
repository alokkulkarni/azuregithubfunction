import logging
import requests
from datetime import datetime, UTC
from typing import Dict, List, Optional

class GitHubInsights:
    def __init__(self, token: str, org: str):
        self.token = token
        self.org = org
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'

    def get_repo_contributors(self, repo: str) -> List[Dict]:
        """Get list of contributors for a repository."""
        url = f'{self.base_url}/repos/{self.org}/{repo}/contributors'
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            contributors = response.json()
            logging.info(f"Found {len(contributors)} contributors for {repo}")
            return contributors
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching contributors for {repo}: {str(e)}")
            return []

    def get_last_commit(self, repo: str) -> Optional[Dict]:
        """Get the most recent commit for a repository."""
        url = f'{self.base_url}/repos/{self.org}/{repo}/commits'
        try:
            response = requests.get(url, headers=self.headers, params={'per_page': 1})
            response.raise_for_status()
            commits = response.json()
            if commits:
                return commits[0]
            return None
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching last commit for {repo}: {str(e)}")
            return None

    def get_repo_stats(self, repo: str) -> Dict:
        """Get repository statistics including stars, forks, and watchers."""
        url = f'{self.base_url}/repos/{self.org}/{repo}'
        try:
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            logging.error(f"Error fetching stats for {repo}: {str(e)}")
            return {}

    def get_insights(self, repo: str) -> Dict:
        """Get comprehensive insights for a repository."""
        insights = {
            'repository': repo,
            'last_commit': None,
            'contributors': [],
            'stats': {}
        }

        # Get last commit
        last_commit = self.get_last_commit(repo)
        if last_commit:
            insights['last_commit'] = {
                'sha': last_commit['sha'],
                'message': last_commit['commit']['message'],
                'author': last_commit['commit']['author']['name'],
                'date': last_commit['commit']['author']['date']
            }

        # Get contributors
        contributors = self.get_repo_contributors(repo)
        insights['contributors'] = [
            {
                'login': c['login'],
                'contributions': c['contributions'],
                'avatar_url': c['avatar_url']
            }
            for c in contributors
        ]

        # Get repository stats
        stats = self.get_repo_stats(repo)
        if stats:
            insights['stats'] = {
                'stars': stats.get('stargazers_count', 0),
                'forks': stats.get('forks_count', 0),
                'watchers': stats.get('watchers_count', 0),
                'open_issues': stats.get('open_issues_count', 0),
                'size': stats.get('size', 0),
                'language': stats.get('language', 'Unknown')
            }

        return insights

    def format_insights(self, insights: Dict) -> str:
        """Format insights into a readable string."""
        output = []
        output.append(f"\nRepository: {insights['repository']}")
        
        if insights['last_commit']:
            commit = insights['last_commit']
            date = datetime.fromisoformat(commit['date'].replace('Z', '+00:00'))
            output.append(f"Last Commit:")
            output.append(f"  - SHA: {commit['sha'][:7]}")
            output.append(f"  - Message: {commit['message']}")
            output.append(f"  - Author: {commit['author']}")
            output.append(f"  - Date: {date.strftime('%Y-%m-%d %H:%M:%S')}")

        if insights['contributors']:
            output.append(f"\nTop Contributors:")
            for contributor in insights['contributors'][:5]:  # Show top 5
                output.append(f"  - {contributor['login']}: {contributor['contributions']} contributions")

        if insights['stats']:
            stats = insights['stats']
            output.append(f"\nRepository Statistics:")
            output.append(f"  - Stars: {stats['stars']}")
            output.append(f"  - Forks: {stats['forks']}")
            output.append(f"  - Watchers: {stats['watchers']}")
            output.append(f"  - Open Issues: {stats['open_issues']}")
            output.append(f"  - Size: {stats['size']} KB")
            output.append(f"  - Primary Language: {stats['language']}")

        return '\n'.join(output)

# Example usage
if __name__ == "__main__":
    import os
    from dotenv import load_dotenv

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Load environment variables
    load_dotenv()
    token = os.getenv('GITHUB_TOKEN')
    org = os.getenv('GITHUB_ORG')
    repos = os.getenv('GITHUB_REPOS', '').split(',')

    if not all([token, org, repos]):
        logging.error("Missing required environment variables")
        logging.error(f"GITHUB_TOKEN present: {bool(token)}")
        logging.error(f"GITHUB_ORG present: {bool(org)}")
        logging.error(f"GITHUB_REPOS present: {bool(repos)}")
        exit(1)

    insights_client = GitHubInsights(token, org)
    
    # Process each repository
    for repo in repos:
        if not repo.strip():
            continue
            
        logging.info(f"\nProcessing repository: {repo}")
        insights = insights_client.get_insights(repo)
        formatted_output = insights_client.format_insights(insights)
        print(formatted_output) 