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

    def check_repo_content(self, repo_name: str) -> dict:
        """Check if repository has any code files."""
        try:
            url = f'{self.base_url}/repos/{self.org}/{repo_name}/contents'
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            contents = response.json()
            if not contents:
                return {'has_content': False, 'content_type': 'Empty'}
            
            # Check for code files
            code_extensions = {'.py', '.js', '.java', '.cpp', '.cs', '.go', '.rb', '.php', '.ts', '.swift'}
            has_code = any(
                any(item.get('name', '').endswith(ext) for ext in code_extensions)
                for item in contents if isinstance(item, dict)
            )
            
            return {
                'has_content': True,
                'content_type': 'Contains Code' if has_code else 'No Code Files'
            }
        except Exception as e:
            logging.error(f"Error checking content for {repo_name}: {str(e)}")
            return {'has_content': False, 'content_type': 'Error checking content'}

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
        if not repo or not isinstance(repo, dict):
            logging.error("Invalid repository data received")
            return None

        repo_name = repo.get('name')
        if not repo_name:
            logging.error("Repository name not found in data")
            return None

        logging.info(f"Processing repository: {repo_name}")
        
        # Initialize insights with default values
        insights = {
            'Repository': repo_name,
            'Description': repo.get('description', ''),
            'Created At': repo.get('created_at', ''),
            'Updated At': repo.get('updated_at', ''),
            'Last Push': repo.get('pushed_at', ''),
            'Is Archived': repo.get('archived', False),
            'Is Private': repo.get('private', False),
            'Default Branch': repo.get('default_branch', ''),
            'License': '',
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
            'Has Content': '',
            'Content Type': '',
            'Processed At': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }

        try:
            # Check repository content
            content_info = self.check_repo_content(repo_name)
            insights['Has Content'] = content_info['has_content']
            insights['Content Type'] = content_info['content_type']

            # Safely get license information
            license_info = repo.get('license') or {}
            if isinstance(license_info, dict):
                insights['License'] = license_info.get('name', '')
            else:
                insights['License'] = ''

            # Get additional insights using GitHubInsights
            try:
                repo_insights = self.insights_client.get_insights(repo_name)
            except Exception as e:
                logging.error(f"Error getting insights from GitHubInsights for {repo_name}: {str(e)}")
                repo_insights = None

            if repo_insights and isinstance(repo_insights, dict):
                # Update last commit information
                last_commit = repo_insights.get('last_commit') or {}
                if isinstance(last_commit, dict):
                    insights['Last Commit SHA'] = last_commit.get('sha', '')[:7] if last_commit.get('sha') else ''
                    insights['Last Commit Message'] = last_commit.get('message', '')
                    insights['Last Commit Author'] = last_commit.get('author', '')
                    insights['Last Commit Date'] = last_commit.get('date', '')

                # Update contributors information
                contributors = repo_insights.get('contributors') or []
                if isinstance(contributors, list):
                    insights['Total Contributors'] = len(contributors)
                    top_contributors = []
                    for c in contributors[:5]:
                        if isinstance(c, dict):
                            login = c.get('login', '')
                            contributions = c.get('contributions', 0)
                            if login:
                                top_contributors.append(f"{login} ({contributions})")
                    insights['Top Contributors'] = ', '.join(top_contributors)

            # Get PR counts
            try:
                pr_url = f'{self.base_url}/repos/{self.org}/{repo_name}/pulls'
                pr_params = {'state': 'all', 'per_page': 1}
                pr_response = requests.get(pr_url, headers=self.headers, params=pr_params)
                
                if pr_response.status_code == 200:
                    link_header = pr_response.headers.get('Link', '')
                    if 'rel="last"' in link_header:
                        try:
                            last_page = int(link_header.split('page=')[-1].split('>')[0])
                            insights['Closed PRs'] = last_page
                        except (ValueError, IndexError) as e:
                            logging.error(f"Error parsing PR count for {repo_name}: {str(e)}")
                            insights['Closed PRs'] = 0
                    else:
                        pr_data = pr_response.json()
                        insights['Closed PRs'] = len(pr_data) if isinstance(pr_data, list) else 0

                # Get open PRs
                pr_params['state'] = 'open'
                open_prs = requests.get(pr_url, headers=self.headers, params=pr_params)
                if open_prs.status_code == 200:
                    pr_data = open_prs.json()
                    insights['Open PRs'] = len(pr_data) if isinstance(pr_data, list) else 0
            except requests.exceptions.RequestException as e:
                logging.error(f"Error fetching PR data for {repo_name}: {str(e)}")
                insights['Open PRs'] = 0
                insights['Closed PRs'] = 0

        except Exception as e:
            logging.error(f"Error getting insights for {repo_name}: {str(e)}")
            insights['Processed At'] = f"Error: {str(e)}"

        # Ensure all string values are empty strings instead of None
        for key, value in insights.items():
            if value is None:
                insights[key] = ''

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
                if insights:  # Only add valid insights
                    all_insights.append(insights)

            if not all_insights:
                logging.error("No valid repository insights found")
                return

            # Create DataFrame and export to Excel
            df = pd.DataFrame(all_insights)
            
            # Format datetime columns
            date_columns = ['Created At', 'Updated At', 'Last Push', 'Last Commit Date']
            for col in date_columns:
                if col in df.columns:
                    df[col] = pd.to_datetime(df[col], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S')

            # Replace NaN values with empty strings
            df = df.fillna('')

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