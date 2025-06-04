# this is not working for aura
from dotenv import load_dotenv
import os
import neo4j
import pymssql
import pandas as pd
import re
from datetime import datetime
from neo4j import GraphDatabase

# Create Relationship
def create_relationship(neo4j_session, url, username, password):
    try:
        query = """
        MATCH (p:Process), (ts:Steps)
        WHERE p.ProcessID = ts.ProcessID
        MERGE (p)-[:PROCESS_STEPS]->(ts)
        """
        neo4j_session.run(query)
    except neo4j.exceptions.SessionExpired as e:
        print("Session expired, attempting to reconnect...")
        # Attempt to reconnect and rerun the query
        neo4j_session = neo4j.GraphDatabase.driver(url, auth=(username, password)).session()
        neo4j_session.run(query)        
    except Exception as e:
        print(f"An error occurred: {e}")  

# -----------------------------------------------------------------------------
# main()
# -----------------------------------------------------------------------------
def main():
    # Load env
    load_dotenv()


    # Neo4j connection details - Aura
    url = os.getenv('NEO4J_URI')
    username = os.getenv('NEO4J_USERNAME')
    password = os.getenv('NEO4J_PASSWORD')
    driver = GraphDatabase.driver(
      url,
      auth=(username, password)
    )
    with driver.session() as neo4j_sess:
        create_relationship(neo4j_sess, url, username, password)
    driver.close()

if __name__ == "__main__":
    main()
