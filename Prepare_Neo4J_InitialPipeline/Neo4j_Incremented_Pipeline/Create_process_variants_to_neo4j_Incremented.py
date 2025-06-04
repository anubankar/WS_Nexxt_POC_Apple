from neo4j import GraphDatabase
import pandas as pd
from dotenv import load_dotenv
import os
import neo4j
from Upload_Base_Table_Incremented import get_last_data_pulled_date

def main():
    # Load env
    load_dotenv()

    # Connect to the Neo4j database
    URI = os.getenv('NEO4J_URI')
    USERNAME = "neo4j"
    PASSWORD = os.getenv('NEO4J_PASSWORD')
    driver = GraphDatabase.driver(URI, auth=(USERNAME, PASSWORD))

    def query_neo4j(query):
        with driver.session() as session:
            result = session.run(query)
            return [record.data() for record in result]

    # Get the last data pulled date
    with driver.session() as session:
        last_date = get_last_data_pulled_date(session)
        print(f"Last Data Pulled Date = {last_date}")

    ### STEP 1: Prepare Table All_Process_TCode_Variants
    print("Preparing Table => Process_TCode_Variants_All")

    # Neo4j query to extract the required data with date filter
    query = """
    MATCH (p:Steps),(q:TCode_var)
    WHERE q.VariantID IS NOT NULL 
    AND p.ProcessID=q.ProcessID
    AND p.ModifiedDt >= $last_date
    RETURN p.ProcessID as ProcessID, COLLECT(DISTINCT q.VariantID) AS TCode_Variants
    """
    data = query_neo4j(query)

    # Convert the result to a pandas DataFrame
    df = pd.DataFrame(data)

    # If no new data, exit early
    if df.empty:
        print("No new data found since last pull date")
        driver.close()
        return

    #here changes are done
    # Convert TCode_Variants to a string representation if it's a list
    df['TCode_Variants'] = df['TCode_Variants'].apply(lambda x: ','.join(x) if isinstance(x, list) else x)

    # Step 1: Create a mapping of unique TCode_Variants combinations to unique TCode_Variant_ID
    tcode_variants_mapping = {tcode_variants: idx + 1 for idx, tcode_variants in enumerate(df['TCode_Variants'].unique())}

    # Step 2: Assign the TCode_Variant_ID to each row based on the mapping
    df['TCode_Variant_ID'] = df['TCode_Variants'].map(tcode_variants_mapping)

    # Step 3: Add an auto-increment RowID to each row
    df['RowID'] = range(1, len(df) + 1)

    # Write to Neo4j Process_TCode_Variants_All nodes
    print("Writing to Neo4j Process_TCode_Variants_All nodes...")
    
    with driver.session() as session:
        # Clear existing Process_TCode_Variants_All nodes
        session.run("MATCH (n:Process_TCode_Variants_All) DETACH DELETE n")
        
        # Create nodes using UNWIND for bulk insert
        query = """
        UNWIND $rows AS row
        MERGE (n:Process_TCode_Variants_All {
            ProcessID: row.ProcessID,
            TCode_Variants: row.TCode_Variants,
            TCode_Variant_ID: row.TCode_Variant_ID,
            RowID: row.RowID
        })
        """
        
        # Convert DataFrame to list of dictionaries
        rows = df.to_dict('records')
        
        # Execute the query with parameters
        session.run(query, rows=rows)
        
    print("Successfully wrote Process_TCode_Variants_All nodes to Neo4j")

    # # Save to CSV
    # df.to_csv('All_Process_TCode_Variants.csv', index=False)
    # print("Rows Written to All_Process_TCode_Variants CSV => ", df.shape[0])

    ### STEP 2: Prepare Table All_Process_Unique_TCode_Variants
    print("Preparing Node Label Process_Unique_TCode_Variants")

    # Filter out rows that are subsets of any other row's TCode_Variants
    filtered_df = pd.DataFrame(columns=df.columns)

    for idx, row in df.iterrows():
        is_subset = False
        for _, other_row in df.iterrows():
            if row['TCode_Variants'] != other_row['TCode_Variants'] and set(row['TCode_Variants'].split(',')).issubset(set(other_row['TCode_Variants'].split(','))):
                is_subset = True
                break
        if not is_subset:
            filtered_df = pd.concat([filtered_df, pd.DataFrame(row).T], ignore_index=True)

    filtered_df['RowID'] = range(1, 1 + len(filtered_df))

    # Write to Neo4j Process_Unique_TCode_Variants nodes
    print("Writing to Neo4j Process_Unique_TCode_Variants nodes...")
    
    with driver.session() as session:
        # Clear existing Process_Unique_TCode_Variants nodes
        session.run("MATCH (n:Process_Unique_TCode_Variants) DETACH DELETE n")
        
        # Create nodes using UNWIND for bulk insert
        query = """
        UNWIND $rows AS row
        MERGE (n:Process_Unique_TCode_Variants {
            ProcessID: row.ProcessID,
            TCode_Variants: row.TCode_Variants,
            TCode_Variant_ID: row.TCode_Variant_ID,
            RowID: row.RowID
        })
        """
        
        # Convert DataFrame to list of dictionaries
        rows = filtered_df.to_dict('records')
        
        # Execute the query with parameters
        session.run(query, rows=rows)
        
    print("Successfully wrote Process_Unique_TCode_Variants nodes to Neo4j")

    # # Save to CSV
    # filtered_df.to_csv('All_Process_Unique_TCode_Variants.csv', index=False)
    # print("Rows Written to All_Process_Unique_TCode_Variants CSV => ", filtered_df.shape[0])

    # Close the Neo4j connection
    driver.close()

if __name__ == "__main__":
    main()
