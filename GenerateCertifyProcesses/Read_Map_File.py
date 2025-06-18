""" - Reads Map file, give it to LLM to identify Object Class and Parent for each row. Process line one by one
- Getting ObjectID for each row. If ObjectID is not found then create object:
    - Get MainWindow Details: CLASS=GuiMainWindow!~SAPNAME=SAPMV45A:0101
    - Get Object ID of Main Window:
        select * from Object where PhysicalName = 'SAPMV45A:0101' and ApplicationVersionid = 34 
        ObjectID = 4889286. This is your ParentID
    - If ObjectID is not found then create it: 
        You need MapSourceID = 6 (Inline Capture), ApplicationVersionID = 34, ComponentID = 163 (Window)
        Parent = NULL, PhysicalName = <Get it from Map> for e.g. 'SAPMV45A:0101'
    - For Order Type, sample query as below:
    select * from Object where PhysicalName = 'GuiCTextField.VBAK-AUART' and ApplicationVersionid = 34 and ParentID = 4889286. You got the ObjectID = 4919510
 
For Creating we need:
- For TestStep: we need ProcessID, ComponentActionID, ApplicationVersionID (34), ObjectID, InterfaceLibraryID 
INSERT INTO [dbo].[Process] ([Name], [ProcessFolderID], [ResultLogStatusID], [CreatedDt], [CreatedBy], [ModifiedDt], [ModifiedBy])
VALUES ('Anu Test', 404101, 10, '2025-02-21 00:00:00', 11000370, '2025-02-21 00:00:00', 11000370)
--86442

INSERT INTO TestStep (
    [ProcessID] , [ComponentActionID] ,[ApplicationVersionID] ,[Narrative] ,[InterfaceLibraryID]
    ,[ObjectID],[CertifySequence],[Skip],[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy]) 
VALUES (
	(SELECT ProcessID FROM Process WHERE Name = 'NextGen_Create_Sales_Order'),
	1490, 34, 'Input T[Order Type] into the Order Type field.', 9, 4919510, 0, 0,'2025-02-21 00:00:00', 11000213, '2025-02-21 00:00:00', 11000370
);

INSERT INTO [dbo].[TestStepAction]
([TestStepID], [CertifySequence],[ComponentActionParmsID],[CertifyValue],[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy])
VALUES (501768, 0, 4093, 'Certify Value Test', '2025-02-24 13:09:39', 11000370, '2025-02-24 13:09:39', 11000370)

For Object: We need ParentID, Name, PhysicalName, ApplicationVersionID, ComponentID, MapSourceID(6)

INSERT INTO [dbo].[Object] ([Name],[PhysicalName],[ApplicationVersionID],[ComponentID]
  ,[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy],[MapSourceID])
VALUES ('Create Sales Document', 'SAPMV45A:0101', 34, 163, '2025-02-21 00:00:00', 11000370, '2025-02-21 00:00:00', 11000370, 6) 
 """

#Extract the Object class and Parent from the map file
import re
import pandas as pd
import pymssql 
import os 
import openai
from dotenv import load_dotenv
import logging
from datetime import datetime

#Load env
load_dotenv()

#Setup Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Parse row in Map File
def parse_line(line):
    """Extract Object Class and Parent from a given line."""
    #match = re.search(r'!~CLASS=(.*?)!~.*?PARENT~TYPE=.*?~CLASS=(.*?)!~', line)
    match = re.search(r'!~CLASS=(.*?)!~PARENT~TYPE=.*?~CLASS=(.*?)!~', line)
    if match:
        #print("Object Class => ", match.group(1), "; Parent Class => ", match.group(2))
        return match.group(1), match.group(2)
    return None, None

