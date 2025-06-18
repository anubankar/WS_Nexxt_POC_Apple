import pandas as pd
import pymssql
import openai
import json
import re
from dotenv import load_dotenv
import os
import sys
from  Db_Connections import connect_to_database
import logging
from datetime import datetime
#from Invoke_Learn import Invoke_Certify_Process
from RecordStatistics import add_data_to_df

#PENDING
# Check if ObjectIdParmValue Table to be filled when creating new Object

# Load env
load_dotenv()
os.getenv('OPENAI_API_KEY')

# Hard Coding
logger = logging.getLogger(__name__)
global ApplicationVersionID, InterfaceLibraryID, ProcessFolderID, ResultLogStatusID, UserID, ProcessName, ParentID, ProcessID;
global va01_data, username, password;
ApplicationVersionID= 34;
InterfaceLibraryID = 9
ProcessFolderID = 404106; # Anu/Demo4 Folder
ResultLogStatusID = 10; #Unknown
UserID = 11000370; #NextGenAI Login User
ProcessName = ""
ParentID = 0;
ProcessID = 1
current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
va01_data  = {'Order_Type':'OR',
              'Sales_Organization':'1710', 
              'Division':'00',
              'Div':'00',
              'Distribution_Channel':'10',
              'Sold to party': 'USCU_S12',
              'Ship to party': 'USCU_S12',
              'Sold-To Party': 'USCU_S12',
              'Ship-To Party': 'USCU_S12', 
              'Cust. Reference': 'Bike Mirrors',
              'Customer Reference': 'Bike Mirrors',
              'Material': 'TG22',
              'Quantity': '1',
              'Plant': '1710',
              'Validate Plant': '1710',
              'Validate Payment term': 'NT30',
              'Payment term': 'NT30',
              'Inco term 1': 'CFR',
              'Validate Inco term 1': 'CFR'             
             }

# Username and password for invoking certify processes
username = "NextGenAI"
password = "Welcome@123"

# Connect to SQL Server DB
conn = connect_to_database()
cursor = conn.cursor(as_dict=True)
  
# Create ProcessID
def Create_Process(cursor, conn, ProcessName):
    # Check if Process exists, then use it
    sql = f"""select Top 1 ProcessID from Process where Name = '{ProcessName}' and ProcessFolderID = {ProcessFolderID}"""
    cursor.execute(sql)
    results = cursor.fetchall()
    if(results):
        processid = results[0]['ProcessID']
        logger.info(f"Process Already Exists => {ProcessName} and ProcessID: {processid}")

        # Delete existing TestStepID and TestStepActionID
        sql = f"""delete from TestStepAction where TestStepID in (select distinct TestStepID from TestStep where ProcessID = {processid})"""
        cursor.execute(sql)

        sql = f"""delete from TestStep where ProcessID = {processid}"""
        cursor.execute(sql)
    else:
        # Create Process
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql = f"""INSERT INTO [dbo].[Process] ([Name], [ProcessFolderID], [ResultLogStatusID], [CreatedDt], 
    [CreatedBy], [ModifiedDt], [ModifiedBy])
    VALUES ('{ProcessName}', {ProcessFolderID}, {ResultLogStatusID}, '{current_date}', {UserID}, '{current_date}', {UserID})""";
        cursor.execute(sql)
        conn.commit()
        processid = cursor.lastrowid
        logger.info(f"Process Created => {ProcessName} and ProcessID: {processid}")
    return processid;

# Call Open AI
def get_response_from_openai(prompt):
    try:
        os.getenv('OPENAI_API_KEY')
        response = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=8000,
            n=1,
            temperature=0.0
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        logger.error(f"Error in LLM processing: {str(e)}")
        return None  

# Function to check if  Tcode objects are present in certify repository
def check_if_tcode_exist (sap_screen, conn):
    with conn.cursor() as cursor:
       sql = "SELECT TOP 5 Narrative FROM TestStep WHERE LOWER(Narrative) LIKE '%" + sap_screen.lower() + "%'"
       cursor.execute(sql)
       records = cursor.fetchall()
       #logger.info(f"Records found: {records}")
       
       if records:
           return 'Found'
       else:
           return 'Not Found'

