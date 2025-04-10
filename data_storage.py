import json
import os
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder to handle datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class DataStorage:
    """Handles data storage operations for repository analysis."""
    
    def __init__(self, mongo_uri: str):
        """Initialize data storage with MongoDB connection."""
        self.mongo_uri = mongo_uri
        self.logger = logging.getLogger(__name__)
        self._initialize_mongodb()
    
    def _initialize_mongodb(self):
        """Initialize MongoDB connection and collections."""
        try:
            if not self.mongo_uri:
                raise ValueError("MONGO_URI environment variable not set")
            
            self.client = MongoClient(self.mongo_uri)
            self.db = self.client.get_database()
            
            # Initialize collections
            self.github_collection = self.db['github']
            self.sonar_collection = self.db['sonar']
            self.nexus_collection = self.db['nexus']
            
            self.logger.info("Successfully initialized MongoDB connection and collections")
        except Exception as e:
            self.logger.error(f"Error initializing MongoDB: {str(e)}")
            raise
    
    def store_github_data(self, repository: str, data: Dict) -> bool:
        """Store GitHub data in MongoDB."""
        try:
            if self.github_collection is None:
                raise ValueError("GitHub collection not initialized")
            
            # Prepare the document
            document = {
                'repository': repository,
                'timestamp': datetime.utcnow(),
                'data': {
                    'repo_stats': data.get('repo_stats', {}),
                    'pr_metrics': data.get('pr_metrics', {}),
                    'commit_stats': data.get('commit_stats', {}),
                    'contributors': data.get('contributors', {}),
                    'branches': data.get('branches', {}),
                    'releases': data.get('releases', {}),
                    'issue_stats': data.get('issue_stats', {}),
                    'commit_activity': data.get('commit_activity', {})
                }
            }
            
            # Insert the document
            result = self.github_collection.insert_one(document)
            self.logger.info(f"Stored GitHub data for repository {repository}")
            return result.acknowledged
        except Exception as e:
            self.logger.error(f"Error storing GitHub data: {str(e)}")
            return False
    
    def store_sonar_data(self, data: Dict) -> bool:
        """Store SonarQube data in MongoDB."""
        try:
            if self.sonar_collection is None:
                raise ValueError("SonarQube collection not initialized")
            
            # Add timestamp to data
            data['timestamp'] = datetime.utcnow()
            
            # Insert document
            result = self.sonar_collection.insert_one(data)
            if result.acknowledged:
                self.logger.info(f"Successfully stored SonarQube data for repository: {data.get('repository')}")
                return True
            else:
                self.logger.error(f"Failed to store SonarQube data for repository: {data.get('repository')}")
                return False
        except Exception as e:
            self.logger.error(f"Error storing SonarQube data: {str(e)}")
            return False
    
    def store_nexus_data(self, data: Dict) -> bool:
        """Store NexusIQ data in MongoDB."""
        try:
            if self.nexus_collection is None:
                raise ValueError("NexusIQ collection not initialized")
            
            # Add timestamp to data
            data['timestamp'] = datetime.utcnow()
            
            # Insert document
            result = self.nexus_collection.insert_one(data)
            if result.acknowledged:
                self.logger.info(f"Successfully stored NexusIQ data for repository: {data.get('repository')}")
                return True
            else:
                self.logger.error(f"Failed to store NexusIQ data for repository: {data.get('repository')}")
                return False
        except Exception as e:
            self.logger.error(f"Error storing NexusIQ data: {str(e)}")
            return False
    
    def get_latest_github_data(self, repository: str) -> Optional[Dict]:
        """Get the latest GitHub data for a repository."""
        try:
            if self.github_collection is None:
                raise ValueError("GitHub collection not initialized")
            
            result = self.github_collection.find_one(
                {'repository': repository},
                sort=[('timestamp', -1)]
            )
            return result
        except Exception as e:
            self.logger.error(f"Error getting latest GitHub data for {repository}: {str(e)}")
            return None
    
    def get_latest_sonar_data(self, repository: str) -> Optional[Dict]:
        """Get the latest SonarQube data for a repository."""
        try:
            if self.sonar_collection is None:
                raise ValueError("SonarQube collection not initialized")
            
            result = self.sonar_collection.find_one(
                {'repository': repository},
                sort=[('timestamp', -1)]
            )
            return result
        except Exception as e:
            self.logger.error(f"Error getting latest SonarQube data for {repository}: {str(e)}")
            return None
    
    def get_latest_nexus_data(self, repository: str) -> Optional[Dict]:
        """Get the latest NexusIQ data for a repository."""
        try:
            if self.nexus_collection is None:
                raise ValueError("NexusIQ collection not initialized")
            
            result = self.nexus_collection.find_one(
                {'repository': repository},
                sort=[('timestamp', -1)]
            )
            return result
        except Exception as e:
            self.logger.error(f"Error getting latest NexusIQ data for {repository}: {str(e)}")
            return None
    
    def create_excel_report(self, output_file: str = "repository_report.xlsx") -> Optional[str]:
        """Create an Excel report from the collected data."""
        try:
            if any(collection is None for collection in [self.github_collection, self.sonar_collection, self.nexus_collection]):
                raise ValueError("One or more collections not initialized")
            
            # Get all repositories from GitHub collection
            repositories = list(self.github_collection.distinct('repository'))
            if not repositories:
                self.logger.warning("No repositories found to create report")
                return None
            
            # Create a timestamp for the filename
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f"repository_analysis_{timestamp}.xlsx"
            
            # Create Excel writer
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Create summary sheet
                summary_data = []
                for repo in repositories:
                    github_data = self.get_latest_github_data(repo)
                    sonar_data = self.get_latest_sonar_data(repo)
                    nexus_data = self.get_latest_nexus_data(repo)
                    
                    if github_data:
                        pr_metrics = github_data.get('pr_metrics', {})
                        summary_data.append({
                            'Repository': repo,
                            'Last Updated': github_data.get('timestamp', 'N/A'),
                            'Total PRs': pr_metrics.get('total_prs', 0),
                            'Open PRs': pr_metrics.get('open_prs', 0),
                            'Closed PRs': pr_metrics.get('closed_prs', 0),
                            'Merged PRs': pr_metrics.get('merged_prs', 0),
                            'Avg Cycle Time (hours)': pr_metrics.get('avg_cycle_time', 0),
                            'Median Cycle Time (hours)': pr_metrics.get('median_cycle_time', 0),
                            'Avg Time to First Review (hours)': pr_metrics.get('review_time', {}).get('avg_time_to_first_review', 0),
                            'Avg Review Time (hours)': pr_metrics.get('review_time', {}).get('avg_review_time', 0),
                            'Comment Density': pr_metrics.get('comment_density', 0),
                            'Total Commits': github_data.get('commit_activity', {}).get('total_commits', 0),
                            'Code Smells': sonar_data.get('code_smells', 0) if sonar_data else 0,
                            'Bugs': sonar_data.get('bugs', 0) if sonar_data else 0,
                            'Vulnerabilities': sonar_data.get('vulnerabilities', 0) if sonar_data else 0,
                            'Coverage': sonar_data.get('coverage', 0) if sonar_data else 0,
                            'Policy Violations': nexus_data.get('policy_violations', 0) if nexus_data else 0
                        })
                
                # Write summary sheet
                if summary_data:
                    pd.DataFrame(summary_data).to_excel(writer, sheet_name='Summary', index=False)
                
                # Create detailed sheets for each repository
                for repo in repositories:
                    github_data = self.get_latest_github_data(repo)
                    sonar_data = self.get_latest_sonar_data(repo)
                    nexus_data = self.get_latest_nexus_data(repo)
                    
                    if github_data:
                        # PR Metrics sheet
                        pr_metrics = github_data.get('pr_metrics', {})
                        if pr_metrics:
                            # PR Size Distribution
                            size_distribution = pd.DataFrame([pr_metrics.get('pr_size_distribution', {})])
                            size_distribution.to_excel(writer, sheet_name=f'{repo}_PR_Size_Distribution', index=False)
                            
                            # Review Times
                            review_times = pd.DataFrame([pr_metrics.get('review_time', {})])
                            review_times.to_excel(writer, sheet_name=f'{repo}_Review_Times', index=False)
                            
                            # Contributors
                            contributors_data = []
                            for contributor, stats in pr_metrics.get('contributors', {}).items():
                                contributors_data.append({
                                    'Contributor': contributor,
                                    'PRs Created': stats.get('prs_created', 0),
                                    'PRs Merged': stats.get('prs_merged', 0),
                                    'Total Comments': stats.get('total_comments', 0),
                                    'Total Reviews': stats.get('total_reviews', 0)
                                })
                            if contributors_data:
                                pd.DataFrame(contributors_data).to_excel(writer, sheet_name=f'{repo}_Contributors', index=False)
                        
                        # Commit Activity sheet
                        commit_activity = github_data.get('commit_activity', {})
                        if commit_activity:
                            pd.DataFrame([commit_activity]).to_excel(writer, sheet_name=f'{repo}_Commit_Activity', index=False)
                    
                    if sonar_data:
                        # SonarQube Analysis sheet
                        pd.DataFrame([sonar_data]).to_excel(writer, sheet_name=f'{repo}_SonarQube', index=False)
                    
                    if nexus_data:
                        # NexusIQ Analysis sheet
                        pd.DataFrame([nexus_data]).to_excel(writer, sheet_name=f'{repo}_NexusIQ', index=False)
            
            self.logger.info(f"Successfully created Excel report: {filename}")
            return filename
        except Exception as e:
            self.logger.error(f"Error creating Excel report: {str(e)}")
            return None
    
    def close(self):
        """Close MongoDB connection."""
        if self.client:
            self.client.close()
            self.logger.info("MongoDB connection closed")

