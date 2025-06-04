# this is not working for aura
from dotenv import load_dotenv
import os
import neo4j
import pymssql
import pandas as pd
import re
from datetime import datetime
from neo4j import GraphDatabase

# Define a mapping of keywords to SAP TCodes
tcode_mapping = {
    "Create Sales Order": "VA01",
    "Display Sales Orders": "VA03",
    "Create Billing Documents": "VF01",
    "Post Goods Issue": "VL02N",
    "Accounting Overview": "FAGLB03",
    "Display General Ledger View": "FBL3N",
    "Manage G/L Account Master Data": "FS00",
    "Post General Journal Entries": "FB50",
    "Manage Cost Centers": "KS01",
    "Pricing": "VK11",
    "/NVL01N": "VL01N",
    "/nVL01n":"VL01N",
    "/nVl01n":"VL01N"
}

# Excluded non‑standard TCodes
excluded_tcodes = {"AS400","D365","AUTH0","MS365","PHIL2","SET1",
                   "STEP1","STEP2","STEP3","TC200","TC300","TC400","HRMS"}

# -----------------------------------------------------------------------------
# 1) Copy all SQL Server tables into Neo4j as nodes
        # 'Application',
        # 'ApplicationVersion',
        # 'Component',
        # 'ComponentAction',
        # 'ComponentActionParms',
        # 'InterfaceLibrary',
        # 'Object',
        # 'Process',
# -----------------------------------------------------------------------------
def cp_from_sqlserver_to_neo4j(sql_server_cursor, neo4j_session, url, username, password):
    tables = [
        'Application',
        'ApplicationVersion',
        'Component',
        'ComponentAction',
        'ComponentActionParms',
        'InterfaceLibrary',
        'Object',
        'Process',
        # 'TestStep',   
        # 'TestStepAction'
    ]

    # (Optional) clear out all existing nodes for these labels
    for tbl in tables:
        try:        
            # Run the query
            label = 'Steps' if tbl == 'TestStep' else tbl
            print(f"{tbl} => Delete existing data...")
            query = f"MATCH (n:{label}) DETACH DELETE n"
            neo4j_session.run(query)
        
        except neo4j.exceptions.SessionExpired as e:
            print("Session expired, attempting to reconnect...")
            # Attempt to reconnect and rerun the query
            neo4j_session = neo4j.GraphDatabase.driver(url, auth=(username, password)).session()
            neo4j_session.run(query)
        
        except Exception as e:
            print(f"An error occurred while deleting {tbl}: {e}")
    
    print("Finished Deleting...")

    for table in tables:
        print(f"{table} => Process...")

        # fetch all rows
        select_sql = f"SELECT * FROM {table}"
        sql_server_cursor.execute(select_sql)
        rows = sql_server_cursor.fetchall()
        if not rows:
            continue

        # convert each row to a dict
        records = [dict(r) for r in rows]

        #determine label 
        label = 'Steps' if table == 'TestStep' else table

        # bulk‐insert into Neo4j via UNWIND
        bulk_insert_to_neo4j(label, records, neo4j_session, url, username, password)

# Bulk insert
def bulk_insert_to_neo4j(label, records, neo4j_session, url, username, password):
    try:
        print(f"{label} => bulk-insert into Neo4j via UNWIND")
        query = f"""
        UNWIND $records AS rec
        CREATE (n:{label})
        SET n = rec
        """
        neo4j_session.run(query, records=records)
    
    except neo4j.exceptions.SessionExpired as e:
        print("Session expired, attempting to reconnect...")
        # Attempt to reconnect and create a new session
        neo4j_session = neo4j.GraphDatabase.driver(url, auth=(username, password)).session()
        try:
            neo4j_session.run(query, records=records)  # Rerun the query with records
        except Exception as e:
            print(f"An error occurred during reconnection: {e}")
    
    except Exception as e:
        print(f"An error occurred during bulk insert for {label}: {e}")

