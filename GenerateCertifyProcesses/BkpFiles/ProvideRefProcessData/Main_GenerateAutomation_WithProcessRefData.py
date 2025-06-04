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
from GenerateCertifyProcesses.BkpFiles.GetProcessData import Get_ProcessData

# Load env
load_dotenv()
os.getenv('OPENAI_API_KEY')

# Set up logging
global logger;
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define Prompt Details
def define_prompt():
    #try but not working
    # base_prompt = """
    # Instructions:
    # Convert the following excel test case into a Worksoft Certify automation script in JSON format.
    # For every step, identify SAP Screen Name, Object, ObjectName, Action and ActionDescription.
    # SAP Screen Name(for e.g. VA01) has SAP Transaction Code. Use it to identify SAP screens associated with this Transaction code and then identify per screen fields based on description provided
    # Important: Only use screen fields in description and do not add additional fields. 
    # For e.g. If Ship To Party is not in description then do not add step for it.

    # JSON Structure:
    # - Maintain proper JSON formatting with indentation
    # - Each JSON must be organized screen wise further have its associated steps.
    # - Adding SAP TCode in 'SAP Main' screen should be first step. 'Object' for 'SAP Ok Code' is 'GuiOkCodeField.wnd[0]/tbar[0]/okcd'. 
    # - Identify and add fields screen wise in JSON. For e,g SAP Screen SAPMV45A:0101 has Order Type, Sales Organization, Division and
    # Sold To party and Ship to party are on next Screen 'SAPMV45A:4001'
    # - Use GuiCTextField instead of GuiTextField and  GuiButton instead of GuiCButton in 'Object'
    # - Use GuiButton.btn[0] as Object for Continue or Enter and GuiButton.btn[11] as Object for save button
    # Example JSON Output:
    # [ 
    #     {
    #         "name": "Sales Document Creation",
    #         "Application": "S4 Hana Sales and Distribution",
    #         "Windows": [
    #             {
    #                 "Screen": "SAP Main",
    #                 "Window Name": "SAP Main",
    #                 "screen number": "1",
    #                 "steps": [
    #                     {
    #                         "Step": 1,
    #                         "Object": "GuiOkCodeField.wnd[0]/tbar[0]/okcd",
    #                         "ObjectName": "Enter TCode into OK Code field",
    #                         "Action": "Input TCode in GuiOkCode Field",
    #                         "ActionDescription": "Input TCode in GuiOkCode Field"
    #                     }
    #                 ]
    #             },
    #         ]
    #     }
    # ]
    # """

    base_prompt = """
    Instructions:
    Convert the following manual test case into a Worksoft Certify automation script in JSON format.
    SAP Screen Name(for e.g. VA01) has SAP Transaction Code. Use it to identify SAP screens associated with this Transaction code and then identify per screen fields based on description provided
    Important: Only use screen fields in description and do not add additional fields. 
    For e.g. If Ship To Party it not in description then do not add step for it.

    JSON Structure:
    - Maintain proper JSON formatting with indentation
    - Each JSON must be organized screen wise further have its associated steps.
    - Adding SAP TCode in 'SAP Main' screen should be first step. 'Object' for 'SAP Ok Code' is 'GuiOkCodeField.wnd[0]/tbar[0]/okcd'. 
    - Identify and add fields screen wise in JSON. For e,g SAP Screen SAPMV45A:0101 has Order Type, Sales Organization, Division and
    Sold To party, Ship to party and Customer Reference are on next Screen 'SAPMV45A:4001'
    - Use GuiCTextField instead of GuiTextField and  GuiButton instead of GuiCButton in 'Object'
    - Use GuiButton.btn[0] as Object for Continue or Enter and GuiButton.btn[11] as Object for save button
    - For 'Process Enter' step use Object 'GuiButton.btn[0]'. Before moving to next screen, add step for 'Press Enter'. 
    -Add one step at the end as "Choose Save Document. Make a note of the sales order number" if there is "create" in the description. 
    for eg "Create Sales Document", "Create Delivery", "Create Invoice", "Create Billing Document" etc.
    Example JSON Output:
    [ 
        {
            "name": "Sales Document Creation",
            "Application": "S4 Hana Sales and Distribution",
            "Windows": [
                {
                    "Screen": "SAP Main",
                    "Window Name": "SAP Main",
                    "screen number": "1",
                    "steps": [
                        {
                            "Step": 1,
                            "Object": "GuiOkCodeField.wnd[0]/tbar[0]/okcd",
                            "ObjectName": "Enter TCode into OK Code field",
                            "Action": "Input TCode in GuiOkCode Field",
                            "ActionDescription": "Input TCode in GuiOkCode Field"
                        }
                    ]
                },
                {
                    "Screen": "SAPMV45A:0101",
                    "Window Name": "Create Sales Order",
                    "screen number": "n",
                    "steps": [
                        {
                            "Step": 1,
                            "Object": "GuiCTextField.VBAK-AUART",
                            "ObjectName": "Order Type",
                            "Action": "Enter text",
                            "ActionDescription": "Enter the order type"
                        },
                        {
                            "Step": 2,
                            "Object": "GuiCTextField.VBAK-VKORG",
                            "ObjectName": "Sales Organization",
                            "Action": "Enter text",
                            "ActionDescription": "Enter the sales organization"
                        },
                        {
                            "Step": 3,
                            "Object": "GuiCTextField.VBAK-VTWEG",
                            "ObjectName": "Distribution Channel",
                            "Action": "Enter text",
                            "ActionDescription": "Enter the distribution channel"
                        },
                        {
                            "Step": 4,
                            "Object": "GuiCTextField.VBAK-SPART",
                            "ObjectName": "Division",
                            "Action": "Enter text",
                            "ActionDescription": "Enter the division"
                        },
                        {
                            "Step": 10,
                            "Object": "GuiButton.btn[0]",
                            "ObjectName": "Press Enter",
                            "Action": "Press Button",
                            "ActionDescription": "Press Enter to proceed"
                        }
                    ]
                }            
            ]
        }
    ]
    """
    return base_prompt

