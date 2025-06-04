import numpy as np
import hdbscan
from umap import UMAP
import matplotlib.pyplot as plt
from collections import defaultdict
from sklearn.preprocessing import normalize
from neo4j import GraphDatabase
from datetime import datetime
from dotenv import load_dotenv
import logging
import os

# setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
url = os.getenv("NEO4J_URI") 
username = "neo4j"
password = os.getenv("NEO4J_PASSWORD") 
        
try:
        driver = GraphDatabase.driver(url, auth=(username, password))
        with driver.session() as session:
            session.run("RETURN 1")
        logger.info("Successfully connected to Neo4j")
except Exception as e:
        logger.error(f"Failed to initialize Neo4j connection: {str(e)}")
        raise

# === 1. Load your nodes data ===
def fetch_nodes(tx):
    query = """
    MATCH (n)
    WHERE n.description_embeddings IS NOT NULL
    RETURN n.id AS id, n.Description AS description, n.description_embeddings AS embedding
    """
    return list(tx.run(query))

with driver.session() as session:
    records = session.execute_read(fetch_nodes)

# === Format Results ===
nodes = []
for record in records:
    nodes.append({
        "id": record["id"],
        "Description": record["description"],
        "description_embeddings": record["embedding"]
    })

print(f"Fetched {len(nodes)} nodes with embeddings.")

# === 2. Extract embeddings and descriptions ===
embeddings = np.array([node["description_embeddings"] for node in nodes])
descriptions = [node["Description"] for node in nodes]
node_ids = [node["id"] for node in nodes]

# === 3. Normalize the embeddings (recommended) ===
embeddings = normalize(embeddings)

# === 4. Run HDBSCAN clustering ===
clusterer = hdbscan.HDBSCAN(min_cluster_size=2, metric='euclidean')
labels = clusterer.fit_predict(embeddings)

# === 5. Attach labels back to nodes ===
for node, label in zip(nodes, labels):
    node["cluster_id"] = int(label)

# === 6. Group and print clusters ===
cluster_map = defaultdict(list)
for desc, label in zip(descriptions, labels):
    cluster_map[label].append(desc)

print("\n=== Clusters ===")
for cluster_id, descs in cluster_map.items():
    print(f"\nCluster {cluster_id}:")
    for desc in descs:
        print(f" - {desc[:80]}...")  # Truncated for readability

# === 7. (Optional) Visualize with UMAP ===
reducer = UMAP(n_neighbors=10, min_dist=0.1, random_state=42)
embedding_2d = reducer.fit_transform(embeddings)

plt.figure(figsize=(10, 6))
scatter = plt.scatter(embedding_2d[:, 0], embedding_2d[:, 1], c=labels, cmap='Spectral', s=60)
plt.title("HDBSCAN Clustering of Descriptions", fontsize=14)
plt.xlabel("UMAP 1")
plt.ylabel("UMAP 2")
plt.colorbar(scatter, label="Cluster ID")
plt.grid(True)
plt.show()
