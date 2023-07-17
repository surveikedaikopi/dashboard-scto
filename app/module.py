import os
import json
import yaml
import sqlite3
import numpy as np
import pandas as pd
from io import BytesIO
import streamlit as st
import geopandas as gpd
from st_aggrid import JsCode
from datetime import datetime
from dotenv import load_dotenv
from yaml.loader import SafeLoader
from pysurveycto import SurveyCTOObject


load_dotenv()

WORK_DIR = 'app'
JSON_DIR = 'app/json'
IMG_DIR = 'app/images'
DB_PATH = 'app/local.db'
TEMPLATE_FILE = 'app/templates.zip'
DECODER_FILE = 'app/decoder.xlsx'
AUTHENTICATION_YAML = 'app/config_auth.yaml'
SERVER_NAME = os.getenv('SERVER_NAME')
DASHBOARD_HOST = os.getenv('DASHBOARD_HOST')
SCTO_USERNAME = os.getenv('SCTO_USERNAME')
SCTO_PASSWORD = os.getenv('SCTO_PASSWORD')

# ----------------------------------------------------------------------------------------------------------------------------
# AUXILIARY FUNCTIONS

# load local lottie file
def get_json(file):
    with open(file, 'r') as f:
        out = json.load(f)
    return out

@st.cache_data
def get_lottie_wait():
    return get_json(os.path.join(JSON_DIR, 'coffee.json'))

@st.cache_data
def get_lottie_forbidden():
    return get_json(os.path.join(JSON_DIR, 'forbidden.json'))

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
            "Survey Name" STR,
            "Form ID" STR,
            "Last Download" TIMESTAMP,
            "List Location" TEXT,
            Wilayah TEXT,
            Target TEXT,
            "Target Column" STR,
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
    list_surveys.sort()
    return df, list_surveys, update_time, target_columns

# update surveys table
def update_surveys_table(survey_name, form_id, list_location, wilayah, targets, target_column, decoder):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    insert_sql = '''
        INSERT INTO list_surveys ("Selection", "Survey Name", "Form ID", "Last Download", "List Location", "Wilayah", "Target", "Target Column", "Decoder")
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    '''
    update_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(insert_sql, (False, survey_name, form_id, update_time, list_location, wilayah, targets, target_column, decoder))
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
def download_data(form_id, wilayah, decoder):
    # build connection to SurveyCTO server
    scto = SurveyCTOObject(SERVER_NAME, SCTO_USERNAME, SCTO_PASSWORD)
    # donwload data as json
    res = scto.get_form_data(form_id, format='json', shape='wide', review_status=['approved', 'rejected', 'pending'])
    # build dataframe
    df = pd.DataFrame(res)
    # used fields
    if 'CATATAN_QC' not in df.columns:
        df['CATATAN_QC'] = ''
    usecols = ['CATATAN_QC', 'PROV', 'KOTA_KAB', 'KEC', 'KEC_LAINNYA', 'KEL', 'KEL_LAINNYA', 'RW', 'RT', 'NAMA_KK', 'NAMA_RESPONDEN', 'NAMA_ENUM', 'JK', 'WILAYAH', 'review_status', 'KEY']
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
    # apply uppercase and remove whitespace at the beginning and at the end of the strings
    for col in ['NAMA_RESPONDEN', 'NAMA_KK', 'NAMA_ENUM', 'PROV', 'KOTA_KAB', 'KEC', 'KEC_LAINNYA', 'KEL', 'KEL_LAINNYA']:
        df.loc[:,col] = df[col].str.upper().str.strip()
        df.loc[:,col] = df[col].str.rstrip()
    # fix "LAINNYA" in KEC & KEL
    for f in ['KEC', 'KEL']:
        df[f] = df.apply(lambda x : x[f'{f}_LAINNYA'] if x[f] == 'TIDAK DIKENALI' else x[f], axis=1)
    # WILAYAH
    df['WILAYAH'] = df['KEL'].map(wilayah).values
    # link KEY to Survey CTO server
    df['Link'] = df['KEY'].apply(lambda x : x.split('uuid:')[-1])
    df['Link'] = df['Link'].apply(lambda x : f'<a href="https://{SERVER_NAME}.surveycto.com/view/submission.html?uuid=uuid%3A{x}" target="_blank">link</a>')
    return df.drop(['KEC_LAINNYA', 'KEL_LAINNYA', 'KEY'], axis=1)

