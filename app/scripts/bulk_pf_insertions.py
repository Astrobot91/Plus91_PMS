import os
import pandas as pd
from datetime import datetime
import psycopg2
from psycopg2.extras import execute_values

# Database connection parameters (replace with your actual values)
db_params = {
    'dbname': 'plus91_cms',
    'user': 'postgres',
    'password': '+91atplus91',
    'host': 'plus91-db-instance-instance-1.c128qeo8eoe3.ap-south-1.rds.amazonaws.com',
    'port': '5432'
}

# Path to the DATA_CLEANING_NEW directory (replace with your actual path)
data_cleaning_new_path = '/home/admin/Plus91Backoffice/plus91_management/app/scripts/keynote_clients_data'

# Function to retrieve account_id for a given broker_code
def get_account_id(broker_code, cursor):
    """Queries the client_details table to get the account_id for a broker_code."""
    cursor.execute("SELECT account_id FROM client_details WHERE broker_code = %s LIMIT 1", (broker_code,))
    result = cursor.fetchone()
    return result[0] if result else None

# Establish database connection
try:
    conn = psycopg2.connect(**db_params)
    cursor = conn.cursor()
    print("Database connection established.")
except Exception as e:
    print(f"Failed to connect to database: {e}")
    exit()

# Get list of broker_code folders
broker_code_folders = [
    f for f in os.listdir(data_cleaning_new_path)
    if os.path.isdir(os.path.join(data_cleaning_new_path, f))
]

# Process each broker_code folder
for broker_code in broker_code_folders:
    if broker_code == 'MK100':
        print(f"Processing broker_code: {broker_code}")
        
        # Get the associated account_id
        account_id = get_account_id(broker_code, cursor)
        if not account_id:
            print(f"No account found for broker_code {broker_code}. Skipping.")
            continue
        
        # Define the holdings folder path
        holdings_path = os.path.join(data_cleaning_new_path, broker_code, 'holdings')
        if not os.path.exists(holdings_path):
            print(f"Holdings folder not found for {broker_code}. Skipping.")
            continue
        
        # Get list of Excel files in the holdings folder
        excel_files = [f for f in os.listdir(holdings_path) if f.endswith('.xlsx')]
        
        for excel_file in excel_files:
            print(f"Processing file: {excel_file}")
            
            # Parse snapshot_date from the filename (e.g., 2024-05-31.xlsx -> 2024-05-31)
            date_str = os.path.splitext(excel_file)[0]
            try:
                snapshot_date = datetime.strptime(date_str, '%Y-%m-%d').date()
            except ValueError:
                print(f"Invalid date format in filename {excel_file}. Skipping.")
                continue
            
            # Read the Excel file
            file_path = os.path.join(holdings_path, excel_file)
            try:
                df = pd.read_excel(file_path)
            except Exception as e:
                print(f"Error reading {excel_file}: {e}")
                continue
            
            # Verify required columns are present
            required_columns = ['trading_symbol', 'quantity', 'market_value']
            if not all(col in df.columns for col in required_columns):
                print(f"Missing required columns in {excel_file}. Skipping.")
                continue
            
            # Aggregate data by trading_symbol, summing quantity and market_value
            df_grouped = df.groupby('trading_symbol', as_index=False).agg({
                'quantity': 'sum',
                'market_value': 'sum'
            })
            
            # Prepare data for insertion
            data = [
                (account_id, 'single', snapshot_date, row['trading_symbol'], row['quantity'], row['market_value'])
                for _, row in df_grouped.iterrows()
            ]
            
            # Define the SQL insert query
            insert_query = """
            INSERT INTO account_actual_portfolio (owner_id, owner_type, snapshot_date, trading_symbol, quantity, market_value)
            VALUES %s
            """
            
            # Perform the bulk insert
            try:
                execute_values(cursor, insert_query, data)
                print(f"Inserted {len(data)} aggregated rows from {excel_file}.")
            except Exception as e:
                print(f"Error inserting data from {excel_file}: {e}")
                conn.rollback()  # Roll back on error
                continue
        
        # Commit changes after processing all files for this broker_code
        conn.commit()
        print(f"Completed processing for broker_code {broker_code}.")

# Clean up
cursor.close()
conn.close()
print("Database connection closed.")