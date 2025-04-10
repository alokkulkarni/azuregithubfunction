import os
import logging
from typing import Dict, List, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime
from github_scanner import GitHubScanner
from sonarqube_analyzer import SonarQubeAnalyzer
from nexus_iq_analyzer import NexusIQAnalyzer
from data_storage import DataStorage

class OrgRepoScanner:
    def __init__(self, github_token: str, github_org: str, sonar_url: str, sonar_token: str,
                 nexus_url: str, nexus_username: str, nexus_password: str, mongo_uri: str):
        """Initialize the repository scanner with all required components."""
        self.github_scanner = GitHubScanner(github_token, github_org)
        self.sonar_analyzer = SonarQubeAnalyzer(sonar_url, sonar_token)
        self.nexus_analyzer = NexusIQAnalyzer(nexus_url, nexus_username, nexus_password)
        self.data_storage = DataStorage(mongo_uri)
        self.logger = logging.getLogger(__name__)
        
        # Initialize checkpoint and results files
        self.checkpoint_file = f"{github_org}_scan_checkpoint.json"
        self.results_file = f"{github_org}_scan_results.json"
        
    def process_repository(self, repo: Dict) -> Optional[Dict]:
        """Process a single repository and return enriched data."""
        try:
            repo_name = repo['name']
            self.logger.info(f"Processing repository: {repo_name}")
            
            # Get PR cycle time
            pr_cycle_time = self.github_scanner.get_pr_cycle_time(repo_name)
            
            # Get SonarQube metrics
            sonar_metrics = self.sonar_analyzer.get_project_metrics(repo_name)
            
            # Get Nexus IQ metrics
            nexus_metrics = self.nexus_analyzer.get_application_metrics(repo_name)
            
            # Combine all data
            enriched_data = {
                'repository': repo_name,
                'pr_cycle_time': pr_cycle_time,
                'sonarqube_metrics': sonar_metrics,
                'nexus_metrics': nexus_metrics,
                'last_updated': datetime.utcnow().isoformat()
            }
            
            # Store in MongoDB
            if self.data_storage.store_data(enriched_data):
                self.logger.info(f"Successfully stored data for {repo_name}")
                return enriched_data
            else:
                self.logger.error(f"Failed to store data for {repo_name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error processing repository {repo_name}: {str(e)}")
            return None

    def process_page(self, page: int, per_page: int = 100) -> List[Dict]:
        """Process a page of repositories in parallel."""
        try:
            repos = self.github_scanner.get_repositories(page, per_page)
            if not repos:
                return []
            
            results = []
            with ThreadPoolExecutor(max_workers=10) as executor:
                future_to_repo = {
                    executor.submit(self.process_repository, repo): repo
                    for repo in repos
                }
                
                for future in as_completed(future_to_repo):
                    repo = future_to_repo[future]
                    try:
                        result = future.result()
                        if result:
                            results.append(result)
                    except Exception as e:
                        self.logger.error(f"Error processing repository {repo['name']}: {str(e)}")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error processing page {page}: {str(e)}")
            return []

    def scan_organization(self) -> None:
        """Scan all repositories in the organization."""
        try:
            # Load checkpoint if exists
            checkpoint = self.load_checkpoint()
            current_page = checkpoint.get('current_page', 1)
            processed_results = checkpoint.get('processed_results', [])
            
            while True:
                self.logger.info(f"Processing page {current_page}")
                page_results = self.process_page(current_page)
                
                if not page_results:
                    break
                
                # Update processed results
                processed_results.extend(page_results)
                
                # Save checkpoint
                self.save_checkpoint({
                    'current_page': current_page + 1,
                    'processed_results': processed_results
                })
                
                current_page += 1
            
            # Create final Excel report
            excel_file = self.data_storage.create_excel_report()
            if excel_file:
                self.logger.info(f"Final Excel report created: {excel_file}")
            
            # Clean up checkpoint files
            self.cleanup_checkpoint()
            
        except Exception as e:
            self.logger.error(f"Error during organization scan: {str(e)}")
            raise
        finally:
            self.data_storage.close()

    def load_checkpoint(self) -> Dict:
        """Load scan checkpoint if it exists."""
        try:
            if os.path.exists(self.checkpoint_file):
                with open(self.checkpoint_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            self.logger.error(f"Error loading checkpoint: {str(e)}")
            return {}

    def save_checkpoint(self, data: Dict) -> None:
        """Save scan checkpoint."""
        try:
            with open(self.checkpoint_file, 'w') as f:
                json.dump(data, f)
            self.logger.info(f"Checkpoint saved for page {data.get('current_page')}")
        except Exception as e:
            self.logger.error(f"Error saving checkpoint: {str(e)}")

    def cleanup_checkpoint(self) -> None:
        """Remove checkpoint files after successful completion."""
        try:
            if os.path.exists(self.checkpoint_file):
                os.remove(self.checkpoint_file)
            if os.path.exists(self.results_file):
                os.remove(self.results_file)
            self.logger.info("Checkpoint files cleaned up")
        except Exception as e:
            self.logger.error(f"Error cleaning up checkpoint files: {str(e)}")

def main():
    """Main function to run the repository scanner."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load environment variables
    github_token = os.getenv('GITHUB_TOKEN')
    github_org = os.getenv('GITHUB_ORG')
    sonar_url = os.getenv('SONAR_URL')
    sonar_token = os.getenv('SONAR_TOKEN')
    nexus_url = os.getenv('NEXUS_URL')
    nexus_username = os.getenv('NEXUS_USERNAME')
    nexus_password = os.getenv('NEXUS_PASSWORD')
    mongo_uri = os.getenv('MONGO_URI')
    
    # Validate environment variables
    if not all([github_token, github_org, sonar_url, sonar_token, 
                nexus_url, nexus_username, nexus_password, mongo_uri]):
        logging.error("Missing required environment variables")
        return
    
    # Initialize and run scanner
    scanner = OrgRepoScanner(
        github_token=github_token,
        github_org=github_org,
        sonar_url=sonar_url,
        sonar_token=sonar_token,
        nexus_url=nexus_url,
        nexus_username=nexus_username,
        nexus_password=nexus_password,
        mongo_uri=mongo_uri
    )
    
    try:
        scanner.scan_organization()
    except Exception as e:
        logging.error(f"Error running repository scanner: {str(e)}")

if __name__ == "__main__":
    main() 