from neo4j import GraphDatabase
from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings
import os
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

# try:
#     paper_graph = Neo4jVector.from_existing_graph(
#         embedding=OpenAIEmbeddings(),  # Embedding model
#         url=os.getenv('NEO4J_URI'),    # Neo4j database URI
#         username="neo4j",               # Username
#         password=os.getenv('NEO4J_PASSWORD'),  # Password
#         index_name="Process_Step",      # Unique index name
#         node_label="Process",            # Node label
#         text_node_properties=["Step"],   # Properties containing text
#         embedding_node_property="Step_embeddings"  # Property for storing embeddings
#     )

#     print("Vector store created successfully.")
# except Exception as e:
#     print(f"Error creating vector store: {e}")

# Create Process Details Index
try:
    paper_graph = Neo4jVector.from_existing_graph(
        embedding=OpenAIEmbeddings(),  # Embedding model
        url=os.getenv('NEO4J_URI'),    # Neo4j database URI
        username="neo4j",               # Username
        password=os.getenv('NEO4J_PASSWORD'),  # Password
        index_name="Process_Details_Index",      # Unique index name
        node_label="Process",            # Node label
        text_node_properties=["Process_Details"],   # Properties containing text
        embedding_node_property="Process_Details_Embeddings"  # Property for storing embeddings
    )
    print("Vector store created successfully.")
except Exception as e:
    print(f"Error creating vector store: {e}")    

# Create Index on Unique_TCode_Var
try:
    paper_graph = Neo4jVector.from_existing_graph(
        embedding=OpenAIEmbeddings(),  # Embedding model
        url=os.getenv('NEO4J_URI'),    # Neo4j database URI
        username="neo4j",               # Username
        password=os.getenv('NEO4J_PASSWORD'),  # Password
        index_name="TCode_Variant_Tcode_Steps_Index",      # Unique index name
        node_label="Unique_TCode_Var",            # Node label
        text_node_properties=["Tcode_Steps"],   # Properties containing text
        embedding_node_property="Tcode_Steps_Embeddings"  # Property for storing embeddings
    )

    print("Vector store created successfully.")
except Exception as e:
    print(f"Error creating vector store: {e}")    
