import os
import pandas as pd
from docx import Document
from neo4j import GraphDatabase
from datetime import datetime
from dotenv import load_dotenv
import logging
from FindReferenceProcess import findProcessFromGraph1

# setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#inserting data to neo4j 
def create_test_case_node(file_name, table_name, tcode, description , created_on):
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

    with driver.session() as session:
        session.run(
            "MERGE (n:Test_cases {File_Name: $file_name, Table_Name: $table_name, Transaction: $tcode}) "
            "SET n.Description = $description, n.Created_on = $created_on",
            file_name=file_name,
            table_name=table_name,
            tcode=tcode,
            description=str (description),
            created_on=created_on
        )

def extract_table_data(doc):
    """
    Extract data from all tables in the document.
    
    Args:
        doc: Document object from python-docx
        
    Returns:
        List of tables, where each table is a list of rows
    """

    tables_data = []
    for table in doc.tables:
        # Check if table has the expected column headers
        if len(table.rows) > 0:
            headers = [cell.text.strip() for cell in table.rows[0].cells]
            expected_headers = ['Test Step #', 'Test Step Name', 'Instruction', 'Expected Result', 'Pass/Fail/Comments']
            
            # if it is signavio document 
            if all(header in headers for header in expected_headers):
                table_data = []
                for row in table.rows:
                    row_data = []
                    for cell in row.cells:
                        row_data.append(cell.text.strip())
                    table_data.append(row_data)
                tables_data.append(table_data)

            else:
                print("other Document")
                #logic for other than signavio document 

    return tables_data

def excel_preprocessing(file_path):
    # Placeholder for Excel preprocessing logic
    df = pd.read_excel(os.path.join(os.path.dirname(__file__), file_path))

    df_final = pd.DataFrame(columns=["SAP Screen", "Description", "Process ID", "Steps"])

    # Iterate through each row in the DataFrame
    for index, row in df.iterrows():
        # Extract the description for each step
        description = row["Description"]  # Ensure the column name matches your Excel sheet
        tcode = row["SAP Screen"]
        print(tcode, description)    
        table_name = ""
        created_on = datetime.now()
        #print (tcode, description)
        create_test_case_node(os.path.basename(file_path), table_name, tcode, description, created_on)


def doc_preprocessing(file_path):
    # Placeholder for DOCX preprocessing logic
    doc = Document(file_path)
    tables = extract_table_data(doc)
    for i, table in enumerate(tables, 1):
        print(f"\nTable {i}:")

        # Convert table rows to text format
        table_text = []
        instruction_text = []  # New list to store only instructions
        for row in table:
            print(" | ".join(row))
            table_text.append(" | ".join(row))  # Keep full table text
            if len(row) > 2:  # Ensure row has enough columns
                instruction_text.append(row[2])  # Store only instruction column
        
        #Extract TCode from the table text
        for line in table_text:
            if "Access the App" in line:
                start = line.find("(")
                end = line.find(")")
                if start != -1 and end != -1 and start < end:
                    tcode = line[start + 1:end].strip()
                    
        description = instruction_text  # Use only instruction column for description
        table_name= f"Table {i}"
        created_on = datetime.now()
        #print (tcode, description)
        create_test_case_node(os.path.basename(file_path), table_name, tcode, description, created_on)

    print(f"Processing DOCX file: {file_path}")

def create_excel_from_query():
    load_dotenv()
    url = os.getenv("NEO4J_URI") 
    username = "neo4j"
    password = os.getenv("NEO4J_PASSWORD") 
    
    try:
        driver = GraphDatabase.driver(url, auth=(username, password))
        with driver.session() as session:
            # Execute the query to get test cases
            result = session.run("""
                MATCH (r:Test_cases)
                WITH r.Description AS descList, COLLECT(r) AS records
                WHERE SIZE(records) = 1
                RETURN 
                    descList AS Description, 
                    records[0].Transaction AS TCode
            """)
            
            # Convert results to a list of dictionaries and find reference processes
            data = []
            for i, record in enumerate(result):
                # Find reference process using findProcessFromGraph1
                reference_process = findProcessFromGraph1(
                    sap_screen=record["TCode"],
                    description=record["Description"],
                    logger1=logger
                )
                
                data.append({
                    "Step Name": f"Step {i+1}",
                    "SAP Screen": record["TCode"],
                    "Description": record["Description"],
                    "Reference Process ID": reference_process["ProcessID"] if reference_process else "",
                    "Similarity Score": reference_process["similarity"] if reference_process else "",
                    "Expected Result": ""  # Leave blank
                })

            # Create DataFrame
            df = pd.DataFrame(data)
            
            # Create output directory if it doesn't exist
            output_dir = 'output'
            if not os.path.exists(output_dir):
                os.makedirs(output_dir)
            
            # Generate filename with timestamp
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            output_file = os.path.join(output_dir, f'test_cases_{timestamp}.xlsx')
            
            # Save to Excel
            df.to_excel(output_file, index=False)
            logger.info(f"Excel file created successfully at: {output_file}")
            
    except Exception as e:
        logger.error(f"Error creating Excel file: {str(e)}")
        raise
    finally:
        if 'driver' in locals():
            driver.close()

def main():
    batch_folder = 'Batch_Files'  # Adjust the path as necessary

    
    # # Walk through all subdirectories and files in the Batchfiles folder
    # for root, dirs, files in os.walk(batch_folder):
    #     for filename in files:
    #         file_path = os.path.join(root, filename)
            
    #         if filename.endswith(('.xlsx', '.xls')):
    #             excel_preprocessing(file_path)
    #         elif filename.endswith('.docx'):
    #             doc_preprocessing(file_path)
    
    # # Create Excel file from Neo4j query
    create_excel_from_query()

if __name__ == "__main__":
    main()
