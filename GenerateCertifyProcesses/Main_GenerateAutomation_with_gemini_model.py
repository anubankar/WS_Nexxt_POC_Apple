# TRY: Provide SAP Screen names and Objects as Inputs
# Process_Test_Case.py -> Read excel test case. Later on it can have additional functions to read different test case format. Create JSON
import pandas as pd
import openai
from openai import OpenAI
import json
import re
from dotenv import load_dotenv
import os, sys
from Process_JSON import process_json_file
import logging
from Db_Connections import connect_to_database
from datetime import datetime
from RecordStatistics import create_statistics_file
from FindReferenceProcess import findProcessFromGraph1
from CreateMainProcess import create_main_process
from neo4j import GraphDatabase
import sqlite3
from Read_Map_File import process_map_files
#from FindScreenObjects import fetch_screen_object_mapping

# Load env
load_dotenv()
os.getenv('OPENAI_API_KEY')

# Set up logging
global logger;
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define List
ProcessList = pd.DataFrame(columns=["Step_Name", "SAP_Screen" ,"ProcessID", "similarity_score"])

#Openrouter Setup
client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY")
)

# Add to Process List
def add_entry_to_processlist(step_name, sap_screen, process_id, similarity_score):
    global ProcessList
    new_entry = pd.DataFrame([[step_name, sap_screen, process_id, similarity_score]], columns=["Step_Name", "SAP_Screen" ,"ProcessID", "similarity_score"])
    ProcessList = pd.concat([ProcessList, new_entry], ignore_index=True)
    logger.info(f"Added entry to ProcessList: Step Name: {step_name}, SAP_Screen: {sap_screen}, ProcessID: {process_id}")

# Define Prompt Details
def define_prompt():
    base_prompt = """
            You are expert in generating Worksoft Certify test automation. You can convert descriptions of manual tests or operation into certify test automation in the form of structured JSON output as below :
            The automation is created screen by screen, for each screen, the steps are specified as step sequence("Step"), Object Name ("Object), Action and Action Description. 
            Please ensure that object must exist on the screen. For reference list of objects per screen is also provided. 
            Please create appropriate step for navigation when you transition from one screen to another screen by pressing enter or clicking appropriate tab.
            Only provide json and nothing else. reference JSON Format:

            [ 
                {
                    "name": "Sales Document Creation",
                    "Application": "S4 Hana Sales and Distribution",
                
                            "steps": [
                                {
                                    "Step": 1,
                                    "Object": "GuiOkCodeField.wnd[0]/tbar[0]/okcd",
                                    "ObjectName": "okcd",
                                    "Action": "Enter transaction code",
                                    "ActionDescription": "Enter the transaction code 'VA01' in the OK code field",
                        "Screen": "SAP Main",
                                "Screen Name": "SAP Main"
                                }
                ,        
                    
                                {
                                    "Step": 2,
                                    "Object": "GuiCTextField.VBAK-AUART",
                                    "ObjectName": "Order Type",
                                    "Action": "Enter content into an EditBox",
                                    "ActionDescription": "Enter the order type",
                                "Screen": "SAPMV45A:0101",
                                "Screen Name": "Create Sales Order"
                                },
                                {
                                    "Step": 3,
                                    "Object": "GuiButton.btn[0]",
                                    "ObjectName": "Press Enter",
                                    "Action": "Press Button",
                                    "ActionDescription": "Press Enter to proceed",
                                "Screen": "SAPMV45A:0101",
                                "Screen Name": "Create Sales Order"
                    
                        },    

                                {
                                    "Step": 4,
                                    "Object": "GuiCTextField.KUAGV-KUNNR",
                                    "ObjectName": "Sold to party",
                                    "Action": "Enter text",
                                    "ActionDescription": "Enter the sold to party",
                                "Screen": "SAPMV45A:4701",
                                "Screen Name": "Sales Order Items"
                                },
                                {
                                    "Step": 5,
                                    "Object": "GuiCTextField.KUWEV-KUNNR",
                                    "ObjectName": "Ship to party",
                                    "Action": "Enter text",
                                    "ActionDescription": "Enter the ship to party",
                                "Screen": "SAPMV45A:4701",
                                "Screen Name": "Sales Order Items"
                                },
                                {
                                    "Step": 6,
                                    "Object": "GuiButton.btn[0]",
                                    "ObjectName": "Press Enter",
                                    "Action": "Press Button",
                                    "ActionDescription": "Press Enter to proceed",
                                "Screen": "SAPMV45A:4701",
                                "Screen Name": "Sales Order Items"
                                }                            

            ]
            }
            ]
            SAP Fields and their SAP Screen Names should be as per screen object maping provided.

            """
    return base_prompt

sysprompt = ""#You are expert in Worksoft Certify, SAP and creating automation test cases. Convert descriptions into structured JSON steps."

