import os
import json
import sqlite3
import numpy as np
import pandas as pd
from io import BytesIO
import streamlit as st
import geopandas as gpd
from st_aggrid import JsCode
from datetime import datetime
from dotenv import load_dotenv
from pysurveycto import SurveyCTOObject


load_dotenv()

WORK_DIR = 'app'
CONFIG_YAML = 'app/config.yaml'
JSON_DIR = 'app/json'
IMG_DIR = 'app/images'
DB_PATH = 'app/local.db'
TEMPLATE_FILE = 'app/templates.zip'
DECODER_FILE = 'app/decoder.xlsx'
SERVER_NAME = 'risetkedaikopi'
DASHBOARD_HOST = os.getenv('DASHBOARD_HOST')
SCTO_USERNAME = os.getenv('SCTO_USERNAME')
SCTO_PASSWORD = os.getenv('SCTO_PASSWORD')

# ----------------------------------------------------------------------------------------------------------------------------
# AUXILIARY FUNCTIONS

# page config
def set_page_config():
    if 'set_page_config' not in st.session_state:
        st.set_page_config(layout="wide")
        st.session_state.set_page_config = True

# load local lottie file
def get_json(file):
    with open(file, 'r') as f:
        out = json.load(f)
    return out

@st.cache_data
def get_lottie_wait():
    return get_json(os.path.join(JSON_DIR, 'coffee.json'))

# get table height
def get_table_height(data):
    if len(data) > 20:
        return 20 * 30
    else:
        return (1 + len(data)) * 30

# create empty 'list_surveys' table
def create_empty_table():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    sql_create_table = """
        CREATE TABLE IF NOT EXISTS list_surveys (
            Selection BOOLEAN,
            "Survey Name" TEXT,
            "Last Download" TIMESTAMP,
            "List Location" TEXT,
            "Target" TEXT,
            "Target Column" STR, 
            "Target Column Values" TEXT,
            Decoder TEXT
        );
    """
    cursor.execute(sql_create_table)
    conn.commit()
    conn.close()

# get surveys table
def get_survey_names():
    # get table
    conn = sqlite3.connect(DB_PATH)
    df = pd.read_sql_query(f'SELECT * FROM list_surveys', conn)
    df['Selection'] = df['Selection'].astype('bool')
    df = df.sort_values('Last Download', ascending=False)
    conn.close()
    # get values
    list_surveys, download_time, targets = [], [], []
    for i in range(len(df)):
        list_surveys.append(df.loc[i,'Survey Name'])
        download_time.append(df.loc[i,'Last Download'])
        targets.append(df.loc[i,'Target Column'])
    update_time = {k:v for k,v in zip(list_surveys, download_time)}
    target_columns = {k:v for k,v in zip(list_surveys, targets)}
    return df, list_surveys, update_time, target_columns

# update surveys table
def update_surveys_table(survey_name, list_location, targets, target_column, target_column_values, decoder):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    insert_sql = '''
        INSERT INTO list_surveys ("Selection", "Survey Name", "Last Download", "List Location", "Target", "Target Column", "Target Column Values", "Decoder")
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    '''
    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(insert_sql, (False, survey_name, update_time, list_location, targets, target_column, target_column_values, decoder))
    conn.commit()
    conn.close()

# internal decoder
def get_internal_decoder():
    fields = pd.read_excel(DECODER_FILE, sheet_name='FIELDS')
    internal_decoder = {}
    for f in fields['FIELDS'].values:
        out = pd.read_excel(DECODER_FILE, sheet_name=f)
        out['CODE'] = out['CODE'].astype('str')
        out = out.set_index('CODE').to_dict()['LABEL']
        internal_decoder.update({f: out})
    return internal_decoder

