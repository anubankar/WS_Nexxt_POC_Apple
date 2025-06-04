# TRY: Provide SAP Screen names and Objects as Inputs
# Process_Test_Case.py -> Read excel test case. Later on it can have additional functions to read different test case format. Create JSON
import pandas as pd
import openai
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
from FindScreenObjects import fetch_screen_object_mapping
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from CallLlms import CallforLLm


# Load env
load_dotenv()
os.getenv('OPENAI_API_KEY')

# Set up logging
global logger;
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define List
ProcessList = pd.DataFrame(columns=["Step_Name", "SAP_Screen" ,"ProcessID", "similarity_score"])

# Add to Process List
def add_entry_to_processlist(step_name, sap_screen, process_id, similarity_score):
    global ProcessList
    new_entry = pd.DataFrame([[step_name, sap_screen, process_id, similarity_score]], columns=["Step_Name", "SAP_Screen" ,"ProcessID", "similarity_score"])
    ProcessList = pd.concat([ProcessList, new_entry], ignore_index=True)
    logger.info(f"Added entry to ProcessList: Step Name: {step_name}, SAP_Screen: {sap_screen}, ProcessID: {process_id}")

# Define Prompt Details
def define_prompt():
    # base_prompt = """
    # Convert the following manual test case into a Worksoft Certify automation script in JSON format.
    # Take SAP Screen Name(for e.g. VA01), then identify its SAP screens and then identify fields based on description provided
    # Only use fields in description. Do not add additional fields. For e.g. If Ship To Party it not in description then do not add step for it
    # Each JSON must be organized screen wise further have its associated steps.

    # Most Imp:
    # - Refer to to the reference processes given as example processes which best matches with the description do not copy as it is, take it as reference only. 
    # - Start from 'SAP Main' as first screen, then add remaining screens and fields.  
    # - Identify screen wise fields and seperate it accordingly refer to Description. 
    # - Dont add any other additional fields which is not there in Description from the excel.
    # - Add 'Enter' and 'Save' steps if it is there in reference process 
    # - Dont add all steps in one screen, identify from the description and add steps beloging to different screen in screen wise distribution. 
    # - Add 'ObjectName' in json file
    # Example JSON Output:
    # [ 
    #     {
    #         "name": "Sales Document Creation",
    #         "Application": "S4 Hana Sales and Distribution",
    #         "Windows": [
    #             {
    #                 "Screen": "SAPMV45A:0101",
    #                 "Window Name": "Create Sales Order",
    #                 "screen number": "n",
    #                 "steps": [
    #                     {
    #                         "Step": 1,
    #                         "Object": "GuiTextField.VBAK-VBELN",
    #                         "ObjectName": "Enter Sales Document Number",
    #                         "Action": "Enter content into an EditBox",
    #                         "ActionDescription": "Enter the sales document number to be changed"
    #                     }
    #                 ]
    #             }
    #         ]
    #     }
    # ]

    # Use only the screen-object mapping values that are referenced in the description below. 
    # Try to map each step to an appropriate screen, action, and object, generating unique step numbers and filling out realistic values.
    
    # Key Requirements:  
    # - Ensure each step contains:
    # - Screen ID (e.g., SAPMV45A:0101)
    # - Window Name
    # - GUI Object ID (e.g., GuiCTextField.VBAK-AUART)
    # - Action (e.g., Enter text, Press Button)
    # - Step Sequence Number (Strict order)
    # - Description (Clear explanation of the action)
    
    # Rules:
    # - Identify screen wise feilds and seperate it accordingly 
    # - Take "Object": "GuiButton.btn[0]" for the press enter step.
    # - Dont add any other additional feilds which is not there in Description from the excel 
    # - Do not merge multiple numbered lines in one JSON.
    # - Maintain proper JSON formatting with indentation.
    # """    

    base_prompt = """
    You are an expert in SAP automation documentation.
    Given the task description below and the screen-object mapping, create a JSON structure of the process in this format:

    [ 
        {
            "name": "Sales Document Creation",
            "Application": "S4 Hana Sales and Distribution",
            "Windows": [
                {
                    "Screen": "SAPMV45A:0101",
                    "Window Name": "Create Sales Order",
                    "screen number": "n",
                    "steps": [
                        {
                            "Step": 1,
                            "Object": "GuiTextField.VBAK-VBELN",
                            "ObjectName": "Enter Sales Document Number",
                            "Action": "Enter content into an EditBox",
                            "ActionDescription": "Enter the sales document number to be changed"
                        }
                    ]
                }
            ]
        }
    ]

    Use only the screen-object mapping values that are referenced in the description below. 
    Try to map each step to an appropriate screen, action, and object, generating unique step numbers and filling out realistic values.

    imp :
    - Add first step as enter tcode which ever it is for eg. ("VA01") in ok code field get its screen mapping and add this first with 1st screen
    """
    return base_prompt