# Create Relationship
def create_relationship(neo4j_session, url, username, password):
    try:
        query = """
        MATCH (p:Process), (ts:TestStep)
        WHERE p.ProcessID = ts.ProcessID
        CREATE (p)-[:PROCESS_STEPS]->(ts)
        """
        neo4j_session.run(query)
    except neo4j.exceptions.SessionExpired as e:
        print("Session expired, attempting to reconnect...")
        # Attempt to reconnect and rerun the query
        neo4j_session = neo4j.GraphDatabase.driver(url, auth=(username, password)).session()
        neo4j_session.run(query)        
    except Exception as e:
        print(f"An error occurred: {e}")  

#------------------------------------------------------------------------------
# Extract TCodes
#------------------------------------------------------------------------------
def find_tcode_subprocess(sql_server_cursor, sql_server_conn):
    sql = f"""select t1.TestStepID, t1.ProcessID,
t1.ComponentActionID,
t1.ApplicationVersionID,
t1.Narrative,
t1.InterfaceLibraryID,
t1.ObjectID,
t1.CertifySequence,
t1.Skip,
t1.CreatedDt,
t1.CreatedBy,
t1.ModifiedDt,
t1.ModifiedBy,
cast(t2.ExecProcessID as int) as ExecProcessID,
t2.CertifyValue as ExecProcessName
from TestStep as t1 LEFT JOIN TestStepAction as t2
ON t1.TestStepID = t2.TestStepID and t2.ExecProcessID is not null
Order by t1.ProcessID, CAST(t1.CertifySequence AS INTEGER)"""
    sql_server_cursor.execute(sql)
    rows = sql_server_cursor.fetchall()

    # Get column names from cursor description
    columns = [column[0] for column in sql_server_cursor.description]

    # Create DataFrame
    df = pd.DataFrame(rows, columns=columns)

    # If no data, return early
    if df.empty:
        print("No data found in the query results")
        return

    # Prepare a list to collect necessary fields
    results = []
    last_found_tcode = ''
    last_process_id = None

    # Process DataFrame
    for index, row in df.iterrows():
        test_step_id = row['TestStepID']
        process_id = row['ProcessID']
        component_action_id = row['ComponentActionID']
        narrative = str(row['Narrative'])
        subprocess = row['ExecProcessName'] if row['ExecProcessName'] else ""
        
        # Reset TCode when moving to a new ProcessID
        if last_process_id is not None and process_id != last_process_id:
            last_found_tcode = ''

        # Determine SubProcess from narrative
        if component_action_id == 8 and (narrative.startswith('Execute') or narrative.startswith('Exec')):
            if 'SAP GUI Logoff' not in narrative:
                subprocess = narrative.replace('Execute', '').replace('Exec', '').replace('Process', '').strip().strip('.')
                subprocess = re.sub(r'at First Step use None.*', '', subprocess).strip()
        
        # Extract TCode from predefined mapping
        mapped_tcode = extract_tcode(narrative)
        
        # Extract TCode from narrative if not found in mapping
        found_tcodes = []
        if component_action_id in [1586, 8]:
            words = re.split(r'[_\s\\"/n\\/n\\/o\\/O]', narrative)
            found_tcodes = [word.upper() for word in words if is_valid_tcode(word)]
        
        # Prioritize mapped TCode, otherwise use extracted TCode (excluding non-standard ones)
        last_found_tcode = (
            mapped_tcode if mapped_tcode 
            else (found_tcodes[0] if found_tcodes else last_found_tcode)
        )
        
        # Handle potential NaN values in ExecProcessID before converting to int
        exec_process_id = row['ExecProcessID']
        if pd.isna(exec_process_id):
            exec_process_id = None
        else:
            exec_process_id = int(exec_process_id)

        results.append({
            'TestStepID': test_step_id,
            'ProcessID': process_id,
            'Narrative': narrative,
            'ComponentActionID': component_action_id,
            'ApplicationVersionID': row['ApplicationVersionID'],
            'InterfaceLibraryID': row['InterfaceLibraryID'],
            'ObjectID': row['ObjectID'],
            'CertifySequence': row['CertifySequence'],
            'Skip': row['Skip'],
            'CreatedDt': row['CreatedDt'],
            'CreatedBy': row['CreatedBy'],
            'ModifiedDt': row['ModifiedDt'],
            'ModifiedBy': row['ModifiedBy'],
            'TCode': last_found_tcode,
            'ExecProcessID': exec_process_id, #row['ExecProcessID'],
            'SubProcess': subprocess
        })
        
        last_process_id = process_id

    # Create a DataFrame from results and remove duplicates
    result_df = pd.DataFrame(results).drop_duplicates()

    # Reorder columns
    column_order = ['TestStepID', 'ProcessID', 'Narrative', 'ComponentActionID',
                    'ApplicationVersionID', 'InterfaceLibraryID', 'ObjectID',
                    'CertifySequence', 'Skip', 'CreatedDt', 'CreatedBy',
                    'ModifiedDt', 'ModifiedBy', 'TCode', 'ExecProcessID', 'SubProcess']
    result_df = result_df[column_order]

    # # Check if 'TCode', 'ExecProcessID', and 'SubProcess' columns exist in the SQLite TestStep table
    # sqlite_cursor.execute("PRAGMA table_info(TestStep)")
    # existing_columns = [column[1] for column in sqlite_cursor.fetchall()]

    # # Add columns if they do not exist
    # if 'TCode' not in existing_columns:
    #     sqlite_cursor.execute("ALTER TABLE TestStep ADD COLUMN TCode TEXT")
    # if 'ExecProcessID' not in existing_columns:
    #     sqlite_cursor.execute("ALTER TABLE TestStep ADD COLUMN ExecProcessID INT")
    # if 'SubProcess' not in existing_columns:
    #     sqlite_cursor.execute("ALTER TABLE TestStep ADD COLUMN SubProcess TEXT")

    # # Delete existing data from the TestStep table
    # sqlite_cursor.execute("DELETE FROM TestStep")
    # sqlite_conn.commit()

    # # Write data to TestStep
    # result_df.to_sql('TestStep', sqlite_conn, if_exists='append', index=False)

    # Save the result to a timestamped CSV file
    output_file_name = f"TestStep_with_ProcessID_and_TCodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    print("File =>", output_file_name)
    result_df.to_csv(output_file_name, index=False)

