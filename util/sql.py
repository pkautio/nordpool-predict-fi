import sqlite3
import pandas as pd

# A set of functions to work with the predictions SQLite database

# Suppress FutureWarning messages from pandas for now
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

# "FutureWarning: The behavior of DataFrame concatenation with empty or all-NA entries is deprecated. In a future version, this will no longer exclude empty or all-NA columns when determining the result dtypes. To retain the old behavior, exclude the relevant entries before the concat operation."
# Reason: We are already excluding empty or all-NA entries before the concat operation to retain the old behavior. No need to log this warning.

def normalize_timestamp(ts):
    '''
    Internal function to convert a timestamp string into a datetime object and format it as an ISO8601 string. This function is crucial for ensuring timestamp consistency across database operations.
    '''
    # Convert to datetime object using pandas, then format as ISO8601 string
    return pd.to_datetime(ts).strftime('%Y-%m-%d %H:%M:%S')

def db_update(db_path, df):
    '''
    Update existing rows or insert new rows into the 'prediction' table in the specified SQLite database based on the input DataFrame. Returns two DataFrames: one containing inserted rows and another containing updated rows. Does not handle duplicate timestamps. Does not delete rows or columns, always inserts (with defaults) or updates (with new values given).
    '''
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    updated_rows = pd.DataFrame()
    inserted_rows = pd.DataFrame()

    # Normalize timestamp in the dataframe before processing
    df['timestamp'] = df['timestamp'].apply(normalize_timestamp)

    for index, row in df.iterrows():
        # Timestamp is already normalized
        cur.execute("SELECT * FROM prediction WHERE timestamp=?", (row['timestamp'],))
        data = cur.fetchone()
        if data is not None:
            # Update existing row
            for col in df.columns:
                if pd.notnull(row[col]):
                    cur.execute(f"UPDATE prediction SET \"{col}\"=? WHERE timestamp=?", (row[col], row['timestamp']))
            updated_rows = pd.concat([updated_rows, df.loc[[index]]], ignore_index=True)
        else:
            # Insert new row
            cols = ', '.join(f'"{col}"' for col in df.columns)
            placeholders = ', '.join('?' * len(df.columns))
            cur.execute(f"INSERT INTO prediction ({cols}) VALUES ({placeholders})", tuple(row))
            inserted_rows = pd.concat([inserted_rows, df.loc[[index]]], ignore_index=True)

    conn.commit()
    conn.close()

    return inserted_rows, updated_rows

def db_query(db_path, df):
    '''
    Query the 'prediction' table in the specified SQLite database based on timestamps specified in the input DataFrame. Returns a DataFrame with the query results, sorted by timestamp.
    '''
    # Normalize timestamps in query dataframe
    if 'timestamp' not in df.columns:
        print("timestamp is not a column in the DataFrame")
    else:
        df['timestamp'] = df['timestamp'].apply(normalize_timestamp)

    conn = sqlite3.connect(db_path)

    result_frames = []  # List to store each chunk of dataframes
    for timestamp in df['timestamp']:
        # Timestamp is already normalized
        data = pd.read_sql_query(f"SELECT * FROM prediction WHERE timestamp='{timestamp}'", conn)
        if not data.empty and not data.isna().all().all():  # Exclude empty dataframes and dataframes with all-NA entries
            result_frames.append(data)

    result = pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame()
    result = result.sort_values(by='timestamp', ascending=True)

    conn.close()

    return result

def db_query_all(db_path):
    '''
    Query all rows from the 'prediction' table in the specified SQLite database. Returns a DataFrame with the query results.
    '''
    conn = sqlite3.connect(db_path)
    query = "SELECT * FROM prediction"
    data = pd.read_sql_query(query, conn)
    conn.close()
    return data
    
"This script is not meant to be executed directly."
