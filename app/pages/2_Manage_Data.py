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
    st.markdown("---")

    title = 'Load New Survey'
    st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)

    # Get survey name
    survey_name = st.text_input("Survey Form ID:", key='survey_name')

    # Get decoders
    with st.expander('Decoder'):
        uploaded_file = st.file_uploader("Please follow the given template", accept_multiple_files=False, type=['xlsx'])
        if uploaded_file is not None:
            try:
                fields = pd.read_excel(uploaded_file, sheet_name='FIELDS')
                decoder = {}
                for f in fields['FIELDS'].values:
                    out = pd.read_excel(uploaded_file, sheet_name=f)
                    out['CODE'] = out['CODE'].astype('str')
                    out = out.set_index('CODE').to_dict()['LABEL']
                    decoder.update({f: out})
                    st.session_state.decoder = decoder
            except:
                st.error('There is something wrong with the file structure. Please look at the given template.')

    # Get number of target
    options = ['Single Value', 'Multiple Values']
    selected_option = st.radio("Target Per Kelurahan", options)
    if selected_option == 'Single Value':
        target_kelurahan = st.text_input("Number of Target Per Kelurahan:", key='target_kelurahan')
    else:
        uploaded_file = st.file_uploader("The table should contain ONLY 2 columns: 'KELURAHAN' & 'JML_TARGET'", accept_multiple_files=False, type=['csv', 'xlsx'])
        if uploaded_file is not None:
            map_target = pd.read_csv(uploaded_file) if uploaded_file.name.endswith('.csv') else pd.read_excel(uploaded_file)
            # check if columns are correct
            if map_target.columns.tolist() != ['KELURAHAN', 'JML_TARGET']:
                st.error('Columns are not correct.')
            else:
                map_target['KELURAHAN'] = map_target['KELURAHAN'].astype(str)
                map_target = map_target.set_index('KELURAHAN')
                target_kelurahan = map_target['JML_TARGET'].to_dict()
                st.session_state.target_kelurahan = target_kelurahan
    with st.expander('Advanced Options'):   
        target_column = st.text_input("Target Column:", key='target_column')

    # ------------------------------------------------------------------------------------------------------------
    # Download
    
    with st.form('Form'):

        # SCTO Username
        scto_account = st.text_input('SCTO Account:', key='scto_account')
        # SCTO Password
        scto_password = st.text_input('SCTO Password', type='password', key='scto_password')

        # Create the download button
        download_button = st.form_submit_button('Download Data')

        # Check if the button is clicked
        if download_button:
            # Check if name exists
            if survey_name in list_survei:
                st.warning('form_id already exists')
            # Check if target is specified
            if target_kelurahan == '':
                st.error('Specify the target')
            else:
                # download process
                with st_lottie_spinner(get_lottie_wait(), height=200):
                    # Lottie
                    lottie_wait = get_lottie_wait()
                    try:
                        # download data
                        if 'decoder' in st.session_state:
                            df = download_data(survey_name, st.session_state.decoder, scto_account, scto_password)
                        else:
                            df = download_data(survey_name, None, scto_account, scto_password)
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
                if type(st.session_state.target_kelurahan) == dict:
                    target_kelurahan = st.session_state.target_kelurahan
                else:
                    target_kelurahan = int(st.session_state.target_kelurahan)
                if type(st.session_state.decoder) == dict:
                    decoder = st.session_state.decoder
                else:
                    decoder = None
                # Process data
                with st_lottie_spinner(get_lottie_wait(), height=150):
                    # data preprocessing
                    generate_datalake(survey_name, st.session_state.df, target_kelurahan, target_column, target_column_values)
                    if type(target_column_values) == dict:
                        target_column_values = json.dumps(target_column_values)
                    if type(st.session_state.target_kelurahan) == dict:
                        target_kelurahan = json.dumps(st.session_state.target_kelurahan)
                    if type(st.session_state.decoder) == dict:
                        decoder = json.dumps(st.session_state.decoder)
                    # insert survey_name into 'list_surveys' table
                    update_surveys_table(survey_name, target_kelurahan, target_column, target_column_values, decoder, st.session_state.scto_account, st.session_state.scto_password)            
                    # Reload table
                    surveys_df, _, _, _ = get_survey_names()
                    # Clear cache
                    clear_cache()

    # ------------------------------------------------------------------------------------------------------------
    # Show Surveys Table
    st.markdown("---")

    title = 'List of Surveys'
    st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)

    data = surveys_df.iloc[:,:-1]
    height = get_table_height(data)

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
        