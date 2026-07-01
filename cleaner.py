import pandas as pd
import numpy as np
from company_mapping import get_company_name

# ─── LEVEL MAPPING ────────────────────────────────────────────────────────────
# Level = All India / Zone / State for each sheet
# This is used as a column in Master_Clean so pivot filters work without double counting

LEVEL_MAPPING = {
    "All India U+R": "All India",
    "All India Urban": "All India",
    "All India Rural": "All India",
    "North Zone(U+R)": "Zone",
    "North Zone(U)": "Zone",
    "North Zone(R)": "Zone",
    "GCPL East(U+R)": "Zone",
    "GCPL East(U)": "Zone",
    "GCPL East(R)": "Zone",
    "GCPL West(U+R)": "Zone",
    "GCPL West(U)": "Zone",
    "GCPL West(R)": "Zone",
    "South Zone(U+R)": "Zone",
    "South Zone(U)": "Zone",
    "South Zone(R)": "Zone",
}
# Everything else is State level (default)

# ─── ZONE MAPPING ─────────────────────────────────────────────────────────────
ZONE_MAPPING = {
    "All India U+R": "All India",
    "All India Urban": "All India",
    "All India Rural": "All India",
    "North Zone(U+R)": "North Zone",
    "North Zone(U)": "North Zone",
    "North Zone(R)": "North Zone",
    "GCPL East(U+R)": "GCPL East",
    "GCPL East(U)": "GCPL East",
    "GCPL East(R)": "GCPL East",
    "GCPL West(U+R)": "GCPL West",
    "GCPL West(U)": "GCPL West",
    "GCPL West(R)": "GCPL West",
    "South Zone(U+R)": "South Zone",
    "South Zone(U)": "South Zone",
    "South Zone(R)": "South Zone",
    "Delhi (U)": "North",
    "Punjab_Haryana (U+R)": "North", "Punjab_Haryana (U)": "North", "Punjab_Haryana (R)": "North",
    "Rajasthan (U+R)": "North", "Rajasthan (U)": "North", "Rajasthan (R)": "North",
    "Uttar Pradesh (U+R)": "North", "Uttar Pradesh (U)": "North", "Uttar Pradesh (R)": "North",
    "West Bengal (U+R)": "East", "West Bengal (U)": "East", "West Bengal (R)": "East",
    "Bihar excl Jharkhand (U+R)": "East", "Bihar excl Jharkhand (U)": "East", "Bihar excl Jharkhand (R)": "East",
    "Jharkhand (U+R)": "East", "Jharkhand (U)": "East", "Jharkhand (R)": "East",
    "Guwahati (U)": "East", "Guwahati (R)": "East",
    "Orissa (U+R)": "East", "Orissa (U)": "East", "Orissa (R)": "East",
    "Maharashtra (U+R)": "West", "Maharashtra (U)": "West", "Maharashtra (R)": "West",
    "Gujarat (U+R)": "West", "Gujarat (U)": "West", "Gujarat (R)": "West",
    "Madhya Pradesh excl Chha (U+R)": "West", "Madhya Pradesh excl Chha (U)": "West", "Madhya Pradesh excl Chha (R)": "West",
    "Chhattisgarh (U+R)": "West", "Chhattisgarh (U)": "West", "Chhattisgarh (R)": "West",
    "Tamil Nadu (U+R)": "South", "Tamil Nadu (U)": "South", "Tamil Nadu (R)": "South",
    "Karnataka (U+R)": "South", "Karnataka (U)": "South", "Karnataka (R)": "South",
    "Kerala (U+R)": "South", "Kerala (U)": "South", "Kerala (R)": "South",
    "Andhra Pradesh excl Tela (U+R)": "South", "Andhra Pradesh excl Tela (U)": "South", "Andhra Pradesh excl Tela (R)": "South",
    "Telangana (U+R)": "South", "Telangana (U)": "South", "Telangana (R)": "South",
}