# Function to Find Objects
def Find_Object(step_info):
    ObjectID = 1
    ComponentActionID = 1
    ComponentActionParmsID = 1
    InterfaceLibraryID = 9
    ApplicationVersionID = 34
    MapSourceID = 2
    ParentComponentID = 163

    # Find Parent ID
    ParentID = 1
    Screen = step_info['Screen']

    # handle for continue Enter where Screen Name is coming as Object Name. Example as below:
#     {
#     "Step": 6,
#     "Object": "SAPMV45A:0101",
#     "ObjectName": "Press Enter",
#     "Action": "Press Button",
#     "ActionDescription": "Send Enter key to proceed"
#       }
    if(Screen == step_info['Object']):
        ParentID = "NULL";
    else:
        sql = f"SELECT * FROM [dbo].[Object] WHERE PhysicalName = '{Screen}' AND ApplicationVersionid = {ApplicationVersionID}"
        cursor.execute(sql)
        object_results = cursor.fetchall()
        if object_results:
            # Get ObjectID, ComponentID, MapSourceID
            ParentID = object_results[0]['ObjectID'];
    #     # Else commenting as we do not want to create new Objects if not found. return null
    #     else:
    #         # Add Parent
    #         current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    #         sql = f"""INSERT INTO [dbo].[Object] ([Name],[PhysicalName],[ApplicationVersionID],[ComponentID]
    # ,[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy],[MapSourceID])
    # VALUES ('{ProcessName}', '{Screen}', {ApplicationVersionID}, {ParentComponentID}, '{current_date}', {UserID}, '{current_date}', {UserID}, {MapSourceID})""";
    #         cursor.execute(sql)
    #         conn.commit()
    #         ParentID = cursor.lastrowid
    #         logger.info(f"Parent not found. Created ParentID = {ParentID} => Object = {Screen} => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # Find Object
    PhysicalName = step_info['Object']

    #Generate SQL query to find the object based on the physical name
    if(ParentID == "NULL"):
        sql = f"SELECT * FROM [dbo].[Object] WHERE PhysicalName = '{PhysicalName}' AND ApplicationVersionid = {ApplicationVersionID} AND ParentID is NULL"
    else:
        sql = f"SELECT * FROM [dbo].[Object] WHERE PhysicalName = '{PhysicalName}' AND ApplicationVersionid = {ApplicationVersionID} AND ParentID = {ParentID}"
    cursor.execute(sql)
    object_results = cursor.fetchall()
    
    ### Check if the object exists and handle accordingly
    #Object Found
    if object_results:
        # Get ObjectID, ComponentID, MapSourceID
        ObjectID = object_results[0]['ObjectID'];
        ComponentID = object_results[0]['ComponentID'];
        MapSourceID = object_results[0]['MapSourceID'];

        #Find ComponentActionID and ComponentActionParmsID. ComponentActionTypeID 1 is for Normal and Name is Click Event
        sql = f"Select * from dbo.ComponentAction where ComponentID = {ComponentID} and ComponentActionTypeID = 1"
        if('GuiButton' in PhysicalName or 'GuiCButton' in PhysicalName):
             sql += " and Name = '[Press]'";
        elif('GuiTextField' in PhysicalName or 'GuiCTextField' in PhysicalName):          
             sql += " and Name = '[Input]'";
        elif('GuiOkCodeField' in PhysicalName):          
            sql += " and Name = '[Input]'";
        elif(Screen == step_info['Object']): #For Enter Key
            sql += " and Name = '[SendVKey]'";
        cursor.execute(sql)
        comp_action_result = cursor.fetchall()
        if comp_action_result:
            ComponentActionID = comp_action_result[0]['ComponentActionID']

            if(ComponentActionID):
                if(Screen == step_info['Object']):
                    sql = f"Select ComponentActionParmsID from ComponentActionParms where ComponentActionID = {ComponentActionID} and Name in ('Key')";
                else:
                    sql = f"Select ComponentActionParmsID from ComponentActionParms where ComponentActionID = {ComponentActionID} and Name in ('Value', 'Type')";

                cursor.execute(sql)
                comp_action_parms_result = cursor.fetchall()
                if comp_action_parms_result:
                    ComponentActionParmsID = comp_action_parms_result[0]['ComponentActionParmsID']
                else:
                    logger.error("ComponentActionParmsID Not Found => ComponentActionID = ", ComponentActionID)
                    return ObjectID, ComponentActionID, InterfaceLibraryID, ApplicationVersionID, ComponentActionParmsID
        else:
            logger.error("ComponentAction Not Found => ComponentID = ", ComponentID)
            return ObjectID, ComponentActionID, InterfaceLibraryID, ApplicationVersionID, ComponentActionParmsID
    
        logger.info(f"Object Found => ObjectName = {PhysicalName} => ObjectID = {ObjectID}, ComponentID = {ComponentID}, MapSourceID = {MapSourceID}, ComponentActionID = {ComponentActionID}")

        # Else commenting as we do not want to create new Objects if not found. return null

