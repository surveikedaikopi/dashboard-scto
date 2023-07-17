import sys
sys.path.append('../')
import numpy as np
from module import *
import streamlit as st
import streamlit_authenticator as stauth
from streamlit_lottie import st_lottie_spinner, st_lottie
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


# ----------------------------------------------------------------------------------------------------------------------------
# Set Page Layout

st.set_page_config(page_title='Manage Data - QC Dashboard', layout='wide', page_icon='☕')
st.markdown(st_style, unsafe_allow_html=True)

# ----------------------------------------------------------------------------------------------------------------------------
# Authentication

authenticator = stauth.Authenticate(
    auth_config['credentials'],
    auth_config['cookie']['name'],
    auth_config['cookie']['key'],
    auth_config['cookie']['expiry_days'],
    auth_config['preauthorized']
)

if 'authentication_status' in st.session_state:
    if not st.session_state.authentication_status:
        name, authentication_status, username = authenticator.login('Login', 'main')
        if st.session_state.authentication_status == False:
            st.error('Username/password is incorrect')
        elif st.session_state.authentication_status == None:
            st.warning('Please enter your username and password')
else:
    name, authentication_status, username = authenticator.login('Login', 'main')
    if st.session_state.authentication_status == False:
        st.error('Username/password is incorrect')
    elif st.session_state.authentication_status == None:
        st.warning('Please enter your username and password') 

if st.session_state.authentication_status:
    if st.session_state.name != 'viewers only':
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

            # Get survey name & form id
            survey_name = st.text_input("Survey Name:", key='survey_name')
            form_id = st.text_input("Form ID:", key='form_id')

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

            # Get target sample
            with st.expander('Sample Target'):
                uploaded_file2 = st.file_uploader("Please follow the given template", accept_multiple_files=False, type=['xlsx'], key='uploader2')
                if uploaded_file2 is not None:
                    # get internal decoder for sanity check
                    with st_lottie_spinner(get_lottie_wait(), height=200, key='lottie_decoder'):
                        internal_decoder = get_internal_decoder()
                    try:
                        # target split format
                        try:
                            target_sheet = pd.read_excel(uploaded_file2, sheet_name='TARGET_COLUMN')
                            target_column = target_sheet.columns[0]
                            target_categories = target_sheet[target_column].tolist()
                            data = pd.read_excel(uploaded_file2, sheet_name='DATA')
                        # no-target format
                        except:
                            target_column = None
                            data = pd.read_excel(uploaded_file2)
                        regions = ['PROV', 'KOTA_KAB', 'KEC', 'KEL']
                        data[regions] = data[regions].applymap(lambda x: x.upper() if isinstance(x, str) else x)
                        metadata = data.copy()
                        # set empty dictionary
                        if target_column is not None:
                            data = data.melt(id_vars=regions, value_vars=target_categories)
                            targets = {cat:{} for cat in target_categories}
                            list_location = {'all': {}}
                            list_location.update({cat:{} for cat in target_categories})
                        else:
                            targets = {}
                            list_location = {}
                        for region in regions:
                            # get target
                            if target_column is not None:
                                list_location['all'].update({region : metadata[region].unique().tolist()})
                                list_location['all'][region].sort()
                                if region == 'PROV':
                                    data['loc_id'] = data.apply(lambda x : f'{x.PROV}_{x.variable}', axis=1)
                                elif region == 'KOTA_KAB':
                                    data['loc_id'] = data.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.variable}', axis=1)
                                elif region == 'KEC':
                                    data['loc_id'] = data.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.variable}', axis=1)
                                elif region == 'KEL':
                                    data['loc_id'] = data.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}_{x.variable}', axis=1)
                                for cat in target_categories:
                                    targets[cat].update({region : data[data['variable']==cat].groupby('loc_id').sum('value').to_dict()['value']})
                                    # get list of locations
                                    list_location[cat].update({region : metadata[metadata[cat]>0][region].unique().tolist()})
                                    list_location[cat][region].sort()
                                list_not_exist = [i for i in list_location['all'][region] if i not in [j for _,j in internal_decoder[region].items()]]
                            else:
                                if region == 'PROV':
                                    data['loc_id'] = data.apply(lambda x : f'{x.PROV}', axis=1)
                                elif region == 'KOTA_KAB':
                                    data['loc_id'] = data.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}', axis=1)
                                elif region == 'KEC':
                                    data['loc_id'] = data.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}', axis=1)
                                elif region == 'KEL':
                                    data['loc_id'] = data.apply(lambda x : f'{x.PROV}_{x.KOTA_KAB}_{x.KEC}_{x.KEL}', axis=1)
                                targets.update({region : data.groupby('loc_id').sum('JML').to_dict()['JML']})
                                # get list of locations
                                list_location.update({region : metadata[region].unique().tolist()})
                                list_location[region].sort()
                                list_not_exist = [i for i in list_location[region] if i not in [j for _,j in internal_decoder[region].items()]]
                            # check consistency with internal database
                            if len(list_not_exist) != 0:
                                if region in ['PROV', 'KOTA_KAB']:
                                    st.error(f'{list_not_exist} do not exist in {region} database')
                                    st.stop()
                                else:
                                    st.warning(f'{list_not_exist} do not exist in {region} database')
                        # map WILAYAH
                        wilayah = metadata[['KEL', 'WILAYAH']].set_index('KEL').to_dict()['WILAYAH']
                    except:
                        st.error('There is something wrong with the file structure. Please look at the given template.')
                        st.session_state.check = False

        # ------------------------------------------------------------------------------------------------------------
        # Download
        
            # Create the download button
            download_button = st.form_submit_button('Download Data')

            # Check if the button is clicked
            if download_button:
                # Check if name exists
                if survey_name in list_survei:
                    st.warning('survey name already exists')
                elif not st.session_state.check:
                    st.warning('fix the error')
                else:
                    # download process
                    with st_lottie_spinner(get_lottie_wait(), height=200, key='lottie_download'):
                        try:
                            # download data
                            if 'decoder' in st.session_state:
                                df = download_data(form_id, wilayah, st.session_state.decoder)
                            else:
                                df = download_data(form_id, wilayah, None)

                            if 'decoder' in st.session_state:
                                decoder = st.session_state.decoder
                            else:
                                decoder = None
                            # data preprocessing
                            generate_datalake(survey_name, df, targets, target_column, metadata)
                            list_location = json.dumps(list_location) 
                            wilayah = json.dumps(wilayah)   
                            targets = json.dumps(targets)
                            if decoder is not None:
                                decoder = json.dumps(decoder)
                            # insert survey_name into 'list_surveys' table
                            update_surveys_table(survey_name, form_id, list_location, wilayah, targets, target_column, decoder)            
                            # Reload table
                            surveys_df, _, _, _ = get_survey_names()
                        except:
                            st.error('Possible errors: form_id is wrong, SurveyCTO service cannot be accessed or target is incorrect.')

        # ------------------------------------------------------------------------------------------------------------
        # Show Surveys Table
        st.markdown("---")

        title = 'List of Surveys'
        st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)

        data = surveys_df.drop(['List Location', 'Wilayah', 'Target', 'Decoder'], axis=1)
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

    else:
        st.error('You need to be an administrator or a data manager to access this page.')
        draw_logo()
        authenticator.logout('Logout', 'sidebar')
        st.markdown('#')
        st_lottie(get_lottie_forbidden(), height=200)

else:
    draw_logo()