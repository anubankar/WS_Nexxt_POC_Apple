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
        "Create Sales Orders PushButton": 'F0018',
        "Create Sales Order": "VA01",
        "Display Sales Orders": "VA03",
        "Create Billing Documents": "VF01",
        "Create Billing Documents (Tile) PushButton": "F0798",
        "Manage G/L Account Master Data PushButton": "F0731A",
        "Display Billing Documents PushButton":"F2250",
        "Display Document Flow PushButton": "F3665",
        "Display G/L Account Line Items PushButton": "F2217",
        "Manage Cost Centers (New) PushButton": "F1443A",
        "Manage Journal Entries Link": "F0717A",
        "Manage Solution Quotations Link": "F7671",
        "Outbound Delivery Link" :"F0233A",
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

#------------------------------------------------------------------------------
# Extract TCodes
#------------------------------------------------------------------------------
def find_tcode_subprocess(sql_server_cursor,  sql_server_conn):
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
    print(f"Number of rows: {len(rows)}")

    # Get column names from the cursor description
    columns = [column[0] for column in sql_server_cursor.description] if sql_server_cursor.description else []
    # print(f"Number of columns: {len(columns)}")
    # print("Column names:")
    # for col in columns:
    #     print(f"- {col}")

    # columns = []
    # if isinstance(rows, list) and len(rows) > 0 and isinstance(rows[0], tuple):
    #     # Convert list of tuples to a list of dictionaries for easier access
    #     columns = [column[0] for column in sql_server_cursor.description]  # Get column names from the cursor
    
    df = pd.DataFrame(rows, columns=columns)

    # Append the DataFrame to the results list
    rows.append(df)

    # print("First row in DataFrame:")
    # print(df.iloc[0])
    # print("\nColumns in DataFrame:")
    # for col in df.columns:
    #     print(f"- {col}")

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
            #words = re.split(r'[_\s"/n/o/O]', narrative)  # Split words by _ and spaces
            words = re.split(r'[_\s\\"/n\\/n\\/o\\/O]', narrative)
            
            found_tcodes = [word.upper() for word in words if is_valid_tcode(word)]
        
        # Prioritize mapped TCode, otherwise use extracted TCode (excluding non-standard ones)
        last_found_tcode = (
            mapped_tcode if mapped_tcode 
            else (found_tcodes[0] if found_tcodes else last_found_tcode)
        )
        
        # Append results
        # Handle potential NaN values in ExecProcessID before converting to int
        exec_process_id = row['ExecProcessID']
        if pd.isna(exec_process_id):
            exec_process_id = None  # Set to None if it's NaN
        else:
            exec_process_id = int(exec_process_id)  # Convert to int if not NaN

        row['ExecProcessID'] = exec_process_id
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
    return result_df

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


      as_dict=True,
      login_timeout=3
    )

    # Connect Neo4j
    driver = GraphDatabase.driver(
      os.getenv("NEO4J_URI"),
      auth=(os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
    )
    sql_server_cursor = sql_server_conn.cursor()

    #Find TCodes and Sub Process
    result_df = find_tcode_subprocess(sql_server_cursor, sql_server_conn)

    # Save the result to a timestamped CSV file
    output_file_name = f"TestStep_with_ProcessID_and_TCodes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
    print("File =>", output_file_name)
    result_df.to_csv(output_file_name, index=False)

    sql_server_conn.close()

if __name__ == "__main__":
    main()
