import sys
sys.path.append('../')
import yaml
import numpy as np
from module import *
import streamlit as st
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from streamlit_lottie import st_lottie_spinner
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


# ----------------------------------------------------------------------------------------------------------------------------
# Set Page Layout

if 'set_page_config' not in st.session_state:
    set_page_config()
    st.session_state.set_page_config = True 
st.markdown(st_style, unsafe_allow_html=True)

# ----------------------------------------------------------------------------------------------------------------------------
# Authentication

# Load config
with open(CONFIG_YAML) as file:
    config = yaml.load(file, Loader=SafeLoader)

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days'],
    config['preauthorized']
)

name, authentication_status, username = authenticator.login('Login', 'main')

if st.session_state.authentication_status == False:
    st.error('Username/password is incorrect')
elif st.session_state.authentication_status == None:
    st.warning('Please enter your username and password')
elif st.session_state.authentication_status:
    st.session_state.check = True

# ----------------------------------------------------------------------------------------------------------------------------

    # Title
    title = "Manage Surveys" 
    st.markdown(f"<h1 style='text-align: center; color: black; font-size:32px;'>{title}</h1>", unsafe_allow_html=True)

    # Add image to the sidebar
    draw_logo()

    # ----------------------------------------------------------------------------------------------------------------------------
    # Add logout button
    st.sidebar.markdown("---")
    authenticator.logout('Logout', 'sidebar')

    # load surveys
    surveys_df, list_survei, _, _ = get_survey_names()

    # ------------------------------------------------------------------------------------------------------------
    # User Input

    with st.form('Form'):

        title = 'Load New Survey'
        st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)

        # Get survey name
        survey_name = st.text_input("Survey Form ID:", key='survey_name')

        # Get decoders
        with st.expander('Decoder'):
            uploaded_file1 = st.file_uploader("Please follow the given template", accept_multiple_files=False, type=['xlsx'], key='uploader1')
            if uploaded_file1 is not None:
                try:
                    fields = pd.read_excel(uploaded_file1, sheet_name='FIELDS')
                    decoder = {}
                    for f in fields['FIELDS'].values:
                        out = pd.read_excel(uploaded_file1, sheet_name=f)
                        out['CODE'] = out['CODE'].astype('str')
                        out = out.set_index('CODE').to_dict()['LABEL']
                        decoder.update({f: out})
                        st.session_state.decoder = decoder
                except:
                    st.error('There is something wrong with the file structure. Please look at the given template.')
                    st.session_state.check = False

        # Get target sample
        with st.expander('Sample Target'):
            uploaded_file2 = st.file_uploader("Please follow the given template", accept_multiple_files=False, type=['xlsx'], key='uploader2')
            if uploaded_file2 is not None:
                try:
                    # get internal decoder for sanity check
                    internal_decoder = get_internal_decoder()
                    # load uploaded file to dataframe
                    tmp = pd.read_excel(uploaded_file2)
                    list_location, targets = {}, {}
                    for col in ['PROV', 'KOTA_KAB', 'KEC', 'KEL']:
                        # get target
                        tmp[col] = tmp[col].str.upper()
                        targets.update({col : tmp.groupby(col).sum('JML').to_dict()['JML']})
                        # get list of locations
                        list_location.update({col : tmp[col].str.upper().unique().tolist()})
                        list_location[col].sort()
                        # check consistency with internal database
                        list_not_exist = [i for i in list_location[col] if i not in [j for _,j in internal_decoder[col].items()]]
                        if len(list_not_exist) != 0:
                            if col in ['PROV', 'KOTA_KAB']:
                                st.error(f'{list_not_exist} do not exist in {col} database')
                                st.stop()
                            else:
                                st.warning(f'{list_not_exist} do not exist in {col} database')
                    # session state variables
                    st.session_state.list_location = list_location
                    st.session_state.targets = targets
                except:
                    st.error('There is something wrong with the file structure. Please look at the given template.')
                    st.session_state.check = False

        with st.expander('Advanced Options'):   
            target_column = st.text_input("Target Column:", key='target_column')

    # ------------------------------------------------------------------------------------------------------------
    # Download
    
        # Create the download button
        download_button = st.form_submit_button('Download Data')

        # Check if the button is clicked
        if download_button:
            # Check if name exists
            if survey_name in list_survei:
                st.warning('form_id already exists')
            elif not st.session_state.check:
                st.warning('fix the error')
            else:
                # download process
                with st_lottie_spinner(get_lottie_wait(), height=200):
                    # Lottie
                    lottie_wait = get_lottie_wait()
                    try:
                        # download data
                        if 'decoder' in st.session_state:
                            df = download_data(survey_name, st.session_state.decoder)
                        else:
                            df = download_data(survey_name, None)
                        st.session_state.df = df
                        if target_column != '':
                            list_categories = df[st.session_state.target_column].unique()
                            list_categories.sort()
                            st.session_state.list_categories = list_categories
                        st.session_state.success = True
                    except:
                        st.error('Possible errors: form_id is wrong, SurveyCTO service cannot be accessed or target is incorrect.')

        # ------------------------------------------------------------------------------------------------------------
        # Preprocessing

        if 'success' in st.session_state:

            # redefine target column
            if st.session_state.target_column != '':
                values = {cat:0 for cat in st.session_state.list_categories}
                st.write('Specify target percentage (%) for each category:')
                for cat in st.session_state.list_categories:
                    values[cat] = st.text_input(cat, key=cat)
                    values[cat] = 0 if values[cat]=='' else int(values[cat])
            else:
                st.write('Proceed by pressing "Process Data".')

            # create process button
            process_button = st.form_submit_button('Process Data')
            if process_button:
                # Check if sum of values is consistent with target kelurahan
                if st.session_state.target_column != '':
                    sum_ = np.sum([values[k] for k in values.keys()])
                    if sum_ != 100:
                        st.error('The sum is not consistent.')
                        st.stop()
                    else:
                        target_column = st.session_state.target_column
                        target_column_values = values
                else:
                    target_column = None
                    target_column_values = None
                    targets = st.session_state.targets
                if 'decoder' in st.session_state:
                    decoder = st.session_state.decoder
                else:
                    decoder = None
                # Process data
                with st_lottie_spinner(get_lottie_wait(), height=200):
                    # data preprocessing
                    generate_datalake(survey_name, st.session_state.df, list_location, targets, target_column, target_column_values)
                    if type(target_column_values) == dict:
                        target_column_values = json.dumps(target_column_values)
                    list_location = json.dumps(st.session_state.list_location)    
                    targets = json.dumps(st.session_state.targets)
                    if 'decoder' in st.session_state:
                        decoder = json.dumps(st.session_state.decoder)
                    # insert survey_name into 'list_surveys' table
                    update_surveys_table(survey_name, list_location, targets, target_column, target_column_values, decoder)            
                    # Reload table
                    surveys_df, _, _, _ = get_survey_names()
                    # Clear cache
                    clear_cache()

    # ------------------------------------------------------------------------------------------------------------
    # Show Surveys Table
    st.markdown("---")

    title = 'List of Surveys'
    st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)

    data = surveys_df.drop(['List Location', 'Target', 'Target Column Values', 'Decoder'], axis=1)
    height = get_table_height(data) + 15

    gb = GridOptionsBuilder.from_dataframe(data)
    gb.configure_column('Selection', minWidth=90, maxWidth=90, editable=False, cellRenderer=checkbox_renderer)
    gridOptions = gb.build()
    gridOptions["getRowStyle"] = rowStyle_renderer
    ag_grid = AgGrid(
        data,
        gridOptions=gridOptions,
        data_return_mode="as_input",
        update_mode=GridUpdateMode.VALUE_CHANGED,
        allow_unsafe_jscode=True,
        enable_enterprise_modules=False,
        reload_data=False,
        height = height
    )

    selected_rows = ag_grid["data"]['Selection'].values

    # ------------------------------------------------------------------------------------------------------------
    # Add a 'Delete' button
    if np.sum(selected_rows) > 0:
        if st.button("Delete"):
            delete_rows_surveys(surveys_df, selected_rows)
            st.cache_data.clear()
            st.experimental_rerun()
        
    # ------------------------------------------------------------------------------------------------------------
    # Templates
    st.markdown("---")

    with st.expander('Templates'):   
        with open(TEMPLATE_FILE, "rb") as fp:
            btn = st.download_button(label="Download", data=fp, file_name="templates.zip", mime="application/zip")
