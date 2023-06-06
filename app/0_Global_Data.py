from module import *
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import streamlit_authenticator as stauth
from streamlit_plotly_events import plotly_events
from st_aggrid import AgGrid, GridOptionsBuilder, GridUpdateMode



# ----------------------------------------------------------------------------------------------------------------------------
# Set Page Layout

st.set_page_config(page_title='Global Data - QC Dashboard', layout='wide', page_icon='☕')
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

    # ----------------------------------------------------------------------------------------------------------------------------
    # Load Data

    # GeoJson Provinsi
    geojson_provinsi = get_provinsi_geojson()

    # load surveys
    _, list_survei, update_time, target_columns = get_survey_names()
    if len(list_survei) == 0:
        st.error('Database is empty.')
        st.stop()

    # ----------------------------------------------------------------------------------------------------------------------------
    # Initiate URL Parameters

    query_params = st.experimental_get_query_params()
    url_params = {'nama_survei': query_params['nama_survei'][0] if 'nama_survei' in query_params else None,
                  'selected_category': query_params['selected_category'][0] if 'selected_category' in query_params else None}

    if 'nama_survei' in st.session_state:
        url_params.update({'nama_survei': st.session_state.nama_survei})
        if 'selected_category' in st.session_state:
            url_params.update({'selected_category': st.session_state.selected_category})

    param_nama_survei = url_params['nama_survei']
    param_category = url_params['selected_category']

    # nama survei
    if param_nama_survei is not None:
        nama_survei = url_params['nama_survei']
    else:
        nama_survei = list_survei[0]
    st.session_state.nama_survei = nama_survei

    target_column = target_columns[nama_survei]
    if target_column is None:
        st.session_state.selected_category = None

    # ----------------------------------------------------------------------------------------------------------------------------
    # Define States

    if 'nama_survei' in st.session_state:
        if 'selected_category' in st.session_state:
            url_params.update({'selected_category': st.session_state.selected_category})

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
        dm.df_rekap_prov['Provinsi'] = dm.df_rekap_prov['prov_str'].apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x}</a>')
    else:
        selected_category = None

    # ----------------------------------------------------------------------------------------------------------------------------
    # Title

    title_h1(nama_survei)
    if selected_category is not None:
        text = f'Target Category: {selected_category}'
        st.markdown(f"<h6 style='text-align: center; color: #5e6ff9;'>{text}</h6>", unsafe_allow_html=True)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Category Filter

    if target_column is not None:
        filter_ = dm.df_rekap_prov[target_column] == selected_category
    else:
        filter_ = pd.Series([True] * len(dm.df_rekap_prov))

    # ----------------------------------------------------------------------------------------------------------------------------
    # Build Global Datamart
    
    dm.get_total_number(None, target_column, selected_category)
    dm.get_list_location(target_column)
    dm.get_agg_status(None, target_column, selected_category)
    dm.get_number_location(target_column, selected_category)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Metrics: number of people
    st.markdown("---")

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric('Total Target', dm.n_target, dm.delta_n_target)
    col2.metric('Total Data', dm.n_data, '.', delta_color='off')
    col3.metric('Total Responden', dm.n_resp, '.', delta_color='off')
    col4.metric('Total KK', dm.n_kk, '.', delta_color='off')
    col5.metric('Total Enumerator', dm.n_enum, '.', delta_color='off')

    # ----------------------------------------------------------------------------------------------------------------------------
    # Chart Layout
    st.markdown("---")

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

        data = dm.df
        target_piechart(dm.get_agg_target(data, target_column))

    # ----------------------------------------------------------------------------------------------------------------------------
    # Metrics: number of locations
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric('Target Provinsi', dm.n_prov, dm.delta_n_prov)
    col2.metric('Target Kabupaten / Kota', dm.n_kab, dm.delta_n_kab)
    col3.metric('Target Kecamatan', dm.n_kec, dm.delta_n_kec)
    col4.metric('Target Kelurahan', dm.n_kel, dm.delta_n_kel)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Distribution Map

    if target_column is not None:
        map_title = f'Sample Distribution Map (Category: {selected_category})'
    else:
        map_title = 'Sample Distribution Map'

    # radio buttons
    st.sidebar.markdown("---")
    options = ['Target (%)', 'Total Sample', 'Approved (%)', 'Rejected (%)', 'Awaiting (%)', 'Deficit']
    selected_option = st.sidebar.radio('Map Filter', options)

    if selected_option == 'Target (%)':
        values = dm.df_rekap_prov[filter_]['Target_percent'].values
        colormap = 'Sunset'
    elif selected_option == 'Total Sample':
        values = dm.df_rekap_prov[filter_]['Sample'].values
        colormap = 'matter'
    elif selected_option == 'Approved (%)':
        values = dm.df_rekap_prov[filter_]['Approved_percent'].values
        colormap = 'YlGn'
    elif selected_option == 'Rejected (%)':
        values = dm.df_rekap_prov[filter_]['Rejected_percent'].values
        colormap = 'YlOrRd'
    elif selected_option == 'Awaiting (%)':
        values = dm.df_rekap_prov[filter_]['Awaiting_percent'].values
        colormap = 'Viridis'
    elif selected_option == 'Deficit':
        values = dm.df_rekap_prov[filter_]['Deficit'].values
        colormap = 'Reds'

    def draw_map(list_prov_map):
        fig = go.Figure()
        fig.add_trace(go.Choroplethmapbox(
            geojson = geojson_provinsi,
            locations = list_prov_map,
            z = values,
            colorscale=colormap,
            colorbar=dict(title=selected_option),
            hovertemplate='<b>%{location}</b><br>' + f'{selected_option}:' + ' %{z}<br>' + '<extra></extra>'
        ))
        fig.update_layout(
            title = map_title,
            mapbox=dict(
                style = 'carto-positron',
                zoom = 3.3,
                center = dict(lat=-2.5489, lon=118.0149),
            ),
        )
        # Show the chart in Streamlit with plotly events library
        selected_points = plotly_events(fig)
        return selected_points

    list_prov_map = dm.df_rekap_prov[filter_]['prov_str'].values
    selected_points = draw_map(list_prov_map)
    if len(selected_points) != 0:
        selected_provinsi_map = list_prov_map[selected_points[0]['pointIndex']]
        # Show filtered summary table
        if target_column is not None:
            filter_selection = (dm.df_rekap_prov['prov_str'] == selected_provinsi_map) & (dm.df_rekap_prov[target_column] == selected_category)
        else:
            filter_selection = dm.df_rekap_prov['prov_str'] == selected_provinsi_map
        data = dm.df_rekap_prov[filter_selection]
        data = data.drop(['prov_str', 'Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent'], axis=1)
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_column('Provinsi', cellRenderer=cell_renderer)
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode2
        AgGrid(data, gridOptions=gridOptions, fit_columns_on_grid_load=False, allow_unsafe_jscode=True, height=65, update_mode=GridUpdateMode.VALUE_CHANGED)
            
    # ----------------------------------------------------------------------------------------------------------------------------
    # Tabel Rekapitulasi Level Provinsi
    st.markdown("---")

    expander = st.expander('Tabel Rekapitulasi')
    with expander:

        if target_column is not None:
            title = f'Tabel Rekapitulasi Level Provinsi (Category: {selected_category})'
        else:
            title = 'Tabel Rekapitulasi Level Provinsi'
        st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)

        data = dm.df_rekap_prov[filter_].sort_values('prov_str')
        dropcols = ['prov_str', 'Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent']
        if target_column is not None:
            dropcols += [target_column]
        data = data.drop(dropcols, axis=1)
        height = (1 + len(data)) * 29

        # Build Table
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_default_column(min_column_width=200)
        gb.configure_column('Provinsi', cellRenderer=cell_renderer, pinned='left')
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode2
        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False,
                allow_unsafe_jscode=True, height=height, enableSorting=True, enableFilter=True,
                update_mode=GridUpdateMode.VALUE_CHANGED)             

    # ----------------------------------------------------------------------------------------------------------------------------
    # Pivot Table
    st.markdown("---") 

    expander = st.expander('Pivot Table (Unfiltered)')
    with expander:
        usecols = ['Provinsi', 'Kabupaten/Kota', 'Kecamatan', 'Kelurahan', 'Target', 'Approved', 'Deficit']
        if target_column is not None:
            usecols = [target_column] + usecols
        data = dm.df_rekap_all[usecols]
        height = 600
        # Build Table
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_column( field=target_column, pivot=True)
        for f in ['Provinsi', 'Kabupaten/Kota', 'Kecamatan', 'Kelurahan']:
            gb.configure_column(field=f, rowGroup=True)
        for f in ['Target', 'Approved', 'Deficit']:
            gb.configure_column(field=f, type=["numericColumn"], aggFunc="sum")
        gb.configure_grid_options(pivotMode=True)
        gridOptions = gb.build()
        ag_grid = AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True,
                allow_unsafe_jscode=True, height=height, enableSorting=True, enableFilter=True,
                update_mode=GridUpdateMode.VALUE_CHANGED)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Raw Table
    st.markdown("---")

    expander = st.expander('Raw Table (Unfiltered)')
    with expander:

        data = dm.df
        height = get_table_height(data)

        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_column('Link', cellRenderer=cell_link, pinned='right')
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode1

        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False,
                allow_unsafe_jscode=True, height=height, 
                update_mode=GridUpdateMode.VALUE_CHANGED)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Duplicates By Respondent
    st.markdown("---")

    expander = st.expander('Duplicates By Respondent (Unfiltered)')
    with expander:

        data = dm.df[dm.df[['PROV', 'KOTA_KAB', 'KEC', 'KEL', 'NAMA_KK', 'NAMA_RESPONDEN']].duplicated(keep=False)].sort_values('NAMA_RESPONDEN')
        height = get_table_height(data)

        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_column('Link', cellRenderer=cell_link, pinned='right')
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode1

        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False,
                allow_unsafe_jscode=True, height=height, 
                update_mode=GridUpdateMode.VALUE_CHANGED)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Rejected Enumerators
    st.markdown("---")

    expander = st.expander('Rejected Enumerators (Unfiltered)')
    with expander:

        cols = ['PROV', 'KOTA_KAB', 'KEC', 'KEL', 'NAMA_ENUM', 'review_status']
        data = dm.df.groupby(cols).size().reset_index().sort_values([0, 'NAMA_ENUM'], ascending=False)
        data.columns = cols + ['Rejected Count']
        data = data[data['review_status']=='REJECTED'].drop(['review_status'], axis=1)
        height = get_table_height(data)

        gb = GridOptionsBuilder.from_dataframe(data)
        gridOptions = gb.build()

        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False,
                allow_unsafe_jscode=True, height=height, 
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
    st.experimental_set_query_params(nama_survei=url_params['nama_survei'], selected_category=url_params['selected_category'])

else:
    draw_logo()