# Function to determine if a word is a valid TCode
def is_valid_tcode(word):
    return (
        len(word) in [4, 5] and 
        re.search(r'[A-Za-z]', word) and 
        re.search(r'[0-9]', word) and 
        not any(char in word for char in "./,()%$:-_") and  # Ensure no special characters
        word.upper() not in excluded_tcodes  # Exclude non-standard TCodes
    )

# Function to extract TCode from narrative keywords
def extract_tcode(narrative):
    for keyword, tcode in tcode_mapping.items():
        if keyword.lower() in str(narrative).lower():
            return tcode
    return ""

# -----------------------------------------------------------------------------
# main()
# -----------------------------------------------------------------------------
def main():
    # Load env
    load_dotenv()

    # Connect SQL Server
    sql_server_conn = pymssql.connect(
      host= os.getenv("SQL_HOST"),
      port= os.getenv("SQL_PORT"),
      server= os.getenv("SQL_SERVER"),
      user= os.getenv("SQL_USER"),
      password= os.getenv("SQL_PASSWORD"),
      database= os.getenv("SQL_DATABASE"),

      # Worksoft
      #server='worksoft.database.windows.net', #Worksoft
      #user='NextGenAIreader', #Worksoft
      #password=r'P^8?"H\gBNGvj6}uU72,', # Worksoft

      as_dict=True,
      login_timeout=3
    )

    sql_server_cursor = sql_server_conn.cursor()
    # Neo4j connection details - Aura
    url = os.getenv('NEO4J_URI')
    username = os.getenv("NEO4J_USERNAME")
    password = os.getenv('NEO4J_PASSWORD')
    driver = GraphDatabase.driver(
      url,
      auth=(username, password)
    )
    with driver.session() as neo4j_sess:

        # 1) bulk copy all raw tables
        cp_from_sqlserver_to_neo4j(sql_server_cursor, neo4j_sess, url, username, password)


    #Find TCodes and Sub Process
    find_tcode_subprocess(sql_server_cursor, sql_server_conn)

    sql_server_conn.close()
    driver.close()

if __name__ == "__main__":
    main()
