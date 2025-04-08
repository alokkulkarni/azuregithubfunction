import os
import logging
import requests
from typing import Dict, Optional, Any
from datetime import datetime
from base64 import b64encode

class NexusIQAnalyzer:
    """Class to analyze Nexus IQ data for repositories."""
    
    def __init__(self, nexus_url: str, username: str, password: str):
        self.base_url = nexus_url.rstrip('/')
        # Create basic auth header
        auth_string = b64encode(f"{username}:{password}".encode('utf-8')).decode('utf-8')
        self.headers = {
            'Authorization': f'Basic {auth_string}',
            'Content-Type': 'application/json'
        }

    def get_application_info(self, repo_name: str) -> Optional[Dict]:
        """Get application information from Nexus IQ."""
        try:
            # Search for application by public ID (assuming repo name is used as public ID)
            url = f"{self.base_url}/api/v2/applications"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            applications = response.json().get('applications', [])
            app = next((a for a in applications if a.get('publicId', '').lower() == repo_name.lower()), None)
            
            return app if app else None
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logging.info(f"Application {repo_name} not found in Nexus IQ")
            else:
                logging.error(f"Error fetching application info for {repo_name}: {str(e)}")
            return None
        except Exception as e:
            logging.error(f"Error fetching application info for {repo_name}: {str(e)}")
            return None

    def get_security_metrics(self, app_id: str) -> Dict[str, Any]:
        """Get security metrics for an application."""
        metrics = {
            'critical_issues': 0,
            'severe_issues': 0,
            'moderate_issues': 0,
            'low_issues': 0,
            'policy_violations': 0,
            'security_violations': 0,
            'license_violations': 0,
            'quality_violations': 0,
            'total_components': 0,
            'vulnerable_components': 0,
            'last_scan_date': 'Never',
            'policy_action': 'N/A',
            'risk_score': 0.0,
            'evaluated_components': 0
        }
        
        try:
            # Get latest evaluation report
            url = f"{self.base_url}/api/v2/reports/applications/{app_id}/latest"
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            
            report = response.json()
            
            # Extract metrics from report
            metrics.update({
                'critical_issues': self._count_issues_by_severity(report, 'CRITICAL'),
                'severe_issues': self._count_issues_by_severity(report, 'SEVERE'),
                'moderate_issues': self._count_issues_by_severity(report, 'MODERATE'),
                'low_issues': self._count_issues_by_severity(report, 'LOW'),
                'policy_violations': self._count_policy_violations(report),
                'security_violations': self._count_violations_by_type(report, 'SECURITY'),
                'license_violations': self._count_violations_by_type(report, 'LICENSE'),
                'quality_violations': self._count_violations_by_type(report, 'QUALITY'),
                'total_components': self._get_total_components(report),
                'vulnerable_components': self._get_vulnerable_components(report),
                'last_scan_date': report.get('evaluationDate', 'Never'),
                'policy_action': report.get('policyAction', 'N/A'),
                'risk_score': self._calculate_risk_score(report),
                'evaluated_components': self._get_evaluated_components(report)
            })
            
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                logging.info(f"No evaluation report found for application {app_id}")
            else:
                logging.error(f"Error fetching security metrics for {app_id}: {str(e)}")
        except Exception as e:
            logging.error(f"Error fetching security metrics for {app_id}: {str(e)}")
        
        return metrics

    def _count_issues_by_severity(self, report: Dict, severity: str) -> int:
        """Count issues of a specific severity in the report."""
        try:
            return sum(1 for issue in report.get('securityIssues', [])
                      if issue.get('severity', '').upper() == severity.upper())
        except Exception:
            return 0

    def _count_policy_violations(self, report: Dict) -> int:
        """Count total policy violations in the report."""
        try:
            return len(report.get('policyViolations', []))
        except Exception:
            return 0

    def _count_violations_by_type(self, report: Dict, violation_type: str) -> int:
        """Count violations of a specific type in the report."""
        try:
            return sum(1 for violation in report.get('policyViolations', [])
                      if violation.get('type', '').upper() == violation_type.upper())
        except Exception:
            return 0

    def _get_total_components(self, report: Dict) -> int:
        """Get total number of components in the report."""
        try:
            return len(report.get('components', []))
        except Exception:
            return 0

    def _get_vulnerable_components(self, report: Dict) -> int:
        """Get number of vulnerable components in the report."""
        try:
            return sum(1 for component in report.get('components', [])
                      if component.get('vulnerabilities', []))
        except Exception:
            return 0

    def _get_evaluated_components(self, report: Dict) -> int:
        """Get number of evaluated components in the report."""
        try:
            return report.get('evaluatedComponents', 0)
        except Exception:
            return 0

    def _calculate_risk_score(self, report: Dict) -> float:
        """Calculate risk score based on issue severity and count."""
        try:
            weights = {'CRITICAL': 10, 'SEVERE': 7, 'MODERATE': 4, 'LOW': 1}
            total_weight = sum(
                count * weights[severity]
                for severity in weights
                for count in [self._count_issues_by_severity(report, severity)]
            )
            max_score = 100
            return min(total_weight, max_score)
        except Exception:
            return 0.0