# build recapitulation table
def get_recap(df, target_column, targets, region, metadata, all_regions=False):
    reg = {'Provinsi': 'PROV', 'Kabupaten_Kota': 'KOTA_KAB', 'Kecamatan': 'KEC', 'Kelurahan': 'KEL'}
    # generate location ids
    if target_column is not None:
        if region == 'Provinsi':
            df['loc_id'] = df.apply(lambda x : f'{x.PROV}_{x[target_column]}', axis=1)
        elif region == 'Kabupaten_Kota':
            df['loc_id'] = df.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x[target_column]}', axis=1)
        elif region == 'Kecamatan':
            df['loc_id'] = df.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x[target_column]}', axis=1)
        elif region == 'Kelurahan':
            df['loc_id'] = df.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}_{x[target_column]}', axis=1)
    else:
        if region == 'Provinsi':
            df['loc_id'] = df.apply(lambda x : f'{x.PROV}', axis=1)
        elif region == 'Kabupaten_Kota':
            df['loc_id'] = df.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}', axis=1)
        elif region == 'Kecamatan':
            df['loc_id'] = df.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}', axis=1)
        elif region == 'Kelurahan':
            df['loc_id'] = df.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}', axis=1)
    # grouping
    tmp1 = df.groupby('loc_id').size().reset_index()
    tmp2 = df[df['review_status']=='APPROVED'].groupby('loc_id').size().reset_index()
    tmp3 = df[df['review_status']=='REJECTED'].groupby('loc_id').size().reset_index()
    # merging
    tmp = pd.merge(tmp1, tmp2[['loc_id', 0]], how='left', on='loc_id').fillna(0)
    recap = pd.merge(tmp, tmp3[['loc_id', 0]], how='left', on='loc_id').fillna(0)
    recap.columns = [region, 'Sample', 'Approved', 'Rejected']
    # set target
    if target_column is not None:
        recap[target_column] = recap[region].apply(lambda x : x.split('_')[-1])
        # set target
        recap['Target'] = 0
        for cat in targets.keys():
            idx = recap[recap[target_column]==cat].index
            recap.loc[idx,'Target'] = recap.loc[idx,region].map(targets[cat][reg[region]]).values
        newcols = [region, target_column, 'Target', 'Sample', 'Approved', 'Rejected']
    else:
        recap['Target'] = recap[region].map(targets[reg[region]]).values
        newcols = [region, 'Target', 'Sample', 'Approved', 'Rejected'] 
    recap = recap[newcols]
    # add empty samples
    row_indices = recap.index
    idx = {'Provinsi': 0, 'Kabupaten_Kota': 1, 'Kecamatan': 2, 'Kelurahan': 3}
    if target_column is not None:
        tmp = metadata.melt(id_vars=['PROV', 'KOTA_KAB', 'KEC', 'KEL', 'WILAYAH'], value_vars=[i for i in metadata.columns if i not in ['PROV', 'KOTA_KAB', 'KEC', 'KEL', 'WILAYAH']])
        ori = tmp.copy()
        tmp['PROV'] = ori.apply(lambda x : f'{x.PROV}_{x.variable}', axis=1)
        tmp['KOTA_KAB'] = ori.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.variable}', axis=1)
        tmp['KEC'] = ori.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.variable}', axis=1)
        tmp['KEL'] = ori.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}_{x.variable}', axis=1)
        for cat in targets.keys():
            list_exist = recap[recap[target_column]==cat][region].unique().tolist() 
            for ireg in [i for i in tmp[tmp['variable']==cat][reg[region]].unique() if i not in list_exist]:
                if all_regions:
                    kel = ireg.split('_')[3]
                    kec = ireg.split('_')[2]
                    kab = ireg.split('_')[1]
                    prov = ireg.split('_')[0]
                    vals = {'Provinsi': prov, 'Kabupaten_Kota': kab, 'Kecamatan': kec, 'Kelurahan': kel, target_column: cat, 'Sample': 0, 'Approved': 0, 'Rejected': 0, 'Target': targets[cat]['KEL'][ireg]}
                else:
                    vals = {region: ireg.split('_')[idx[region]], target_column: cat, 'Sample': 0, 'Approved': 0, 'Rejected': 0, 'Target': targets[cat][reg[region]][ireg]}
                recap = recap.append(vals, ignore_index=True)
    else:
        metadata['PROV'] = metadata.apply(lambda x : f'{x.PROV}', axis=1)
        metadata['KOTA_KAB'] = metadata.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}', axis=1)
        metadata['KEC'] = metadata.apply(lambda x : f'{x.KOTA_KAB}_{x.KEC}', axis=1)
        metadata['KEL'] = metadata.apply(lambda x : f'{x.KEC}_{x.KEL}', axis=1)  
        list_exist = recap[region].unique().tolist() 
        for ireg in [i for i in metadata[reg[region]].unique() if i not in list_exist]:
            if all_regions:
                kel = ireg.split('_')[3]
                kec = ireg.split('_')[2]
                kab = ireg.split('_')[1]
                prov = ireg.split('_')[0]
                vals = {'Provinsi': prov, 'Kabupaten_Kota': kab, 'Kecamatan': kec, 'Kelurahan': kel, 'Sample': 0, 'Approved': 0, 'Rejected': 0, 'Target': targets['KEL'][ireg]}
            else:
                vals = {region: ireg.split('_')[idx[region]], 'Sample': 0, 'Approved': 0, 'Rejected': 0, 'Target': targets[reg[region]][ireg]}
            recap = recap.append(vals, ignore_index=True)
    # restoration
    if all_regions:
        for ireg in idx.keys():
            recap.loc[row_indices, ireg] = recap.loc[row_indices, 'Kelurahan'].apply(lambda x : x.split('_')[idx[ireg]])
    else:
        recap.loc[row_indices, region] = recap.loc[row_indices, region].apply(lambda x : x.split('_')[idx[region]])            
    # add more features
    recap['Awaiting'] = recap['Sample'] - recap['Approved'] - recap['Rejected']   
    recap['Deficit'] = recap['Target'] - recap['Approved']
    recap['Deficit'] = np.where(recap['Deficit']<0, 0, recap['Deficit'])
    cols = ['Sample', 'Approved', 'Rejected', 'Awaiting', 'Target', 'Deficit']
    recap[cols] = recap[cols].fillna(0).astype(int)
    return recap.sort_values(region)