# Function to read Map File
def read_map_file(file_path):
    """Reads the map file line by line and extracts Object Class, Parent, and the field name from the line, displaying as a tabular format using pandas."""
    data = []
    
    # Read the map file line by line for Object Class and Parent
    with open(os.path.join(os.path.dirname(__file__), file_path), 'r', encoding='utf-8') as file:
        sr_no = 1
        for line in file:
            line = line.strip()
            if not line:
                continue
            
            # Split the line by tabs
            columns = line.split('\t')
            if len(columns) >= 3:
                # Extract the field name from the third column
                match = re.search(r'\)\s*(.+)', columns[2])
                if match:
                    field_name = match.group(1)  # Get the desired field name

                    # Extract Object Class and Parent using the existing parse_line function
                    obj_class, parent = parse_line(line)
                    if obj_class and parent:
                        if obj_class.startswith("GuiTextField!") or obj_class.startswith("GuiLabel"):
                            continue
                        else:
                            # Replace SAPNAME in the object class before adding to data
                            obj_class = obj_class.replace("!~SAPNAME=", ".")
                            data.append([sr_no, obj_class, parent, field_name])
                            sr_no += 1
    
    df = pd.DataFrame(data, columns=["Sr No", "Object_Class", "Parent", "Field_Name"])  # Updated column name
    return df

def process_map_files(sap_screen, map_files_dir=None):
    """
    Process map files in the specified directory that match the SAP screen and return a dictionary of lists.
    
    Args:
        sap_screen (str): The SAP screen to search for in map files
        map_files_dir (str, optional): Path to directory containing map files. 
                                     If None, uses default 'map_files' directory.
    
    Returns:
        dict: Dictionary with map filenames as keys and their corresponding lists as values
    """
    if map_files_dir is None:
        map_files_dir = os.path.join(os.path.dirname(__file__), "map_files")
    
    os.makedirs(map_files_dir, exist_ok=True)
    
    # Get all map files from the directory that contain the SAP screen
    map_files = [f for f in os.listdir(map_files_dir) if f.endswith('.map') and sap_screen in f]
    
    if not map_files:
        print(f"No .map files found for SAP screen {sap_screen} in {map_files_dir}")
        return {}
    
    # Dictionary to store lists
    data_lists = {}
    
    # Process each map file
    for map_file in map_files:
        input_file_path = os.path.join(map_files_dir, map_file)
        
        try:
            # Read Map File into list
            data = []
            with open(input_file_path, 'r', encoding='utf-8') as file:
                sr_no = 1
                for line in file:
                    line = line.strip()
                    if not line:
                        continue
                    
                    # Split the line by tabs
                    columns = line.split('\t')
                    if len(columns) >= 3:
                        # Extract the field name from the third column
                        match = re.search(r'\)\s*(.+)', columns[2])
                        if match:
                            field_name = match.group(1)  # Get the desired field name

                            # Extract Object Class and Parent using the existing parse_line function
                            obj_class, parent = parse_line(line)
                            if obj_class and parent:
                                if obj_class.startswith("GuiTextField!") or obj_class.startswith("GuiLabel"):
                                    continue
                                else:
                                    # Replace SAPNAME in the object class before adding to data
                                    obj_class = obj_class.replace("!~SAPNAME=", ".")
                                    data.append([sr_no, obj_class, parent, field_name])
                                    sr_no += 1
            
            data_lists[map_file] = data
            
        except FileNotFoundError:
            print(f"Error: The file {input_file_path} does not exist.")
            continue
        except Exception as e:
            print(f"Error processing {map_file}: {str(e)}")
            continue
    
    return data_lists

def save_data_to_csv(data_lists, output_dir=None):
    """
    Save all data lists to CSV files.
    
    Args:
        data_lists (dict): Dictionary of data lists to save
        output_dir (str, optional): Directory to save CSV files. If None, uses script directory.
    """
    if output_dir is None:
        output_dir = os.path.dirname(__file__)
    
    os.makedirs(output_dir, exist_ok=True)
    
    for map_file, data in data_lists.items():
        output_csv_path = os.path.join(output_dir, f"{os.path.splitext(map_file)[0]}.csv")
        df = pd.DataFrame(data, columns=["Sr No", "Object_Class", "Parent", "Field_Name"])
        df.to_csv(output_csv_path, index=False, mode='w')
        print(f"CSV file created at: {output_csv_path}")

# Main Function
def main():
    # Process all map files and get data lists
    data_lists = process_map_files(sap_screen)
    
    if data_lists:
        print(f"Found {len(data_lists)} map files for SAP screen {sap_screen}")
        print("Map file details:", data_lists)
        # Save data to CSV files
        save_data_to_csv(data_lists)
    else:
        print(f"No mapping files found for SAP screen {sap_screen}")

if __name__ == "__main__":
    main()
