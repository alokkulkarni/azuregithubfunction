import logging
import requests
from datetime import datetime, timezone
from typing import Dict, List, Optional
import time

class GitHubInsights:
    def __init__(self, token: str, account: str, is_organization: bool = True):
        """Initialize GitHub Insights with token and account name."""
        self.token = token
        self.account = account
        self.is_organization = is_organization
        self.base_url = "https://api.github.com"
        self.headers = {
            "Authorization": f"token {token}",
            "Accept": "application/vnd.github.v3+json"
        }
        self.logger = logging.getLogger(__name__)
        self.logger.info(f"Initialized GitHub Insights for {'organization' if is_organization else 'user'} account: {account}")
        self.rate_limit_remaining = 5000  # Default rate limit
        self.rate_limit_reset = 0

    def _make_request(self, url: str, params: Dict = None) -> Optional[Dict]:
        """Make a request to the GitHub API with rate limit handling."""
        try:
            # Check rate limit
            if self.rate_limit_remaining <= 10:  # Leave some buffer
                reset_time = datetime.fromtimestamp(self.rate_limit_reset)
                now = datetime.now()
                if now < reset_time:
                    wait_time = (reset_time - now).total_seconds() + 1
                    self.logger.warning(f"Rate limit low. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)

            response = requests.get(url, headers=self.headers, params=params)
            
            # Update rate limit info
            self.rate_limit_remaining = int(response.headers.get('X-RateLimit-Remaining', 5000))
            self.rate_limit_reset = int(response.headers.get('X-RateLimit-Reset', 0))
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                self.logger.warning(f"Resource not found: {url}")
                return None
            elif e.response.status_code == 403:
                self.logger.error("Rate limit exceeded or access denied")
                return None
            else:
                self.logger.error(f"HTTP error: {str(e)}")
                return None
        except Exception as e:
            self.logger.error(f"Error making request: {str(e)}")
            return None

    def get_repositories(self, page: int = 1, per_page: int = 100) -> List[Dict]:
        """Get repositories for either organization or user."""
        try:
            if self.is_organization:
                url = f'{self.base_url}/orgs/{self.account}/repos'
            else:
                url = f'{self.base_url}/users/{self.account}/repos'
                
            params = {
                'per_page': per_page,
                'page': page,
                'sort': 'updated',
                'direction': 'desc'
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                account_type = "organization" if self.is_organization else "user"
                self.logger.error(f"{account_type.capitalize()} '{self.account}' not found or you don't have access to it")
            elif e.response.status_code == 403:
                self.logger.error("GitHub API rate limit exceeded or token doesn't have sufficient permissions")
            else:
                self.logger.error(f"HTTP error fetching repositories: {str(e)}")
            return []
        except Exception as e:
            self.logger.error(f"Error fetching repositories: {str(e)}")
            return []

    def verify_account_access(self) -> bool:
        """Verify if the account (org or user) exists and the token has access to it."""
        try:
            if self.is_organization:
                url = f'{self.base_url}/orgs/{self.account}'
            else:
                url = f'{self.base_url}/users/{self.account}'
                
            response = requests.get(url, headers=self.headers)
            
            if response.status_code == 404:
                account_type = "organization" if self.is_organization else "user"
                self.logger.error(f"{account_type.capitalize()} '{self.account}' not found or you don't have access to it")
                return False
            elif response.status_code == 403:
                self.logger.error("GitHub API rate limit exceeded or token doesn't have sufficient permissions")
                return False
            elif response.status_code == 200:
                account_type = "organization" if self.is_organization else "user"
                self.logger.info(f"Successfully verified access to {account_type} '{self.account}'")
                return True
            else:
                self.logger.error(f"Unexpected error verifying account access: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error verifying account access: {str(e)}")
            return False

    def calculate_cycle_time(self, created_at: str, closed_at: str = None) -> float:
        """Calculate cycle time in days between created_at and closed_at dates."""
        try:
            created = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
            closed = datetime.fromisoformat(closed_at.replace('Z', '+00:00')) if closed_at else datetime.now(timezone.utc)
            return (closed - created).total_seconds() / (24 * 3600)  # Convert to days
        except Exception as e:
            self.logger.error(f"Error calculating cycle time: {str(e)}")
            return 0.0

    def get_pr_cycle_time(self, repo_name: str) -> Dict[str, float]:
        """Get PR cycle time metrics for a repository."""
        try:
            url = f'{self.base_url}/repos/{self.account}/{repo_name}/pulls'
            params = {
                'state': 'all',  # Get both open and closed PRs
                'per_page': 100,
                'sort': 'updated',
                'direction': 'desc'
            }
            
            closed_times = []
            open_times = []
            all_times = []
            
            while True:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                prs = response.json()
                
                if not prs:
                    break
                
                for pr in prs:
                    created_at = pr['created_at']
                    closed_at = pr.get('closed_at')
                    cycle_time = self.calculate_cycle_time(created_at, closed_at)
                    
                    all_times.append(cycle_time)
                    if closed_at:
                        closed_times.append(cycle_time)
                    else:
                        open_times.append(cycle_time)
                
                # Check for next page
                if 'next' in response.links:
                    url = response.links['next']['url']
                else:
                    break
            
            return {
                'avg_cycle_time_closed': sum(closed_times) / len(closed_times) if closed_times else 0.0,
                'avg_cycle_time_open': sum(open_times) / len(open_times) if open_times else 0.0,
                'total_avg_cycle_time': sum(all_times) / len(all_times) if all_times else 0.0
            }
            
        except Exception as e:
            self.logger.error(f"Error getting PR cycle times for {repo_name}: {str(e)}")
            return {
                'avg_cycle_time_closed': 0.0,
                'avg_cycle_time_open': 0.0,
                'total_avg_cycle_time': 0.0
            }

    def get_repository_insights(self, repo_name: str) -> Dict:
        """Get comprehensive insights for a repository."""
        try:
            # Initialize empty insights dictionary
            insights = {
                'repo_stats': {},
                'pr_metrics': {},
                'commit_stats': {},
                'contributors': {},
                'branches': {},
                'releases': {},
                'issue_stats': {},
                'commit_activity': {}
            }

            # Get repository details
            repo_url = f'{self.base_url}/repos/{self.account}/{repo_name}'
            repo_data = self._make_request(repo_url)
            if not repo_data:
                self.logger.error(f"Failed to get repository data for {repo_name}")
                return insights

            # Update repository stats
            insights['repo_stats'] = {
                'name': repo_data.get('name', ''),
                'description': repo_data.get('description', ''),
                'created_at': repo_data.get('created_at'),
                'updated_at': repo_data.get('updated_at'),
                'stars': repo_data.get('stargazers_count', 0),
                'watchers': repo_data.get('watchers_count', 0),
                'forks': repo_data.get('forks_count', 0),
                'open_issues': repo_data.get('open_issues_count', 0),
                'size': repo_data.get('size', 0),
                'language': repo_data.get('language', ''),
                'topics': repo_data.get('topics', []),
                'license': repo_data.get('license', {}).get('name', ''),
                'archived': repo_data.get('archived', False),
                'private': repo_data.get('private', False),
                'has_wiki': repo_data.get('has_wiki', False),
                'has_pages': repo_data.get('has_pages', False),
                'has_projects': repo_data.get('has_projects', False),
                'has_downloads': repo_data.get('has_downloads', False),
                'has_issues': repo_data.get('has_issues', False)
            }

            # Get PR statistics
            try:
                pr_metrics = self.get_pr_statistics(repo_name)
                if pr_metrics:
                    insights['pr_metrics'] = pr_metrics
            except Exception as e:
                self.logger.error(f"Error getting PR statistics: {str(e)}")
            
            # Get commit statistics
            try:
                commit_stats = self.get_commit_statistics(repo_name)
                if commit_stats:
                    insights['commit_stats'] = commit_stats
            except Exception as e:
                self.logger.error(f"Error getting commit statistics: {str(e)}")
            
            # Get contributors
            try:
                contributors = self.get_contributors(repo_name)
                if contributors:
                    insights['contributors'] = contributors
            except Exception as e:
                self.logger.error(f"Error getting contributors: {str(e)}")
            
            # Get branch information
            try:
                branches = self.get_branch_info(repo_name)
                if branches:
                    insights['branches'] = branches
            except Exception as e:
                self.logger.error(f"Error getting branch information: {str(e)}")
            
            # Get release information
            try:
                releases = self.get_release_info(repo_name)
                if releases:
                    insights['releases'] = releases
            except Exception as e:
                self.logger.error(f"Error getting release information: {str(e)}")
            
            # Get issue statistics
            try:
                issue_stats = self.get_issue_statistics(repo_name)
                if issue_stats:
                    insights['issue_stats'] = issue_stats
            except Exception as e:
                self.logger.error(f"Error getting issue statistics: {str(e)}")
            
            # Get commit activity
            try:
                commit_activity = self.get_commit_activity(repo_name)
                if commit_activity:
                    insights['commit_activity'] = commit_activity
            except Exception as e:
                self.logger.error(f"Error getting commit activity: {str(e)}")

            return insights
            
        except Exception as e:
            self.logger.error(f"Error getting repository insights: {str(e)}")
            return {
                'repo_stats': {},
                'pr_metrics': {},
                'commit_stats': {},
                'contributors': {},
                'branches': {},
                'releases': {},
                'issue_stats': {},
                'commit_activity': {}
            }

    def get_pr_statistics(self, repo_name: str) -> Dict:
        """Get PR statistics for a repository."""
        try:
            url = f'{self.base_url}/repos/{self.account}/{repo_name}/pulls'
            params = {'state': 'all', 'per_page': 100}
            prs = self._make_request(url, params)
            if not prs:
                return {}

            pr_metrics = {
                'total_prs': len(prs),
                'open_prs': 0,
                'closed_prs': 0,
                'merged_prs': 0,
                'cycle_times': {
                    'total': [],
                    'closed': [],
                    'open': [],
                    'merged': []
                },
                'avg_cycle_times': {
                    'total': 0,
                    'closed': 0,
                    'open': 0,
                    'merged': 0
                },
                'median_cycle_times': {
                    'total': 0,
                    'closed': 0,
                    'open': 0,
                    'merged': 0
                },
                'pr_size_distribution': {
                    'small': 0,    # < 100 lines
                    'medium': 0,   # 100-500 lines
                    'large': 0,    # 500-1000 lines
                    'xlarge': 0    # > 1000 lines
                },
                'review_time': {
                    'avg_time_to_first_review': 0,
                    'avg_review_time': 0
                },
                'comment_density': 0,
                'contributors': {}
            }

            total_review_time = 0
            total_time_to_first_review = 0
            total_comments = 0
            total_changes = 0

            for pr in prs:
                # Count PR states
                if pr.get('state') == 'open':
                    pr_metrics['open_prs'] += 1
                elif pr.get('state') == 'closed':
                    pr_metrics['closed_prs'] += 1
                    if pr.get('merged_at'):
                        pr_metrics['merged_prs'] += 1

                # Calculate cycle time
                created_at = datetime.fromisoformat(pr.get('created_at').replace('Z', '+00:00'))
                closed_at = pr.get('closed_at')
                merged_at = pr.get('merged_at')
                current_time = datetime.now(timezone.utc)

                # Calculate cycle time in hours
                if closed_at:
                    closed_at = datetime.fromisoformat(closed_at.replace('Z', '+00:00'))
                    cycle_time = (closed_at - created_at).total_seconds() / 3600
                    pr_metrics['cycle_times']['closed'].append(cycle_time)
                    if merged_at:
                        merged_at = datetime.fromisoformat(merged_at.replace('Z', '+00:00'))
                        merged_cycle_time = (merged_at - created_at).total_seconds() / 3600
                        pr_metrics['cycle_times']['merged'].append(merged_cycle_time)
                else:
                    cycle_time = (current_time - created_at).total_seconds() / 3600
                    pr_metrics['cycle_times']['open'].append(cycle_time)

                pr_metrics['cycle_times']['total'].append(cycle_time)

                # Calculate PR size
                additions = pr.get('additions', 0)
                deletions = pr.get('deletions', 0)
                total_changes = additions + deletions
                if total_changes < 100:
                    pr_metrics['pr_size_distribution']['small'] += 1
                elif total_changes < 500:
                    pr_metrics['pr_size_distribution']['medium'] += 1
                elif total_changes < 1000:
                    pr_metrics['pr_size_distribution']['large'] += 1
                else:
                    pr_metrics['pr_size_distribution']['xlarge'] += 1

                # Get review information
                reviews_url = f'{self.base_url}/repos/{self.account}/{repo_name}/pulls/{pr.get("number")}/reviews'
                reviews = self._make_request(reviews_url)
                if reviews:
                    first_review = None
                    for review in reviews:
                        if review.get('submitted_at'):
                            review_time = datetime.fromisoformat(review.get('submitted_at').replace('Z', '+00:00'))
                            if not first_review or review_time < first_review:
                                first_review = review_time

                    if first_review:
                        time_to_first_review = (first_review - created_at).total_seconds() / 3600
                        total_time_to_first_review += time_to_first_review

                        if closed_at:
                            review_time = (closed_at - first_review).total_seconds() / 3600
                            total_review_time += review_time

                # Count comments
                comments = pr.get('comments', 0)
                review_comments = pr.get('review_comments', 0)
                total_comments += comments + review_comments

                # Track contributors
                user = pr.get('user', {})
                if user:
                    contributor = user.get('login')
                    if contributor:
                        if contributor not in pr_metrics['contributors']:
                            pr_metrics['contributors'][contributor] = {
                                'prs_created': 0,
                                'prs_merged': 0,
                                'total_comments': 0,
                                'total_reviews': 0
                            }
                        pr_metrics['contributors'][contributor]['prs_created'] += 1
                        if pr.get('merged_at'):
                            pr_metrics['contributors'][contributor]['prs_merged'] += 1
                        pr_metrics['contributors'][contributor]['total_comments'] += comments
                        pr_metrics['contributors'][contributor]['total_reviews'] += len(reviews) if reviews else 0

            # Calculate average cycle times
            for state in ['total', 'closed', 'open', 'merged']:
                times = pr_metrics['cycle_times'][state]
                if times:
                    pr_metrics['avg_cycle_times'][state] = sum(times) / len(times)
                    # Calculate median
                    times.sort()
                    mid = len(times) // 2
                    pr_metrics['median_cycle_times'][state] = (
                        times[mid] if len(times) % 2 != 0
                        else (times[mid - 1] + times[mid]) / 2
                    )

            # Calculate review metrics
            if pr_metrics['total_prs'] > 0:
                pr_metrics['review_time']['avg_time_to_first_review'] = total_time_to_first_review / pr_metrics['total_prs']
                pr_metrics['review_time']['avg_review_time'] = total_review_time / pr_metrics['total_prs']
                pr_metrics['comment_density'] = total_comments / total_changes if total_changes > 0 else 0

            return pr_metrics
        except Exception as e:
            self.logger.error(f"Error getting PR statistics: {str(e)}")
            return {}

    def get_commit_statistics(self, repo_name: str) -> Dict:
        """Get commit statistics for a repository."""
        try:
            url = f'{self.base_url}/repos/{self.account}/{repo_name}/commits'
            params = {'per_page': 100}
            commits = self._make_request(url, params)
            if not commits:
                return None
            
            total_commits = 0
            authors = {}
            dates = {}
            
            for commit in commits:
                total_commits += 1
                author = commit['commit']['author']['name']
                date = commit['commit']['author']['date'].split('T')[0]
                
                authors[author] = authors.get(author, 0) + 1
                dates[date] = dates.get(date, 0) + 1
            
            return {
                'total_commits': total_commits,
                'authors': authors,
                'dates': dates
            }
        except Exception as e:
            self.logger.error(f"Error getting commit statistics for {repo_name}: {str(e)}")
            return None

    def get_contributors(self, repo_name: str) -> Dict:
        """Get contributor information for a repository."""
        try:
            url = f'{self.base_url}/repos/{self.account}/{repo_name}/contributors'
            contributors = self._make_request(url)
            if not contributors:
                return None
            
            contributor_data = []
            for contributor in contributors:
                contributor_data.append({
                    'login': contributor['login'],
                    'contributions': contributor['contributions'],
                    'avatar_url': contributor['avatar_url'],
                    'type': contributor['type']
                })
            
            return {
                'total_contributors': len(contributor_data),
                'contributors': contributor_data
            }
        except Exception as e:
            self.logger.error(f"Error getting contributors for {repo_name}: {str(e)}")
            return None

    def get_branch_info(self, repo_name: str) -> Dict:
        """Get branch information for a repository."""
        try:
            url = f'{self.base_url}/repos/{self.account}/{repo_name}/branches'
            branches = self._make_request(url)
            if not branches:
                return None
            
            branch_data = []
            for branch in branches:
                branch_data.append({
                    'name': branch['name'],
                    'protected': branch['protected'],
                    'commit_sha': branch['commit']['sha']
                })
            
            return {
                'total_branches': len(branch_data),
                'branches': branch_data
            }
        except Exception as e:
            self.logger.error(f"Error getting branch info for {repo_name}: {str(e)}")
            return None

    def get_release_info(self, repo_name: str) -> Dict:
        """Get release information for a repository."""
        try:
            url = f'{self.base_url}/repos/{self.account}/{repo_name}/releases'
            releases = self._make_request(url)
            if not releases:
                return None
            
            release_data = []
            for release in releases:
                release_data.append({
                    'tag_name': release['tag_name'],
                    'name': release['name'],
                    'created_at': release['created_at'],
                    'published_at': release['published_at'],
                    'prerelease': release['prerelease'],
                    'draft': release['draft'],
                    'assets_count': len(release['assets'])
                })
            
            return {
                'total_releases': len(release_data),
                'releases': release_data
            }
        except Exception as e:
            self.logger.error(f"Error getting release info for {repo_name}: {str(e)}")
            return None

    def get_issue_statistics(self, repo_name: str) -> Dict:
        """Get issue statistics for a repository."""
        try:
            url = f'{self.base_url}/repos/{self.account}/{repo_name}/issues'
            params = {'state': 'all', 'per_page': 100}
            issues = self._make_request(url, params)
            if not issues:
                return None
            
            open_issues = 0
            closed_issues = 0
            issue_labels = {}
            
            for issue in issues:
                if issue['state'] == 'open':
                    open_issues += 1
                else:
                    closed_issues += 1
                
                for label in issue['labels']:
                    label_name = label['name']
                    issue_labels[label_name] = issue_labels.get(label_name, 0) + 1
            
            return {
                'total_issues': open_issues + closed_issues,
                'open_issues': open_issues,
                'closed_issues': closed_issues,
                'issue_labels': issue_labels
            }
        except Exception as e:
            self.logger.error(f"Error getting issue statistics for {repo_name}: {str(e)}")
            return None

    def get_commit_activity(self, repo_name: str) -> Dict:
        """Get commit activity for a repository."""
        try:
            url = f'{self.base_url}/repos/{self.account}/{repo_name}/stats/commit_activity'
            activity = self._make_request(url)
            if not activity:
                return None
            
            return {
                'activity': activity
            }
        except Exception as e:
            self.logger.error(f"Error getting commit activity for {repo_name}: {str(e)}")
            return None

    def get_repo_insights(self, repo: Dict) -> Optional[Dict]:
        """Get insights for a specific repository."""
        try:
            repo_name = repo.get('name')
            if not repo_name:
                return None

            self.logger.info(f"Getting insights for repository: {repo_name}")
            
            # Get PR cycle times
            pr_cycle_times = self.get_pr_cycle_time(repo_name)
            
            # Combine all data
            insights = {
                'Repository': repo_name,
                'Description': repo.get('description', ''),
                'Language': repo.get('language', ''),
                'Stars': repo.get('stargazers_count', 0),
                'Forks': repo.get('forks_count', 0),
                'Open Issues': repo.get('open_issues_count', 0),
                'PR Cycle Time (Closed)': f"{pr_cycle_times['avg_cycle_time_closed']:.1f}",
                'PR Cycle Time (Open)': f"{pr_cycle_times['avg_cycle_time_open']:.1f}",
                'Total Avg PR Cycle Time': f"{pr_cycle_times['total_avg_cycle_time']:.1f}",
                'Last Updated': datetime.now(timezone.utc).isoformat()
            }
            
            return insights
            
        except Exception as e:
            self.logger.error(f"Error getting insights for {repo.get('name', 'unknown')}: {str(e)}")
            return None

    def get_repo_contributors(self, repo: str) -> List[Dict]:
        """Get list of contributors for a repository."""
        url = f'{self.base_url}/repos/{self.account}/{repo}/contributors'
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
        url = f'{self.base_url}/repos/{self.account}/{repo}/commits'
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
        url = f'{self.base_url}/repos/{self.account}/{repo}'
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
    account = os.getenv('GITHUB_ACCOUNT')
    is_organization = os.getenv('GITHUB_IS_ORGANIZATION', 'True').lower() == 'true'
    repos = os.getenv('GITHUB_REPOS', '').split(',')

    if not all([token, account, is_organization, repos]):
        logging.error("Missing required environment variables")
        logging.error(f"GITHUB_TOKEN present: {bool(token)}")
        logging.error(f"GITHUB_ACCOUNT present: {bool(account)}")
        logging.error(f"GITHUB_IS_ORGANIZATION present: {bool(is_organization)}")
        logging.error(f"GITHUB_REPOS present: {bool(repos)}")
        exit(1)

    insights_client = GitHubInsights(token, account, is_organization)
    
    # Process each repository
    for repo in repos:
        if not repo.strip():
            continue
            
        logging.info(f"\nProcessing repository: {repo}")
        insights = insights_client.get_repository_insights(repo)
        formatted_output = insights_client.format_insights(insights)
        print(formatted_output) 