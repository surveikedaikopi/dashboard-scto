import sys
sys.path.append('../')
from module import *
import streamlit as st
import plotly.express as px
import streamlit_authenticator as stauth
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode


# ----------------------------------------------------------------------------------------------------------------------------
# Set Page Layout

st.set_page_config(page_title='Local Data - QC Dashboard', layout='wide', page_icon='☕')
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

# ----------------------------------------------------------------------------------------------------------------------------

    # load surveys
    _, list_survei, update_time, target_columns = get_survey_names()
    if len(list_survei) == 0:
        st.error('Database is empty.')
        st.stop()

    st.session_state.tabel_rekapitulasi = True

    # ----------------------------------------------------------------------------------------------------------------------------
    # Initiate URL Parameters

    query_params = st.experimental_get_query_params()
    url_params = {'nama_survei': query_params['nama_survei'][0] if 'nama_survei' in query_params else None,
                  'selected_category': query_params['selected_category'][0] if 'selected_category' in query_params else None,
                  'selected_provinsi': query_params['selected_provinsi'][0] if 'selected_provinsi' in query_params else None,
                  'selected_kab_kota': query_params['selected_kab_kota'][0] if 'selected_kab_kota' in query_params else None,
                  'selected_kecamatan': query_params['selected_kecamatan'][0] if 'selected_kecamatan' in query_params else None,
                  'selected_kelurahan': query_params['selected_kelurahan'][0] if 'selected_kelurahan' in query_params else None}

    # update URL parameters from the session states
    if 'selected_kelurahan' in st.session_state:
        url_params.update({'selected_kelurahan': st.session_state.selected_kelurahan}) 
    elif 'selected_kecamatan' in st.session_state:
        url_params.update({'selected_kecamatan': st.session_state.selected_kecamatan}) 
    elif 'selected_kab_kota' in st.session_state:
        url_params.update({'selected_kab_kota': st.session_state.selected_kab_kota}) 
    elif 'selected_provinsi' in st.session_state:
        url_params.update({'selected_provinsi': st.session_state.selected_provinsi})

    # get 'nama survei' from session state
    if 'nama_survei' in st.session_state:
        url_params.update({'nama_survei': st.session_state.nama_survei})
        if 'selected_category' in st.session_state:
            url_params.update({'selected_category': st.session_state.selected_category})

    nama_survei = url_params['nama_survei']
    param_category = url_params['selected_category']
    param_provinsi = url_params['selected_provinsi']
    param_kab_kota = url_params['selected_kab_kota']
    param_kecamatan = url_params['selected_kecamatan']
    param_kelurahan = url_params['selected_kelurahan']

    # get 'nama survei' from URL parameters
    if nama_survei is None:
        nama_survei = list_survei[0]
    st.session_state.nama_survei = nama_survei

    # get target column
    target_column = target_columns[nama_survei]
    if target_column is None:
        st.session_state.selected_category = None

    # ----------------------------------------------------------------------------------------------------------------------------
    # Survey Name Filter

    idx = list_survei.index(nama_survei)
    nama_survei = st.sidebar.selectbox('Nama Survei', list_survei, index=idx)
    url_params.update({'nama_survei': nama_survei})

    # Remove 'dm' state if nama_survei changes
    if 'nama_survei' in st.session_state:
        if nama_survei != st.session_state.nama_survei:
            dm = generate_datamart(nama_survei)
            st.session_state.dm = dm
            st.session_state.nama_survei = nama_survei
            target_column = target_columns[nama_survei]
            if target_column is None:
                st.session_state.selected_category = None

    # ----------------------------------------------------------------------------------------------------------------------------
    # Data Mart

    if 'dm' not in st.session_state:
        dm = generate_datamart(nama_survei)
        st.session_state.dm = dm
    else:
        dm = st.session_state.dm

    # ----------------------------------------------------------------------------------------------------------------------------
    # Target Categories

    target_column = target_columns[nama_survei]
    if target_column is not None:
        target_categories = dm.df[target_column].unique().tolist()
        target_categories.sort()
        if param_category is not None:
            selected_category = st.sidebar.selectbox('Target Category', target_categories, index=target_categories.index(param_category))
        else:
            selected_category = st.sidebar.selectbox('Target Category', target_categories)
        st.session_state.selected_category = selected_category
        url_params.update({'selected_category': selected_category})
    else:
        selected_category = None
    st.sidebar.markdown("---")

    # ----------------------------------------------------------------------------------------------------------------------------
    # Category Filter

    if target_column is not None:
        filter_ = dm.df_rekap_prov[target_column] == selected_category
    else:
        filter_ = pd.Series([True] * len(dm.df_rekap_prov))

    dm.get_list_location(target_column)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Define Filters

    # provinsi
    if param_provinsi is not None:
        selected_provinsi = st.sidebar.selectbox('Provinsi', dm.list_provinsi, index=dm.list_provinsi.index(param_provinsi))
    else:
        selected_provinsi = st.sidebar.selectbox('Provinsi', dm.list_provinsi)
    if selected_provinsi != param_provinsi:
        st.session_state.change_selected_provinsi = True 
    st.session_state.selected_provinsi = selected_provinsi
    url_params.update({'selected_provinsi': selected_provinsi})    

    # kab/kota
    list_kabkota_prov = [i for i in dm.list_kab_kota if i in dm.df[dm.df['PROV']==selected_provinsi]['KOTA_KAB'].tolist()] + ['ALL']
    if (param_kab_kota is not None) & ('change_selected_provinsi' not in st.session_state):
        selected_kab_kota = st.sidebar.selectbox('Kabupaten/Kota', list_kabkota_prov, index=list_kabkota_prov.index(param_kab_kota))
    else:
        selected_kab_kota = st.sidebar.selectbox('Kabupaten/Kota', list_kabkota_prov, index=list_kabkota_prov.index('ALL'))
    if selected_kab_kota != param_kab_kota:
        st.session_state.change_selected_kab_kota = True
    st.session_state.selected_kab_kota = selected_kab_kota
    url_params.update({'selected_kab_kota': selected_kab_kota}) 

    # kecamatan
    list_kec_kabkota = [i for i in dm.list_kecamatan if i in dm.df[dm.df['KOTA_KAB']==selected_kab_kota]['KEC'].tolist()] + ['ALL']
    if (param_kecamatan is not None) & ('change_selected_kab_kota' not in st.session_state):
        selected_kecamatan = st.sidebar.selectbox('Kecamatan', list_kec_kabkota, index=list_kec_kabkota.index(param_kecamatan))
    else:
        selected_kecamatan = st.sidebar.selectbox('Kecamatan', list_kec_kabkota, index=list_kec_kabkota.index('ALL'))
    if selected_kecamatan != param_kecamatan:
        st.session_state.change_selected_kecamatan = True
    st.session_state.selected_kecamatan = selected_kecamatan
    url_params.update({'selected_kecamatan': selected_kecamatan}) 

    # kelurahan
    list_kel_kec = [i for i in dm.list_kelurahan if i in dm.df[dm.df['KEC']==selected_kecamatan]['KEL'].tolist()] + ['ALL']
    if (param_kelurahan is not None) & ('change_selected_kecamatan' not in st.session_state):
        selected_kelurahan = st.sidebar.selectbox('Kelurahan', list_kel_kec, index=list_kel_kec.index(param_kelurahan))
    else:
        selected_kelurahan = st.sidebar.selectbox('Kelurahan', list_kel_kec, index=list_kel_kec.index('ALL'))
    st.session_state.selected_kelurahan = selected_kelurahan
    url_params.update({'selected_kelurahan': selected_kelurahan}) 

    # ----------------------------------------------------------------------------------------------------------------------------
    # Get Selections

    if selected_kab_kota == 'ALL':
        selection1 = (dm.df['PROV']==selected_provinsi)
        selection2 = (dm.df_rekap_all['Provinsi']==selected_provinsi)
    elif selected_kecamatan == 'ALL':
        selection1 = (dm.df['PROV']==selected_provinsi) & (dm.df['KOTA_KAB']==selected_kab_kota)
        selection2 = (dm.df_rekap_all['Provinsi']==selected_provinsi) & (dm.df_rekap_all['Kabupaten/Kota']==selected_kab_kota)
    elif selected_kelurahan == 'ALL':
        selection1 = (dm.df['PROV']==selected_provinsi) & (dm.df['KOTA_KAB']==selected_kab_kota) & (dm.df['KEC']==selected_kecamatan)
        selection2 = (dm.df_rekap_all['Provinsi']==selected_provinsi) & (dm.df_rekap_all['Kabupaten/Kota']==selected_kab_kota) & (dm.df_rekap_all['Kecamatan']==selected_kecamatan)
    else:
        selection1 = (dm.df['PROV']==selected_provinsi) & (dm.df['KOTA_KAB']==selected_kab_kota) & (dm.df['KEC']==selected_kecamatan) & (dm.df['KEL']==selected_kelurahan)
        selection2 = (dm.df_rekap_all['Provinsi']==selected_provinsi) & (dm.df_rekap_all['Kabupaten/Kota']==selected_kab_kota) & (dm.df_rekap_all['Kecamatan']==selected_kecamatan) & (dm.df_rekap_all['Kelurahan']==selected_kelurahan)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Local Data Mart

    dm.get_total_number(selection1, target_column, selected_category)
    dm.get_agg_status(selection1, target_column, selected_category)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Title and Subtitle

    # Title
    title_h1(nama_survei)

    if selected_category is not None:
        text = f'Target Category: {selected_category}'
        st.markdown(f"<h6 style='text-align: center; color: #5e6ff9;'>{text}</h6>", unsafe_allow_html=True)

    # Location info
    text = f'PROV. {selected_provinsi}'
    if selected_kab_kota != 'ALL':
        text = f'{selected_kab_kota} --- ' + text
        if selected_kecamatan != 'ALL':
            text = f'KEC. {selected_kecamatan} --- ' + text
            if selected_kelurahan != 'ALL':
                text = f'KEL. {selected_kelurahan} --- '  + text
    st.markdown(f"<h5 style='text-align: center; color: #8e44ad;'>{text}</h5>", unsafe_allow_html=True)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Metrics: total numbers

    st.markdown("---")
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric('Total Target', dm.n_target, dm.delta_n_target)
    col2.metric('Total Data', dm.n_data, '.', delta_color='off')
    col3.metric('Total Responden', dm.n_resp, '.', delta_color='off')
    col4.metric('Total KK', dm.n_kk, '.', delta_color='off')
    col5.metric('Total Enumerator', dm.n_enum, '.', delta_color='off')
    st.markdown("---")

    # ----------------------------------------------------------------------------------------------------------------------------
    # Chart Layout

    if target_column is not None:
        pie1, pie2 = st.columns(2)
    else:
        _, pie1, _ = st.columns([1,2,1])

    # ----------------------------------------------------------------------------------------------------------------------------
    # Review Status: Pie Chart

    def status_piechart(data):
        fig = px.pie(data, values='Count', names='Status', hole=.6, color='Status', color_discrete_map=color_map2)
        fig.update_layout(
            title='Review Status' if target_column is None else f'Review Status ({selected_category})',
            font=dict(size=16,),
        )
        pie1.plotly_chart(fig, use_container_width=True)

    status_piechart(dm.agg_status)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Target Status: Bar Chart

    if target_column is not None:
        
        def target_piechart(data):
            fig = px.bar(data, x='Target', y='Count', color='Status', color_discrete_map=color_map2)
            fig.update_layout(
                barmode='group',
                title='Status By Target Category',
                showlegend=True,
                font=dict(size=16),
                xaxis={'categoryorder': 'total descending'}
            )
            pie2.plotly_chart(fig, use_container_width=True)

        data = dm.df[selection1]
        target_piechart(dm.get_agg_target(data, target_column))

    # ----------------------------------------------------------------------------------------------------------------------------
    # Tabel Rekapitulasi
    st.markdown("---")

    if selected_kab_kota == 'ALL':
        title = 'Tabel Rekapitulasi Level Kabupaten / Kota'
        filter_1 = dm.df_rekap_kab['Kabupaten/Kota'].isin(list_kabkota_prov)
        # category filter
        if selected_category is not None:
            filter_2 = dm.df_rekap_kab[target_column] == selected_category
            title += f' (Category: {selected_category})'
        else:
            filter_2 = pd.Series([True] * len(dm.df_rekap_kab))
        data = dm.df_rekap_kab[filter_1 & filter_2]
    elif selected_kecamatan == 'ALL':
        title = 'Tabel Rekapitulasi Level Kecamatan'
        filter_1 = dm.df_rekap_kec['Kecamatan'].isin(list_kec_kabkota)
        # category filter
        if selected_category is not None:
            filter_2 = dm.df_rekap_kec[target_column] == selected_category
            title += f' (Category: {selected_category})'
        else:
            filter_2 = pd.Series([True] * len(dm.df_rekap_kec))
        data = dm.df_rekap_kec[filter_1 & filter_2]
    elif selected_kelurahan == 'ALL':
        title = 'Tabel Rekapitulasi Level Kelurahan'
        filter_1 = dm.df_rekap_kel['Kelurahan'].isin(list_kel_kec)
        # category filter
        if selected_category is not None:
            filter_2 = dm.df_rekap_kel[target_column] == selected_category
            title += f' (Category: {selected_category})'
        else:
            filter_2 = pd.Series([True] * len(dm.df_rekap_kel))
        data = dm.df_rekap_kel[filter_1 & filter_2]
    else:
        title = 'Tabel Rekapitulasi Level Kelurahan'
        filter_1 = dm.df_rekap_kel['Kelurahan'] == selected_kelurahan
        if selected_category is not None:
            filter_2 = dm.df_rekap_kel[target_column] == selected_category
            title += f' (Category: {selected_category})'
        else:
            filter_2 = pd.Series([True] * len(dm.df_rekap_kel))
        data = dm.df_rekap_kel[filter_1 & filter_2]
        st.session_state.tabel_rekapitulasi = False
    
    if target_column is not None:
        data = data.drop([target_column], axis=1)
    st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)
    height = get_table_height(data)

    gb = GridOptionsBuilder.from_dataframe(data)
    gridOptions = gb.build()
    gridOptions['getRowStyle'] = jscode2
    with st.container():
        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False,
            allow_unsafe_jscode=True, height=height, enableSorting=True, enableFilter=True,
            update_mode=GridUpdateMode.VALUE_CHANGED)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Tabel Rekapitulasi (All Levels)

    if st.session_state.tabel_rekapitulasi:
        st.markdown("---")

        expander = st.expander('Tabel Rekapitulasi (Level Kelurahan)')

        with expander:

            data = dm.df_rekap_all
            # category filter
            if target_column is not None:
                filter_ = data[target_column] == selected_category
                title = f'Category: {selected_category}'
                st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)
            else:
                filter_ = pd.Series([True] * len(data))

            if target_column is not None:
                data = data.drop([target_column], axis=1)
            data = data[selection2 & filter_]
            height = get_table_height(data)

            gb = GridOptionsBuilder.from_dataframe(data)
            gridOptions = gb.build()
            gridOptions['getRowStyle'] = jscode2

            AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False,
                    allow_unsafe_jscode=True, height=height, enableSorting=True, enableFilter=True,
                    update_mode=GridUpdateMode.VALUE_CHANGED)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Raw Table
    st.markdown("---")

    with st.expander('Raw Table (Filtered)'):

        if target_column is not None:
            filter_ = selection1 & (dm.df[target_column]==selected_category)
        else:
            filter_ = selection1
        data = dm.df[filter_]
        height = get_table_height(data)

        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_column('Link', cellRenderer=cell_link, pinned='right')
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode1

        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True,
                allow_unsafe_jscode=True, height=height, enableSorting=True, enableFilter=True,
                update_mode=GridUpdateMode.VALUE_CHANGED)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Last update
    st.sidebar.markdown("---")
    st.sidebar.markdown('last update:')
    st.sidebar.markdown(f':blue[{update_time[nama_survei]}]')

    # ----------------------------------------------------------------------------------------------------------------------------
    # Add image to the sidebar
    draw_logo(1)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Add logout button
    st.sidebar.markdown("---")
    authenticator.logout('Logout', 'sidebar')

    # ----------------------------------------------------------------------------------------------------------------------------
    # Set URL parameters
    st.experimental_set_query_params(selected_category = url_params['selected_category'], 
                                     selected_kelurahan = url_params['selected_kelurahan'], 
                                     selected_kecamatan = url_params['selected_kecamatan'], 
                                     selected_kab_kota = url_params['selected_kab_kota'], 
                                     selected_provinsi = url_params['selected_provinsi'], 
                                     nama_survei = url_params['nama_survei'])

else:
    draw_logo()