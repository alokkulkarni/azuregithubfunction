import os
import logging
from typing import Dict, List, Optional, Tuple, Any
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from datetime import datetime, timezone, timedelta
import requests
import schedule
import time
from github_insights import GitHubInsights
from sonarqube_analyzer import SonarQubeAnalyzer
from nexus_iq_analyzer import NexusIQAnalyzer
from data_storage import DataStorage
from pymongo import MongoClient
from dotenv import load_dotenv
import pandas as pd

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class OrgRepoScanner:
    def __init__(self, github_token: str, github_org: str, is_organization: bool, sonar_url: str, sonar_token: str, 
                 nexus_url: str, nexus_username: str, nexus_password: str, mongo_uri: str):
        """Initialize the repository scanner with all required components."""
        self.logger = logging.getLogger(__name__)
        
        # Initialize GitHub Insights
        self.github_insights = GitHubInsights(github_token, github_org, is_organization)
        
        # Initialize SonarQube Analyzer
        self.sonar_analyzer = SonarQubeAnalyzer(sonar_url, sonar_token)
        
        # Initialize NexusIQ Analyzer
        self.nexus_analyzer = NexusIQAnalyzer(nexus_url, nexus_username, nexus_password)
        
        # Initialize Data Storage
        self.data_storage = DataStorage(mongo_uri)
        
        self.logger.info("Repository scanner initialized successfully")

    def _scan_repository(self, repo_name: str) -> Dict:
        """Scan a single repository and collect data."""
        try:
            self.logger.info(f"Scanning repository: {repo_name}")
            
            # Initialize data dictionaries
            github_data = {
                'repo_stats': {},
                'pr_metrics': {},
                'commit_stats': {},
                'contributors': {},
                'branches': {},
                'releases': {},
                'issue_stats': {},
                'commit_activity': {}
            }
            
            sonar_data = {
                'repository': repo_name,
                'code_smells': 0,
                'bugs': 0,
                'vulnerabilities': 0,
                'coverage': 0,
                'complexity': 0
            }
            
            nexus_data = {
                'repository': repo_name,
                'policy_violations': 0,
                'critical_vulnerabilities': 0,
                'high_vulnerabilities': 0,
                'medium_vulnerabilities': 0,
                'low_vulnerabilities': 0
            }
            
            # Get GitHub insights
            try:
                github_insights = self.github_insights.get_repository_insights(repo_name)
                if github_insights:
                    github_data.update(github_insights)
                    self.data_storage.store_github_data(repo_name, github_insights)
            except Exception as e:
                self.logger.error(f"Error fetching GitHub insights: {str(e)}")
            
            # Get SonarQube insights
            try:
                sonar_insights = self.sonar_analyzer.analyze_repository(repo_name)
                if sonar_insights:
                    sonar_data.update(sonar_insights)
                    self.data_storage.store_sonar_data(sonar_data)
            except Exception as e:
                self.logger.error(f"Error fetching SonarQube insights: {str(e)}")
            
            # Get NexusIQ insights
            try:
                nexus_insights = self.nexus_analyzer.analyze_repository(repo_name)
                if nexus_insights:
                    nexus_data.update(nexus_insights)
                    self.data_storage.store_nexus_data(nexus_data)
            except Exception as e:
                self.logger.error(f"Error fetching NexusIQ insights: {str(e)}")
            
            return {
                'github': github_data,
                'sonar': sonar_data,
                'nexus': nexus_data
            }
            
        except Exception as e:
            self.logger.error(f"Error scanning repository {repo_name}: {str(e)}")
            return {
                'github': {},
                'sonar': {},
                'nexus': {}
            }

    def scan_organization(self) -> List[Dict]:
        """Scan all repositories in the organization."""
        try:
            self.logger.info(f"Starting organization scan for {self.github_insights.account}")
            
            # Get all repositories
            repositories = self.github_insights.get_repositories()
            if not repositories:
                self.logger.error("No repositories found")
                return []
            
            results = []
            for repo in repositories:
                repo_name = repo.get('name')
                if not repo_name:
                    continue
                
                result = self._scan_repository(repo_name)
                if result:
                    results.append(result)
            
            self.logger.info(f"Organization scan completed. Processed {len(results)} repositories")
            return results
            
        except Exception as e:
            self.logger.error(f"Error scanning organization: {str(e)}")
            return []

    def generate_report(self, output_file: str = "repository_report.xlsx") -> bool:
        """Generate a comprehensive report of all repository data."""
        try:
            self.logger.info("Generating repository report")
            return self.data_storage.create_excel_report(output_file)
            
        except Exception as e:
            self.logger.error(f"Error generating report: {str(e)}")
            return False