#     #Object not found. Create new Object
#     else:
#         ComponentPhysicalName = PhysicalName.split('.')[0];
#         if(ComponentPhysicalName == "GuiCButton"):
#             ComponentPhysicalName = "GuiButton"

#         # Get ComponentID
#         sql = f"""SELECT * from dbo.Component where PhysicalName = '{ComponentPhysicalName}'"""
#         cursor.execute(sql)
#         comp3 = cursor.fetchall()
#         if comp3:
#             ComponentID = comp3[0]['ComponentID']
#         else:
#             logger.error("Component Not Found => ComponentPhysicalName = ", ComponentPhysicalName)
#             return ObjectID, ComponentActionID, InterfaceLibraryID, ApplicationVersionID, ComponentActionParmsID

#         #Find ComponentActionID and ComponentActionParmsID. ComponentActionTypeID 1 is for Normal and Name is Click Event
#         sql = f"Select * from dbo.ComponentAction where ComponentID = {ComponentID} and ComponentActionTypeID = 1"
#         if('GuiButton' in PhysicalName or 'GuiCButton' in PhysicalName):
#              sql += " and Name = '[Press]'";
#         elif('GuiTextField' in PhysicalName or 'GuiCTextField' in PhysicalName):          
#              sql += " and Name = '[Input]'";
#         elif('GuiOkCodeField' in PhysicalName):          
#             sql += " and Name = '[Input]'";
#         elif('GuiOkCodeField' in PhysicalName):          
#             sql += " and Name = '[Input]'";
#         elif(Screen == step_info['Object']): #For Enter Key
#             sql += " and Name = '[SendVKey]'";
#         cursor.execute(sql)
#         comp_action_result = cursor.fetchall()
#         if comp_action_result:
#             ComponentActionID = comp_action_result[0]['ComponentActionID']

#             if(ComponentActionID):
#                 if(Screen == step_info['Object']):
#                     sql = f"Select ComponentActionParmsID from ComponentActionParms where ComponentActionID = {ComponentActionID} and Name in ('Key')";
#                 else:
#                     sql = f"Select ComponentActionParmsID from ComponentActionParms where ComponentActionID = {ComponentActionID} and Name in ('Value', 'Type')";

#                 cursor.execute(sql)
#                 comp_action_parms_result = cursor.fetchall()
#                 if comp_action_parms_result:
#                     ComponentActionParmsID = comp_action_parms_result[0]['ComponentActionParmsID']
#                 else:
#                     logger.error("ComponentActionParmsID not found for ComponentActionID = ", str(ComponentActionID))
#                     return ObjectID, ComponentActionID, InterfaceLibraryID, ApplicationVersionID, ComponentActionParmsID

#         # Handle the case where the object is not found
#         #For Object: We need ParentID, Name, PhysicalName, ApplicationVersionID, ComponentID, MapSourceID(6)
#         #logger.info(f"No object found for PhysicalName: {PhysicalName}. Creating new ObjectID")

