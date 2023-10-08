import sqlite3
import pandas as pd

# Connect to the SQLite database
conn = sqlite3.connect('/Users/ZoesComputer/Desktop/Midi Creation/midi_features.db')

# Query to fetch the first few rows from the PadFeatures table
query = "SELECT * FROM PadFeatures LIMIT 5;"
df = pd.read_sql_query(query, conn)

# Close the connection
conn.close()

print(df)
