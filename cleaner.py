import pandas as pd
import numpy as np
from company_mapping import get_company_name

# Zone to State mapping (only U and R sheets, no U+R in raw data)
ZONE_MAPPING = {
    "All India Urban": "All India", "All India Rural": "All India",
    "North Zone(U)": "North Zone", "North Zone(R)": "North Zone",
    "GCPL East(U)": "GCPL East", "GCPL East(R)": "GCPL East",
    "GCPL West(U)": "GCPL West", "GCPL West(R)": "GCPL West",
    "South Zone(U)": "South Zone", "South Zone(R)": "South Zone",
    "Delhi (U)": "North",
    "Punjab_Haryana (U)": "North", "Punjab_Haryana (R)": "North",
    "Rajasthan (U)": "North", "Rajasthan (R)": "North",
    "Uttar Pradesh (U)": "North", "Uttar Pradesh (R)": "North",
    "West Bengal (U)": "East", "West Bengal (R)": "East",
    "Bihar excl Jharkhand (U)": "East", "Bihar excl Jharkhand (R)": "East",
    "Jharkhand (U)": "East", "Jharkhand (R)": "East",
    "Guwahati (U)": "East", "Guwahati (R)": "East",
    "Orissa (U)": "East", "Orissa (R)": "East",
    "Maharashtra (U)": "West", "Maharashtra (R)": "West",
    "Gujarat (U)": "West", "Gujarat (R)": "West",
    "Madhya Pradesh excl Chha (U)": "West", "Madhya Pradesh excl Chha (R)": "West",
    "Chhattisgarh (U)": "West", "Chhattisgarh (R)": "West",
    "Tamil Nadu (U)": "South", "Tamil Nadu (R)": "South",
    "Karnataka (U)": "South", "Karnataka (R)": "South",
    "Kerala (U)": "South", "Kerala (R)": "South",
    "Andhra Pradesh excl Tela (U)": "South", "Andhra Pradesh excl Tela (R)": "South",
    "Telangana (U)": "South", "Telangana (R)": "South",
}

# Sheets to exclude completely
EXCLUDED_SHEETS = [
    "AP+Tel(U+R)", "AP+Tel(U)", "AP+Tel(R)",
    "All India U+R", "North Zone(U+R)", "GCPL East(U+R)", "GCPL West(U+R)",
    "South Zone(U+R)", "Punjab_Haryana (U+R)", "Rajasthan (U+R)",
    "Uttar Pradesh (U+R)", "West Bengal (U+R)", "Bihar excl Jharkhand (U+R)",
    "Jharkhand (U+R)", "Orissa (U+R)", "Maharashtra (U+R)", "Gujarat (U+R)",
    "Madhya Pradesh excl Chha (U+R)", "Chhattisgarh (U+R)", "Tamil Nadu (U+R)",
    "Karnataka (U+R)", "Kerala (U+R)", "Andhra Pradesh excl Tela (U+R)",
    "Telangana (U+R)"
]

# TG segment start rows (0-indexed)
TG_SEGMENTS = {
    "TOTAL": 6,
    "SEC A": 114,
    "SEC B": 223,
    "SEC C": 332,
    "SEC D/E": 441
}

def get_urban_rural(region_name):
    """Extract Urban/Rural tag from region name."""
    if "(U)" in region_name or "Urban" in region_name:
        return "U"
    elif "(R)" in region_name or "Rural" in region_name:
        return "R"
    else:
        return "U"

def get_state_name(region_name):
    """Extract clean state name without U/R suffix."""
    if region_name in ["All India Urban", "All India Rural"]:
        return "All India"
    name = region_name
    for suffix in [" (U+R)", " (U)", " (R)", "(U+R)", "(U)", "(R)"]:
        name = name.replace(suffix, "")
    return name.strip()

def get_flag(product):
    """Determine Flag (Category/Brand/Sub-brand) from product name."""
    product_upper = product.upper()
    # Category = ANY line items
    if "] ANY " in product_upper or product_upper.startswith("[HCEXL] ANY") or \
       product_upper.startswith("[HEXLI] ANY") or product_upper.startswith("[COLOR] ANY"):
        return "Category"
    # Brand = [HCEXL] / [HEXLI] / [COLOR] prefixed items that are not Category
    elif product.startswith("[HCEXL]") or product.startswith("[HEXLI]") or \
         product.startswith("[COLOR]"):
        return "Brand"
    # Sub-brand = everything else (actual SKU level)
    else:
        return "Sub-brand"

