import pandas as pd
import re
from datetime import datetime  
import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Print the current working directory
print("Current Working Directory:", os.getcwd())

# Define file path for the TestStep CSV file
teststep_file = "TestStep_WithChildProcess.csv"

# Check if the file exists before loading
if not os.path.isfile(teststep_file):
    raise FileNotFoundError(f"The file {teststep_file} does not exist.")

# Load CSV data
df = pd.read_csv(teststep_file)

# Filter for ApplicationVersionID 319 
df = df[(df['ApplicationVersionID'] == 319)]

# Define a mapping of keywords to SAP TCodes
tcode_mapping = {
    "Create Sales Orders PushButton": 'F0018',
    "Create Sales Order PushButton": 'F0018',
    "Create Sales Orders Link": 'F0018',
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

# Excluded non-standard TCodes
excluded_tcodes = {"AS400", "D365", "AUTH0", "MS365", "PHIL2", "SET1", 
                   "STEP1", "STEP2", "STEP3", "TC200", "TC300", "TC400", "HRMS"}

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

# Sort DataFrame by ProcessID and TestStepID
df = df.sort_values(by=['ProcessID', 'TestStepID'])

# Prepare a list to collect necessary fields
results = []
last_found_tcode = ''
last_process_id = None

# Function to extract TCode from narrative keywords
def extract_tcode(narrative):
    for keyword, tcode in tcode_mapping.items():
        if keyword.lower() in str(narrative).lower():
            return tcode
    return ""

# Sort DataFrame by ProcessID and TestStepID
df = df.sort_values(by=['ProcessID', 'CertifySequence'])

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
    
   
    # Only add to results if we found a TCode
    if last_found_tcode:
        results.append({
            'TestStepID': test_step_id,
            'TCode': last_found_tcode,
            'SubProcess': subprocess
        })
    
    last_process_id = process_id

# Connect to Neo4j
url = os.getenv('NEO4J_URI')
username = os.getenv('NEO4J_USERNAME')
password = os.getenv('NEO4J_PASSWORD')

if not all([url, username, password]):
    raise ValueError("Neo4j connection details not found in environment variables")

driver = GraphDatabase.driver(url, auth=(username, password))

try:
    with driver.session() as session:
        # Update TestStep nodes with TCode and SubProcess
        query = """
        UNWIND $updates AS update
        MATCH (ts:Steps {TestStepID: update.TestStepID})
        SET ts.TCode = update.TCode,
            ts.SubProcess = update.SubProcess
        """
        
        # Execute the update query
        session.run(query, updates=results)
        print(f"Successfully updated {len(results)} TestStep nodes in Neo4j")

except Exception as e:
    print(f"An error occurred while updating Neo4j: {e}")
finally:
    driver.close()
