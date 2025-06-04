import pymssql
import logging
from dotenv import load_dotenv
import os


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def connect_to_database():
    """Connects to the local SQL Server database called NextGenAI."""
    try:
        load_dotenv()
        # Connection Details
        conn = pymssql.connect(  
            port= os.getenv('SQL_PORT'),
            server= os.getenv('SQL_SERVER'),
            user= os.getenv('SQL_USER'),
            password= os.getenv('SQL_PASSWORD'),

            database='NextGenAI',
            as_dict=True,
            login_timeout=3
        )

    
        #logger.info("Connection to the database was successful.")
        return conn
    except Exception as e:
        logger.error(f"An error occurred while connecting to the database: {e}")
        return None