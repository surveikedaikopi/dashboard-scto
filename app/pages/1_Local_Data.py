import sys
sys.path.append('../')
import yaml
from module import *
import streamlit as st
import plotly.express as px
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
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

    # load surveys
    _, list_survei, update_time, target_columns = get_survey_names()
    if len(list_survei) == 0:
        st.error('Database is empty.')
        st.stop()

    st.session_state.tabel_rekapitulasi = True

    # ----------------------------------------------------------------------------------------------------------------------------
    # Define States

    if 'nama_survei' in st.session_state:
        nama_survei = st.experimental_set_query_params(nama_survei=st.session_state.nama_survei)
    if 'selected_provinsi' in st.session_state:
        selected_provinsi = st.experimental_set_query_params(selected_provinsi=st.session_state.selected_provinsi)
    if 'selected_kab_kota' in st.session_state:
        selected_kab_kota = st.experimental_set_query_params(selected_kab_kota=st.session_state.selected_kab_kota, selected_provinsi=st.session_state.selected_provinsi)
    if 'selected_kecamatan' in st.session_state:
        selected_kecamatan = st.experimental_set_query_params(selected_kecamatan=st.session_state.selected_kecamatan, selected_kab_kota=st.session_state.selected_kab_kota, selected_provinsi=st.session_state.selected_provinsi)
    if 'selected_kelurahan' in st.session_state:
        selected_kelurahan = st.experimental_set_query_params(selected_kelurahan=st.session_state.selected_kelurahan, selected_kecamatan=st.session_state.selected_kecamatan, selected_kab_kota=st.session_state.selected_kab_kota, selected_provinsi=st.session_state.selected_provinsi)

    query_params = st.experimental_get_query_params()
    param_nama_survei = query_params.get('nama_survei', [None])
    param_category = query_params.get('selected_category', [None])
    param_provinsi = query_params.get('selected_provinsi', [None])
    param_kab_kota = query_params.get('selected_kab_kota', [None])
    param_kecamatan = query_params.get('selected_kecamatan', [None])
    param_kelurahan = query_params.get('selected_kelurahan', [None])

    # nama survei
    if param_nama_survei[0] is not None:
        nama_survei = param_nama_survei[0]
    else:
        nama_survei = list_survei[0]

    # ----------------------------------------------------------------------------------------------------------------------------
    # Base Data Mart

    # Build base datamart
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
        if param_category[0] is not None:
            selected_category = st.sidebar.selectbox('Target Category', target_categories, index=target_categories.index(param_category[0]))
        else:
            selected_category = st.sidebar.selectbox('Target Category', target_categories)
        st.sidebar.markdown("---")
        if selected_category != param_category[0]:
            st.session_state.change_selected_category = True
        st.session_state.selected_category = selected_category
    else:
        selected_category = None

    # ----------------------------------------------------------------------------------------------------------------------------
    # Category Filter
    if target_column is not None:
        filter_ = dm.df_rekap_prov[target_column] == selected_category
    else:
        filter_ = pd.Series([True] * len(dm.df_rekap_prov))

    dm.get_list_location(target_column, selected_category)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Define Filters

    # provinsi
    if param_provinsi[0] is not None:
        selected_provinsi = st.sidebar.selectbox('Provinsi', dm.list_provinsi, index=dm.list_provinsi.index(param_provinsi[0]))
    else:
        selected_provinsi = st.sidebar.selectbox('Provinsi', dm.list_provinsi)
    if selected_provinsi != param_provinsi[0]:
        st.session_state.change_selected_provinsi = True
    st.session_state.selected_provinsi = selected_provinsi
    if target_column is not None:
        st.experimental_set_query_params(selected_provinsi=selected_provinsi, selected_category=selected_category)
    else:
        st.experimental_set_query_params(selected_provinsi=selected_provinsi)

    # kab/kota
    list_kabkota_prov = [i for i in dm.list_kab_kota if i in dm.df[dm.df['PROV']==selected_provinsi]['KOTA_KAB'].tolist()] + ['ALL']
    if (param_kab_kota[0] is not None) & ('change_selected_provinsi' not in st.session_state):
        selected_kab_kota = st.sidebar.selectbox('Kabupaten/Kota', list_kabkota_prov, index=list_kabkota_prov.index(param_kab_kota[0]))
    else:
        selected_kab_kota = st.sidebar.selectbox('Kabupaten/Kota', list_kabkota_prov, index=list_kabkota_prov.index('ALL'))
    if selected_kab_kota != param_kab_kota[0]:
        st.session_state.change_selected_kab_kota = True
    st.session_state.selected_kab_kota = selected_kab_kota
    if target_column is not None:
        st.experimental_set_query_params(selected_kab_kota=selected_kab_kota, selected_provinsi=selected_provinsi, selected_category=selected_category)
    else:
        st.experimental_set_query_params(selected_kab_kota=selected_kab_kota, selected_provinsi=selected_provinsi)

    # kecamatan
    list_kec_kabkota = [i for i in dm.list_kecamatan if i in dm.df[dm.df['KOTA_KAB']==selected_kab_kota]['KEC'].tolist()] + ['ALL']
    if (param_kecamatan[0] is not None) & ('change_selected_kab_kota' not in st.session_state):
        selected_kecamatan = st.sidebar.selectbox('Kecamatan', list_kec_kabkota, index=list_kec_kabkota.index(param_kecamatan[0]))
    else:
        selected_kecamatan = st.sidebar.selectbox('Kecamatan', list_kec_kabkota, index=list_kec_kabkota.index('ALL'))
    if selected_kecamatan != param_kecamatan[0]:
        st.session_state.change_selected_kecamatan = True
    st.session_state.selected_kecamatan = selected_kecamatan
    if target_column is not None:
        st.experimental_set_query_params(selected_kecamatan=selected_kecamatan, selected_kab_kota=selected_kab_kota, selected_provinsi=selected_provinsi, selected_category=selected_category)
    else:
        st.experimental_set_query_params(selected_kecamatan=selected_kecamatan, selected_kab_kota=selected_kab_kota, selected_provinsi=selected_provinsi)

    # kelurahan
    list_kel_kec = [i for i in dm.list_kelurahan if i in dm.df[dm.df['KEC']==selected_kecamatan]['KEL'].tolist()] + ['ALL']
    if (param_kelurahan[0] is not None) & ('change_selected_kecamatan' not in st.session_state):
        selected_kelurahan = st.sidebar.selectbox('Kelurahan', list_kel_kec, index=list_kel_kec.index(param_kelurahan[0]))
    else:
        selected_kelurahan = st.sidebar.selectbox('Kelurahan', list_kel_kec, index=list_kel_kec.index('ALL'))
    st.session_state.selected_kelurahan = selected_kelurahan
    if target_column is not None:
        st.experimental_set_query_params(selected_kelurahan=selected_kelurahan, selected_kecamatan=selected_kecamatan, selected_kab_kota=selected_kab_kota, selected_provinsi=selected_provinsi, selected_category=selected_category)
    else:
        st.experimental_set_query_params(selected_kelurahan=selected_kelurahan, selected_kecamatan=selected_kecamatan, selected_kab_kota=selected_kab_kota, selected_provinsi=selected_provinsi)

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

    # set dataframe for get_agg_target
    if target_column is not None:
        dm.tdf = dm.df[selection1]

    # ----------------------------------------------------------------------------------------------------------------------------
    # Title and Subtitle

    # Title
    title_h1(nama_survei)

    if selected_category is not None:
        text = f'Target Category: {selected_category}'
        st.markdown(f"<h6 style='text-align: center; color: #5e6ff9;'>{text}</h6>", unsafe_allow_html=True)

    # location info
    text = f'PROV. {selected_provinsi}'
    if selected_kab_kota != 'ALL':
        text = f'{selected_kab_kota} --- ' + text
        if selected_kecamatan != 'ALL':
            text = f'KEC. {selected_kecamatan} --- ' + text
            if selected_kelurahan != 'ALL':
                text = f'KEL. {selected_kelurahan} --- '  + text
    #     
    st.markdown(f"<h5 style='text-align: center; color: #8e44ad;'>{text}</h5>", unsafe_allow_html=True)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Metrics: total numbers

    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    col1.metric('Total Data', dm.n_data)
    col2.metric('Total Responden', dm.n_resp)
    col3.metric('Total KK', dm.n_kk)
    col4.metric('Total Enumerator', dm.n_enum)
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
        # create doughnut chart
        fig = px.pie(data, values='Count', names='Status', hole=.6, color='Status', color_discrete_map=color_map2)
        # set chart layout
        fig.update_layout(
            title='Review Status' if target_column is None else f'Review Status ({selected_category})',
            font=dict(size=16,),
        )
        # Show chart
        pie1.plotly_chart(fig, use_container_width=True)

    status_piechart(dm.agg_status)

    # ----------------------------------------------------------------------------------------------------------------------------
    # Target Status: Bar Chart

    if target_column is not None:
        
        def target_piechart(data):
            fig = px.bar(data, x='Target', y='Count', color='Status', color_discrete_map=color_map2)
            # set chart layout
            fig.update_layout(
                barmode='group',
                title='Status By Target Category',
                showlegend=True,
                font=dict(size=16),
                xaxis={'categoryorder': 'total descending'}
            )
            # Show chart
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
            if selected_category is not None:
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

    expander = st.expander('Raw Table (Filtered)')

    with expander:

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