#         # Call LLM and Get Name. This is required for Creating Object
#         if('GuiButton.btn[0]' in PhysicalName): 
#             if('Save' in step_info['ObjectName']):
#                 ObjectName = 'Save'  
#             else:
#                 ObjectName = 'Continue (Enter)'
#         elif('GuiOkCodeField' in PhysicalName):   
#             ObjectName = 'GuiOkCodeField'
#         elif('GuiButton.Save' in PhysicalName or 'GuiCButton.Save' in PhysicalName):   
#             ObjectName = 'Save'
#         elif(Screen == step_info['Object']): #For Enter Key            
#             ObjectName = step_info['ObjectName']
#         else:
#             prompt = 'Find the name for sap table field ' + PhysicalName.split('.')[1] + ". Only return name";
#             ObjectName = get_response_from_openai(prompt)  

#         #Create ObjectID
#         current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

#         sql = f"""INSERT INTO [dbo].[Object] ([Name],[PhysicalName],[ParentID],[ApplicationVersionID],[ComponentID]
# ,[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy],[MapSourceID])
# VALUES ('{ObjectName}', '{PhysicalName}', {ParentID},{ApplicationVersionID}, {ComponentID}, '{current_date}', {UserID}, '{current_date}', {UserID}, {MapSourceID})""";
#         cursor.execute(sql)
#         conn.commit()
#         ObjectID = cursor.lastrowid

#         logger.info(f"Object Created => ObjectName = {PhysicalName} => ObjectID = {ObjectID}, ComponentID = {ComponentID}, MapSourceID = {MapSourceID}, ComponentActionID = {ComponentActionID}")

    # Generate multiple variable returns for ObjectID, ComponentActionID, InterfaceLibraryID, and ApplicationVersionID
    return ObjectID, ComponentActionID, InterfaceLibraryID, ApplicationVersionID, ComponentActionParmsID
    