# Call LLM
def callLlmForJson(sap_screen, description, expected_result, base_prompt, reference_process1, object_prompt):
    # Prompt    
    # testprompt = f"""
    # Manual Test Case to Automate for transaction: {sap_screen}, description: {description} 
    # and expected result: {expected_result}
    
    # Make sure you create Test Steps that reflects all the instructions in description. Use below process as a reference but do not create steps that are not in description or logical, and do not omit any steps that are mentioned in above desciption.
    # IMP : Only provide json and nothing else.
    # """            
    
    testprompt = f"""
    Manual Test Case to Automate for transaction: {sap_screen}, description: {description} 
    IMP : Only provide json and nothing else.
    """     
    sysprompt = "You are an AI that converts descriptions into structured JSON steps."

    # Call OpenAI GPT-4o API
    usrprompt = base_prompt + testprompt + object_prompt #+ reference_process1 
    print("usrprompt: ", usrprompt)
    systemprompt = "You are expert in Worksoft Certify Database and know processes, test steps and certify learn tool"
    json_output = CallforLLm(systemprompt, usrprompt, "gpt-4o-mini")
    # response = openai.chat.completions.create(
    #     model="gpt-4o-mini",
    #     temperature=0.0,
    #     messages=[ {"role": "system", "content": systemprompt},
    #                 {"role": "user", "content": usrprompt}
    #             ]        
    # )

    # # Extract JSON output from OpenAI response
    # json_output = response.choices[0].message.content
    # print(json_output)
    # json_output = json_output.replace("```json", "").replace("```", "").strip()
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
        object_prompt ="This is the Screen object mapping: " + fetch_screen_object_mapping(sap_screen)

        # Find Similar Process by Calling Neo4J Vector Search Query
        reference_pr1 = findProcessFromGraph1(sap_screen,description, logger)
        reference_process1=f""" Reference Process_1: {reference_pr1}"""
        similarity_score = 0;
        ProcessID = 0;
        if(reference_pr1):
            ProcessID = reference_pr1.get("ProcessID") # return top matched process
            similarity_score = reference_pr1.get("similarity") # get score of top process
        if(similarity_score >= 1):
            add_entry_to_processlist(step_name, sap_screen, ProcessID, similarity_score)
            json_output = json.dumps([], indent=4)  # Create an empty JSON array
        else:
            # Call LLM and get JSON
            json_output = callLlmForJson(sap_screen, description, expected_result, base_prompt, reference_process1, object_prompt)
            
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
    cursor = conn.cursor(as_dict=True)
    
    # Define base_prompt
    base_prompt = define_prompt()

    # Define Statistic DF
    df = pd.DataFrame(columns=["Step_Name", "SAP_Screen", "JSON_Screen", "JSON_Object", "JSON_ObjectName", "ProcessID", "TestStepID", "Narrative", "ObjectID", "ComponentActionID", "ApplicationVersionID", "InterfaceLibraryID" , "CertifySequence", "Skip", "TestStepActionID","CertifyValue", "Status", "Notes"])

    # Excel File path
    logger.info(f"Create JSON Files => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    excel_file_path = "TestCases_Input\\Standard Export Sales Order Flow_First1.xlsx"  # Update with actual file path
    df = Create_JSON(excel_file_path, df)

    # # Process the generated JSON => Process_JSON.py
    # logger.info(f"Process JSON Files => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    # json_file_path = "Output_JSON_Files"
    # json_files = [s for s in os.listdir(json_file_path)
    #     if os.path.isfile(os.path.join(json_file_path, s))]
    # json_files.sort(key=lambda s: os.path.getmtime(os.path.join(json_file_path, s)))
    # index = 0
    # for json_file in json_files:
    #     index += 1

    #     # Process the generated Certify steps file
    #     step_name, sap_screen = json_file.split('_', 1)
    #     sap_screen = sap_screen.replace('.json', '')
    #     json_full_path = os.path.join(json_file_path, json_file)

    #     logger.info(f"{index}. Processing {json_file}  =>  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    #     # Check if ProcessID already found for this step
    #     if not ProcessList[(ProcessList['Step_Name'] == step_name) & (ProcessList['SAP_Screen'] == sap_screen)].empty:
    #         logger.info(f"ProcessID found for Step Name: {step_name}, SAP Screen: {sap_screen}")

    #         process_entry = ProcessList[(ProcessList['Step_Name'] == step_name) & (ProcessList['SAP_Screen'] == sap_screen)]
    #         if not process_entry.empty:
    #             ProcessID = process_entry.iloc[0]['ProcessID']
    #             similarity_score = process_entry.iloc[0]['similarity_score']

    #             # Add to statistics DF
    #             status = '';
    #             notes = f"Existing Process Found with similarity score {similarity_score}";
    #             status = "Pass";
    #             new_data = [{
    #                 "Step_Name": str(step_name), 
    #                 "SAP_Screen": str(sap_screen), 
    #                 "JSON_Screen": "N/A", 
    #                 "JSON_Object": "N/A", 
    #                 "JSON_ObjectName": "N/A",
    #                 "ProcessID": str(ProcessID), 
    #                 "TestStepID": "N/A", 
    #                 "Narrative": "N/A", 
    #                 "ObjectID": "N/A", 
    #                 "ComponentActionID": "N/A", 
    #                 "ApplicationVersionID": "N/A", 
    #                 "InterfaceLibraryID": "N/A", 
    #                 "CertifySequence": "N/A", 
    #                 "Skip": "N/A", 
    #                 "TestStepActionID": "N/A",
    #                 "CertifyValue": "N/A", 
    #                 "Status": str(status), 
    #                 "Notes": str(notes)
    #             }]

    #             new_df = pd.DataFrame(new_data)
    #             df = pd.concat([new_df, df], ignore_index=True)
    #     else:
    #         logger.warning(f"Process JSON as No ProcessID found for Step Name: {step_name}, SAP Screen: {sap_screen}")
    #         df, ProcessList = process_json_file(json_full_path, step_name, sap_screen, logger, conn, cursor, df, ProcessList)

    # logger.info(f"Processing Finished => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

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