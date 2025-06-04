import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

def create_neo4j_connection():
    # Neo4j connection details from environment variables
    url = "neo4j+s://00dedc34.databases.neo4j.io:7687"
    username = "neo4j"
    password = "Ap3oo16wSEHi960BIYSKJmzQ2ol0ieCO0qxCkifsymc"
    
    try:
        # Create driver instance
        driver = GraphDatabase.driver(url, auth=(username, password))
        
        # Test the connection
        with driver.session() as session:
            result = session.run("RETURN 1")
            logger.info("Successfully connected to Neo4j")
            return driver
    except Exception as e:
        logger.error(f"Failed to connect to Neo4j: {str(e)}")
        raise

def test_simple_query(driver):
    try:
        with driver.session() as session:
            # Run a simple query to get count of Process nodes
            result = session.run("MATCH (n:Process) RETURN count(n) as count")
            record = result.single()
            logger.info(f"Number of Process nodes in database: {record['count']}")
    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        raise

def main():
    try:
        # Create connection
        driver = create_neo4j_connection()
        
        # Test a simple query
        test_simple_query(driver)
        
        # Close the driver
        driver.close()
        logger.info("Connection closed successfully")
        
    except Exception as e:
        logger.error(f"Test failed: {str(e)}")

if __name__ == "__main__":
    main()