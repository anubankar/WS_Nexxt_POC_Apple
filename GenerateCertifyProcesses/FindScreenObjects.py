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

def fetch_screen_object_mapping(sap_screen):
    # Initialize Neo4j driver
    url = os.getenv('NEO4J_URI')
    username = "neo4j"
    password = os.getenv('NEO4J_PASSWORD')

    try:
        driver = GraphDatabase.driver(url, auth=(username, password))
        with driver.session() as session:
            query = f"MATCH (n:SAP_Transactions) WHERE n.TCode='{sap_screen}' RETURN n.ScreenObjectMapping"
            result = session.run(query)
            mapping = result.single()
            return mapping[0]
    except Exception as e:
        logger.error(f"Failed to initialize Neo4j connection: {str(e)}")
        return None