# ─── EXCLUDED SHEETS ──────────────────────────────────────────────────────────
# Only exclude AP+Tel (duplicate of Andhra Pradesh excl Tela)
# Keep ALL other sheets including U+R, Zone, All India
EXCLUDED_SHEETS = [
    "AP+Tel(U+R)", "AP+Tel(U)", "AP+Tel(R)",
]

# ─── TG SEGMENT START ROWS ────────────────────────────────────────────────────
TG_SEGMENTS = {
    "TOTAL": 6,
    "SEC A": 114,
    "SEC B": 223,
    "SEC C": 332,
    "SEC D/E": 441
}

def get_level(region_name):
    """Get geographic level: All India / Zone / State."""
    return LEVEL_MAPPING.get(region_name, "State")

def get_urban_rural(region_name):
    """Extract Urban/Rural tag from region name."""
    if "(U+R)" in region_name:
        return "U+R"
    elif "(U)" in region_name or "Urban" in region_name:
        return "U"
    elif "(R)" in region_name or "Rural" in region_name:
        return "R"
    else:
        return "U+R"

def get_state_name(region_name):
    """Extract clean state name without U/R suffix."""
    if region_name in ["All India Urban", "All India Rural", "All India U+R"]:
        return "All India"
    name = region_name
    for suffix in [" (U+R)", " (U)", " (R)", "(U+R)", "(U)", "(R)"]:
        name = name.replace(suffix, "")
    return name.strip()

def get_flag(product):
    """Determine Flag (Category/Brand/Sub-brand) from product name."""
    product_upper = product.upper()
    if "] ANY " in product_upper or product_upper.startswith("[HCEXL] ANY") or \
       product_upper.startswith("[HEXLI] ANY") or product_upper.startswith("[COLOR] ANY"):
        return "Category"
    elif product.startswith("[HCEXL]") or product.startswith("[HEXLI]") or \
         product.startswith("[COLOR]"):
        return "Brand"
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

    # Region metadata
    urban_rural = get_urban_rural(sheet_name)
    state_name = get_state_name(sheet_name)
    zone = ZONE_MAPPING.get(sheet_name, "Unknown")
    level = get_level(sheet_name)

    current_brand = ""

    for seg_name, seg_start in TG_SEGMENTS.items():
        for i in range(seg_start, len(data)):
            row = data[i]
            if not row or len(row) < 5:
                continue

            product = str(row[4]) if row[4] is not None else ""
            if product in ["nan", "None"]:
                product = ""

            if "Target Group" in product or "Universe" in product:
                break

            if not product.strip():
                continue

            flag = get_flag(product)

            if flag == "Brand":
                current_brand = get_company_name(
                    product,
                    extra_mapping=extra_mapping,
                    extra_keywords=extra_keywords
                )
            elif flag == "Category":
                current_brand = "All Brands"

            new_row = {
                "Category": category,
                "Level": level,
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

def process_all_files(uploaded_files, extra_mapping=None, extra_keywords=None):
    """Process all uploaded Excel files and return combined master dataframe."""
    all_rows = []

    for uploaded_file in uploaded_files:
        category = get_category_from_filename(uploaded_file.name)

        try:
            xl = pd.ExcelFile(uploaded_file, engine="openpyxl")
            sheet_names = xl.sheet_names

            for sheet_name in sheet_names:
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
                    rows = process_single_sheet(
                        data, sheet_name, category,
                        extra_mapping=extra_mapping,
                        extra_keywords=extra_keywords
                    )
                    all_rows.extend(rows)
                except Exception as e:
                    print(f"Warning: Could not process sheet {sheet_name}: {str(e)}")
                    continue

        except Exception as e:
            raise Exception(f"Could not read file {uploaded_file.name}: {str(e)}")

    if not all_rows:
        raise Exception("No data was extracted. Please check your files.")

    master_df = pd.DataFrame(all_rows)

    metadata_keywords = ["Universe", "TG Base", "Target Group"]
    mask = master_df["Brand_SKU_Item"].apply(
        lambda x: not any(kw in str(x) for kw in metadata_keywords)
    )
    master_df = master_df[mask].reset_index(drop=True)

    return master_df
