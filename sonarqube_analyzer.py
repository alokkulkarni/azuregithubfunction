import os
import logging
import requests
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any, Optional
from dotenv import load_dotenv
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class SonarQubeAnalyzer:
    """Class to analyze SonarQube data for repositories."""
    
    def __init__(self, sonar_url: str, sonar_token: str):
        self.base_url = sonar_url.rstrip('/')
        self.auth = (sonar_token, '')
        self.headers = {
            'Content-Type': 'application/json'
        }

    def get_project_info(self, project_key: str) -> Optional[Dict]:
        """Get project information from SonarQube."""
        try:
            url = f"{self.base_url}/api/projects/search"
            params = {
                'q': project_key
            }
            response = requests.get(url, auth=self.auth, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            components = data.get('components', [])
            
            return components[0] if components else None
            
        except Exception as e:
            logging.error(f"Error fetching project info for {project_key}: {str(e)}")
            return None

    def get_project_metrics(self, project_key: str) -> Dict[str, Any]:
        """Get quality metrics for a project."""
        metrics = {
            'bugs': 0,
            'vulnerabilities': 0,
            'code_smells': 0,
            'coverage': 0.0,
            'duplicated_lines_density': 0.0,
            'security_rating': 'N/A',
            'reliability_rating': 'N/A',
            'sqale_rating': 'N/A',
            'last_analysis': 'Never',
            'quality_gate_status': 'N/A',
            'lines_of_code': 0,
            'cognitive_complexity': 0,
            'technical_debt': '0min'
        }
        
        try:
            # Get measures
            url = f"{self.base_url}/api/measures/component"
            params = {
                'component': project_key,
                'metricKeys': 'bugs,vulnerabilities,code_smells,coverage,duplicated_lines_density,'
                             'security_rating,reliability_rating,sqale_rating,ncloc,cognitive_complexity,'
                             'sqale_index'
            }
            response = requests.get(url, auth=self.auth, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            measures = {m['metric']: m['value'] for m in data.get('component', {}).get('measures', [])}
            
            # Update metrics with actual values
            metrics.update({
                'bugs': int(measures.get('bugs', 0)),
                'vulnerabilities': int(measures.get('vulnerabilities', 0)),
                'code_smells': int(measures.get('code_smells', 0)),
                'coverage': float(measures.get('coverage', 0)),
                'duplicated_lines_density': float(measures.get('duplicated_lines_density', 0)),
                'security_rating': self._convert_rating(measures.get('security_rating', '0')),
                'reliability_rating': self._convert_rating(measures.get('reliability_rating', '0')),
                'sqale_rating': self._convert_rating(measures.get('sqale_rating', '0')),
                'lines_of_code': int(measures.get('ncloc', 0)),
                'cognitive_complexity': int(measures.get('cognitive_complexity', 0)),
                'technical_debt': self._convert_technical_debt(measures.get('sqale_index', '0'))
            })
            
            # Get quality gate status
            url = f"{self.base_url}/api/qualitygates/project_status"
            params = {'projectKey': project_key}
            response = requests.get(url, auth=self.auth, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            metrics['quality_gate_status'] = data.get('projectStatus', {}).get('status', 'N/A')
            
            # Get last analysis date
            url = f"{self.base_url}/api/project_analyses/search"
            params = {
                'project': project_key,
                'ps': 1  # Get only the latest analysis
            }
            response = requests.get(url, auth=self.auth, headers=self.headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            analyses = data.get('analyses', [])
            if analyses:
                metrics['last_analysis'] = analyses[0].get('date', 'N/A')
            
        except Exception as e:
            logging.error(f"Error fetching metrics for {project_key}: {str(e)}")
        
        return metrics

    def _convert_rating(self, rating: str) -> str:
        """Convert SonarQube rating from number to letter grade."""
        rating_map = {
            '1': 'A',
            '2': 'B',
            '3': 'C',
            '4': 'D',
            '5': 'E'
        }
        return rating_map.get(rating, 'N/A')

    def _convert_technical_debt(self, minutes: str) -> str:
        """Convert technical debt from minutes to readable format."""
        try:
            minutes = int(minutes)
            if minutes < 60:
                return f"{minutes}min"
            elif minutes < 1440:  # 24 hours
                hours = minutes // 60
                return f"{hours}h {minutes % 60}min"
            else:
                days = minutes // 1440
                hours = (minutes % 1440) // 60
                return f"{days}d {hours}h"
        except (ValueError, TypeError):
            return "0min"

    def enrich_github_analysis(self, github_analysis_file: str, output_file: str):
        """Enrich GitHub analysis with SonarQube data."""
        try:
            # Read the GitHub analysis Excel file
            xls = pd.ExcelFile(github_analysis_file)
            
            # Read all sheets
            sheets = {
                sheet_name: pd.read_excel(xls, sheet_name)
                for sheet_name in xls.sheet_names
            }
            
            # Add SonarQube metrics to the Summary sheet
            summary_df = sheets['Summary']
            
            # Add new columns for SonarQube metrics
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
                'Last Analysis'
            ]
            
            for col in sonar_columns:
                summary_df[col] = 'N/A'
            
            # Update each repository with SonarQube data
            for idx, row in summary_df.iterrows():
                repo = row['Repository']
                project_key = f"{os.getenv('GITHUB_ORG')}_{repo}".lower()
                
                if project_info := self.get_project_info(project_key):
                    metrics = self.get_project_metrics(project_key)
                    
                    summary_df.at[idx, 'SonarQube Status'] = 'Active'
                    summary_df.at[idx, 'Quality Gate'] = metrics['quality_gate_status']
                    summary_df.at[idx, 'Bugs'] = metrics['bugs']
                    summary_df.at[idx, 'Vulnerabilities'] = metrics['vulnerabilities']
                    summary_df.at[idx, 'Code Smells'] = metrics['code_smells']
                    summary_df.at[idx, 'Coverage (%)'] = f"{metrics['coverage']:.1f}"
                    summary_df.at[idx, 'Duplication (%)'] = f"{metrics['duplicated_lines_density']:.1f}"
                    summary_df.at[idx, 'Security Rating'] = metrics['security_rating']
                    summary_df.at[idx, 'Reliability Rating'] = metrics['reliability_rating']
                    summary_df.at[idx, 'Maintainability Rating'] = metrics['sqale_rating']
                    summary_df.at[idx, 'Lines of Code'] = metrics['lines_of_code']
                    summary_df.at[idx, 'Cognitive Complexity'] = metrics['cognitive_complexity']
                    summary_df.at[idx, 'Technical Debt'] = metrics['technical_debt']
                    summary_df.at[idx, 'Last Analysis'] = metrics['last_analysis']
                else:
                    summary_df.at[idx, 'SonarQube Status'] = 'Not Found'
            
            # Create a new Excel writer
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Write updated summary sheet
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Copy other sheets as is
                for sheet_name, df in sheets.items():
                    if sheet_name != 'Summary':
                        df.to_excel(writer, sheet_name=sheet_name, index=False)
                
                # Format the Summary sheet
                worksheet = writer.sheets['Summary']
                
                # Set column widths
                column_widths = {
                    'A': 30,  # Repository
                    'B': 15,  # Quality Score
                    'C': 15,  # Aberrancy Score
                    'D': 20,  # Industry Rating
                    'E': 15,  # Risk Level
                    'F': 40,  # Risk Factors
                    'G': 25,  # Analyzed At
                    'H': 15,  # SonarQube Status
                    'I': 15,  # Quality Gate
                    'J': 10,  # Bugs
                    'K': 15,  # Vulnerabilities
                    'L': 15,  # Code Smells
                    'M': 15,  # Coverage (%)
                    'N': 15,  # Duplication (%)
                    'O': 15,  # Security Rating
                    'P': 15,  # Reliability Rating
                    'Q': 20,  # Maintainability Rating
                    'R': 15,  # Lines of Code
                    'S': 20,  # Cognitive Complexity
                    'T': 15,  # Technical Debt
                    'U': 20   # Last Analysis
                }
                
                for col, width in column_widths.items():
                    worksheet.column_dimensions[col].width = width
                
                # Format header row
                header_font = Font(bold=True)
                header_fill = PatternFill(
                    start_color='CCE5FF',
                    end_color='CCE5FF',
                    fill_type='solid'
                )
                header_alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
                
                for cell in worksheet[1]:
                    cell.font = header_font
                    cell.fill = header_fill
                    cell.alignment = header_alignment
                
                # Format data cells
                for row in worksheet.iter_rows(min_row=2):
                    for cell in row:
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            
            logging.info(f"Successfully enriched analysis with SonarQube data: {output_file}")
            
        except Exception as e:
            logging.error(f"Error enriching GitHub analysis with SonarQube data: {str(e)}")
            raise

def main():
    """Main function to run the SonarQube analysis."""
    # Load environment variables
    load_dotenv()
    
    # Get required environment variables
    sonar_url = os.getenv('SONAR_URL', 'http://localhost:9000')
    sonar_token = os.getenv('SONAR_TOKEN')
    
    if not sonar_token:
        logging.error("Missing required environment variable: SONAR_TOKEN")
        return
    
    # Find the most recent GitHub analysis file
    analysis_files = [f for f in os.listdir('.') if f.endswith('.xlsx') and 'code_quality_analysis' in f]
    if not analysis_files:
        logging.error("No GitHub analysis file found")
        return
    
    # Get the most recent file
    latest_file = max(analysis_files, key=os.path.getctime)
    
    # Create output filename
    output_file = latest_file.replace('.xlsx', '_with_sonar.xlsx')
    
    # Initialize SonarQube analyzer
    analyzer = SonarQubeAnalyzer(sonar_url, sonar_token)
    
    # Enrich GitHub analysis with SonarQube data
    analyzer.enrich_github_analysis(latest_file, output_file)

if __name__ == "__main__":
    main() 