def Create_TestSteps(step_name, sap_screen, ProcessID, CertifySequence, ObjectID, ComponentActionID, InterfaceLibraryID, ApplicationVersionID, ComponentActionParmsID, step_info, df):
    TestStepID = 1
    TestStepActionID = 1
    Skip = 0; 

    # Find Narrative
    ObjectName = step_info['ObjectName']
    Object = step_info['Object']
    
    value = ''
    print("ObjectName = ", ObjectName, " => Object = ", Object)
    #print("va01_data[ObjectName] = ", va01_data[ObjectName])
    if 'GuiOkCodeField' in Object:
        value = sap_screen
    elif 'Order Type' in ObjectName:
        value = va01_data.get('Order_Type', '')
        value = str(value)
    elif 'Sales Organization' in ObjectName:
        value = va01_data.get('Sales_Organization', '')
    elif 'Distribution Channel' in ObjectName:
        value = va01_data.get('Distribution_Channel', '')
    elif 'Division' in ObjectName:
        value = va01_data.get('Division', '')
    elif 'GuiButton.btn[0]' in Object:
        value = "Continue"
    elif 'GuiButton.btn[11]' in Object:
        value = "Save"
    elif(ObjectName in va01_data):
        value = va01_data[ObjectName]
    else:
        value = ObjectName

    # Add Narrative
    value = str(value)
    Narrative = ""
    if 'GuiOkCodeField' in Object:
        Narrative = "Enter \"/n" + sap_screen + "\" into the Ok Code Field."
    elif('GuiCTextField' in Object or 'GuiTextField' in Object):
        Narrative = "Input \"" + value + "\" into " + ObjectName.replace('Enter', '').strip() + " - " + Object
    elif 'GuiButton.btn[0]' in Object:
        Narrative = "Press the Continue (Enter) Button."
    elif 'GuiButton.btn[11]' in Object:
        Narrative = "Press the Save Button."
    else:
        Narrative = value;

    if(Narrative == "Status Bar"):
        print(Narrative)

    # Find Certify Value
    if 'GuiOkCodeField' in Object:
        CertifyValue = "/n" + sap_screen
    else:
        CertifyValue = value

    #For TestStep & TestStepAction
    # we need ProcessID, ComponentActionID, ApplicationVersionID (34), ObjectID, InterfaceLibraryID 
    if(ObjectID != 0 and ComponentActionID != 0):
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        sql = f"""INSERT INTO TestStep (
            [ProcessID] , [ComponentActionID] ,[ApplicationVersionID] ,[Narrative] ,[InterfaceLibraryID]
            ,[ObjectID],[CertifySequence],[Skip],[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy]) 
        VALUES (
            {ProcessID},
            {ComponentActionID}, {ApplicationVersionID}, '{Narrative}', {InterfaceLibraryID}, 
            {ObjectID}, {CertifySequence}, {Skip},'{current_date}', {UserID}, '{current_date}', {UserID}
        )""";
        cursor.execute(sql)
        conn.commit()
        TestStepID = cursor.lastrowid
        
        #Insert into TestStepAction
        if(TestStepID):
            current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

            sql = f"""INSERT INTO [dbo].[TestStepAction]
([TestStepID], [CertifySequence],[ComponentActionParmsID],[CertifyValue],[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy])
VALUES ({TestStepID}, {CertifySequence}, {ComponentActionParmsID}, '{CertifyValue}',
'{current_date}', {UserID}, '{current_date}', {UserID}
)"""
            cursor.execute(sql)
            conn.commit()
            TestStepActionID = cursor.lastrowid

        logger.info(f"TestStep Created => TestStepID = {TestStepID} => TestStepActionID = {TestStepActionID}")

        # Increment Certify Sequence Number
        CertifySequence += 1;
    
    # Add to statistics DF
    status = '';
    notes = '';
    if(TestStepID != 1 and TestStepActionID != 1):
        status = "Pass"
    else:
        status = "Fail"  

    new_data = [{
        "Step_Name": str(step_name), 
        "SAP_Screen": str(sap_screen), 
        "JSON_Screen": str(step_info['Screen']), 
        "JSON_Object": str(step_info['Object']), 
        "JSON_ObjectName": str(step_info['ObjectName']),
        "ProcessID": str(ProcessID), 
        "TestStepID": str(TestStepID), 
        "Narrative": str(Narrative), 
        "ObjectID": str(ObjectID), 
        "ComponentActionID": str(ComponentActionID), 
        "ApplicationVersionID": str(ApplicationVersionID), 
        "InterfaceLibraryID": str(InterfaceLibraryID), 
        "CertifySequence": str(CertifySequence), 
        "Skip": str(Skip), 
        "TestStepActionID": str(TestStepActionID),
        "CertifyValue": str(CertifyValue), 
        "Status": str(status), 
        "Notes": str(notes)
    }]

    new_df = pd.DataFrame(new_data)
    updated_df = pd.concat([new_df, df], ignore_index=True)
    #print(updated_df)
    #df = add_data_to_df(df, new_data)

    return TestStepID, TestStepActionID, updated_df

# Add Comment Step
#def Add_Comment_Step()

# Add Fail Entry in Stats File
def Add_Fail_In_Statistics_File(df, step_name, sap_screen, step_info, reason):
    # Add to statistics DF
    notes = 'This step is not processed. ';
    notes += f"\nReason: {reason}"
    status = "Fail"  
    Skip = 1;
    new_data = [{
        "Step_Name": str(step_name), 
        "SAP_Screen": str(sap_screen), 
        "JSON_Screen": str(step_info['Screen']), 
        "JSON_Object": str(step_info['Object']), 
        "JSON_ObjectName": str(step_info['ObjectName']),
        "ProcessID": str("N/A"), 
        "TestStepID": str("N/A"), 
        "Narrative": str("N/A"),  
        "ObjectID": str("N/A"),  
        "ComponentActionID": str("N/A"), 
        "ApplicationVersionID": str("N/A"), 
        "InterfaceLibraryID": str("N/A"), 
        "CertifySequence": str("N/A"), 
        "Skip": str("N/A"),  
        "TestStepActionID": str("N/A"), 
        "CertifyValue": str("N/A"),  
        "Status": str(status), 
        "Notes": str(notes)
    }]

    new_df = pd.DataFrame(new_data)
    updated_df = pd.concat([new_df, df], ignore_index=True)
    return updated_df

