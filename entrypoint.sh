#!/bin/bash
python app/updater.py >> output.log &
streamlit run app/0_Global_Data.py --server.port 8501 --server.address 0.0.0.0