# Call LLM
def callLlmForJson(sap_screen, description, expected_result, base_prompt, reference_process1, object_prompt):
    # Prompt    
    # testprompt = f"""
    # Manual Test Case to Automate for transaction: {sap_screen}, description: {description} 
    # and expected result: {expected_result}
    
    # Make sure you create Test Steps that reflects all the instructions in description. Use below process as a reference but do not create steps that are not in description or logical, and do not omit any steps that are mentioned in above desciption.
    # IMP : Only provide json and nothing else.
    # """            
    
    testprompt = f"""\n
    
    Important Instructions:
- First Step should be entering SAP TCode, for eg. ("VA01") in ok code field on SAP Main Screen.
- Find SAP Program name for the SAP TCode, for e.g. VA01 program name is SAPMV45A and first screen is SAPMV45A:0101.
- Then get the objects on SAPMV45A:0101 screen from screen mapping provided and add them in JSON.
- add navigation step by pressing enter or click on a tab during screen tansition.
- Then move on to next screen and add objects for next screen in JSON. Before moving to next screen.
- Make sure to add objects specified in description and on screen they exist as per the mapping.
    
    Requirement for Certify Automation: 
    SAP TCode: {sap_screen} and Step Description: {description}"""            
    
    usrprompt = base_prompt + object_prompt + testprompt
    #print("Prompt : ", usrprompt)

    file = "prompt_" + sap_screen + ".txt"
    with open(file, "w") as file:
        file.write(sysprompt)        
        file.write("\n")
        file.write(usrprompt)

    # Call OpenAI GPT-4o API
    response = client.chat.completions.create(
        model="google/gemini-2.5-flash-preview-05-20",
        messages=[
            {"role": "system", "content": sysprompt},
            {"role": "user", "content": usrprompt}
        ]
    )

    # Extract JSON output from OpenAI response
    json_output = response.choices[0].message.content
    #print(json_output)
    json_output = json_output.replace("```json", "").replace("```", "").strip()
    return json_output

# Create JSON
def Create_JSON(file_path, stats_df):
    # Load Excel file
    df = pd.read_excel(os.path.join(os.path.dirname(__file__), file_path))

    # Iterate through each row in the DataFrame
    for index, row in df.iterrows():
        # Extract the description for each step
        description = row["Description"]  # Ensure the column name matches your Excel sheet
        sap_screen = row["SAP Screen"]
        expected_result = row["Expected Result"]
        step_name = row["Step Name"]

        # Fetch screen object mapping from Neo4j
        # Fetch screen object mapping from Neo4j
        #screen_json = fetch_screen_object_mapping()
        ApplicationVersionID = 34;
        #screen_json = fetch_screen_object_mappingNew(sap_screen, description, ApplicationVersionID)
        screen_json = str (process_map_files())       
        print ("screen json from map file",screen_json)
        objectprompt ="\nSAP Object and Screen mapping  is as follows: "+ screen_json
        objectprompt += "\nStrictly follow Screen corresponding to the object when you are generate step. Please think step by step and only add step when corresponding object belong to the screen as per mapping json"
        if objectprompt is None:
            print(f"No mapping found for TCode: {sap_screen}")
            continue  # Skip this iteration if no mapping is found

        # # Find Similar Process by Calling Neo4J Vector Search Query
        # reference_pr1 = findProcessFromGraph1(sap_screen,description, logger)
        # reference_process1=f""" Reference Process_1: {reference_pr1}"""
        # similarity_score = 0;
        # ProcessID = 0;
        # if(reference_pr1):
        #     ProcessID = reference_pr1.get("ProcessID") # return top matched process
        #     similarity_score = reference_pr1.get("similarity") # get score of top process
        # if(similarity_score > 1): # TODO: ANU: For testing , increased similarity score. reduce it later
        #     add_entry_to_processlist(step_name, sap_screen, ProcessID, similarity_score)
        #     json_output = json.dumps([], indent=4)  # Create an empty JSON array
        # else:
        #     # Call LLM and get JSON
        #     json_output = callLlmForJson(sap_screen, description, expected_result, base_prompt, reference_process1, objectprompt)
            
        json_output = callLlmForJson(sap_screen, description, expected_result, base_prompt, "", objectprompt)
        
        sysprompt= """you are expert figuring out the mistakes in the json fromat"""
        usrprompt = f"""This is the generated Json format and the map files details.
        can you check if there any mismatch of screen to objects in the json refering to map file details is yes then correct it and return the json only\n

          this is the generated json :
          {json_output}\n
          this is the map file details :
          {screen_json}
         
          """
        response = client.chat.completions.create(
        model="google/gemini-2.5-flash-preview-05-20",
        messages=[
            {"role": "system", "content": sysprompt},
            {"role": "user", "content": usrprompt}
        ]
    )
        json_output = response.choices[0].message.content
        json_output = json_output.replace("```json", "").replace("```", "").strip()

        # Save JSON output to a file
        # Create the output directory if it doesn't exist
        output_directory = "Output_JSON_Files"
        if not os.path.exists(output_directory):
            os.makedirs(output_directory)
        output_file =os.path.join("Output_JSON_Files",f"{step_name}_{sap_screen}.json")
        with open(output_file, "w") as f:
            f.write(json_output)

    return stats_df

