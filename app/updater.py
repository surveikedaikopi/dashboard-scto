import os
os.chdir('/app')
from module import *
import time
import schedule
from datetime import datetime



def update():
    # load list_surveys table
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query('SELECT * FROM list_surveys', conn)
    conn.close()

    # get parameters
    for i in range(len(df)):
        survey_name = df.loc[i,'Survey Name']
        last_download = df.loc[i,'Last Download']
        list_location = json.loads(df.loc[i,'List Location'])
        targets = json.loads(df.loc[i,'Target'])
        target_column = df.loc[i,'Target Column']
        try:
            target_column_values = json.loads(df.loc[i,'Target Column Values'])
        except:
            target_column_values = None
        try:
            decoder = json.loads(df.loc[i,'Decoder'])
        except:
            decoder = None
    
        # download data
        df = download_data(survey_name, decoder)
        
        # data preprocessing
        generate_datalake(survey_name, df, list_location, targets, target_column, target_column_values)
        
        # update last_download in list_surveys table
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        update_sql = '''
            UPDATE list_surveys 
            SET [Last Download] = ?
            WHERE [Survey Name] = ?
        '''
        last_download = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(update_sql, (last_download, survey_name))
        conn.commit()
        conn.close()


# ------------------------------------------------------------------------------------

# Schedule the job to run every hour
schedule.every().hour.do(update)

# Set the start and end time for the schedule
for i in range(7,22):
    if i < 10:
        schedule.every().day.at(f"0{i}:00").do(update)
        schedule.every().day.at(f"0{i}:30").do(update)
    else:
        schedule.every().day.at(f"{i}:00").do(update)
        schedule.every().day.at(f"{i}:30").do(update)

# Run the scheduler continuously
while True:
    schedule.run_pending()
    time.sleep(1)
