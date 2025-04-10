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

class DataStorage:
    """Class to handle MongoDB storage of repository data."""
    
    def __init__(self, mongo_uri: str):
        """Initialize DataStorage with MongoDB connection."""
        self.mongo_uri = mongo_uri
        self.client = MongoClient(mongo_uri)
        self.db = self.client.get_database()
        self.collection = self.db.repository_analysis
        self.logger = logging.getLogger(__name__)
        
    def store_data(self, data: Dict) -> bool:
        """Store repository data directly in MongoDB."""
        try:
            # Add timestamp
            data['timestamp'] = datetime.utcnow()
            
            # Insert or update document
            self.collection.update_one(
                {'repository': data['repository']},
                {'$set': data},
                upsert=True
            )
            self.logger.info(f"Successfully stored data for repository: {data['repository']}")
            return True
        except Exception as e:
            self.logger.error(f"Error storing data in MongoDB: {str(e)}")
            return False

    def create_excel_report(self, output_dir: str = 'output') -> Optional[str]:
        """Create Excel report from MongoDB data."""
        try:
            # Create output directory if it doesn't exist
            os.makedirs(output_dir, exist_ok=True)
            
            # Get all data from MongoDB
            cursor = self.collection.find({})
            data = list(cursor)
            
            if not data:
                self.logger.warning("No data found in MongoDB to create Excel report")
                return None
            
            # Convert to DataFrame
            df = pd.DataFrame(data)
            
            # Drop MongoDB specific fields
            df = df.drop(['_id', 'timestamp'], axis=1, errors='ignore')
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            excel_file = os.path.join(output_dir, f'repository_analysis_{timestamp}.xlsx')
            
            # Save to Excel
            df.to_excel(excel_file, index=False, engine='openpyxl')
            self.logger.info(f"Excel report created successfully: {excel_file}")
            return excel_file
            
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
        storage.store_data({'repository': github_org})
        
        # Create Excel report
        excel_file = storage.create_excel_report()
        if excel_file:
            logging.info(f"Excel report created: {excel_file}")
        
    except Exception as e:
        logging.error(f"Error in main execution: {str(e)}")
    finally:
        if 'storage' in locals():
            storage.close()

if __name__ == "__main__":
    main() 