def get_category_from_filename(filename):
    """Extract category name from filename."""
    name = filename.replace(".xlsx", "").replace(".xls", "").strip()
    name_lower = name.lower()
    if "hair" in name_lower or "hc" in name_lower.split("_")[0]:
        return "Haircare"
    elif "body" in name_lower or "bc" in name_lower.split("_")[0]:
        return "Bodycare"
    elif "creme" in name_lower:
        return "Creme"
    elif "powder" in name_lower:
        return "Powders"
    elif "henna" in name_lower:
        return "Henna"
    else:
        return name

def process_single_sheet(data, sheet_name, category, extra_mapping=None, extra_keywords=None):
    """Process one sheet and return cleaned rows."""
    rows = []

    if len(data) < 6:
        return rows

    # Get metric and period rows (row index 3 and 4)
    metric_row = data[3] if len(data) > 3 else []
    period_row = data[4] if len(data) > 4 else []

    # Build column names
    col_names = []
    current_metric = ""
    for i in range(len(metric_row)):
        val = str(metric_row[i]) if metric_row[i] is not None else ""
        if val and val not in ["nan", "None", ""]:
            current_metric = val.strip()
        period = str(period_row[i]) if period_row[i] is not None else ""
        if period in ["nan", "None"]:
            period = ""
        if i < 5:
            col_names.append(f"id_{i}")
        else:
            col_names.append(f"{current_metric}__{period}")

    # Get urban/rural and state info
    urban_rural = get_urban_rural(sheet_name)
    state_name = get_state_name(sheet_name)
    zone = ZONE_MAPPING.get(sheet_name, "Unknown")

    current_brand = ""

    for seg_name, seg_start in TG_SEGMENTS.items():
        for i in range(seg_start, len(data)):
            row = data[i]
            if not row or len(row) < 5:
                continue

            product = str(row[4]) if row[4] is not None else ""
            if product in ["nan", "None"]:
                product = ""

            # Stop at next segment header
            if "Target Group" in product or "Universe" in product:
                break

            # Skip empty rows
            if not product.strip():
                continue

            # Determine flag
            flag = get_flag(product)

            # Track current brand using company mapping
            if flag == "Brand":
                current_brand = get_company_name(
                    product,
                    extra_mapping=extra_mapping,
                    extra_keywords=extra_keywords
                )
            elif flag == "Category":
                current_brand = "All Brands"

            # Build identifier columns
            new_row = {
                "Category": category,
                "Region": sheet_name,
                "State": state_name,
                "Zone": zone,
                "Urban_Rural": urban_rural,
                "TG_Segment": seg_name,
                "Flag": flag,
                "Format": str(row[1]).strip() if row[1] is not None else "",
                "Grammage": str(row[2]).strip() if row[2] is not None else "",
                "SU": str(row[3]).strip() if row[3] is not None else "",
                "Brand_Name": current_brand,
                "Brand_SKU_Item": product,
            }

            # Add all metric columns
            for j in range(5, len(row)):
                if j < len(col_names):
                    val = row[j]
                    if val is None or str(val) in ["nan", "None", ""]:
                        val = 0.0
                    try:
                        val = float(val)
                    except:
                        val = 0.0
                    new_row[col_names[j]] = val

            rows.append(new_row)

    return rows