# Create a log file with a timestamp
def Create_LogFile():
    log_directory = "Log_Files"
    if not os.path.exists(log_directory):
        os.makedirs(log_directory)

    log_file_name = os.path.join(log_directory, f"log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - [ %(filename)s-%(module)s-%(lineno)d ]  : %(message)s')

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.DEBUG)
    stdout_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(log_file_name)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(stdout_handler)

    logger.info("Log file created: %s", log_file_name)
  
if __name__ == "__main__":
    # Create a log file with a timestamp
    #Create_LogFile()
    logger.info(f"Start => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Connect to SQL Server DB
    conn = connect_to_database()
    cursor = conn.cursor()
    
    # Define base_prompt
    base_prompt = define_prompt()

    # Define Statistic DF
    df = pd.DataFrame(columns=["Step_Name", "SAP_Screen", "JSON_Screen", "JSON_Object", "JSON_ObjectName", "ProcessID", "TestStepID", "Narrative", "ObjectID", "ComponentActionID", "ApplicationVersionID", "InterfaceLibraryID" , "CertifySequence", "Skip", "TestStepActionID","CertifyValue", "Status", "Notes"])

    # Excel File path
    logger.info(f"Create JSON Files => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    excel_file_path = "TestCases_Input\\Standard Export Sales Order Flow_First1.xlsx"  # Update with actual file path
    df = Create_JSON(excel_file_path, df)

    # Process the generated JSON => Process_JSON.py
    logger.info(f"Process JSON Files => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    json_file_path = "Output_JSON_Files"
    json_files = [s for s in os.listdir(json_file_path)
        if os.path.isfile(os.path.join(json_file_path, s))]
    json_files.sort(key=lambda s: os.path.getmtime(os.path.join(json_file_path, s)))
    index = 0
    for json_file in json_files:
        index += 1

        # Process the generated Certify steps file
        step_name, sap_screen = json_file.split('_', 1)
        sap_screen = sap_screen.replace('.json', '')
        json_full_path = os.path.join(json_file_path, json_file)

        logger.info(f"{index}. Processing {json_file}  =>  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        # Check if ProcessID already found for this step
        if not ProcessList[(ProcessList['Step_Name'] == step_name) & (ProcessList['SAP_Screen'] == sap_screen)].empty:
            logger.info(f"ProcessID found for Step Name: {step_name}, SAP Screen: {sap_screen}")

            process_entry = ProcessList[(ProcessList['Step_Name'] == step_name) & (ProcessList['SAP_Screen'] == sap_screen)]
            if not process_entry.empty:
                ProcessID = process_entry.iloc[0]['ProcessID']
                similarity_score = process_entry.iloc[0]['similarity_score']

                # Add to statistics DF
                status = '';
                notes = f"Existing Process Found with similarity score {similarity_score}";
                status = "Pass";
                new_data = [{
                    "Step_Name": str(step_name), 
                    "SAP_Screen": str(sap_screen), 
                    "JSON_Screen": "N/A", 
                    "JSON_Object": "N/A", 
                    "JSON_ObjectName": "N/A",
                    "ProcessID": str(ProcessID), 
                    "TestStepID": "N/A", 
                    "Narrative": "N/A", 
                    "ObjectID": "N/A", 
                    "ComponentActionID": "N/A", 
                    "ApplicationVersionID": "N/A", 
                    "InterfaceLibraryID": "N/A", 
                    "CertifySequence": "N/A", 
                    "Skip": "N/A", 
                    "TestStepActionID": "N/A",
                    "CertifyValue": "N/A", 
                    "Status": str(status), 
                    "Notes": str(notes)
                }]

                new_df = pd.DataFrame(new_data)
                df = pd.concat([new_df, df], ignore_index=True)
        else:
            logger.warning(f"Process JSON as No ProcessID found for Step Name: {step_name}, SAP Screen: {sap_screen}")
            df, ProcessList = process_json_file(json_full_path, step_name, sap_screen, logger, conn, cursor, df, ProcessList)

    logger.info(f"Processing Finished => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # # Create MainProcess HARD CODED
    # logger.info("Create MainProcess")
    # UserID = 11000370; #NextGenAI Login User
    # ProcessFolderID = 404106; # Anu/Demo4 Folder
    # ComponentActionID = 8;
    # ApplicationVersionID = 1;
    # InterfaceLibraryID = 1;
    # ComponentActionParmsID = 19;
    # ObjectID = 5;
    # MainProcessName = "MainProcess_Export_Sales_Order_Flow"
    # df = create_main_process(ProcessFolderID, ProcessList, UserID, conn, cursor, logger, MainProcessName, ComponentActionID, ApplicationVersionID, InterfaceLibraryID, ComponentActionParmsID, ObjectID, df)

    # # Create Stats File
    # df = df.iloc[::-1].reset_index(drop=True)
    # file_name = "Statistics_"  + str(datetime.now().strftime('%Y_%m_%d_%H_%M_%S') + ".csv")
    # create_statistics_file(df, file_name, logger)