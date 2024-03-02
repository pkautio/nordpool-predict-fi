import sqlite3
import pandas as pd
import sys

# A set of functions to work with the predictions SQLite database

# Suppress FutureWarning messages from pandas for now
import warnings
warnings.filterwarnings('ignore', category=FutureWarning)

def normalize_timestamp(ts):
    '''
    Converts a timestamp string into a datetime object, ensuring it is timezone-aware (UTC),
    and formats it as an ISO8601 string. This standardized format is crucial for consistency 
    across database operations, especially when dealing with the TIMESTAMP type in the schema.
    
    Parameters:
    - ts: A timestamp string that may or may not include timezone information.
    
    Returns:
    - A string representing the timestamp in ISO8601 format with UTC timezone information.
    '''
    # Convert to datetime object using pandas
    dt = pd.to_datetime(ts)
    
    # If the datetime object is naive (no timezone), localize it to UTC
    if dt.tzinfo is None:
        dt = dt.tz_localize('UTC')
    else:
        # If it already has a timezone, convert it to UTC
        dt = dt.tz_convert('UTC')
    
    # Format as ISO8601 string with timezone information
    return dt.isoformat()

def db_update(db_path, df):
    '''
    Update existing rows or insert new rows into the 'prediction' table in the specified SQLite database based on the input DataFrame. Returns two DataFrames: one containing inserted rows and another containing updated rows. Does not handle duplicate timestamps. Does not delete rows or columns, always inserts (with defaults) or updates (with new values given).
    '''
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
    except sqlite3.Error as e:
        print(f"SQLite connection error: {e}")
        sys.exit(1)

    updated_rows = pd.DataFrame()
    inserted_rows = pd.DataFrame()

    # Normalize timestamp in the dataframe before processing
    df['Timestamp'] = df['Timestamp'].apply(normalize_timestamp)

    for index, row in df.iterrows():
        # Timestamp is already normalized
        cur.execute("SELECT * FROM prediction WHERE Timestamp=?", (row['Timestamp'],))
        data = cur.fetchone()
        if data is not None:
            # Update existing row
            for col in df.columns:
                if pd.notnull(row[col]):
                    cur.execute(f"UPDATE prediction SET \"{col}\"=? WHERE timestamp=?", (row[col], row['Timestamp']))
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
    if 'Timestamp' not in df.columns:
        print("Timestamp is not a column in the DataFrame")
    else:
        df['Timestamp'] = df['Timestamp'].apply(normalize_timestamp)

    try:
        conn = sqlite3.connect(db_path)
    except Exception as e:
        print(f"Error preparing for SQLite query: {e}")
        sys.exit(1)
        
    result_frames = []  # List to store each chunk of dataframes
    for timestamp in df['Timestamp']:
        # Timestamp is already normalized
        data = pd.read_sql_query(f"SELECT * FROM prediction WHERE timestamp='{timestamp}'", conn)
        if not data.empty and not data.isna().all().all():  # Exclude empty dataframes and dataframes with all-NA entries
            result_frames.append(data)

    result = pd.concat(result_frames, ignore_index=True) if result_frames else pd.DataFrame()
    # print(result)
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

def add_prediction_snapshot(db_path, predictions):
    """
    Insert a new prediction snapshot and its details into the database.
    
    Parameters:
    - db_path: Path to the SQLite database file.
    - predictions: List of dictionaries, where each dictionary contains the timestamp and the predicted price.
    """
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Insert into prediction_snapshot table
        cur.execute("INSERT INTO prediction_snapshot (snapshot_date) VALUES (CURRENT_TIMESTAMP)")
        snapshot_id = cur.lastrowid

        # Insert each prediction detail
        for prediction in predictions:
            cur.execute("INSERT INTO snapshot_details (snapshot_id, timestamp, PricePredict_cpkWh) VALUES (?, ?, ?)",
                        (snapshot_id, prediction['timestamp'], prediction['PricePredict_cpkWh']))

        conn.commit()
    except sqlite3.Error as e:
        print(f"SQL: Error while adding a prediction snapshot: {e}")
    finally:
        conn.close()
        
def fetch_prediction_snapshots(db_path, limit=4):
    """
    Fetch the last N prediction snapshots from the database.
    
    Parameters:
    - db_path: Path to the SQLite database file.
    - limit: Number of recent snapshots to retrieve.
    
    Returns:
    - A list of dictionaries, each representing a snapshot with its details.
    """
    snapshots = []
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()

        # Fetch the last N snapshots
        cur.execute("""
            SELECT ps.snapshot_id, ps.snapshot_date, sd.timestamp, sd.PricePredict_cpkWh
            FROM prediction_snapshot ps
            JOIN snapshot_details sd ON ps.snapshot_id = sd.snapshot_id
            ORDER BY ps.snapshot_date DESC, sd.timestamp
            LIMIT ?
        """, (limit,))

        rows = cur.fetchall()
        for row in rows:
            snapshots.append({
                'snapshot_id': row[0],
                'snapshot_date': row[1],
                'timestamp': row[2],
                'PricePredict_cpkWh': row[3],
            })
    except sqlite3.Error as e:
        print(f"SQL: Error while fetching snapshots: {e}")
    finally:
        conn.close()

    return snapshots
    
"This script is not meant to be executed directly."
