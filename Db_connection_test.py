import pymssql
import logging
from dotenv import load_dotenv
import os
import time


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def connect_to_database(max_retries=3, retry_delay=1):
    """Connects to the SQL Server database with retry logic.
    
    Args:
        max_retries (int): Maximum number of connection attempts
        retry_delay (int): Delay between retries in seconds
        
    Returns:
        pymssql.Connection: Database connection object or None if connection fails
    """
    load_dotenv()
    
    for attempt in range(max_retries):
        try:
            # Connection Details
            conn = pymssql.connect(  
                host= os.getenv("SQL_HOST"),
                port= os.getenv("SQL_PORT"),
                server= os.getenv("SQL_SERVER"),
                user= os.getenv("SQL_USER"),
                password= 'Welcome@123',
                database= os.getenv("SQL_DATABASE"),
                as_dict=True,
                login_timeout=3  # Reduced timeout to match Upload_Base_Tables.py
            )
            
            # Validate connection
            with conn.cursor() as cursor:
                cursor.execute("SELECT 1 as test")
                cursor.fetchone()
            
            logger.info("Successfully connected to the database")
            return conn
            
        except Exception as e:
            logger.error(f"Connection attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                logger.info(f"Retrying in {retry_delay} seconds...")
                time.sleep(retry_delay)
            else:
                logger.error("Max retries reached. Could not connect to database.")
                return None

def main():
    """Main function to test database connection."""
    logger.info("Attempting to connect to database...")
    conn = connect_to_database()
    
    if conn:
        logger.info("Database connection successful!")
        conn.close()
        logger.info("Database connection closed.")
    else:
        logger.error("Failed to establish database connection.")

if __name__ == "__main__":
    main()