# Create JSON
def Create_JSON(file_path):
    # Get Reference Data - Not working
    #ProcessData = Get_ProcessData(86414)

    # Load Excel file
    df = pd.read_excel(os.path.join(os.path.dirname(__file__), file_path))

    # Iterate through each row in the DataFrame
    for index, row in df.iterrows():
        # Extract the description for each step
        description = row["Description"]  # Ensure the column name matches your Excel sheet
        sap_screen = row["SAP Screen"]
        expected_result = row["Expected Result"]
        step_name = row["Step Name"]

        # Prompt    
        testprompt = f"""
        Manual Test Case to Automate for transaction: {sap_screen}, description: {description} 
        and expected result: {expected_result}
        
        IMP : Only provide json and nothing else.
        """      

        # Not working
        # reference_process=f""" Reference Process Data: {ProcessData}. Object field should be in ObjectPhysicalName in reference process data provided.
        # For e.g. Order Type ObjectName, Object = GuiCTextField.VBAK-AUART
        # """

        # Call OpenAI GPT-4o API
        usrprompt = base_prompt + testprompt #+ reference_process   
        systemprompt = "You are expert in Worksoft Certify Database and know processes, test steps and certify learn tool"

        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[ {"role": "system", "content": systemprompt},
                        {"role": "user", "content": usrprompt}]
        )

        # Extract JSON output from OpenAI response
        json_output = response.choices[0].message.content
        #print(json_output)

        json_output = json_output.replace("```json", "").replace("```", "").strip()

        # Save JSON output to a file
        output_file =os.path.join("Output_JSON_Files",f"{step_name}_{sap_screen}.json")
        with open(output_file, "w") as f:
            f.write(json_output)

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
    Create_LogFile()
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
    Create_JSON(excel_file_path)

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
    #     df = process_json_file(json_full_path, step_name, sap_screen, logger, conn, cursor, df)
    # logger.info(f"Processing Finished => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # # Create Stats File
    # df = df.iloc[::-1].reset_index(drop=True)
    # file_name = "Statistics_"  + str(datetime.now().strftime('%Y_%m_%d_%H_%M_%S') + ".csv")
    # create_statistics_file(df, file_name, logger)