def add_ur_rollup(master_df):
    """
    Create U+R rows by summing ONLY additive raw base metrics (HH, Vol, Val,
    Avg Cons, Avg FOP, Avg POC) from U and R rows for the same State + TG_Segment +
    Flag + Format + Brand_SKU_Item + Category.

    IMPORTANT: Avg NOP, Avg PPU, Units, Units Estd, Sales Derived, Value MS%,
    Units MS%, Variance and Individual_Factor are NOT summed here because they
    are ratios/derived values, not additive quantities. They must be
    recalculated fresh on the combined U/R/U+R dataset AFTER this rollup runs
    (see add_calculations in calculator.py, which calls this function first,
    then runs add_calculations_core on the result).

    U+R Individual Factor = (U Factor + R Factor) / 2, set separately.
    """
    id_cols = ["Category", "Region", "State", "Zone", "Urban_Rural",
               "TG_Segment", "Flag", "Format", "Grammage", "SU",
               "Brand_Name", "Brand_SKU_Item"]

    # Only these raw metrics are safe to sum directly (they are true counts/totals)
    ADDITIVE_METRIC_PREFIXES = ["HH__", "Vol__", "Val__", "Avg Cons__", "Avg FOP__", "Avg POC__"]
    additive_cols = [c for c in master_df.columns
                      if any(c.startswith(p) for p in ADDITIVE_METRIC_PREFIXES)]

    # Avg NOP is a weighted average, not additive -- approximate via HH-weighted average
    nop_cols = [c for c in master_df.columns if c.startswith("Avg NOP__")]

    group_cols = ["Category", "State", "TG_Segment", "Flag",
                  "Format", "Grammage", "SU", "Brand_Name", "Brand_SKU_Item"]

    # Sum the truly additive columns
    ur_rows = master_df.groupby(group_cols)[additive_cols].sum().reset_index()

    # HH-weighted average for Avg NOP per period (so Units = HH*NOP stays consistent)
    for nop_col in nop_cols:
        period = nop_col.replace("Avg NOP__", "")
        hh_col = f"HH__{period}"
        if hh_col not in master_df.columns:
            continue
        tmp = master_df[group_cols + [hh_col, nop_col]].copy()
        tmp["_weighted"] = tmp[hh_col] * tmp[nop_col]
        agg = tmp.groupby(group_cols).agg(
            _hh_sum=(hh_col, "sum"),
            _weighted_sum=("_weighted", "sum")
        ).reset_index()
        agg[nop_col] = np.where(
            agg["_hh_sum"] != 0,
            agg["_weighted_sum"] / agg["_hh_sum"],
            0
        ).round(2)
        ur_rows = ur_rows.merge(agg[group_cols + [nop_col]], on=group_cols, how="left")

    # Add U+R identifier columns
    ur_rows["Urban_Rural"] = "U+R"
    ur_rows["Region"] = ur_rows["State"] + " (U+R)"

    # Zone stays same as state zone
    zone_lookup = master_df[["State", "Zone"]].drop_duplicates().set_index("State")["Zone"]
    ur_rows["Zone"] = ur_rows["State"].map(zone_lookup)

    # Individual Factor for U+R = average of U and R factors
    if "Individual_Factor" in master_df.columns:
        u_factors = master_df[master_df["Urban_Rural"] == "U"].groupby("State")["Individual_Factor"].mean()
        r_factors = master_df[master_df["Urban_Rural"] == "R"].groupby("State")["Individual_Factor"].mean()
        ur_factors = ((u_factors + r_factors) / 2).fillna(1.0)
        ur_rows["Individual_Factor"] = ur_rows["State"].map(ur_factors).fillna(1.0)

    # Combine original U/R rows (raw base metrics only) + new U+R rows
    base_cols = id_cols + additive_cols + nop_cols + (["Individual_Factor"] if "Individual_Factor" in master_df.columns else [])
    base_cols = [c for c in base_cols if c in master_df.columns]

    combined = pd.concat([master_df[base_cols], ur_rows[base_cols]], ignore_index=True)
    combined = combined.sort_values(
        ["Category", "State", "Urban_Rural", "TG_Segment", "Flag", "Brand_SKU_Item"]
    ).reset_index(drop=True)

    return combined

def process_all_files(uploaded_files, extra_mapping=None, extra_keywords=None):
    """Process all uploaded Excel files and return combined master dataframe."""
    all_rows = []

    for uploaded_file in uploaded_files:
        category = get_category_from_filename(uploaded_file.name)

        try:
            xl = pd.ExcelFile(uploaded_file, engine="openpyxl")
            sheet_names = xl.sheet_names

            for sheet_name in sheet_names:
                # Skip excluded sheets
                if sheet_name in EXCLUDED_SHEETS:
                    continue

                try:
                    df = pd.read_excel(
                        uploaded_file,
                        sheet_name=sheet_name,
                        header=None,
                        engine="openpyxl"
                    )
                    data = df.values.tolist()
                    rows = process_single_sheet(data, sheet_name, category, extra_mapping=extra_mapping, extra_keywords=extra_keywords)
                    all_rows.extend(rows)
                except Exception as e:
                    print(f"Warning: Could not process sheet {sheet_name}: {str(e)}")
                    continue

        except Exception as e:
            raise Exception(f"Could not read file {uploaded_file.name}: {str(e)}")

    if not all_rows:
        raise Exception("No data was extracted. Please check your files.")

    master_df = pd.DataFrame(all_rows)

    # Remove metadata rows
    metadata_keywords = ["Universe", "TG Base", "Target Group"]
    mask = master_df["Brand_SKU_Item"].apply(
        lambda x: not any(kw in str(x) for kw in metadata_keywords)
    )
    master_df = master_df[mask].reset_index(drop=True)

    return master_df
