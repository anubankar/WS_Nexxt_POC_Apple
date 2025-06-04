import logging
logger = logging.getLogger(__name__)
from Db_Connections import connect_to_database
import pandas as pd

# Connect to SQL Server DB
conn = connect_to_database()
cursor = conn.cursor(as_dict=True)

# Create Main Process
def create_main_process(ProcessFolderID, SubProcessList, UserID, conn1, cursor1, logger1, MainProcessName, ComponentActionID, ApplicationVersionID, InterfaceLibraryID, ComponentActionParmsID, ObjectID, stats_df):
    try:
        global logger;
        logger = logger1;

        global conn;
        conn = conn1;

        global cursor;
        cursor = cursor1;

        SubProcessName = '';
        SubProcessID = 0;
        CertifySequence = 0;
        ProcessID = 0;

        # Delete if Process already exists in ProcessFolder
        sql = f"""delete from Process where Name = '{MainProcessName}' and ProcessFolderID = {ProcessFolderID}"""
        cursor.execute(sql)
        conn.commit()

        # Insert into process
        sql = f"""INSERT INTO Process (Name, ProcessFolderID, ResultLogStatusID) VALUES ('{MainProcessName}', {ProcessFolderID},1)""";
        cursor.execute(sql)
        conn.commit()
        ProcessID = cursor.lastrowid

        # Loop and Add Test Step for Each SubProcess
        for index, row in SubProcessList.iterrows():
           
            SubProcessID = row['ProcessID']  # Read ProcessID from the DataFrame
            SubProcessName = ''

            # Get Process Name
            sql = f"""Select Name from Process where ProcessID = {SubProcessID}"""
            cursor.execute(sql)
            object_results = cursor.fetchall()
            if(object_results):
                SubProcessName = object_results[0]['Name']

            # Insert into TestStep
            narrative = f"Execute {SubProcessName} Process"

            sql = f"""INSERT INTO TestStep (
            [ProcessID] , [ComponentActionID] ,[ApplicationVersionID] ,[Narrative] ,[InterfaceLibraryID]
            ,[ObjectID],[CertifySequence],[Skip],[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy]) 
            VALUES (
                (SELECT Top 1 ProcessID FROM Process WHERE Name = '{MainProcessName}' and ProcessFolderID = {ProcessFolderID}), {ComponentActionID}, {ApplicationVersionID}, 
                '{narrative}', {InterfaceLibraryID}, {ObjectID}, {CertifySequence}, 0, GETDATE(), {UserID}, GETDATE(), {UserID}
            )"""
            cursor.execute(sql)
            conn.commit()
            TestStepID = cursor.lastrowid

            # Insert into TestStepAction
            sql = f"""INSERT INTO [dbo].[TestStepAction]
            ([TestStepID], [CertifySequence],[ComponentActionParmsID],[CertifyValue],[CreatedDt],[CreatedBy],[ModifiedDt],[ModifiedBy])
            VALUES 
            ({TestStepID}, {CertifySequence}, {ComponentActionParmsID}, '{SubProcessName}', GETDATE(), {UserID}, GETDATE(), {UserID})"""
            cursor.execute(sql)
            conn.commit()

            CertifySequence += 1

        logger.info(f"MainProcess Created. MainProcessID = {ProcessID}")

        # Add to statistics DF
        notes = f"MainProcess Created. MainProcessID = {ProcessID}";
        status = "Pass";
        new_data = [{
            "Step_Name": "MainProcess", 
            "SAP_Screen": "N/A", 
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
        updated_df = pd.concat([new_df, stats_df], ignore_index=True)        
        return updated_df        
    except Exception as e:
        logger.error(f"Error Generating MainProcess: {str(e)}")
        raise

