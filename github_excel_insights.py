import os
import logging
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv
from github_insights import GitHubInsights

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

def process_excel(input_file: str, output_file: str) -> None:
    """Process GitHub insights for repositories listed in Excel file."""
    # Load environment variables
    load_dotenv()
    token = os.getenv('GITHUB_TOKEN')
    org = os.getenv('GITHUB_ORG')

    if not all([token, org]):
        logging.error("Missing required environment variables")
        logging.error(f"GITHUB_TOKEN present: {bool(token)}")
        logging.error(f"GITHUB_ORG present: {bool(org)}")
        return

    # Initialize GitHub Insights client
    insights_client = GitHubInsights(token, org)

    try:
        # Read input Excel file
        logging.info(f"Reading input file: {input_file}")
        df = pd.read_excel(input_file)
        
        # Ensure required columns exist
        if 'Repository' not in df.columns:
            logging.error("Input Excel must contain a 'Repository' column")
            return

        # Initialize new columns for insights
        df['Last Commit SHA'] = ''
        df['Last Commit Message'] = ''
        df['Last Commit Author'] = ''
        df['Last Commit Date'] = ''
        df['Top Contributors'] = ''
        df['Stars'] = 0
        df['Forks'] = 0
        df['Watchers'] = 0
        df['Open Issues'] = 0
        df['Size (KB)'] = 0
        df['Primary Language'] = ''
        df['Processed At'] = ''

        # Process each repository
        total_repos = len(df)
        for index, row in df.iterrows():
            repo = row['Repository']
            logging.info(f"Processing repository {index + 1}/{total_repos}: {repo}")
            
            try:
                # Get insights for the repository
                insights = insights_client.get_insights(repo)
                
                # Update DataFrame with insights
                if insights['last_commit']:
                    commit = insights['last_commit']
                    df.at[index, 'Last Commit SHA'] = commit['sha'][:7]
                    df.at[index, 'Last Commit Message'] = commit['message']
                    df.at[index, 'Last Commit Author'] = commit['author']
                    df.at[index, 'Last Commit Date'] = commit['date']

                if insights['contributors']:
                    top_contributors = [
                        f"{c['login']} ({c['contributions']})"
                        for c in insights['contributors'][:5]
                    ]
                    df.at[index, 'Top Contributors'] = ', '.join(top_contributors)

                if insights['stats']:
                    stats = insights['stats']
                    df.at[index, 'Stars'] = stats['stars']
                    df.at[index, 'Forks'] = stats['forks']
                    df.at[index, 'Watchers'] = stats['watchers']
                    df.at[index, 'Open Issues'] = stats['open_issues']
                    df.at[index, 'Size (KB)'] = stats['size']
                    df.at[index, 'Primary Language'] = stats['language']

                df.at[index, 'Processed At'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            except Exception as e:
                logging.error(f"Error processing repository {repo}: {str(e)}")
                df.at[index, 'Processed At'] = f"Error: {str(e)}"

        # Save results to new Excel file
        logging.info(f"Saving results to: {output_file}")
        df.to_excel(output_file, index=False)
        logging.info("Processing completed successfully")

    except Exception as e:
        logging.error(f"Error processing Excel file: {str(e)}")

if __name__ == "__main__":
    # Example usage
    input_file = "repositories.xlsx"  # Input Excel file with 'Repository' column
    output_file = "github_insights.xlsx"  # Output Excel file with insights
    
    process_excel(input_file, output_file) 