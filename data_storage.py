import os
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Any
from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConnectionFailure, OperationFailure

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

class DataStorage:
    """Class to handle MongoDB storage of repository data."""
    
    def __init__(self, mongo_uri: str, db_name: str = "repository_analysis"):
        """Initialize MongoDB connection."""
        try:
            self.client = MongoClient(mongo_uri)
            self.db = self.client[db_name]
            self.repositories = self.db.repositories
            self.analysis_history = self.db.analysis_history
            
            # Create indexes for better query performance
            self.repositories.create_index([('Repository', 1)], unique=True)
            self.repositories.create_index([('last_updated', -1)])
            self.analysis_history.create_index([('timestamp', -1)])
            
            # Test the connection
            self.client.admin.command('ping')
            logging.info("Successfully connected to MongoDB")
            
        except ConnectionFailure as e:
            logging.error(f"Failed to connect to MongoDB: {str(e)}")
            raise
    
    def store_repository_data(self, excel_file: str) -> None:
        """Store repository data from Excel file in MongoDB."""
        try:
            # Read the Excel file
            df = pd.read_excel(excel_file, engine='openpyxl')
            
            # Convert DataFrame to list of dictionaries
            records = df.to_dict('records')
            
            # Add timestamp and metadata
            current_time = datetime.utcnow()
            for record in records:
                record['last_updated'] = current_time
                record['source_file'] = excel_file
                
                # Convert numeric values to appropriate types
                for key, value in record.items():
                    if isinstance(value, (int, float)) and pd.notna(value):
                        record[key] = float(value) if isinstance(value, float) else int(value)
                    elif pd.isna(value):
                        record[key] = None
                    elif key in ['PR Cycle Time (Closed)', 'PR Cycle Time (Open)', 'Total Avg PR Cycle Time']:
                        # Convert PR cycle time strings to numeric values if possible
                        try:
                            if isinstance(value, str) and value != 'N/A':
                                # Remove any non-numeric characters except decimal point
                                numeric_value = float(''.join(c for c in value if c.isdigit() or c == '.'))
                                record[key] = numeric_value
                        except (ValueError, TypeError):
                            record[key] = None
                
                # Update or insert the record
                self.repositories.update_one(
                    {'Repository': record['Repository']},
                    {'$set': record},
                    upsert=True
                )
            
            # Store analysis history
            self.analysis_history.insert_one({
                'timestamp': current_time,
                'source_file': excel_file,
                'records_processed': len(records),
                'status': 'success',
                'metrics_included': {
                    'pr_cycle_time': True,
                    'sonarqube': True,
                    'nexus_iq': True
                }
            })
            
            logging.info(f"Successfully stored {len(records)} repository records in MongoDB")
            
        except Exception as e:
            logging.error(f"Error storing repository data: {str(e)}")
            # Record failure in analysis history
            self.analysis_history.insert_one({
                'timestamp': datetime.utcnow(),
                'source_file': excel_file,
                'error': str(e),
                'status': 'failed'
            })
            raise
    
    def get_repository_data(self, repo_name: str = None) -> List[Dict]:
        """Retrieve repository data from MongoDB."""
        try:
            query = {'Repository': repo_name} if repo_name else {}
            return list(self.repositories.find(query))
        except Exception as e:
            logging.error(f"Error retrieving repository data: {str(e)}")
            return []
    
    def get_analysis_history(self, limit: int = 10) -> List[Dict]:
        """Retrieve analysis history from MongoDB."""
        try:
            return list(self.analysis_history.find().sort('timestamp', -1).limit(limit))
        except Exception as e:
            logging.error(f"Error retrieving analysis history: {str(e)}")
            return []
    
    def get_pr_cycle_time_stats(self) -> Dict[str, Any]:
        """Get statistics about PR cycle times across all repositories."""
        try:
            pipeline = [
                {
                    '$match': {
                        'PR Cycle Time (Closed)': {'$ne': None},
                        'PR Cycle Time (Open)': {'$ne': None},
                        'Total Avg PR Cycle Time': {'$ne': None}
                    }
                },
                {
                    '$group': {
                        '_id': None,
                        'avg_closed_cycle_time': {'$avg': '$PR Cycle Time (Closed)'},
                        'avg_open_cycle_time': {'$avg': '$PR Cycle Time (Open)'},
                        'avg_total_cycle_time': {'$avg': '$Total Avg PR Cycle Time'},
                        'max_closed_cycle_time': {'$max': '$PR Cycle Time (Closed)'},
                        'max_open_cycle_time': {'$max': '$PR Cycle Time (Open)'},
                        'max_total_cycle_time': {'$max': '$Total Avg PR Cycle Time'},
                        'min_closed_cycle_time': {'$min': '$PR Cycle Time (Closed)'},
                        'min_open_cycle_time': {'$min': '$PR Cycle Time (Open)'},
                        'min_total_cycle_time': {'$min': '$Total Avg PR Cycle Time'}
                    }
                }
            ]
            
            result = list(self.repositories.aggregate(pipeline))
            return result[0] if result else {}
            
        except Exception as e:
            logging.error(f"Error getting PR cycle time stats: {str(e)}")
            return {}
    
    def close(self) -> None:
        """Close MongoDB connection."""
        if hasattr(self, 'client'):
            self.client.close()
            logging.info("MongoDB connection closed")

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
        storage.store_repository_data(excel_filename)
        
        # Get and log analysis history
        history = storage.get_analysis_history()
        logging.info(f"Analysis history: {history}")
        
        # Get and log PR cycle time statistics
        pr_stats = storage.get_pr_cycle_time_stats()
        logging.info(f"PR Cycle Time Statistics: {pr_stats}")
        
    except Exception as e:
        logging.error(f"Error in main execution: {str(e)}")
    finally:
        if 'storage' in locals():
            storage.close()

if __name__ == "__main__":
    main() 