def main():
    """Main function to store repository data in MongoDB."""
    # Load environment variables
    load_dotenv()
    
    # Get required environment variables
    mongo_uri = os.getenv('MONGO_URI')
    github_org = os.getenv('GITHUB_ORG')
    
    if not mongo_uri:
        logging.error("Missing required environment variable: MONGO_URI")
        return
    
    if not github_org:
        logging.error("Missing required environment variable: GITHUB_ORG")
        return
    
    # Look for the Excel file with org name pattern
    excel_filename = f"{github_org}_repository_insights.xlsx"
    
    if not os.path.exists(excel_filename):
        logging.error(f"Excel file not found: {excel_filename}")
        return
    
    logging.info(f"Found analysis file: {excel_filename}")
    
    try:
        # Initialize MongoDB storage
        storage = DataStorage(mongo_uri)
        
        # Store repository data
        storage.store_github_data(github_org, {'repo_stats': {}, 'pr_metrics': {}, 'commit_stats': {}, 'contributors': {}, 'branches': {}, 'releases': {}, 'issue_stats': {}, 'commit_activity': {}})
        storage.store_sonar_data({'repository': github_org})
        storage.store_nexus_data({'repository': github_org})
        
        # Create Excel report
        storage.create_excel_report(excel_filename)
        
    except Exception as e:
        logging.error(f"Error in main execution: {str(e)}")
    finally:
        if 'storage' in locals():
            storage.close()

if __name__ == "__main__":
    main() 