# generate datalake
def generate_datalake(survey_name, df, targets, target_column, metadata):

    # -------------------------------------------------------------------------------------------------
    
    # tabel rekapitulasi (All, down to Kelurahan)
    rekap = get_recap(df, target_column, targets, 'Kelurahan', metadata.copy(), all_regions=True)
    
    # reorder columns
    if target_column is not None:
        new_column_order = ['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan', target_column, 'Target', 'Sample', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    else:
        new_column_order = ['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan', 'Target', 'Sample', 'Approved', 'Deficit', 'Rejected', 'Awaiting']
    rekap = rekap[new_column_order]

    # -------------------------------------------------------------------------------------------------
    
    # table rekapitulasi up to provinsi level
    rekap_prov = get_recap(df, target_column, targets, 'Provinsi', metadata.copy())

    # get percentages
    rekap_prov['Approved_percent'] = rekap_prov['Approved'] / rekap_prov['Sample'] * 100
    rekap_prov['Rejected_percent'] = rekap_prov['Rejected'] / rekap_prov['Sample'] * 100
    rekap_prov['Awaiting_percent'] = rekap_prov['Awaiting'] / rekap_prov['Sample'] * 100
    rekap_prov['Target_percent'] = rekap_prov['Approved'] / rekap_prov['Target'] * 100
    cols = ['Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent']
    rekap_prov[cols] = rekap_prov[cols].fillna(0)
    rekap_prov[cols] = rekap_prov[cols].round(1)

    # reorder columns
    if target_column is not None:
        new_column_order = ['Provinsi', target_column, 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting', 'Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent']
    else:
        new_column_order = ['Provinsi', 'Sample', 'Target', 'Approved', 'Deficit', 'Rejected', 'Awaiting', 'Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent']
    rekap_prov = rekap_prov[new_column_order]

    # -------------------------------------------------------------------------------------------------
    
    # table rekapitulasi up to kabupaten level
    rekap_kab = get_recap(df, target_column, targets, 'Kabupaten_Kota', metadata.copy())

    # -------------------------------------------------------------------------------------------------
    
    # table rekapitulasi up to kecamatan level
    rekap_kec = get_recap(df, target_column, targets, 'Kecamatan', metadata.copy())

    # -------------------------------------------------------------------------------------------------
    
    # table rekapitulasi up to kelurahan level
    rekap_kel = get_recap(df, target_column, targets, 'Kelurahan', metadata.copy())

    # -------------------------------------------------------------------------------------------------
    
    # save to DB
    conn = sqlite3.connect(DB_PATH)
    df.drop(['loc_id'], axis=1).to_sql(survey_name, conn, if_exists='replace', index=False)
    metadata.to_sql(f'{survey_name}_metadata', conn, if_exists='replace', index=False)
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
    gdf.set_index('Provinsi', inplace=True)
    return  gdf.__geo_interface__

@st.cache_data
def title_h1(nama_survei):
    title = f"Rekapitulasi Data QC <span style='color:  #aeb6bf'>{nama_survei}</span>" 
    st.markdown(f"<h1 style='text-align: center; color: black; font-size:32px;'>{title}</h1>", unsafe_allow_html=True)

# construct links
def get_link(region, df, nama_survei, selected_category):
    if region == 'Provinsi':
        links = df.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Provinsi}</a>' if x[region]!='TIDAK DIKENALI' else x[region], axis=1)
    elif region == 'Kabupaten_Kota':
        links = df.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&selected_kabupaten={x.Kabupaten_Kota}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Kabupaten_Kota}</a>' if x[region]!='TIDAK DIKENALI' else x[region], axis=1)
    elif region == 'Kecamatan':
        links = df.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&selected_kabupaten={x.Kabupaten_Kota}&selected_kecamatan={x.Kecamatan}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Kecamatan}</a>' if x[region]!='TIDAK DIKENALI' else x[region], axis=1)
    elif region == 'Kelurahan':
        links = df.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&selected_kabupaten={x.Kabupaten_Kota}&selected_kecamatan={x.Kecamatan}&selected_kelurahan={x.Kelurahan}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Kelurahan}</a>' if x[region]!='TIDAK DIKENALI' else x[region], axis=1)
    return links

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
        self.list_surveys = self.load_table('list_surveys')
        self.list_surveys = self.list_surveys[self.list_surveys['Survey Name']==self.nama_survei]
        self.df = self.load_table(self.nama_survei)
        self.metadata = self.load_table(table=f'{self.nama_survei}_metadata')
        self.df_rekap_all = self.load_table(table=f'{self.nama_survei}_rekap_all')
        self.df_rekap_prov = self.load_table(table=f'{self.nama_survei}_rekap_prov')
        self.df_rekap_kab = self.load_table(table=f'{self.nama_survei}_rekap_kab')
        self.df_rekap_kec = self.load_table(table=f'{self.nama_survei}_rekap_kec')
        self.df_rekap_kel = self.load_table(table=f'{self.nama_survei}_rekap_kel')

    # get total numbers of people
    def get_total_number(self, location_filter, metadata_filter, target_column, selected_category):
        if location_filter is not None:
            if target_column is not None:
                filter_ = (self.df[target_column]==selected_category) & location_filter
                approved = len(self.df[(self.df['review_status']=='APPROVED') & (self.df[target_column]==selected_category) & filter_])
            else:
                filter_ = location_filter
                approved = len(self.df[(self.df['review_status']=='APPROVED') & filter_])
        else:
            if target_column is not None:
                filter_ = self.df[target_column]==selected_category
                approved = len(self.df[(self.df['review_status']=='APPROVED') & (self.df[target_column]==selected_category)])
            else:
                filter_ = pd.Series([True] * len(self.df))
                approved = len(self.df[self.df['review_status']=='APPROVED'])
        # target
        if target_column is not None:
            if metadata_filter is not None:
                self.n_target = self.metadata[metadata_filter][selected_category].sum()
            else:
                self.n_target = self.metadata[selected_category].sum()
        else:
            if metadata_filter is not None:
                self.n_target = self.metadata[metadata_filter]['JML'].sum()
            else:
                self.n_target = self.metadata['JML'].sum()
        # deficit
        self.delta_n_target = approved - self.n_target
        self.delta_n_target = '.' if self.delta_n_target==0 else '+'+str(self.delta_n_target) if self.delta_n_target>0 else str(self.delta_n_target)
        # others
        self.n_data = len(self.df[filter_])
        cols = ['PROV', 'KOTA_KAB', 'KEC', 'KEL']
        self.n_resp = len(self.df[filter_].groupby(cols+['NAMA_KK', 'NAMA_RESPONDEN']).size().values)
        self.n_enum = len(self.df[filter_].groupby(cols+['NAMA_ENUM']).size().values)
        self.n_kk = len(self.df[filter_].groupby(cols+['NAMA_KK']).size().values)

    @staticmethod
    # organize string for delta_n
    def text_out(val):
        out = '.' if val==0 else '+'+str(val) if val>0 else str(val)
        return out

    # get number of locations
    def get_number_location(self, target_column, selected_category):
        data = self.list_surveys
        # planned
        list_location = json.loads(data['List Location'].values[0])
        if target_column is not None:
            list_prov = list_location[selected_category]['PROV']
            list_kab = list_location[selected_category]['KOTA_KAB']
            list_kec = list_location[selected_category]['KEC']
            list_kel = list_location[selected_category]['KEL']
        else:
            list_prov = list_location['PROV']
            list_kab = list_location['KOTA_KAB']
            list_kec = list_location['KEC']
            list_kel = list_location['KEL']
        self.n_prov = len(list_prov)
        self.n_kab = len(list_kab)
        self.n_kec = len(list_kec)
        self.n_kel = len(list_kel)
        # difference
        self.delta_n_prov = -len([i for i in self.df_rekap_prov[self.df_rekap_prov['Deficit']>0]['Provinsi'] if i in list_prov])
        self.delta_n_prov = self.text_out(self.delta_n_prov)
        self.delta_n_kab = -len([i for i in self.df_rekap_kab[self.df_rekap_kab['Deficit']>0]['Kabupaten_Kota'] if i in list_kab])
        self.delta_n_kab = self.text_out(self.delta_n_kab)
        self.delta_n_kec = -len([i for i in self.df_rekap_kec[self.df_rekap_kec['Deficit']>0]['Kecamatan'] if i in list_kec])
        self.delta_n_kec = self.text_out(self.delta_n_kec)
        self.delta_n_kel = -len([i for i in self.df_rekap_kel[self.df_rekap_kel['Deficit']>0]['Kelurahan'] if i in list_kel])
        self.delta_n_kel = self.text_out(self.delta_n_kel)

    #  get list of locations
    def get_list_location(self):
        self.list_provinsi = sorted(self.df_rekap_prov['Provinsi'].unique().tolist())
        self.list_kab_kota = sorted(self.df_rekap_kab['Kabupaten_Kota'].unique().tolist())
        self.list_kecamatan = sorted(self.df_rekap_kec['Kecamatan'].unique().tolist())
        self.list_kelurahan = sorted(self.df_rekap_kel['Kelurahan'].unique().tolist())

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

