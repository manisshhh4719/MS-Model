import streamlit as st
import pandas as pd
import numpy as np
import time
from io import BytesIO
from cleaner import process_all_files
from calculator import add_calculations, DEFAULT_INDIVIDUAL_FACTOR
from exporter import export_to_excel

st.set_page_config(
    page_title="Godrej Market Share Model",
    page_icon="G",
    layout="wide"
)

# --- Custom CSS ---
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #1F4E79; font-size: 2rem; font-weight: 700; }
    h2, h3 { color: #1F4E79; }
    .section-box {
        background-color: white;
        padding: 1.5rem;
        border-radius: 8px;
        border: 1px solid #dee2e6;
        margin-bottom: 1.5rem;
    }
    .status-success {
        background-color: #d4edda;
        color: #155724;
        padding: 0.6rem 1rem;
        border-radius: 5px;
        margin: 0.4rem 0;
        font-size: 0.9rem;
    }
    .status-info {
        background-color: #cce5ff;
        color: #004085;
        padding: 0.6rem 1rem;
        border-radius: 5px;
        margin: 0.4rem 0;
        font-size: 0.9rem;
    }
    .stButton > button {
        background-color: #1F4E79;
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.6rem 2rem;
        border-radius: 5px;
        width: 100%;
        font-size: 1rem;
    }
    .stButton > button:hover { background-color: #16375a; }
    .stDownloadButton > button {
        background-color: #28a745;
        color: white;
        font-weight: 600;
        border: none;
        padding: 0.6rem 2rem;
        border-radius: 5px;
        width: 100%;
        font-size: 1rem;
    }
    .stDownloadButton > button:hover { background-color: #1e7e34; }
    .file-item {
        background-color: #f1f3f5;
        padding: 0.4rem 0.8rem;
        border-radius: 4px;
        margin: 0.2rem 0;
        font-size: 0.9rem;
        color: #333;
    }
    .step-label {
        font-weight: 600;
        color: #1F4E79;
        font-size: 0.95rem;
    }
</style>
""", unsafe_allow_html=True)

# --- Header ---
st.markdown("<h1>Godrej Market Share Model</h1>", unsafe_allow_html=True)
st.markdown(
    "<p style='color:#555; margin-top:-0.5rem;'>Automated pipeline to clean, combine, calculate and export market share data.</p>",
    unsafe_allow_html=True
)
st.divider()

# --- Section 1: Individual Factor ---
st.markdown("### Individual Factor Configuration")

factor_option = st.radio(
    "Choose how to provide Individual Factor values:",
    ["Use Default (Editable)", "Upload Individual Factor File"],
    horizontal=True
)

final_factor_dict = {}

if factor_option == "Upload Individual Factor File":
    factor_file = st.file_uploader(
        "Upload CSV or Excel file. Any column names are fine. One column should have region names, other should have numeric values.",
        type=["csv", "xlsx", "xls"],
        key="factor_file"
    )

    if factor_file:
        try:
            if factor_file.name.endswith(".csv"):
                factor_df = pd.read_csv(factor_file)
            else:
                factor_df = pd.read_excel(factor_file, engine="openpyxl")

            str_cols = factor_df.select_dtypes(include=["object"]).columns.tolist()
            num_cols = factor_df.select_dtypes(include=["number"]).columns.tolist()

            if not str_cols or not num_cols:
                st.error("Could not detect region and factor columns. Please check your file.")
            else:
                location_col = str_cols[0]
                factor_col = num_cols[0]
                st.success(f"Detected: Region column = '{location_col}' | Factor column = '{factor_col}'")
                factor_df = factor_df[[location_col, factor_col]].dropna()
                final_factor_dict = dict(zip(factor_df[location_col], factor_df[factor_col]))
                st.dataframe(
                    factor_df.rename(columns={location_col: "Region", factor_col: "Individual Factor"}),
                    use_container_width=True,
                    height=300
                )
        except Exception as e:
            st.error(f"Error reading file: {str(e)}")

else:
    st.markdown(
        "<p style='color:#555; font-size:0.9rem;'>Edit any value directly in the table below before running the pipeline. U+R values are calculated automatically as average of U and R.</p>",
        unsafe_allow_html=True
    )

    default_ur_only = {k: v for k, v in DEFAULT_INDIVIDUAL_FACTOR.items()
                       if "(U)" in k or "(R)" in k or k in ["All India Urban", "All India Rural"]}

    default_df = pd.DataFrame(
        list(default_ur_only.items()),
        columns=["Region", "Individual Factor"]
    )

    edited_df = st.data_editor(
        default_df,
        use_container_width=True,
        num_rows="fixed",
        height=400,
        key="factor_editor",
        column_config={
            "Region": st.column_config.TextColumn("Region", disabled=True, width="large"),
            "Individual Factor": st.column_config.NumberColumn(
                "Individual Factor",
                min_value=0.0,
                max_value=10.0,
                step=0.01,
                format="%.2f"
            )
        }
    )

    final_factor_dict = dict(zip(edited_df["Region"], edited_df["Individual Factor"]))

st.divider()

# --- Section 2: File Upload ---
st.markdown("### Upload Category Files")
st.markdown(
    "<p style='color:#555; font-size:0.9rem;'>Upload one or more Excel files. Each file represents one category (Haircare, Creme, SHC etc.).</p>",
    unsafe_allow_html=True
)

uploaded_files = st.file_uploader(
    "Select Excel files",
    type=["xlsx", "xls"],
    accept_multiple_files=True,
    key="category_files"
)

if uploaded_files:
    st.markdown(f"**{len(uploaded_files)} file(s) ready:**")
    for f in uploaded_files:
        st.markdown(f"<div class='file-item'>{f.name}</div>", unsafe_allow_html=True)

st.divider()

# --- Section 3: Run Pipeline ---
if uploaded_files:
    st.markdown("### Run Pipeline")

    if not final_factor_dict:
        st.warning("Individual Factor values are empty. Please configure them above before running.")
    else:
        if st.button("Run Pipeline", type="primary"):

            status_area = st.empty()
            progress_bar = st.progress(0)
            log_area = st.empty()
            logs = []

            def log(msg):
                logs.append(msg)
                log_area.markdown(
                    "".join([f"<div class='status-info'>{l}</div>" for l in logs]),
                    unsafe_allow_html=True
                )

            # Step 1
            status_area.markdown("<div class='step-label'>Step 1 of 3 — Cleaning and combining all files...</div>", unsafe_allow_html=True)
            progress_bar.progress(5)
            try:
                master_df = process_all_files(uploaded_files)
                progress_bar.progress(40)
                log(f"Step 1 complete — {len(master_df):,} rows extracted from {len(uploaded_files)} file(s)")
            except Exception as e:
                st.error(f"Error in Step 1: {str(e)}")
                st.stop()

            # Step 2
            status_area.markdown("<div class='step-label'>Step 2 of 3 — Running calculations (Avg PPU, Units Estd, Sales Derived, MS%, Variance)...</div>", unsafe_allow_html=True)
            progress_bar.progress(45)
            try:
                master_df = add_calculations(master_df, final_factor_dict)
                progress_bar.progress(80)
                log(f"Step 2 complete — Calculations done. Final dataset has {len(master_df):,} rows and {len(master_df.columns)} columns")
            except Exception as e:
                st.error(f"Error in Step 2: {str(e)}")
                st.stop()

            # Step 3
            status_area.markdown("<div class='step-label'>Step 3 of 3 — Exporting to Excel...</div>", unsafe_allow_html=True)
            progress_bar.progress(85)
            try:
                output = export_to_excel(master_df)
                progress_bar.progress(100)
                log("Step 3 complete — Excel file ready for download")
            except Exception as e:
                st.error(f"Error in Step 3: {str(e)}")
                st.stop()

            status_area.markdown(
                "<div class='status-success'><strong>Pipeline complete.</strong> Your file is ready to download.</div>",
                unsafe_allow_html=True
            )

            st.divider()
            st.markdown("### Download Output")
            st.download_button(
                label="Download Master Clean Excel",
                data=output,
                file_name="Godrej_Master_Clean.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True
            )

            st.divider()
            st.markdown("### Preview (first 100 rows)")
            preview_cols = ["Category", "Region", "State", "Zone", "Urban_Rural",
                            "TG_Segment", "Flag", "Format", "Brand_Name", "Brand_SKU_Item"]
            available_cols = [c for c in preview_cols if c in master_df.columns]
            st.dataframe(master_df[available_cols].head(100), use_container_width=True)

else:
    st.info("Please upload at least one category Excel file to get started.")

st.divider()
st.markdown(
    "<p style='text-align:center; color:#aaa; font-size:0.8rem;'>Godrej Market Share Model | Internship Project</p>",
    unsafe_allow_html=True
)