# Main Function to Get Objects and Create TestStep and Test StepEntries
def Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, step_info, df):
    # Get Objects
    ObjectID, ComponentActionID, InterfaceLibraryID, ApplicationVersionID, ComponentActionParmsID = Find_Object(step_info)
    reason = "";
    if(ObjectID is None):
        if(ComponentActionID == 1):
            if(reason != ""):
                reason += "\n"
            reason = "Unable to find ComponentActionID"
        if(ComponentActionParmsID == 1):
            if(reason != ""):
                reason += "\n"
            reason += "Unable to find ComponentActionID"
    if(ObjectID == 1):
        if(reason != ""):
            reason += "\n"
        reason += "Unable to find ObjectID"
    
        updated_df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, step_info, reason)
        return;

    # Create test steps
    TestStepID, TestStepActionID, updated_df = Create_TestSteps(step_name, sap_screen, ProcessID, CertifySequence, ObjectID, ComponentActionID, InterfaceLibraryID, ApplicationVersionID, ComponentActionParmsID, step_info, df)
    return updated_df

# ####Main Function To Process JSON one by one###
# Process JSON File one by one       
def process_json_file(file_path, step_name, sap_screen, logger1, conn1, cursor1, df1, ProcessList):
    try:
        global logger;
        logger = logger1;

        global conn;
        conn = conn1;

        global cursor;
        cursor = cursor1;

        global df;
        df = df1

         #Check if TCode exist in certify liberary
        tcode_status = check_if_tcode_exist(sap_screen, conn)

        #Start JSON Processing
        with open(file_path, 'r') as file:
            sections = json.load(file)

            # Create ProcessID
            ProcessName = sap_screen + "_" + sections[0]['name']
            ProcessID = Create_Process(cursor, conn, ProcessName)
            new_entry = pd.DataFrame([[step_name, sap_screen,ProcessID]], columns=["Step_Name", "SAP_Screen" ,"ProcessID"])
            ProcessList = pd.concat([ProcessList, new_entry], ignore_index=True)

            logger.info(f"Processing SAP Screen = {sap_screen} => ProcessID = {ProcessID}")

            CertifySequence = 0

            # New Logic for Processing new Step JSON File - Anu - 16 April 2025
            for section in sections:
                # Iterate through each window
                for step in section.get('steps', []):
                    step_info = {
                        "Step": step.get('Step'),
                        "Object": step.get('Object'),
                        "ObjectName": step.get('ObjectName'),
                        "Screen": step.get('Screen'),
                        "ScreenName": step.get('Screen Name'),
                        "Action": step.get('Action'),
                        "Action Description": step.get('ActionDescription')
                    }                    

                    if(step_info['Object'] == "GuiTextField.RV45A-KWMENG"):
                        print("step_info['Object']: ", step_info['Object'])

                    # Ignore Validate and Check Log Steps
                    if ('Validate' in step_info['Action'] or 'Validate' in step_info['ObjectName'] or 'Validation' in step_info['ObjectName']):
                        df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, step_info, "Validation Step")
                        continue;
                        
                    if ('Log' in step_info['ObjectName']):
                        df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, step_info, "Check Log Step")
                        continue;
                        
                    # Fix Completion Button
                    if(step_info['Object'] == "GuiCButton.PBENTER"):
                        df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, step_info, "GuiCButton.PBENTER")
                        continue;
                    
                    if(step_info['Object'] == "SAPMV45A:0101"):
                        print("Check");

                    # Check if TCode Objects Exists
                    if tcode_status == "Found":
                        # Find Object for the step and create Test Step and TestStep Action Entry
                        df = Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, step_info, df)
                    else:
                        # PENDING CODE
                        # Use Learn to get Objects
                        # exe_status = Invoke_Certify_Process(logger, username, password)
                        # if(exe_status == "error"):
                        #     logger.error("Error in Certify Process invoking Map File")
                        #     return

                        #df = Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, step_info, df)
                        logger.info(f"TCode Not Found in Certify Repository => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                    # Increment Sequence count
                    CertifySequence += 1

                # Old Logic for Old Step JSON - keeping backup - Anu - 16 April 2025
                # # Iterate through each window
                # for window in section.get('Windows', []):
                #     screen_info = {
                #         "Screen": window.get('Screen'),
                #         "Window Name": window.get('Window Name'),
                #         "Screen Number": window.get('screen number'),
                #         "Steps": window.get('steps', [])
                #     }

                #     # Handle SAP Main issue
                #     if(screen_info['Screen'] == "SAPMain" and screen_info['Window Name'] == "SAP Main"):
                #         screen_info['Screen'] = "SAP Main"

                #     # Iterate through each step
                #     for step in screen_info['Steps']: #window.get('steps', [])
                #         step_info = {
                #             "Step": step.get('Step'),
                #             "Object": step.get('Object'),
                #             "ObjectName": step.get('ObjectName'),
                #             "Action": step.get('Action'),
                #             "Action Description": step.get('ActionDescription')
                #         }

    	        #         # Ignore Validate and Check Log Steps
                #         if ('Validate' in step_info['Action'] or 'Validate' in step_info['ObjectName'] or 'Validation' in step_info['ObjectName']):
                #             df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, screen_info, step_info, "Validation Step")
                #             continue;
                            
                #         if ('Log' in step_info['ObjectName']):
                #             df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, screen_info, step_info, "Check Log Step")
                #             continue;
                            
                #         # Fix Completion Button
                #         if(step_info['Object'] == "GuiCButton.PBENTER"):
                #             df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, screen_info, step_info, "GuiCButton.PBENTER")
                #             continue;
                        
                #         if(step_info['Object'] == "SAPMV45A:0101"):
                #             print("Check");

                #         # Check if TCode Objects Exists
                #         if tcode_status == "Found":
                #             # Find Object for the step and create Test Step and TestStep Action Entry
                #             df = Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, screen_info, step_info, df)
                #         else:
                #             # PENDING CODE
                #             # Use Learn to get Objects
                #             # exe_status = Invoke_Certify_Process(logger, username, password)
                #             # if(exe_status == "error"):
                #             #     logger.error("Error in Certify Process invoking Map File")
                #             #     return

                #             #df = Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, screen_info, step_info, df)
                #             logger.info(f"TCode Not Found in Certify Repository => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                #         # Increment Sequence count
                #         CertifySequence += 1

    except Exception as e:
        logger.error(f"Error processing JSON file: {e}")

    return df, ProcessList;

# Process JSON File one by one       
def process_json_file_old_format(file_path, step_name, sap_screen, logger1, conn1, cursor1, df1, ProcessList):
    try:
        global logger;
        logger = logger1;

        global conn;
        conn = conn1;

        global cursor;
        cursor = cursor1;

        global df;
        df = df1

         #Check if TCode exist in certify liberary
        tcode_status = check_if_tcode_exist(sap_screen, conn)

        #Start JSON Processing
        with open(file_path, 'r') as file:
            sections = json.load(file)

            # Create ProcessID
            ProcessName = sap_screen + "_" + sections[0]['name']
            ProcessID = Create_Process(cursor, conn, ProcessName)
            new_entry = pd.DataFrame([[step_name, sap_screen,ProcessID]], columns=["Step_Name", "SAP_Screen" ,"ProcessID"])
            ProcessList = pd.concat([ProcessList, new_entry], ignore_index=True)

            logger.info(f"Processing SAP Screen = {sap_screen} => ProcessID = {ProcessID}")

            CertifySequence = 0

            # # New Logic for Processing new Step JSON File - Anu - 16 April 2025
            # for section in sections:
            #     # Iterate through each window
            #     for step in section.get('steps', []):
            #         step_info = {
            #             "Step": step.get('Step'),
            #             "Object": step.get('Object'),
            #             "ObjectName": step.get('ObjectName'),
            #             "Screen": step.get('Screen'),
            #             "ScreenName": step.get('Screen Name'),
            #             "Action": step.get('Action'),
            #             "Action Description": step.get('ActionDescription')
            #         }                    

            #         if(step_info['Object'] == "GuiTextField.RV45A-KWMENG"):
            #             print("step_info['Object']: ", step_info['Object'])

            #         # Ignore Validate and Check Log Steps
            #         if ('Validate' in step_info['Action'] or 'Validate' in step_info['ObjectName'] or 'Validation' in step_info['ObjectName']):
            #             df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, step_info, "Validation Step")
            #             continue;
                        
            #         if ('Log' in step_info['ObjectName']):
            #             df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, step_info, "Check Log Step")
            #             continue;
                        
            #         # Fix Completion Button
            #         if(step_info['Object'] == "GuiCButton.PBENTER"):
            #             df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, step_info, "GuiCButton.PBENTER")
            #             continue;
                    
            #         if(step_info['Object'] == "SAPMV45A:0101"):
            #             print("Check");

            #         # Check if TCode Objects Exists
            #         if tcode_status == "Found":
            #             # Find Object for the step and create Test Step and TestStep Action Entry
            #             df = Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, step_info, df)
            #         else:
            #             # PENDING CODE
            #             # Use Learn to get Objects
            #             # exe_status = Invoke_Certify_Process(logger, username, password)
            #             # if(exe_status == "error"):
            #             #     logger.error("Error in Certify Process invoking Map File")
            #             #     return

            #             #df = Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, step_info, df)
            #             logger.info(f"TCode Not Found in Certify Repository => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

            #         # Increment Sequence count
            #         CertifySequence += 1

            #Old Logic for Old Step JSON - keeping backup - Anu - 16 April 2025
            # Iterate through each window
            for section in sections:
                for window in section.get('Windows', []):
                    screen_info = {
                        "Screen": window.get('Screen'),
                        "Window Name": window.get('Window Name'),
                        "Screen Number": window.get('screen number'),
                        "Steps": window.get('steps', [])
                    }

                    # Handle SAP Main issue
                    if(screen_info['Screen'] == "SAPMain" and screen_info['Window Name'] == "SAP Main"):
                        screen_info['Screen'] = "SAP Main"

                    # Iterate through each step
                    for step in screen_info['Steps']: #window.get('steps', [])
                        step_info = {
                            "Step": step.get('Step'),
                            "Object": step.get('Object'),
                            "ObjectName": step.get('ObjectName'),
                            "Action": step.get('Action'),
                            "Action Description": step.get('ActionDescription')
                        }

                        # Ignore Validate and Check Log Steps
                        if ('Validate' in step_info['Action'] or 'Validate' in step_info['ObjectName'] or 'Validation' in step_info['ObjectName']):
                            df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, screen_info, step_info, "Validation Step")
                            continue;
                            
                        if ('Log' in step_info['ObjectName']):
                            df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, screen_info, step_info, "Check Log Step")
                            continue;
                            
                        # Fix Completion Button
                        if(step_info['Object'] == "GuiCButton.PBENTER"):
                            df = Add_Fail_In_Statistics_File(df, step_name, sap_screen, screen_info, step_info, "GuiCButton.PBENTER")
                            continue;
                        
                        if(step_info['Object'] == "SAPMV45A:0101"):
                            print("Check");

                        # Check if TCode Objects Exists
                        if tcode_status == "Found":
                            # Find Object for the step and create Test Step and TestStep Action Entry
                            df = Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, screen_info, step_info, df)
                        else:
                            # PENDING CODE
                            # Use Learn to get Objects
                            # exe_status = Invoke_Certify_Process(logger, username, password)
                            # if(exe_status == "error"):
                            #     logger.error("Error in Certify Process invoking Map File")
                            #     return

                            #df = Process_JSON_ScreenSteps_ObjectsFound(step_name, sap_screen, ProcessID, CertifySequence, screen_info, step_info, df)
                            logger.info(f"TCode Not Found in Certify Repository => {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

                        # Increment Sequence count
                        CertifySequence += 1

    except Exception as e:
        logger.error(f"Error processing JSON file: {e}")

    return df, ProcessList;
