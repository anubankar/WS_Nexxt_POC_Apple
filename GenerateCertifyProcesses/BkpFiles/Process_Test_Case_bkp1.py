# Process_Test_Case.py -> Read excel test case. Later on it can have additional functions to read different test case format. Create JSON
import pandas as pd
import openai
import json
import re
from dotenv import load_dotenv
import os
from Process_JSON import process_json_file
# Load env
load_dotenv()
os.getenv('OPENAI_API_KEY')

# Define prompt details
base_prompt = """
Convert the following manual test case into a Worksoft Certify automation script in JSON format.
Take SAP Screen Name(for e.g. VA01), then identify its SAP screens and then identify fields based on description provided
Only use fields in description. Do not add additional fields. For e.g. If Ship To Party it not in description then do not add step for it
Each JSON must be organized screen wise further have its associated steps.

Most Imp:
- Start from 'SAP Main' as first screen, then add remaining screens and fields. On SAP main screen, add step to enter SAP TCode which is provided in SAP Screen Name(for e.g. VA01). 'Object' for 'SAP Ok Code' is 'GuiOkCodeField.wnd[0]/tbar[0]/okcd'. 
- Identify screen wise fields and seperate it accordingly 
- Dont add any other additional fields which is not there in Description from the excel.
- Dont add all steps in one screen, identify from the description and add steps beloging to different screen in screen wise distribution. 
- Use GuiCTextField instead of GuiTextField and  GuiButton instead of GuiCButton in 'Object'
- Use GuiButton for Enter , continue and save for step 'Object'
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

Key Requirements:  
- Ensure each step contains:
  - Screen ID (e.g., SAPMV45A:0101)
  - Window Name
  - GUI Object ID (e.g., GuiCTextField.VBAK-AUART)
  - Action (e.g., Enter text, Press Button)
  - Step Sequence Number (Strict order)
  - Description (Clear explanation of the action)
 
Rules:
- Identify screen wise feilds and seperate it accordingly 
- Dont add any other additional feilds which is not there in Description from the excel 
- Do not merge multiple numbered lines in one JSON.
- Maintain proper JSON formatting with indentation.
-Add one step at the end as "Choose Save Document. Make a note of the sales order number" if there is "create" in the description. 
  for eg "Create Sales Document", "Create Delivery", "Create Group" etc.
"""

# Load Excel file
file_path = "TestCases_Input\\Standard Export Sales Order Flow2.xlsx"  # Update with actual file path
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
    # Call OpenAI GPT-4o API
    usrprompt = base_prompt + testprompt          
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
        
    # Process the generated JSON => Process_JSON.py
    #process_json_file(output_file, sap_screen)




