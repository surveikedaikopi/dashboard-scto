from module import *
import streamlit as st
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
        draw_logo()
        authenticator.logout('Logout', 'sidebar')
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
    
    dm.get_total_number(None, None, target_column, selected_category)
    dm.get_list_location()
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
        labels, values = data['Status'], data['Count']
        fig = go.Figure(data=[go.Pie(labels=labels, values=values, hole=.6, marker=dict(colors=[color_map2[label] for label in labels]))])
        fig.update_layout(
            title='Review Status' if target_column is None else f'Review Status ({selected_category})',
            font={'size': 16},
            margin={'b': 0},
            height=350
            )
        pie1.plotly_chart(fig, use_container_width=True)

    status_piechart(dm.agg_status)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Target Status: Bar Chart

    if target_column is not None:

        def target_barchart(data):
            labels = ['APPROVED', 'REJECTED', 'AWAITING']
            list_data = [go.Bar(x=data[data['Status']==label]['Target'], y=data[data['Status']==label]['Count'], marker={'color':color_map2[label]}) for label in labels]
            fig = go.Figure(data=list_data)

            # Set layout properties for bar chart
            fig.update_layout(
                barmode='group',
                title='Status By Target Category',
                showlegend=False,
                font=dict(size=16),  # Set the font size to 16
                xaxis=dict(categoryorder='total descending'),
                margin=dict(b=0),
                height=350
            )
            pie2.plotly_chart(fig, use_container_width=True)

        data = dm.df
        target_barchart(dm.get_agg_target(data, target_column))

    # ----------------------------------------------------------------------------------------------------------------------------
    # Metrics: number of locations
    st.markdown("---")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric('Target Provinsi', dm.n_prov, dm.delta_n_prov)
    col2.metric('Target Kabupaten / Kota', dm.n_kab, dm.delta_n_kab)
    col3.metric('Target Kecamatan', dm.n_kec, dm.delta_n_kec)
    col4.metric('Target Kelurahan', dm.n_kel, dm.delta_n_kel)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Target Plan (Metadata)

    with st.expander('Target Plan'):
        data = dm.metadata
        height = get_table_height(data)
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_columns(['PROV', 'KOTA_KAB', 'KEC', 'KEL', 'WILAYAH'], pinned='left')
        gridOptions = gb.build()
        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=True,
                allow_unsafe_jscode=True, height=height, update_mode=GridUpdateMode.VALUE_CHANGED)

        # Create a download button
        st.download_button(
            "Download Table",
            data=download_dataframe_as_excel(data),
            file_name="target_plan.xlsx",
            mime="application/vnd.ms-excel",
        )

    # ----------------------------------------------------------------------------------------------------------------------------
    # Deficits
    usecols1 = ['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan']
    usecols2 = ['Target', 'Sample', 'Approved', 'Deficit']

    def table_aggrid(df, region):
        if target_column is not None:
            title = f'Required {region} in Target Plan (Category: {selected_category})'
        else:
            title = f'Required {region} in Target Plan'
        st.markdown(title)
        height = get_table_height(df)
        gb = GridOptionsBuilder.from_dataframe(df)
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode3
        AgGrid(df, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=True, allow_unsafe_jscode=True, height=height, update_mode=GridUpdateMode.VALUE_CHANGED)

    def table_deficit_kelurahan(region, list_data_target):
        if target_column is not None:
            title = f'Survey Data (Kelurahan Level) (Category: {selected_category})'
            data_survey = dm.df_rekap_all[(dm.df_rekap_all[region].isin(list_data_target)) & (dm.df_rekap_all[target_column]==selected_category)][usecols1+usecols2].sort_values(region)
        else:
            title = 'Survey Data (Kelurahan Level):'
            data_survey = dm.df_rekap_all[dm.df_rekap_all[region].isin(list_data_target)][usecols1+usecols2].sort_values(region)
        st.markdown(title)
        data_survey['Kelurahan'] = data_survey.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&selected_kab_kota={x.Kabupaten_Kota}&selected_kecamatan={x.Kecamatan}&selected_kelurahan={x.Kelurahan}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Kelurahan}</a>', axis=1)
        if region == 'Provinsi':
            data_survey['Provinsi'] = data_survey.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Provinsi}</a>', axis=1)            
        if region == 'Kabupaten_Kota':
            data_survey['Kabupaten_Kota'] = data_survey.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&selected_kab_kota={x.Kabupaten_Kota}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Kabupaten_Kota}</a>', axis=1)            
        if region == 'Kecamatan':
            data_survey['Kecamatan'] = data_survey.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&selected_kab_kota={x.Kabupaten_Kota}&selected_kecamatan={x.Kecamatan}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Kecamatan}</a>', axis=1)            
        height = get_table_height(data_survey)
        gb = GridOptionsBuilder.from_dataframe(data_survey)
        cols = ['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan']
        for reg, renderer in zip(cols, [cell_renderer_prov, cell_renderer_kab, cell_renderer_kec, cell_renderer_kel]):
            gb.configure_column(reg, cellRenderer=renderer)
        gb.configure_columns(cols, pinned='left')
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode3
        AgGrid(data_survey, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=True, allow_unsafe_jscode=True, height=height, update_mode=GridUpdateMode.VALUE_CHANGED)


    with st.expander('Deficits'):
        tab1, tab2, tab3, tab4 = st.tabs(['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan'])

        # Provinsi
        with tab1:
            cols = ['Provinsi'] + usecols2
            if target_column is not None:
                data_target = dm.df_rekap_prov[(dm.df_rekap_prov['Deficit']>0) & (dm.df_rekap_prov[target_column]==selected_category)][cols]
            else:
                data_target = dm.df_rekap_prov[dm.df_rekap_prov['Deficit']>0][cols]
            if len(data_target)==0:
                st.success('Complete')
            else:
                list_data_target = data_target['Provinsi'].tolist()
                table_aggrid(data_target, 'Provinsi')
                table_deficit_kelurahan('Provinsi', list_data_target)

        # Kabupaten_Kota
        with tab2:
            cols = ['Kabupaten_Kota'] + usecols2
            if target_column is not None:
                data_target = dm.df_rekap_kab[(dm.df_rekap_kab['Deficit']>0) & (dm.df_rekap_kab[target_column]==selected_category)][cols]
            else:
                data_target = dm.df_rekap_kab[dm.df_rekap_kab['Deficit']>0][cols]
            if len(data_target)==0:
                st.success('Complete')
            else:
                list_data_target = data_target['Kabupaten_Kota'].tolist()
                table_aggrid(data_target, 'Kabupaten_Kota')
                table_deficit_kelurahan('Kabupaten_Kota', list_data_target)

        # Kecamatan
        with tab3:
            cols = ['Kecamatan'] + usecols2
            if target_column is not None:
                data_target = dm.df_rekap_kec[(dm.df_rekap_kec['Deficit']>0) & (dm.df_rekap_kec[target_column]==selected_category)][cols]
            else:
                data_target = dm.df_rekap_kec[dm.df_rekap_kec['Deficit']>0][cols]
            if len(data_target)==0:
                st.warning('No Data')
            else:
                list_data_target = data_target['Kecamatan'].tolist()
                table_aggrid(data_target, 'Kecamatan')
                table_deficit_kelurahan('Kecamatan', list_data_target)

        # Kelurahan
        with tab4:
            cols = ['Kelurahan'] + usecols2
            if target_column is not None:
                data_target = dm.df_rekap_kel[(dm.df_rekap_kel['Deficit']>0) & (dm.df_rekap_kel[target_column]==selected_category)][cols]
            else:
                data_target = dm.df_rekap_kel[dm.df_rekap_kel['Deficit']>0][cols]
            if len(data_target)==0:
                st.warning('No Data')
            else:
                list_data_target = data_target['Kelurahan'].tolist()
                table_aggrid(data_target, 'Kelurahan')
                table_deficit_kelurahan('Kelurahan', list_data_target)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Distribution Map
    st.markdown("---") 

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
        colormap = 'OrRd'

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

    list_prov_map = dm.df_rekap_prov[filter_]['Provinsi'].values
    selected_points = draw_map(list_prov_map)
    if len(selected_points) != 0:
        selected_provinsi_map = list_prov_map[selected_points[0]['pointIndex']]
        # Show filtered summary table
        if target_column is not None:
            filter_selection = (dm.df_rekap_prov['Provinsi'] == selected_provinsi_map) & (dm.df_rekap_prov[target_column] == selected_category)
        else:
            filter_selection = dm.df_rekap_prov['Provinsi'] == selected_provinsi_map
        data = dm.df_rekap_prov[filter_selection]
        data = data.drop(['Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent'], axis=1)
        data['Provinsi'] = get_link('Provinsi', data, nama_survei, selected_category)
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_column('Provinsi', cellRenderer=cell_renderer_prov)
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode2
        AgGrid(data, gridOptions=gridOptions, fit_columns_on_grid_load=False, allow_unsafe_jscode=True, height=65, update_mode=GridUpdateMode.VALUE_CHANGED)
            
    # ----------------------------------------------------------------------------------------------------------------------------
    # Recapitulation Table Level Provinsi
    st.markdown("---")

    with st.expander('Recapitulation Table'):

        if target_column is not None:
            title = f'Recapitulation Table at Provinsi Level (Category: {selected_category})'
        else:
            title = 'Recapitulation Table at Provinsi Level'
        st.markdown(f"<h6>{title}</h6>", unsafe_allow_html=True)

        data = dm.df_rekap_prov[filter_].sort_values('Provinsi')
        dropcols = ['Approved_percent', 'Rejected_percent', 'Awaiting_percent', 'Target_percent']
        data_download = data.drop(dropcols, axis=1)
        data['Provinsi'] = get_link('Provinsi', data, nama_survei, selected_category)
        if target_column is not None:
            dropcols += [target_column]
        data = data.drop(dropcols, axis=1)
        height = (1 + len(data)) * 29

        # Build Table
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_default_column(min_column_width=200)
        gb.configure_column('Provinsi', cellRenderer=cell_renderer_prov, pinned='left')
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode2
        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False, allow_unsafe_jscode=True, height=height, enableSorting=True, enableFilter=True, update_mode=GridUpdateMode.VALUE_CHANGED)             

        # Create a download button
        st.download_button(
            "Download Table",
            data=download_dataframe_as_excel(data_download),
            file_name="recapitulation.xlsx",
            mime="application/vnd.ms-excel",
        )


    # ----------------------------------------------------------------------------------------------------------------------------
    # Pivot Table
    st.markdown("---") 

    with st.expander('Pivot Table (Unfiltered)'):
        usecols = ['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan', 'Target', 'Approved', 'Deficit']
        if target_column is not None:
            usecols = [target_column] + usecols
        data = dm.df_rekap_all[usecols].sort_values(['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan'])
        height = 600
        # Build Table
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_column( field=target_column, pivot=True)
        for f in ['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan']:
            gb.configure_column(field=f, rowGroup=True)
        for f in ['Target', 'Approved', 'Deficit']:
            gb.configure_column(field=f, type=["numericColumn"], aggFunc="sum")
        gb.configure_grid_options(pivotMode=True)
        gridOptions = gb.build()
        ag_grid = AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True,allow_unsafe_jscode=True, height=height, enableSorting=True, enableFilter=True, update_mode=GridUpdateMode.VALUE_CHANGED)

        # Create a download button
        st.download_button(
            "Download Table",
            data=download_dataframe_as_excel(data),
            file_name="recapitulation_pivot.xlsx",
            mime="application/vnd.ms-excel",
        )

    # ----------------------------------------------------------------------------------------------------------------------------
    # Raw Table
    st.markdown("---")

    with st.expander('Raw Table (Unfiltered)'):
        data = dm.df
        height = get_table_height(data)
        gb = GridOptionsBuilder.from_dataframe(data)
        gb.configure_column('Link', cellRenderer=cell_link, pinned='right')
        gridOptions = gb.build()
        gridOptions['getRowStyle'] = jscode1

        AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False,
                allow_unsafe_jscode=True, height=height, 
                update_mode=GridUpdateMode.VALUE_CHANGED)
        
        # Create a download button
        st.download_button(
            "Download Table",
            data=download_dataframe_as_excel(data.drop(['Link'], axis=1)),
            file_name="raw_data.xlsx",
            mime="application/vnd.ms-excel",
        )

    # ----------------------------------------------------------------------------------------------------------------------------
    # Data Anomalies
    st.markdown("---")

    with st.expander('Data Anomalies'):
        tab1, tab2, tab3 = st.tabs(['Duplicates By Repondents', 'Duplicates By Kelurahan', 'Zero Target'])

        # Duplicates By Repondents
        with tab1:
            data = dm.df[dm.df[['PROV', 'KOTA_KAB', 'KEC', 'KEL', 'NAMA_KK', 'NAMA_RESPONDEN']].duplicated(keep=False)].sort_values('NAMA_RESPONDEN')
            height = get_table_height(data)
            gb = GridOptionsBuilder.from_dataframe(data)
            gb.configure_column('Link', cellRenderer=cell_link, pinned='right')
            gridOptions = gb.build()
            gridOptions['getRowStyle'] = jscode1
            AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=False,
                    allow_unsafe_jscode=True, height=height, 
                    update_mode=GridUpdateMode.VALUE_CHANGED)

        # Duplicates By Kelurahan
        with tab2:
            usecols = ['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan', 'Target', 'Sample', 'Approved']
            data = dm.df_rekap_all[dm.df_rekap_all['Kelurahan'].duplicated(keep=False)][usecols].sort_values('Kelurahan')
            data['Kelurahan'] = data.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&selected_kab_kota={x.Kabupaten_Kota}&selected_kecamatan={x.Kecamatan}&selected_kelurahan={x.Kelurahan}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Kelurahan}</a>', axis=1)
            height = get_table_height(data)
            gb = GridOptionsBuilder.from_dataframe(data)
            gb.configure_column('Kelurahan', cellRenderer=cell_renderer_kel)
            gb.configure_columns(['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan'], pinned='left')
            gridOptions = gb.build()
            AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=True,
                    allow_unsafe_jscode=True, height=height, 
                    update_mode=GridUpdateMode.VALUE_CHANGED)

        # Zero Target
        with tab3:
            data = dm.df_rekap_all[dm.df_rekap_all['Target']==0][usecols].sort_values('Kelurahan')
            data['Kelurahan'] = data.apply(lambda x : f'<a href="{DASHBOARD_HOST}/Local_Data?selected_provinsi={x.Provinsi}&selected_kab_kota={x.Kabupaten_Kota}&selected_kecamatan={x.Kecamatan}&selected_kelurahan={x.Kelurahan}&nama_survei={nama_survei}&selected_category={selected_category}" target="_blank">{x.Kelurahan}</a>', axis=1)
            height = get_table_height(data)
            gb = GridOptionsBuilder.from_dataframe(data)
            gb.configure_column('Kelurahan', cellRenderer=cell_renderer_kel)
            gb.configure_columns(['Provinsi', 'Kabupaten_Kota', 'Kecamatan', 'Kelurahan'], pinned='left')
            gridOptions = gb.build()
            AgGrid(data, gridOptions=gridOptions, enable_enterprise_modules=True, fit_columns_on_grid_load=True,
                    allow_unsafe_jscode=True, height=height, 
                    update_mode=GridUpdateMode.VALUE_CHANGED)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Rejected Enumerators
    st.markdown("---")

    with st.expander('Rejected Enumerators (Unfiltered)'):

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