# download
def download_data(survey_name, decoder):
    # build connection to SurveyCTO server
    scto = SurveyCTOObject(SERVER_NAME, SCTO_USERNAME, SCTO_PASSWORD)
    # donwload data as json
    res = scto.get_form_data(survey_name, format='json', shape='wide', review_status=['approved', 'rejected', 'pending'])
    # build dataframe
    df = pd.DataFrame(res)
    # used fields
    if 'CATATAN_QC' not in df.columns:
        df['CATATAN_QC'] = ''
    usecols = ['CATATAN_QC', 'PROV', 'KOTA_KAB', 'KEC', 'KEC_LAINNYA', 'KEL', 'KEL_LAINNYA', 'RW', 'RT', 'NAMA_KK', 'NAMA_RESPONDEN', 'USIA_KAT', 'NAMA_ENUM', 'JK', 'WILAYAH', 'review_status', 'KEY']
    cols_X = ['_'.join(i.split('_')[:-1]) for i in df.columns if i.split('_')[-1]=='X']
    usecols += [i for i in cols_X if i not in usecols]
    # remove suffix 'X'
    df.columns = ['_'.join(i.split('_')[:-1]) if i.split('_')[-1]=='X' else i for i in df.columns]
    # filter
    df = df[usecols]
    # fix empty data
    df['review_status'] = df['review_status'].replace('NONE', 'AWAITING')
    # decoding with internal decoder
    internal_decoder = get_internal_decoder()
    for f in internal_decoder.keys():
        df.loc[:,f] = df[f].map(internal_decoder[f])
        df[f] = df[f].fillna('TIDAK DIKENALI')
        df[f] = df[f].str.upper()
    # decoding with external decoder
    if decoder is not None:
        for f in decoder.keys():
            df.loc[:,f] = df[f].map(decoder[f])
            df[f] = df[f].fillna('TIDAK DIKENALI')
            df[f] = df[f].str.upper()
    # apply uppercase and remove whitespace at the end of the string
    for col in ['NAMA_RESPONDEN', 'NAMA_KK', 'NAMA_ENUM', 'PROV', 'KOTA_KAB', 'KEC', 'KEC_LAINNYA', 'KEL', 'KEL_LAINNYA']:
        df.loc[:,col] = df[col].str.upper().str.rstrip()
    # fix "LAINNYA" in KEC & KEL
    for f in ['KEC', 'KEL']:
        df[f] = df.apply(lambda x : x[f'{f}_LAINNYA'] if x[f] == 'TIDAK DIKENALI' else x[f], axis=1)
    # link KEY to Survey CTO server
    df['Link'] = df['KEY'].apply(lambda x : x.split('uuid:')[-1])
    df['Link'] = df['Link'].apply(lambda x : f'<a href="https://{SERVER_NAME}.surveycto.com/view/submission.html?uuid=uuid%3A{x}" target="_blank">link</a>')
    return df.drop(['KEC_LAINNYA', 'KEL_LAINNYA', 'KEY'], axis=1)

