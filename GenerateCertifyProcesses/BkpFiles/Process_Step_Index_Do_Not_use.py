from neo4j import GraphDatabase

# URI examples: "neo4j://localhost", "neo4j+s://xxx.databases.neo4j.io"
#URI = "neo4j+ssc://00dedc34.databases.neo4j.io"
#AUTH = ("neo4j", "Ap3oo16wSEHi960BIYSKJmzQ2ol0ieCO0qxCkifsymc")

#with GraphDatabase.driver(URI, auth=AUTH) as driver:
#    driver.verify_connectivity()


from langchain_community.vectorstores import Neo4jVector
from langchain_openai import OpenAIEmbeddings
import os
from dotenv import load_dotenv
from pprint import pprint

load_dotenv()

#Create the vectorstore for our existing graph
paper_graph = Neo4jVector.from_existing_graph(
    embedding=OpenAIEmbeddings(),
    url="neo4j+ssc://00dedc34.databases.neo4j.io",
    username="neo4j",
    password="Ap3oo16wSEHi960BIYSKJmzQ2ol0ieCO0qxCkifsymc",
    index_name="Process_Step",
    node_label="Process",
    text_node_properties=["Narrative"],
    embedding_node_property="narrative_embeddings",
)


#Create the vectorstore for our existing graph
#Create vector index for ApplicationVersionID and Narrative 
#paper_graph = Neo4jVector.from_existing_graph(
#    embedding=OpenAIEmbeddings(),
#    url="neo4j+ssc://00dedc34.databases.neo4j.io",
#    username="neo4j", 
#    password="Ap3oo16wSEHi960BIYSKJmzQ2ol0ieCO0qxCkifsymc",
#    index_name="narratives",
#    node_label="Steps",
#    text_node_properties=["Narrative"],
#    embedding_node_property="narrative_embeddings",
#)




#Create vector index for ApplicationVersionID and Narrative
paper_graph = Neo4jVector.from_existing_graph(
    embedding=OpenAIEmbeddings(),
    url="neo4j+ssc://00dedc34.databases.neo4j.io", 
    username="neo4j",
    password="Ap3oo16wSEHi960BIYSKJmzQ2ol0ieCO0qxCkifsymc",
    index_name="StepDetails",
    node_label="Steps",
    text_node_properties=["ApplicationName", "ProcessName", "Narrative"],
    embedding_node_property="narrative_version_embeddings",
)
