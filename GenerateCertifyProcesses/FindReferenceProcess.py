# Find Reference ProcessID
import pandas as pd
import openai
import json
import re
from dotenv import load_dotenv
import os
import logging
from neo4j import GraphDatabase
from typing import Optional, Dict, Any
from neo4j import GraphDatabase
from langchain_openai import OpenAIEmbeddings
from pydantic.v1 import BaseModel

# Load env
load_dotenv()
os.getenv('OPENAI_API_KEY')

logger = logging.getLogger(__name__)

# Create Neo4J Connection
def create_neo4j_connection():
    # Neo4j connection details
    url = os.getenv('NEO4J_URI')
    username = "neo4j"
    password = os.getenv('NEO4J_PASSWORD')
    try:
        driver = GraphDatabase.driver(url, auth=(username, password))
        with driver.session() as session:
            session.run("RETURN 1")
        logger.info("Successfully connected to Neo4j")
        return driver
    except Exception as e:
        logger.error(f"Failed to initialize Neo4j connection: {str(e)}")
        raise

# Find Similar Process
def findProcessFromGraph1(sap_screen, description, logger1) -> Optional[Dict[str, Any]]:
    try:
        global logger;
        logger = logger1;

        # Create embedding from description in excel
        embeddings = OpenAIEmbeddings(openai_api_key=openai.api_key)
        embedding_vector = embeddings.embed_query(description)
        
        #This is similarity search query. Use Step_embeddings
        driver = create_neo4j_connection()
        with driver.session() as session:
            # result = session.run("""
            #     CYPHER runtime = parallel parallelRuntimeSupport=all 
            #     MATCH (n:Process)-[:PROCESS_STEPS]->(s:Steps)
            #     where n.ProcessID = s.ProcessID 
            #     and s.ApplicationVersionID <> 1
            #     and s.TCode = $sap_screen
            #     and (s.InterfaceLibraryID = 1 or s.InterfaceLibraryID = 9)
            #     and  s.ApplicationVersionName = $appname
            #     WITH collect(n) AS filtered_nodes
            #     CALL db.index.vector.queryNodes($index_name, $k, $vector)
            #     YIELD node, score
            #     WHERE node IN filtered_nodes

            #     RETURN node.ProcessID AS ProcessID,
            #         node.Step AS Step,
            #         score AS similarity
            #     ORDER BY similarity DESC;
            #     """, {
            #     "sap_screen": sap_screen,
            #     "index_name": "Process_Details_Index",
            #     "k": 100,
            #     "vector": embedding_vector,
            #     "appname":"1"
            # })

            # anu - removing ApplicationVersionName from query
            result = session.run("""
                CYPHER runtime = parallel parallelRuntimeSupport=all 
                MATCH (n:Process)-[:PROCESS_STEPS]->(s:Steps)
                where n.ProcessID = s.ProcessID 
                and s.ApplicationVersionID <> 1
                and s.TCode = $sap_screen
                and (s.InterfaceLibraryID = 1 or s.InterfaceLibraryID = 9)
                WITH collect(n) AS filtered_nodes
                CALL db.index.vector.queryNodes($index_name, $k, $vector)
                YIELD node, score
                WHERE node IN filtered_nodes

                RETURN node.ProcessID AS ProcessID,
                    node.Step AS Step,
                    score AS similarity
                ORDER BY similarity DESC;
                """, {
                "sap_screen": sap_screen,
                "index_name": "Process_Details_Index",
                "k": 100,
                "vector": embedding_vector,
                "appname":"1"
            })


            records = [record for record in result]  # Fetch all records before using them

        if records:
            #logger.info(f"Matching Process found for : {records[0]}")
            return records[0]
        else:                
            #logger.info(f"No Matching Process found for : {description}")
            return None
    except Exception as e:
        logger.error(f"Error in Similarity Search: {str(e)}")
        raise





    