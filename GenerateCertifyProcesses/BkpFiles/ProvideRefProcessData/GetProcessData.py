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
from Invoke_Learn import Invoke_Certify_Process
from RecordStatistics import add_data_to_df

# Load env
load_dotenv()
os.getenv('OPENAI_API_KEY')

# Hard Coding
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Connect to SQL Server DB
conn = connect_to_database()
cursor = conn.cursor(as_dict=True)

# Use Reference ProcessID fields to generate JSON
def Get_ProcessData(ProcessID: int):
    sql = f"""
select t1.CreatedDt, t2.ProcessID, t2.TestStepID, t2.Narrative,
t2.ComponentActionID, t6.Name as ComponentActionName,
t2.InterfaceLibraryID, 
t5.ComponentID, t5.PhysicalName as ComponentPhysicalName,
t2.ObjectID, t4.Name as ObjectName, t4.ParentID as ObjectParentiD, t7.PhysicalName as ObjectScreenName,
t2.CertifySequence as TestStepSequence,
t1.TestStepActionID, t1.CertifySequence as TestStepActionSequence, 
t1.ComponentActionParmsID, 
t3.Name as ComponentActionParmsName,
t1.CertifyValue, t1.ExecProcessID
from TestStepAction t1, TestStep t2, ComponentActionParms t3, Object t4, Component t5, ComponentAction t6,  Object t7
where t1.TestStepID = t2.TestStepID and t1.ComponentActionParmsID = t3.ComponentActionParmsID
and t4.ComponentID = t5.ComponentID and t2.ObjectID = t4.ObjectID and t4.ParentID = t7.ObjectID
and t6.ComponentActionID = t2.ComponentActionID
and t2.ProcessID in ({ProcessID}) 
Order by t2.ProcessID, t1.CreatedDt"""
    cursor.execute(sql)
    results = cursor.fetchall()
    return results