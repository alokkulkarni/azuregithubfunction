import os
import logging
import requests
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from github_insights import GitHubInsights
from sonarqube_analyzer import SonarQubeAnalyzer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class OrgRepoScanner:
    def __init__(self, token: str, org: str, sonar_url: str, sonar_token: str):
        self.token = token
        self.org = org
        self.headers = {
            'Authorization': f'token {token}',
            'Accept': 'application/vnd.github.v3+json'
        }
        self.base_url = 'https://api.github.com'
        self.insights_client = GitHubInsights(token, org)
        self.sonar_analyzer = SonarQubeAnalyzer(sonar_url, sonar_token)

    def check_repo_content(self, repo_name: str) -> dict:
        """Check if repository has any code files."""
        try:
            url = f'{self.base_url}/repos/{self.org}/{repo_name}/contents'
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            contents = response.json()
            if not contents:
                return {'has_content': False, 'content_type': 'Empty'}
            
            # Check for code files - comprehensive list of programming language extensions
            code_extensions = {
                # Web Development
                '.html', '.htm', '.css', '.scss', '.sass', '.less', '.jsx', '.tsx',
                '.vue', '.svelte', '.json', '.xml', '.yaml', '.yml',
                
                # JavaScript/TypeScript
                '.js', '.ts', '.mjs', '.cjs', '.map', '.coffee',
                
                # Python
                '.py', '.pyx', '.pxd', '.pxi', '.pyc', '.pyd', '.pyo',
                '.ipynb', '.rpy',
                
                # Java/Kotlin/Scala
                '.java', '.kt', '.kts', '.scala', '.sc', '.gradle',
                
                # C/C++
                '.c', '.cpp', '.cc', '.cxx', '.h', '.hpp', '.hxx',
                
                # C#/.NET
                '.cs', '.vb', '.fs', '.fsx', '.xaml', '.cshtml', '.csproj',
                
                # Ruby
                '.rb', '.rake', '.gemspec', '.rbx', '.rjs', '.erb',
                
                # PHP
                '.php', '.phtml', '.php3', '.php4', '.php5', '.phps',
                
                # Go
                '.go', '.mod', '.sum',
                
                # Rust
                '.rs', '.rlib',
                
                # Swift/Objective-C
                '.swift', '.m', '.mm',
                
                # Shell/Bash
                '.sh', '.bash', '.zsh', '.fish',
                
                # Dart/Flutter
                '.dart',
                
                # R
                '.r', '.rmd',
                
                # Lua
                '.lua',
                
                # Perl
                '.pl', '.pm', '.t',
                
                # SQL
                '.sql', '.mysql', '.pgsql', '.sqlite',
                
                # Other
                '.asm', '.s', '.groovy', '.tcl', '.elm', '.ex', '.exs',
                '.erl', '.hrl', '.clj', '.cls', '.f90', '.f95', '.f03',
                '.ml', '.mli', '.hs', '.lhs', '.v', '.vh'
            }
            
            has_code = any(
                any(item.get('name', '').lower().endswith(ext) for ext in code_extensions)
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
            repos = self.get_all_repos()
            if not repos:
                logging.error("No repositories found or error fetching repositories")
                return

            # Process each repository
            insights_list = []
            for repo in repos:
                if insights := self.get_repo_insights(repo):
                    insights_list.append(insights)

            # Convert to DataFrame
            df = pd.DataFrame(insights_list)

            # Add SonarQube data
            sonar_columns = [
                'SonarQube Status',
                'Quality Gate',
                'Bugs',
                'Vulnerabilities',
                'Code Smells',
                'Coverage (%)',
                'Duplication (%)',
                'Security Rating',
                'Reliability Rating',
                'Maintainability Rating',
                'Lines of Code',
                'Cognitive Complexity',
                'Technical Debt',
                'Test Success (%)',
                'Test Failures',
                'Test Errors',
                'Last Analysis'
            ]

            # Initialize SonarQube columns with 'N/A'
            for col in sonar_columns:
                df[col] = 'N/A'

            # Process each repository for SonarQube data
            for idx, row in df.iterrows():
                repo_name = row['Repository']
                if pd.notna(repo_name):
                    project_key = f"{repo_name}".lower()
                    logging.info(f"Processing SonarQube data for: {repo_name}")
                    
                    if project_info := self.sonar_analyzer.get_project_info(project_key):
                        metrics = self.sonar_analyzer.get_project_metrics(project_key)
                        
                        # Update DataFrame with metrics
                        df.at[idx, 'SonarQube Status'] = 'Active'
                        df.at[idx, 'Quality Gate'] = metrics['quality_gate_status']
                        df.at[idx, 'Bugs'] = metrics['bugs']
                        df.at[idx, 'Vulnerabilities'] = metrics['vulnerabilities']
                        df.at[idx, 'Code Smells'] = metrics['code_smells']
                        df.at[idx, 'Coverage (%)'] = f"{metrics['coverage']:.1f}"
                        df.at[idx, 'Duplication (%)'] = f"{metrics['duplicated_lines_density']:.1f}"
                        df.at[idx, 'Security Rating'] = metrics['security_rating']
                        df.at[idx, 'Reliability Rating'] = metrics['reliability_rating']
                        df.at[idx, 'Maintainability Rating'] = metrics['sqale_rating']
                        df.at[idx, 'Lines of Code'] = metrics['lines_of_code']
                        df.at[idx, 'Cognitive Complexity'] = metrics['cognitive_complexity']
                        df.at[idx, 'Technical Debt'] = metrics['technical_debt']
                        df.at[idx, 'Test Success (%)'] = f"{metrics['test_success_density']:.1f}"
                        df.at[idx, 'Test Failures'] = metrics['test_failures']
                        df.at[idx, 'Test Errors'] = metrics['test_errors']
                        df.at[idx, 'Last Analysis'] = metrics['last_analysis']
                    else:
                        df.at[idx, 'SonarQube Status'] = 'Not Found'

            # Save to Excel with formatting
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Repository Insights')
                
                # Get the workbook and worksheet for formatting
                wb = writer.book
                ws = wb['Repository Insights']
                
                # Format headers
                for col_num, column in enumerate(df.columns, 1):
                    cell = ws.cell(row=1, column=col_num)
                    cell.font = Font(bold=True)
                    cell.fill = PatternFill(start_color='CCE5FF', end_color='CCE5FF', fill_type='solid')
                    cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                    ws.column_dimensions[get_column_letter(col_num)].width = 15
                
                # Format data cells
                for row in range(2, len(df) + 2):
                    for col in range(1, len(df.columns) + 1):
                        cell = ws.cell(row=row, column=col)
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

            logging.info(f"Successfully exported insights to {output_file}")
            
        except Exception as e:
            logging.error(f"Error in scan_and_export: {str(e)}")
            raise

def main():
    """Main function to run the repository scanner."""
    # Load environment variables
    load_dotenv()
    
    # Get required environment variables
    github_token = os.getenv('GITHUB_TOKEN')
    github_org = os.getenv('GITHUB_ORG')
    sonar_url = os.getenv('SONAR_URL', 'http://localhost:9000')
    sonar_token = os.getenv('SONAR_TOKEN')
    
    if not all([github_token, github_org, sonar_token]):
        logging.error("Missing required environment variables")
        return
    
    # Initialize scanner
    scanner = OrgRepoScanner(github_token, github_org, sonar_url, sonar_token)
    
    # Create output filename with organization name
    output_file = f"{github_org}_repository_insights.xlsx"
    
    # Scan repositories and export insights
    scanner.scan_and_export(output_file)

if __name__ == "__main__":
    main() 