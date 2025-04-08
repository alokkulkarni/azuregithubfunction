import os
import logging
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from github_insights import GitHubInsights

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class OrgRepoScanner:
    def __init__(self, token: str, org: str):
        self.token = token
        self.org = org
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'
        self.insights_client = GitHubInsights(token, org)

    def get_all_repos(self) -> list:
        """Get all repositories in the organization."""
        repos = []
        page = 1
        per_page = 100  # Maximum allowed by GitHub API

        while True:
            url = f'{self.base_url}/orgs/{self.org}/repos'
            params = {
                'per_page': per_page,
                'page': page,
                'sort': 'updated',
                'direction': 'desc'
            }
            
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                page_repos = response.json()
                
                if not page_repos:
                    break
                
                repos.extend(page_repos)
                logging.info(f"Fetched {len(page_repos)} repositories from page {page}")
                
                if len(page_repos) < per_page:
                    break
                    
                page += 1
                
            except requests.exceptions.RequestException as e:
                logging.error(f"Error fetching repositories: {str(e)}")
                break

        return repos

    def get_repo_insights(self, repo: dict) -> dict:
        """Get comprehensive insights for a repository."""
        repo_name = repo['name']
        logging.info(f"Processing repository: {repo_name}")
        
        insights = {
            'Repository': repo_name,
            'Description': repo.get('description', ''),
            'Created At': repo.get('created_at', ''),
            'Updated At': repo.get('updated_at', ''),
            'Last Push': repo.get('pushed_at', ''),
            'Is Archived': repo.get('archived', False),
            'Is Private': repo.get('private', False),
            'Default Branch': repo.get('default_branch', ''),
            'License': repo.get('license', {}).get('name', ''),
            'Stars': repo.get('stargazers_count', 0),
            'Forks': repo.get('forks_count', 0),
            'Watchers': repo.get('watchers_count', 0),
            'Open Issues': repo.get('open_issues_count', 0),
            'Size (KB)': repo.get('size', 0),
            'Language': repo.get('language', ''),
            'Last Commit SHA': '',
            'Last Commit Message': '',
            'Last Commit Author': '',
            'Last Commit Date': '',
            'Top Contributors': '',
            'Total Contributors': 0,
            'Open PRs': 0,
            'Closed PRs': 0,
            'Processed At': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            # Get additional insights using GitHubInsights
            repo_insights = self.insights_client.get_insights(repo_name)
            
            # Update last commit information
            if repo_insights['last_commit']:
                commit = repo_insights['last_commit']
                insights['Last Commit SHA'] = commit['sha'][:7]
                insights['Last Commit Message'] = commit['message']
                insights['Last Commit Author'] = commit['author']
                insights['Last Commit Date'] = commit['date']

            # Update contributors information
            if repo_insights['contributors']:
                contributors = repo_insights['contributors']
                insights['Total Contributors'] = len(contributors)
                top_contributors = [
                    f"{c['login']} ({c['contributions']})"
                    for c in contributors[:5]
                ]
                insights['Top Contributors'] = ', '.join(top_contributors)

            # Get PR counts
            pr_url = f'{self.base_url}/repos/{self.org}/{repo_name}/pulls'
            pr_params = {'state': 'all', 'per_page': 1}
            pr_response = requests.get(pr_url, headers=self.headers, params=pr_params)
            if pr_response.status_code == 200:
                link_header = pr_response.headers.get('Link', '')
                if 'rel="last"' in link_header:
                    last_page = int(link_header.split('page=')[-1].split('>')[0])
                    insights['Closed PRs'] = last_page
                else:
                    insights['Closed PRs'] = len(pr_response.json())

            # Get open PRs
            pr_params['state'] = 'open'
            open_prs = requests.get(pr_url, headers=self.headers, params=pr_params)
            if open_prs.status_code == 200:
                insights['Open PRs'] = len(open_prs.json())

        except Exception as e:
            logging.error(f"Error getting insights for {repo_name}: {str(e)}")
            insights['Processed At'] = f"Error: {str(e)}"

        return insights

    def scan_and_export(self, output_file: str) -> None:
        """Scan all repositories and export insights to Excel."""
        try:
            # Get all repositories
            logging.info(f"Fetching all repositories for organization: {self.org}")
            repos = self.get_all_repos()
            logging.info(f"Found {len(repos)} repositories")

            # Process each repository
            all_insights = []
            for repo in repos:
                insights = self.get_repo_insights(repo)
                all_insights.append(insights)

            # Create DataFrame and export to Excel
            df = pd.DataFrame(all_insights)
            
            # Format datetime columns
            date_columns = ['Created At', 'Updated At', 'Last Push', 'Last Commit Date']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col]).dt.strftime('%Y-%m-%d %H:%M:%S')

            # Save to Excel
            logging.info(f"Saving insights to: {output_file}")
            df.to_excel(output_file, index=False)
            logging.info("Export completed successfully")

        except Exception as e:
            logging.error(f"Error during scanning and export: {str(e)}")

def main():
    # Load environment variables
    load_dotenv()
    token = os.getenv('GITHUB_TOKEN')
    org = os.getenv('GITHUB_ORG')

    if not all([token, org]):
        logging.error("Missing required environment variables")
        logging.error(f"GITHUB_TOKEN present: {bool(token)}")
        logging.error(f"GITHUB_ORG present: {bool(org)}")
        return

    # Initialize scanner and start processing
    scanner = OrgRepoScanner(token, org)
    output_file = f"{org}_repository_insights.xlsx"
    scanner.scan_and_export(output_file)

if __name__ == "__main__":
    main() 