from neo4j import GraphDatabase
import pandas as pd
from dotenv import load_dotenv
import os
import neo4j
import pymssql

def fetch_data_from_neo4j(URI, USERNAME, PASSWORD):
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    query = """
        MATCH (t:Steps)
        WHERE t.TCode IS NOT NULL AND t.TCode <> ''
        WITH t.TCode AS TCode, t.ProcessID AS ProcessID, COLLECT(t.ObjectID) AS VariantList
        RETURN TCode, ProcessID, REDUCE(s = '', obj IN VariantList | s + obj + '~') AS Variants
        ORDER BY TCode, ProcessID;
    """
    
    with driver.session() as session:
        result = session.run(query)
        data = [dict(record) for record in result]
    
    driver.close()
    return pd.DataFrame(data)


def main():
    # Load env
    load_dotenv()

    # Neo4j connection details
    URI = os.getenv('NEO4J_URI')
    USERNAME = "neo4j"
    PASSWORD = os.getenv('NEO4J_PASSWORD')

    print("Fetching Data from Neo4j...")
    df = fetch_data_from_neo4j(URI, USERNAME, PASSWORD)
    print("Data Fetched Successfully.")

    # Step 1: Create a mapping for VariantID that resets for each TCode
    print("Prepare TCode_var Node Label...")    
    variant_ids = []
    for tcode, group in df.groupby('TCode'):
        variant_mapping = {variant: idx + 1 for idx, variant in enumerate(group['Variants'].unique())}
        for variant in group['Variants']:
            variant_ids.append(f"{tcode}_{variant_mapping[variant]}")

    df['VariantID'] = variant_ids

    df['RowID'] = range(1, 1 + len(df))

    # # Save to CSV instead of database
    # df.to_csv("All_TCode_Variants.csv", index=False)
    # print("Rows Written to All_TCode_Variants.csv =>", df.shape[0])

    # Write to Neo4j
    print("Writing to Neo4j TCode_var nodes...")
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    
    with driver.session() as session:
        # Clear existing TCode_var nodes
        session.run("MATCH (n:TCode_var) DETACH DELETE n")
        
        # Create nodes using UNWIND for bulk insert
        query = """
        UNWIND $rows AS row
        CREATE (n:TCode_var {
            TCode: row.TCode,
            ProcessID: row.ProcessID,
            Variants: row.Variants,
            VariantID: row.VariantID,
            RowID: row.RowID
        })
        """
        
        # Convert DataFrame to list of dictionaries
        rows = df.to_dict('records')
        
        # Execute the query with parameters
        session.run(query, rows=rows)
        
    driver.close()
    print("Successfully wrote TCode_var nodes to Neo4j")

    #===> STEP2: PREPARE FILE All_TCode_Unique_Variants
    print("Preparing => Unique_TCode_Var node label")
    filtered_rows = []
    for tcode, group in df.groupby('TCode'):
        keep_indices = []
        for idx, row in group.iterrows():
            is_subset_of_any = any(set(row['Variants'].split('~')).issubset(set(other_row['Variants'].split('~'))) for _, other_row in group.iterrows() if idx != _)
            if not is_subset_of_any:
                keep_indices.append(idx)
        filtered_rows.extend(keep_indices)

    filtered_df = df.loc[filtered_rows]
    filtered_df['RowID'] = range(1, 1 + len(filtered_df))

    # Write to Neo4j Unique_TCode_Var nodes
    print("Writing to Neo4j Unique_TCode_Var nodes...")
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))
    
    with driver.session() as session:
        # Clear existing Unique_TCode_Var nodes
        session.run("MATCH (n:Unique_TCode_Var) DETACH DELETE n")
        
        # Create nodes using UNWIND for bulk insert
        query = """
        UNWIND $rows AS row
        CREATE (n:Unique_TCode_Var {
            TCode: row.TCode,
            ProcessID: row.ProcessID,
            Variants: row.Variants,
            VariantID: row.VariantID,
            RowID: row.RowID
        })
        """
        
        # Convert DataFrame to list of dictionaries
        rows = filtered_df.to_dict('records')
        
        # Execute the query with parameters
        session.run(query, rows=rows)
        
    driver.close()
    print("Successfully wrote Unique_TCode_Var nodes to Neo4j")
    # filtered_df.to_csv("All_TCode_Unique_Variants.csv", index=False)
    # print("Rows Written to All_TCode_Unique_Variants.csv =>", filtered_df.shape[0])


if __name__ == "__main__":
    main()
