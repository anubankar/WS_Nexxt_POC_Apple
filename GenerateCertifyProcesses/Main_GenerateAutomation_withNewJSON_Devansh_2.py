import pandas as pd
import openai
import json
import re
from dotenv import load_dotenv
import os
from collections import defaultdict
from neo4j import GraphDatabase
import logging
from CallLlms import CallforLLm

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

#from Find_Objects import NarrativeProcessor  # Import the NarrativeProcessor class
#Load env
load_dotenv()
os.getenv('OPENAI_API_KEY')
# Define prompt details

#print(prompt)
sysprompt = "You are an AI that converts descriptions into structured JSON steps."

tcode_program_mapping = {'VA01':'SAPMV45A'}
parent_object_id = 4889286  # ObjectID for SAPMV45A:0101
field_string = 'order_type', 'sales_organization', 'distribution_channel', 'division', 'sold_to_party', 'ship_to_party', 
'cust_reference', 'material', 'quantity', 'plant', 'payment_term', 'inco_term_1'

# Load Excel file
file_path = "TestCases_Input/Standard Export Sales Order Flow_First2.xlsx"  # Update with actual file path
df = pd.read_excel(os.path.join(os.path.dirname(__file__), file_path))

# Iterate through each row in the DataFrame
for index, row in df.iterrows():
    # Extract the description for each step
    description = row["Description"]  # Ensure the column name matches your Excel sheet
    sap_screen = row["SAP Screen"]
    expected_result = row["Expected Result"]
    step_name = row["Step Name"]
    
    #System Prompt
    system_prompt = """
    You are an expert SAP automation assistant. Your job is to extract only the field names from SAP test case descriptions. 
    Return a clean Python list of field names in snake_case format, with no extra explanations or output. 
    Ignore all other content, and do not return any headings, bullet points, or surrounding text — only the list.
    """
    # Prompt    
    usrprompt = f"""
    Given the following SAP test case step description, extract only the list of unique SAP Certify field names (e.g., 'order_type', 'sales_organization', etc.). Do not include any explanation or other text. Only return a Python list of field names in snake_case.

    Description:\n {description}
    
    """

    # # Call OpenAI GPT-4o API
    # response = openai.chat.completions.create(
    #     model="gpt-4o-mini",
    #     messages=[{"role": "system", "content": sysprompt},
    #                 {"role": "user", "content": usrprompt}],
    #     temperature= 0.0
    # )

    # Extract JSON output from OpenAI response
    field_list = CallforLLm(sysprompt, usrprompt, "gpt-4o-mini")
    field_list = field_list.replace("```python", "").replace("```", "").strip()
    print(field_list)
   
    # # Save JSON output to a file
    # output_file = os.path.join("Output_JSON_Files", f"{step_name}_{sap_screen}.json")
    # with open(output_file, "w") as f:
    #     f.write(json_output)
        
