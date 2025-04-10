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
                'status': 'success'
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
        
    except Exception as e:
        logging.error(f"Error in main execution: {str(e)}")
    finally:
        if 'storage' in locals():
            storage.close()

if __name__ == "__main__":
    main() 