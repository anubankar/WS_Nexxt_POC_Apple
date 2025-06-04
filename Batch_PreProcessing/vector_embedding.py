from neo4j import GraphDatabase
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings
import os
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

#Create the vectorstore for our existing graph
paper_graph = Neo4jVector.from_existing_graph(
    embedding=OpenAIEmbeddings(),
    url= os.getenv("NEO4J_URI"),
    username= os.getenv("NEO4J_USERNAME"),
    password= os.getenv("NEO4J_PASSWORD"),
    index_name="description",
    node_label="Test_cases",
    text_node_properties=["Description"],
    embedding_node_property="description_embeddings",
)