def main():
    """Main function to run the repository scanner."""
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load environment variables
    load_dotenv()  # Ensure .env file is loaded
    
    # Get environment variables
    github_token = os.getenv('GITHUB_TOKEN')
    github_account = os.getenv('GITHUB_ACCOUNT')
    is_organization = os.getenv('GITHUB_IS_ORGANIZATION', 'True').lower() == 'true'
    sonar_url = os.getenv('SONAR_URL')
    sonar_token = os.getenv('SONAR_TOKEN')
    nexus_url = os.getenv('NEXUS_URL')
    nexus_username = os.getenv('NEXUS_USERNAME')
    nexus_password = os.getenv('NEXUS_PASSWORD')
    mongo_uri = os.getenv('MONGO_URI')
    
    # Log environment variable status for debugging
    logging.info("Environment Variables Status:")
    logging.info(f"GITHUB_TOKEN present: {bool(github_token)}")
    logging.info(f"GITHUB_ACCOUNT present: {bool(github_account)}")
    logging.info(f"GITHUB_IS_ORGANIZATION: {is_organization}")
    logging.info(f"SONAR_URL present: {bool(sonar_url)}")
    logging.info(f"SONAR_TOKEN present: {bool(sonar_token)}")
    logging.info(f"NEXUS_URL present: {bool(nexus_url)}")
    logging.info(f"NEXUS_USERNAME present: {bool(nexus_username)}")
    logging.info(f"NEXUS_PASSWORD present: {bool(nexus_password)}")
    logging.info(f"MONGO_URI present: {bool(mongo_uri)}")
    
    # Validate environment variables
    if not all([github_token, github_account, sonar_url, sonar_token, 
                nexus_url, nexus_username, nexus_password, mongo_uri]):
        missing_vars = []
        if not github_token: missing_vars.append('GITHUB_TOKEN')
        if not github_account: missing_vars.append('GITHUB_ACCOUNT')
        if not sonar_url: missing_vars.append('SONAR_URL')
        if not sonar_token: missing_vars.append('SONAR_TOKEN')
        if not nexus_url: missing_vars.append('NEXUS_URL')
        if not nexus_username: missing_vars.append('NEXUS_USERNAME')
        if not nexus_password: missing_vars.append('NEXUS_PASSWORD')
        if not mongo_uri: missing_vars.append('MONGO_URI')
        
        logging.error(f"Missing required environment variables: {', '.join(missing_vars)}")
        logging.error("Please check your .env file and ensure all required variables are set")
        return
    
    # Initialize and run scanner
    scanner = OrgRepoScanner(
        github_token=github_token,
        github_org=github_account,
        is_organization=is_organization,
        sonar_url=sonar_url,
        sonar_token=sonar_token,
        nexus_url=nexus_url,
        nexus_username=nexus_username,
        nexus_password=nexus_password,
        mongo_uri=mongo_uri
    )
    
    try:
        results = scanner.scan_organization()
        if results:
            logger.info(f"Scanned {len(results)} repositories")
        else:
            logger.info("No repositories found")
        
        if results:
            report_file = scanner.generate_report()
            if report_file:
                logger.info(f"Successfully generated report: {report_file}")
            else:
                logger.info("No data found to generate report")
        else:
            logger.info("No repositories found to generate report")
    except Exception as e:
        logging.error(f"Error running repository scanner: {str(e)}")

if __name__ == "__main__":
    main() 