# generate datalake
def generate_datalake(survey_name, df, list_location, targets, target_column, target_column_values):

    # -------------------------------------------------------------------------------------------------
    # tabel rekapitulasi

    # temporary data (1)
    cols = ['PROV', 'KOTA_KAB', 'KEC', 'KEL']
    if target_column is not None:
        cols += [target_column]
    tmp1 = df.groupby(cols).size().reset_index()
    if target_column is not None:
        tmp1['loc_id'] = tmp1.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}_{x[target_column]}', axis=1)
    else:
        tmp1['loc_id'] = tmp1.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}', axis=1)
    # temporary data (2)
    tmp2 = df[df['review_status']=='APPROVED'].fillna(0).groupby(cols).size().reset_index()
    # temporary data (3)
    tmp3 = df[df['review_status']=='REJECTED'].fillna(0).groupby(cols).size().reset_index()
    # merge
    if len(tmp2) == 0:
        rekap = tmp1
        rekap['Approved'] = 0
    else:
        if target_column is not None:
            tmp2['loc_id'] = tmp2.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}_{x[target_column]}', axis=1)
        else:
            tmp2['loc_id'] = tmp2.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}', axis=1)
        rekap = pd.merge(tmp1, tmp2[['loc_id', 0]], how='left', on='loc_id')
    if len(tmp3) == 0:
        rekap['Rejected'] = 0
    else:
        if target_column is not None:
            tmp3['loc_id'] = tmp3.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}_{x[target_column]}', axis=1)
        else:
            tmp3['loc_id'] = tmp3.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}', axis=1)
        rekap = pd.merge(rekap, tmp3[['loc_id', 0]], how='left', on='loc_id')
    rekap = rekap.drop(['loc_id'], axis=1)
    rekap = rekap.fillna(0)
    # rename columns
    if target_column is not None:
        cols = ['Provinsi', 'Kabupaten/Kota', 'Kecamatan', 'Kelurahan', target_column, 'Sample', 'Approved', 'Rejected']
    else:
        cols = ['Provinsi', 'Kabupaten/Kota', 'Kecamatan', 'Kelurahan', 'Sample', 'Approved', 'Rejected']
    rekap.columns = cols
    # add more features
    rekap['Awaiting'] = rekap['Sample'] - rekap['Approved'] - rekap['Rejected']
    # set target
    rekap['Target'] = rekap['Kelurahan'].map(targets['KEL'])
    maxi = np.max([v for (k,v) in targets['KEL'].items()])
    rekap['Target'] = rekap['Target'].fillna(maxi).astype(int)
    if target_column is not None:
        rekap['Target'] = rekap[target_column].map(target_column_values) / 100 * rekap['Target']
        rekap['Target'] = np.ceil(rekap['Target']).astype('int')
    # deficit
    rekap['Deficit'] = rekap['Target'] - rekap['Approved']
    rekap['Deficit'] = np.where(rekap['Deficit']<0, 0, rekap['Deficit'])
    # reorder columns
    if target_column is not None:
        new_column_order = ['Provinsi', 'Kabupaten/Kota', 'Kecamatan', 'Kelurahan', target_column, 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    else:
        new_column_order = ['Provinsi', 'Kabupaten/Kota', 'Kecamatan', 'Kelurahan', 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    rekap = rekap[new_column_order]

    # -------------------------------------------------------------------------------------------------
    # table rekapitulasi up to province level
    
    if target_column is not None:
        tmp1 = df.groupby(['PROV', target_column]).size().reset_index()
        tmp1['loc_id'] = tmp1.apply(lambda x : f'{x.PROV}_{x[target_column]}', axis=1)
        tmp2 = df[df['review_status']=='APPROVED'].groupby(['PROV', target_column]).size().reset_index()
        tmp2['loc_id'] = tmp2.apply(lambda x : f'{x.PROV}_{x[target_column]}', axis=1)
        tmp3 = df[df['review_status']=='REJECTED'].groupby(['PROV', target_column]).size().reset_index()
        tmp3['loc_id'] = tmp3.apply(lambda x : f'{x.PROV}_{x[target_column]}', axis=1)
        # merge
        tmp = pd.merge(tmp1, tmp2[['loc_id', 0]], how='left', on='loc_id').fillna(0)
        rekap_prov = pd.merge(tmp, tmp3[['loc_id', 0]], how='left', on='loc_id').fillna(0)
        rekap_prov.columns = ['Provinsi', target_column, 'Sample', 'loc_id', 'Approved', 'Rejected']
        # target
        rekap['id'] = rekap.apply(lambda x : f'{x.Provinsi}_{x[target_column]}', axis=1)
        dict_target = rekap.groupby('id')['Target'].sum().to_dict()
        rekap_prov['Target'] = rekap_prov['loc_id'].map(dict_target)
        rekap_prov.drop(['loc_id'], axis=1)
    else:
        tmp1 = df.groupby(['PROV']).size().reset_index()
        tmp2 = df[df['review_status']=='APPROVED'].groupby(['PROV']).size().reset_index()
        tmp3 = df[df['review_status']=='REJECTED'].groupby(['PROV']).size().reset_index()
        # merge
        tmp = pd.merge(tmp1, tmp2, how='left', on='PROV').fillna(0)
        rekap_prov = pd.merge(tmp, tmp3, how='left', on='PROV').fillna(0)
        rekap_prov.columns = ['Provinsi', 'Sample', 'Approved', 'Rejected']
        # target
        dict_target = rekap.groupby('Provinsi')['Target'].sum().to_dict()
        rekap_prov['Target'] = rekap_prov['Provinsi'].map(dict_target)
    # add empty samples
    list_exist = rekap_prov['Provinsi'].unique().tolist()
    for prov in [i for i in list_location['PROV'] if i not in list_exist]:
        vals = {'Provinsi': prov, 'Sample': 0, 'Approved': 0, 'Rejected': 0, 'Target': targets['PROV'][prov]}
        rekap_prov = rekap_prov.append(vals, ignore_index=True)
    # add more features
    rekap_prov['Awaiting'] = rekap_prov['Sample'] - rekap_prov['Approved'] - rekap_prov['Rejected']   
    rekap_prov['Deficit'] = rekap_prov['Target'] - rekap_prov['Approved']
    rekap_prov['Deficit'] = np.where(rekap_prov['Deficit']<0, 0, rekap_prov['Deficit'])
    cols = ['Sample', 'Approved', 'Rejected', 'Awaiting', 'Target', 'Deficit']
    rekap_prov[cols] = rekap_prov[cols].fillna(0).astype(int)
    rekap_prov = rekap_prov.sort_values('Provinsi')
    rekap_prov['prov_str'] = rekap_prov['Provinsi']
    rekap_prov['Provinsi'] = rekap_prov['Provinsi'].\
    apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x}&nama_survei={survey_name}" target="_blank">{x}</a>')
    rekap_prov['Provinsi'] = rekap_prov.apply(lambda x : x.prov_str if x.prov_str == 'TIDAK DIKENALI' else x.Provinsi, axis=1)
    rekap_prov['Approved_percent'] = rekap_prov['Approved'] / rekap_prov['Sample'] * 100
    rekap_prov['Rejected_percent'] = rekap_prov['Rejected'] / rekap_prov['Sample'] * 100
    rekap_prov['Awaiting_percent'] = rekap_prov['Awaiting'] / rekap_prov['Sample'] * 100
    rekap_prov['Target_percent'] = rekap_prov['Approved'] / rekap_prov['Target'] * 100
    cols = ['Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent']
    rekap_prov[cols] = rekap_prov[cols].fillna(0)
    rekap_prov[cols] = rekap_prov[cols].round(1)
    # reorder columns
    if target_column is not None:
        new_column_order = ['Provinsi', target_column, 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting', 'Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent', 'prov_str']
    else:
        new_column_order = ['Provinsi', 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting', 'Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent', 'prov_str']
    rekap_prov = rekap_prov[new_column_order]

    # -------------------------------------------------------------------------------------------------
    # table rekapitulasi up to kabupaten level

    if target_column is not None:
        tmp1 = df.groupby(['KOTA_KAB', target_column]).size().reset_index()
        tmp1['loc_id'] = tmp1.apply(lambda x : f'{x.KOTA_KAB}_{x[target_column]}', axis=1)
        tmp2 = df[df['review_status']=='APPROVED'].groupby(['KOTA_KAB', target_column]).size().reset_index()
        tmp2['loc_id'] = tmp2.apply(lambda x : f'{x.KOTA_KAB}_{x[target_column]}', axis=1)
        tmp3 = df[df['review_status']=='REJECTED'].groupby(['KOTA_KAB', target_column]).size().reset_index()
        tmp3['loc_id'] = tmp3.apply(lambda x : f'{x.KOTA_KAB}_{x[target_column]}', axis=1)
        # merge
        tmp = pd.merge(tmp1, tmp2[['loc_id', 0]], how='left', on='loc_id').fillna(0)
        rekap_kab = pd.merge(tmp, tmp3[['loc_id', 0]], how='left', on='loc_id').fillna(0)
        rekap_kab.columns = ['Kabupaten/Kota', target_column, 'Sample', 'loc_id', 'Approved', 'Rejected']
        # target
        rekap['id'] = rekap.apply(lambda x : f"{x['Kabupaten/Kota']}_{x[target_column]}", axis=1)
        dict_target = rekap.groupby('id')['Target'].sum().to_dict()
        rekap_kab['Target'] = rekap_kab['loc_id'].map(dict_target)
        rekap_kab.drop(['loc_id'], axis=1)
    else:
        tmp1 = df.groupby(['KOTA_KAB']).size().reset_index()
        tmp2 = df[df['review_status']=='APPROVED'].groupby(['KOTA_KAB']).size().reset_index()
        tmp3 = df[df['review_status']=='REJECTED'].groupby(['KOTA_KAB']).size().reset_index()
        # merge
        tmp = pd.merge(tmp1, tmp2, how='left', on='KOTA_KAB').fillna(0)
        rekap_kab = pd.merge(tmp, tmp3, how='left', on='KOTA_KAB').fillna(0)
        rekap_kab.columns = ['Kabupaten/Kota', 'Sample', 'Approved', 'Rejected']
        # target
        dict_target = rekap.groupby('Kabupaten/Kota')['Target'].sum().to_dict()
        rekap_kab['Target'] = rekap_kab['Kabupaten/Kota'].map(dict_target)
    # add empty samples
    list_exist = rekap_kab['Kabupaten/Kota'].unique().tolist()
    for kab in [i for i in list_location['KOTA_KAB'] if i not in list_exist]:
        vals = {'Kabupaten/Kota': kab, 'Sample': 0, 'Approved': 0, 'Rejected': 0, 'Target': targets['KOTA_KAB'][kab]}
        rekap_kab = rekap_kab.append(vals, ignore_index=True)
    # add more features
    rekap_kab['Awaiting'] = rekap_kab['Sample'] - rekap_kab['Approved'] - rekap_kab['Rejected']   
    rekap_kab['Deficit'] = rekap_kab['Target'] - rekap_kab['Approved']
    rekap_kab['Deficit'] = np.where(rekap_kab['Deficit']<0, 0, rekap_kab['Deficit'])
    cols = ['Sample', 'Approved', 'Rejected', 'Awaiting', 'Target', 'Deficit']
    rekap_kab[cols] = rekap_kab[cols].fillna(0).astype(int)
    rekap_kab = rekap_kab.sort_values('Kabupaten/Kota')
    # reorder columns
    if target_column is not None:
        new_column_order = ['Kabupaten/Kota', target_column, 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    else:
        new_column_order = ['Kabupaten/Kota', 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    rekap_kab = rekap_kab[new_column_order]

    # -------------------------------------------------------------------------------------------------
    # table rekapitulasi up to kecamatan level

    if target_column is not None:
        tmp1 = df.groupby(['KEC', target_column]).size().reset_index()
        tmp1['loc_id'] = tmp1.apply(lambda x : f'{x.KEC}_{x[target_column]}', axis=1)
        tmp2 = df[df['review_status']=='APPROVED'].groupby(['KEC', target_column]).size().reset_index()
        tmp2['loc_id'] = tmp2.apply(lambda x : f'{x.KEC}_{x[target_column]}', axis=1)
        tmp3 = df[df['review_status']=='REJECTED'].groupby(['KEC', target_column]).size().reset_index()
        tmp3['loc_id'] = tmp3.apply(lambda x : f'{x.KEC}_{x[target_column]}', axis=1)
        # merge
        tmp = pd.merge(tmp1, tmp2[['loc_id', 0]], how='left', on='loc_id').fillna(0)
        rekap_kec = pd.merge(tmp, tmp3[['loc_id', 0]], how='left', on='loc_id').fillna(0)
        rekap_kec.columns = ['Kecamatan', target_column, 'Sample', 'loc_id', 'Approved', 'Rejected']
        # target
        rekap['id'] = rekap.apply(lambda x : f"{x['Kecamatan']}_{x[target_column]}", axis=1)
        dict_target = rekap.groupby('id')['Target'].sum().to_dict()
        rekap_kec['Target'] = rekap_kec['loc_id'].map(dict_target)
        rekap_kec.drop(['loc_id'], axis=1)
    else:
        tmp1 = df.groupby(['KEC']).size().reset_index()
        tmp2 = df[df['review_status']=='APPROVED'].groupby(['KEC']).size().reset_index()
        tmp3 = df[df['review_status']=='REJECTED'].groupby(['KEC']).size().reset_index()
        # merge
        tmp = pd.merge(tmp1, tmp2, how='left', on='KEC').fillna(0)
        rekap_kec = pd.merge(tmp, tmp3, how='left', on='KEC').fillna(0)
        rekap_kec.columns = ['Kecamatan', 'Sample', 'Approved', 'Rejected']
        # target
        dict_target = rekap.groupby('Kecamatan')['Target'].sum().to_dict()
        rekap_kec['Target'] = rekap_kec['Kecamatan'].map(dict_target)
    # add empty samples
    list_exist = rekap_kec['Kecamatan'].unique().tolist()
    for kec in [i for i in list_location['KEC'] if i not in list_exist]:
        vals = {'Kecamatan': kec, 'Sample': 0, 'Approved': 0, 'Rejected': 0, 'Target': targets['KEC'][kec]}
        rekap_kec = rekap_kec.append(vals, ignore_index=True)
    # add more features
    rekap_kec['Awaiting'] = rekap_kec['Sample'] - rekap_kec['Approved'] - rekap_kec['Rejected']   
    rekap_kec['Deficit'] = rekap_kec['Target'] - rekap_kec['Approved']
    rekap_kec['Deficit'] = np.where(rekap_kec['Deficit']<0, 0, rekap_kec['Deficit'])
    cols = ['Sample', 'Approved', 'Rejected', 'Awaiting', 'Target', 'Deficit']
    rekap_kec[cols] = rekap_kec[cols].fillna(0).astype(int)
    rekap_kec = rekap_kec.sort_values('Kecamatan')
    # reorder columns
    if target_column is not None:
        new_column_order = ['Kecamatan', target_column, 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    else:
        new_column_order = ['Kecamatan', 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    rekap_kec = rekap_kec[new_column_order]

    # -------------------------------------------------------------------------------------------------
    # table rekapitulasi up to kelurahan level

    if target_column is not None:
        tmp1 = df.groupby(['KEL', target_column]).size().reset_index()
        tmp1['loc_id'] = tmp1.apply(lambda x : f'{x.KEL}_{x[target_column]}', axis=1)
        tmp2 = df[df['review_status']=='APPROVED'].groupby(['KEL', target_column]).size().reset_index()
        tmp2['loc_id'] = tmp2.apply(lambda x : f'{x.KEL}_{x[target_column]}', axis=1)
        tmp3 = df[df['review_status']=='REJECTED'].groupby(['KEL', target_column]).size().reset_index()
        tmp3['loc_id'] = tmp3.apply(lambda x : f'{x.KEL}_{x[target_column]}', axis=1)
        # merge
        tmp = pd.merge(tmp1, tmp2[['loc_id', 0]], how='left', on='loc_id').fillna(0)
        rekap_kel = pd.merge(tmp, tmp3[['loc_id', 0]], how='left', on='loc_id').fillna(0)
        rekap_kel.columns = ['Kelurahan', target_column, 'Sample', 'loc_id', 'Approved', 'Rejected']
        # target
        rekap['id'] = rekap.apply(lambda x : f"{x['Kelurahan']}_{x[target_column]}", axis=1)
        dict_target = rekap.groupby('id')['Target'].sum().to_dict()
        rekap_kel['Target'] = rekap_kel['loc_id'].map(dict_target)
        rekap_kel.drop(['loc_id'], axis=1)
    else:
        tmp1 = df.groupby(['KEL']).size().reset_index()
        tmp2 = df[df['review_status']=='APPROVED'].groupby(['KEL']).size().reset_index()
        tmp3 = df[df['review_status']=='REJECTED'].groupby(['KEL']).size().reset_index()
        # merge
        tmp = pd.merge(tmp1, tmp2, how='left', on='KEL').fillna(0)
        rekap_kel = pd.merge(tmp, tmp3, how='left', on='KEL').fillna(0)
        rekap_kel.columns = ['Kelurahan', 'Sample', 'Approved', 'Rejected']
        # target
        dict_target = rekap.groupby('Kelurahan')['Target'].sum().to_dict()
        rekap_kel['Target'] = rekap_kel['Kelurahan'].map(dict_target)
    # add empty samples
    list_exist = rekap_kel['Kelurahan'].unique().tolist()
    for kel in [i for i in list_location['KEL'] if i not in list_exist]:
        vals = {'Kelurahan': kel, 'Sample': 0, 'Approved': 0, 'Rejected': 0, 'Target': targets['KEL'][kel]}
        rekap_kel = rekap_kel.append(vals, ignore_index=True)
    # add more features
    rekap_kel['Awaiting'] = rekap_kel['Sample'] - rekap_kel['Approved'] - rekap_kel['Rejected']   
    rekap_kel['Deficit'] = rekap_kel['Target'] - rekap_kel['Approved']
    rekap_kel['Deficit'] = np.where(rekap_kel['Deficit']<0, 0, rekap_kel['Deficit'])
    cols = ['Sample', 'Approved', 'Rejected', 'Awaiting', 'Target', 'Deficit']
    rekap_kel[cols] = rekap_kel[cols].fillna(0).astype(int)
    rekap_kel = rekap_kel.sort_values('Kelurahan')
    # reorder columns
    if target_column is not None:
        new_column_order = ['Kelurahan', target_column, 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
        rekap = rekap.drop(['id'], axis=1)
    else:
        new_column_order = ['Kelurahan', 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    rekap_kel = rekap_kel[new_column_order]

    # -------------------------------------------------------------------------------------------------
    # save to DB
    conn = sqlite3.connect(DB_PATH)
    df.to_sql(survey_name, conn, if_exists='replace', index=False)
    rekap.to_sql(f'{survey_name}_rekap_all', conn, if_exists='replace', index=False)
    rekap_prov.to_sql(f'{survey_name}_rekap_prov', conn, if_exists='replace', index=False)
    rekap_kab.to_sql(f'{survey_name}_rekap_kab', conn, if_exists='replace', index=False) 
    rekap_kec.to_sql(f'{survey_name}_rekap_kec', conn, if_exists='replace', index=False)  
    rekap_kel.to_sql(f'{survey_name}_rekap_kel', conn, if_exists='replace', index=False)  
    conn.close()


# delete selected rows from 'survey_name' table
def delete_rows_surveys(surveys_df, selected_rows):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    # remove survey_name from 'list_surveys' table
    for name in surveys_df[selected_rows]['Survey Name']:
        # Execute the DELETE statement
        delete_sql = f'DELETE FROM list_surveys WHERE "Survey Name" = ?'
        cursor.execute(delete_sql, (name,))
        # drop the corresponding tables
        for table_name in [name, f'{name}_rekap_all', f'{name}_rekap_prov', f'{name}_rekap_kab', f'{name}_rekap_kec', f'{name}_rekap_kel']:
            sql_drop_table = f"DROP TABLE IF EXISTS {table_name};"
            cursor.execute(sql_drop_table)
    # commit the changes & close the connection
    conn.commit()
    conn.close()

# generate datamart
def generate_datamart(nama_survei):
    dm = datamart(DB_PATH, nama_survei)
    dm.load_all_tables()
    return dm

# load provinsi geojson
@st.cache_data
def get_provinsi_geojson(json_path=os.path.join(JSON_DIR, 'provinsi2022.geojson')):
    gdf = gpd.read_file(json_path)
    gdf.set_index('prov_str', inplace=True)
    return  gdf.__geo_interface__

@st.cache_data
def title_h1(nama_survei):
    title = f"Rekapitulasi Data QC <span style='color:  #aeb6bf'>{nama_survei}</span>" 
    st.markdown(f"<h1 style='text-align: center; color: black; font-size:32px;'>{title}</h1>", unsafe_allow_html=True)

# download dataframe
def download_dataframe_as_excel(df):
    output = BytesIO()
    writer = pd.ExcelWriter(output, engine='xlsxwriter')
    df.to_excel(writer, index=False, sheet_name='Sheet1')
    writer.save()
    output.seek(0)
    return output

# clear cache, delete all the items in Session state
def clear_cache():
    for key in st.session_state.keys():
        del st.session_state[key]

# add logo to the sidebar
@st.cache_data
def draw_logo(divider=None):
    if divider is not None:
        st.sidebar.markdown("---")
    st.sidebar.image(image_path, use_column_width=True)

# ----------------------------------------------------------------------------------------------------------------------------
# DATAMART CLASS

class datamart():
    
    def __init__(self, DB_PATH, nama_survei):
        self.DB_PATH = DB_PATH
        self.nama_survei = nama_survei

    # load table
    def load_table(self, table):
        conn = sqlite3.connect(self.DB_PATH)
        df = pd.read_sql_query(f'SELECT * FROM {table}', conn)
        conn.close()
        return df

    # load all tables
    def load_all_tables(self):
        self.df = self.load_table(self.nama_survei)
        self.df_rekap_all = self.load_table(table=f'{self.nama_survei}_rekap_all')
        self.df_rekap_prov = self.load_table(table=f'{self.nama_survei}_rekap_prov')
        self.df_rekap_kab = self.load_table(table=f'{self.nama_survei}_rekap_kab')
        self.df_rekap_kec = self.load_table(table=f'{self.nama_survei}_rekap_kec')
        self.df_rekap_kel = self.load_table(table=f'{self.nama_survei}_rekap_kel')

    # get total numbers of people
    def get_total_number(self, location_filter, target_column, selected_category):
        if location_filter is not None:
            if target_column is not None:
                filter_ = (self.df[target_column]==selected_category) & location_filter
            else:
                filter_ = pd.Series([True] * len(self.df)) & location_filter
        else:
            if target_column is not None:
                filter_ = self.df[target_column]==selected_category
            else:
                filter_ = pd.Series([True] * len(self.df))            
        self.n_data = len(self.df[filter_])
        cols = ['PROV', 'KOTA_KAB', 'KEC', 'KEL']
        self.n_resp = len(self.df[filter_].groupby(cols+['NAMA_RESPONDEN']).size().values)
        self.n_enum = len(self.df[filter_].groupby(cols+['NAMA_ENUM']).size().values)
        self.n_kk = len(self.df[filter_].groupby(cols+['NAMA_KK']).size().values)

    # get number of locations
    def get_number_location(self):
        self.n_prov = len(self.list_provinsi)
        self.n_kab = len(self.list_kab_kota)
        self.n_kec = len(self.list_kecamatan)
        self.n_kel = len(self.list_kelurahan)
        if 'TIDAK DIKENALI' in self.list_provinsi:
            self.n_prov -= 1
        if 'TIDAK DIKENALI' in self.list_kab_kota:
            self.n_kab -= 1
        if 'TIDAK DIKENALI' in self.list_kecamatan:
            self.n_kec -= 1
        if 'TIDAK DIKENALI' in self.list_kecamatan:
            self.n_kel -= 1

    #  get list of locations
    def get_list_location(self, target_column, selected_category):
        if target_column is not None:
            # self.list_provinsi = sorted(self.df_rekap_prov[self.df_rekap_prov[target_column]==selected_category]['prov_str'].unique().tolist())
            self.list_provinsi = sorted(self.df_rekap_prov['prov_str'].unique().tolist())
            self.list_kab_kota = sorted(self.df[self.df[target_column]==selected_category]['KOTA_KAB'].unique().tolist())
            self.list_kecamatan = sorted(self.df[self.df[target_column]==selected_category]['KEC'].unique().tolist())
            self.list_kelurahan = sorted(self.df[self.df[target_column]==selected_category]['KEL'].unique().tolist())
        else:
            self.list_provinsi = sorted(self.df_rekap_prov['prov_str'].unique().tolist())
            self.list_kab_kota = sorted(self.df['KOTA_KAB'].unique().tolist())
            self.list_kecamatan = sorted(self.df['KEC'].unique().tolist())
            self.list_kelurahan = sorted(self.df['KEL'].unique().tolist())

    # get status aggregate
    def get_agg_status(self, location_filter, target_column, selected_category):
        if location_filter is not None:
            if target_column is not None:
                filter_ = (self.df[target_column]==selected_category) & location_filter
            else:
                filter_ = pd.Series([True] * len(self.df)) & location_filter
        else:
            if target_column is not None:
                filter_ = self.df[target_column]==selected_category
            else:
                filter_ = pd.Series([True] * len(self.df))            
        agg = self.df[filter_].groupby('review_status').size().reset_index()
        agg.columns = ['Status', 'Count']
        self.agg_status = agg.sort_values('Count')

    # get quality aggregate
    def get_agg_target(self, data, target_column):
        agg = data.groupby([target_column, 'review_status']).size().reset_index()
        agg.columns = ['Target', 'Status', 'Count']
        agg = agg.sort_values(['Count','Status'], ascending=False)
        return agg.sort_values('Count')

# ----------------------------------------------------------------------------------------------------------------------------
# SETUP

# Create empty 'list_surveys' table
create_empty_table()

# Set page layout
set_page_config()

# ----------------------------------------------------------------------------------------------------------------------------
# Load static data

# Load image
image_path = os.path.join(IMG_DIR, 'Kedaikopi.png')

# Define color maps
color_map1 = {
    'APPROVED': '#AEC7E8',
    'REJECTED': '#FF9896',
    'AWAITING': '#FF7F0E',
    'GOOD': '#a1d99b',
    'POOR': '#fcbba1',
    'OKAY': '#ffd8b1',
    'FAKE': '#045F5F'
}
color_map2 = {
    'APPROVED': '#86d34e',
    'REJECTED': '#f88a77',
    'AWAITING': '#e2fccf '
}

# Define cellStyle function for conditional formatting
jscode1 = JsCode("""
function(params) {
    if (params.data.review_status == 'AWAITING') {
        return {
            'color': 'white',
            'backgroundColor': '#8e44ad'
        }
    }
    else if (params.data.review_status == 'REJECTED') {
        return {
            'color': 'black',
            'backgroundColor': '#f8d5d2'
        }
    }
};
""")
jscode2 = JsCode("""
function(params) {
    if (params.data.Deficit > 0) {
        return {
            'color': 'black',
            'backgroundColor': '#fcf3cf'
        }
    }
};
""")

# Define JS function for rendering the links in Provinsi column (Global Data Table)
cell_renderer = JsCode("""
function(params) {
    return params.data.Provinsi
}
""")

# Define JS function for rendering the links in 'Link' column
cell_link = JsCode("""
function(params) {
    return params.data.Link
}
""")

# Define JS function for rendering checkboxes (Manage Data)
checkbox_renderer = JsCode(
    """
    class CheckboxRenderer{
    init(params) {
        this.params = params;
        this.eGui = document.createElement('input');
        this.eGui.type = 'checkbox';
        this.eGui.checked = params.value;
        this.checkedHandler = this.checkedHandler.bind(this);
        this.eGui.addEventListener('click', this.checkedHandler);
    }
    checkedHandler(e) {
        let checked = e.target.checked;
        let colId = this.params.column.colId;
        this.params.node.setDataValue(colId, checked);
    }
    getGui(params) {
        return this.eGui;
    }
    destroy(params) {
    this.eGui.removeEventListener('click', this.checkedHandler);
    }
    }//end class
"""
)
rowStyle_renderer = JsCode(
    """
    function(params) {
        if (params.data.select) {
            return {
                'color': 'black',
                'backgroundColor': 'yellow'
            }
        }
        else {
            return {
                'color': 'black',
                'backgroundColor': 'white'
            }
        }
    }; 
"""
)

# custom style metrics
st_style = """
<style>
div[data-testid="metric-container"] {
background-color: #F4F8FF;
border: 1px solid #F4F8FF;
padding: 5% 5% 5% 10%;
border-radius: 25px;
color: #404040;
overflow-wrap: break-word;
}
/* breakline for metric text         */
div[data-testid="metric-container"] > label[data-testid="stMetricLabel"] > div {
overflow-wrap: break-word;
white-space: break-spaces;
color: red;
}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
</style>
"""