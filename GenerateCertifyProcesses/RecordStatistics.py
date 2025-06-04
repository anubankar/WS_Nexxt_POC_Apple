import pandas as pd
import pymssql
import openai
import json
import re
from dotenv import load_dotenv
import os
import sys
import logging
from datetime import datetime

# Add Data to DF
def add_data_to_df(df, new_data):
    """Adds new data to the existing DataFrame."""
    try:
        # The new_data should be a list of dictionaries, where each dictionary represents a row of data to be added to the DataFrame.
        # Each dictionary should have keys corresponding to the DataFrame's column names.
        # Example format for new_data:
        # new_data = [
        #     {"Column1": value1, "Column2": value2, ...},
        #     {"Column1": value3, "Column2": value4, ...},
        #     ...
        # ]
        new_df = pd.DataFrame(new_data)
        updated_df = pd.concat([df, new_df], ignore_index=True)
        return updated_df
    except Exception as e:
        return df

def create_statistics_file(df, file_name, logger):
    """Creates a CSV file from the provided data."""
    try:
        statistics_folder = "Statistics"  # Define the statistics folder
        if not os.path.exists(statistics_folder):
            os.makedirs(statistics_folder)  # Create the folder if it doesn't exist

        file_path = os.path.join(statistics_folder, file_name)  # Create the full file path
        df.to_csv(file_path, index=False)  # Save the DataFrame to the specified CSV file
        logger.info(f"Statistic CSV file '{file_path}' created successfully.")
    except Exception as e:
        logger.error(f"Error creating Statistic CSV file: {str(e)}")

