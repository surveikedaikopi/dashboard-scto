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
        survey_name = df.loc[i,'Survey_Name']
        last_download = df.loc[i,'Last_Download']
        scto_account = df.loc[i,'SCTO_Account']
        scto_password = df.loc[i,'SCTO_Password']
        try:
            target_kelurahan = json.loads(df.loc[i,'target_kelurahan'])
        except:
            target_kelurahan = df.loc[i,'target_kelurahan']
        target_column = df.loc[i,'target_column']
        try:
            target_column_values = json.loads(df.loc[i,'target_column_values'])
        except:
            target_column_values = None
        try:
            decoder = json.loads(df.loc[i,'decoder'])
        except:
            decoder = None
    
        # download data
        df = download_data(survey_name, decoder, scto_account, scto_password)
        
        # data preprocessing
        generate_datalake(survey_name, df, target_kelurahan, target_column, target_column_values)
        
        # update last_download in list_surveys table
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        update_sql = '''
            UPDATE list_surveys 
            SET Last_Download = ?
            WHERE Survey_Name = ?
        '''
        last_download = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        cursor.execute(update_sql, (last_download, survey_name))
        conn.commit()
        conn.close()



# ------------------------------------------------------------------------------------

# Schedule the job to run every hour
schedule.every().hour.do(update)

# Set the start and end time for the schedule
for i in range(6,22):
    if i < 10:
        schedule.every().day.at(f"0{i}:00").do(update)
    else:
        schedule.every().day.at(f"{i}:00").do(update)

# Run the scheduler continuously
while True:
    schedule.run_pending()
    time.sleep(1)
