import streamlit as st
import pandas as pd
import numpy as np
from io import BytesIO
from cleaner import process_all_files
from calculator import add_calculations, DEFAULT_INDIVIDUAL_FACTOR
from exporter import export_to_excel
from company_mapping import get_all_company_names, SAGAR_MAPPING, COMPANY_KEYWORDS

st.set_page_config(
    page_title="Godrej Market Share Model",
    page_icon="G",
    layout="wide"
)

st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .block-container { padding-top: 2rem; padding-bottom: 2rem; }
    h1 { color: #1F4E79; font-size: 2rem; font-weight: 700; }
    h2, h3 { color: #1F4E79; }
    .status-success {
        background-color: #d4edda; color: #155724;
        padding: 0.6rem 1rem; border-radius: 5px; margin: 0.4rem 0; font-size: 0.9rem;
    }
    .status-info {
        background-color: #cce5ff; color: #004085;
        padding: 0.6rem 1rem; border-radius: 5px; margin: 0.4rem 0; font-size: 0.9rem;
    }
    .file-item {
        background-color: #f1f3f5; padding: 0.4rem 0.8rem;
        border-radius: 4px; margin: 0.2rem 0; font-size: 0.9rem; color: #333;
    }
    .stButton > button {
        background-color: #1F4E79; color: white; font-weight: 600;
        border: none; padding: 0.6rem 2rem; border-radius: 5px; width: 100%; font-size: 1rem;
    }
    .stButton > button:hover { background-color: #16375a; }
    .stDownloadButton > button {
        background-color: #28a745; color: white; font-weight: 600;
        border: none; padding: 0.6rem 2rem; border-radius: 5px; width: 100%; font-size: 1rem;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("<h1>Godrej Market Share Model</h1>", unsafe_allow_html=True)
st.markdown("<p style='color:#555; margin-top:-0.5rem;'>Automated pipeline to clean, combine, calculate and export market share data.</p>", unsafe_allow_html=True)
st.divider()

# ─── SECTION 1: INDIVIDUAL FACTOR ────────────────────────────────────────────
st.markdown("### Individual Factor")
final_factor_dict = {}

with st.expander("View / Edit Individual Factor", expanded=False):
    factor_option = st.radio(
        "Choose how to provide Individual Factor values:",
        ["Use Default (Editable)", "Upload Individual Factor File"],
        horizontal=True,
        key="factor_option"
    )

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
                        use_container_width=True, height=300
                    )
            except Exception as e:
                st.error(f"Error reading file: {str(e)}")
    else:
        st.markdown("<p style='color:#555; font-size:0.9rem;'>Edit any value directly in the table. U+R values are calculated automatically.</p>", unsafe_allow_html=True)
        default_ur_only = {k: v for k, v in DEFAULT_INDIVIDUAL_FACTOR.items()
                           if "(U)" in k or "(R)" in k or k in ["All India Urban", "All India Rural"]}
        default_df = pd.DataFrame(list(default_ur_only.items()), columns=["Region", "Individual Factor"])
        edited_df = st.data_editor(
            default_df, use_container_width=True, num_rows="fixed", height=400,
            key="factor_editor",
            column_config={
                "Region": st.column_config.TextColumn("Region", disabled=True, width="large"),
                "Individual Factor": st.column_config.NumberColumn(
                    "Individual Factor", min_value=0.0, max_value=10.0, step=0.01, format="%.2f"
                )
            }
        )
        final_factor_dict = dict(zip(edited_df["Region"], edited_df["Individual Factor"]))

st.divider()

# ─── SECTION 2: COMPANY MAPPING ───────────────────────────────────────────────
st.markdown("### Company Mapping")

# Session state for extra mappings
if "extra_keywords" not in st.session_state:
    st.session_state.extra_keywords = {}
if "extra_mapping" not in st.session_state:
    st.session_state.extra_mapping = {}

all_companies = get_all_company_names()

with st.expander("View / Edit Company Mapping", expanded=False):

    tab1, tab2, tab3 = st.tabs(["Current Mapping", "Add by Keyword", "Upload Item List"])

    with tab1:
        st.markdown("**Built-in mapping from Sagar's list** (Brand_SKU_Item → Company)")
        mapping_df = pd.DataFrame(
            list(SAGAR_MAPPING.items()),
            columns=["Brand_SKU_Item", "Company"]
        )
        st.dataframe(mapping_df, use_container_width=True, height=350)

        if st.session_state.extra_keywords:
            st.markdown("**Your added keywords:**")
            kw_df = pd.DataFrame(
                list(st.session_state.extra_keywords.items()),
                columns=["Keyword", "Company"]
            )
            st.dataframe(kw_df, use_container_width=True)

        if st.session_state.extra_mapping:
            st.markdown("**Your uploaded item mappings:**")
            em_df = pd.DataFrame(
                list(st.session_state.extra_mapping.items()),
                columns=["Brand_SKU_Item", "Company"]
            )
            st.dataframe(em_df, use_container_width=True)

    with tab2:
        st.markdown("Add a new keyword → company mapping. If any Brand_SKU_Item contains this keyword, it gets assigned to that company.")
        col1, col2 = st.columns(2)
        with col1:
            new_keyword = st.text_input("Keyword (e.g. BBLUNT, STREAX)", key="new_keyword").strip().upper()
        with col2:
            company_input = st.selectbox(
                "Company name",
                options=[""] + all_companies + ["Add new company..."],
                key="keyword_company_select"
            )
            if company_input == "Add new company...":
                company_input = st.text_input("Type new company name", key="new_company_name").strip()

        if st.button("Add Keyword Mapping", key="add_keyword_btn"):
            if new_keyword and company_input and company_input != "Add new company...":
                st.session_state.extra_keywords[new_keyword] = company_input
                st.success(f"Added: '{new_keyword}' → '{company_input}'")
            else:
                st.warning("Please enter both a keyword and a company name.")

    with tab3:
        st.markdown("Upload a file with Brand_SKU_Item names and their company names. Partial/fuzzy matching is used — no exact match required.")
        uploaded_mapping = st.file_uploader(
            "Upload CSV or Excel (two columns: item name, company name)",
            type=["csv", "xlsx", "xls"],
            key="mapping_upload"
        )
        if uploaded_mapping:
            try:
                if uploaded_mapping.name.endswith(".csv"):
                    map_df = pd.read_csv(uploaded_mapping)
                else:
                    map_df = pd.read_excel(uploaded_mapping, engine="openpyxl")

                str_cols = map_df.select_dtypes(include=["object"]).columns.tolist()
                if len(str_cols) < 2:
                    st.error("File must have at least 2 text columns: item name and company name.")
                else:
                    item_col = str_cols[0]
                    company_col = str_cols[1]
                    st.success(f"Detected: Item column = '{item_col}' | Company column = '{company_col}'")
                    map_df = map_df[[item_col, company_col]].dropna()
                    st.dataframe(map_df.rename(columns={item_col: "Brand_SKU_Item", company_col: "Company"}),
                                 use_container_width=True, height=250)

                    # Auto-map new items using keyword matching if company column is empty
                    from company_mapping import get_company_name
                    new_mappings = {}
                    for _, row in map_df.iterrows():
                        item = str(row[item_col]).strip()
                        company = str(row[company_col]).strip()
                        if company and company.lower() not in ["nan", "none", ""]:
                            new_mappings[item] = company
                        else:
                            # Try keyword matching for items with no company
                            auto_company = get_company_name(item)
                            if auto_company != "Others / Unmapped":
                                new_mappings[item] = auto_company

                    if st.button("Apply This Mapping", key="apply_mapping_btn"):
                        st.session_state.extra_mapping.update(new_mappings)
                        st.success(f"Applied {len(new_mappings)} item mappings.")

            except Exception as e:
                st.error(f"Error reading file: {str(e)}")

st.divider()

# ─── SECTION 3: FILE UPLOAD ───────────────────────────────────────────────────
st.markdown("### Upload Category Files")
st.markdown("<p style='color:#555; font-size:0.9rem;'>Upload one or more Excel files. Each file represents one category.</p>", unsafe_allow_html=True)

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

# ─── SECTION 4: RUN PIPELINE ──────────────────────────────────────────────────
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

            status_area.markdown("<p style='font-weight:600; color:#1F4E79;'>Step 1 of 3 — Cleaning and combining all files...</p>", unsafe_allow_html=True)
            progress_bar.progress(5)
            try:
                master_df = process_all_files(
                    uploaded_files,
                    extra_mapping=st.session_state.extra_mapping,
                    extra_keywords=st.session_state.extra_keywords
                )
                progress_bar.progress(40)
                log(f"Step 1 complete — {len(master_df):,} rows extracted from {len(uploaded_files)} file(s)")
            except Exception as e:
                st.error(f"Error in Step 1: {str(e)}")
                st.stop()

            status_area.markdown("<p style='font-weight:600; color:#1F4E79;'>Step 2 of 3 — Running calculations...</p>", unsafe_allow_html=True)
            progress_bar.progress(45)
            try:
                master_df = add_calculations(master_df, final_factor_dict)
                progress_bar.progress(80)
                log(f"Step 2 complete — {len(master_df):,} rows, {len(master_df.columns)} columns")
            except Exception as e:
                st.error(f"Error in Step 2: {str(e)}")
                st.stop()

            status_area.markdown("<p style='font-weight:600; color:#1F4E79;'>Step 3 of 3 — Exporting to Excel...</p>", unsafe_allow_html=True)
            progress_bar.progress(85)
            try:
                output = export_to_excel(master_df)
                progress_bar.progress(100)
                log("Step 3 complete — Excel file ready")
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
st.markdown("<p style='text-align:center; color:#aaa; font-size:0.8rem;'>Godrej Market Share Model | Internship Project</p>", unsafe_allow_html=True)