# ----------------------------------------------------------------------------------------------------------------------------
# Load static data

# Authentication config
with open(AUTHENTICATION_YAML) as file:
    auth_config = yaml.load(file, Loader=SafeLoader)

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
jscode3 = JsCode("""
function(params) {
    if (params.data.Sample == 0) {
        return {
            'color': 'black',
            'backgroundColor': '#bbfbf9'
        }
    }
    if (params.data.Target == 0) {
        return {
            'color': 'black',
            'backgroundColor': '#fbbbd0'
        }
    }
};
""")

# Define JS function for rendering the links in Provinsi column (Global Data Table)
cell_renderer_prov = JsCode("""
function(params) {
    return params.data.Provinsi
}
""")
# Define JS function for rendering the links in Kabupaten_Kota column (Global Data Table)
cell_renderer_kab = JsCode("""
function(params) {
    return params.data.Kabupaten_Kota
}
""")
# Define JS function for rendering the links in Kecamatan column (Global Data Table)
cell_renderer_kec = JsCode("""
function(params) {
    return params.data.Kecamatan
}
""")
# Define JS function for rendering the links in Kelurahan column (Global Data Table)
cell_renderer_kel = JsCode("""
function(params) {
    return params.data.Kelurahan
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
color: #5e6ff9;
}
#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}
[data-testid="stMetricDelta"] svg {
    display: none;
}
.appview-container .main .block-container {
    padding-top: 0rem;
    padding-bottom: 0rem;
}
.sidebar .sidebar-content {
    font-size: 32px;
}
</style>
"""