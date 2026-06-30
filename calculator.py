import pandas as pd
import numpy as np

# Default Individual Factor - only U and R regions (as confirmed)
DEFAULT_INDIVIDUAL_FACTOR = {
    "All India Urban": 1.50, "All India Rural": 1.80,
    "Delhi (U)": 0.00,
    "Punjab_Haryana (U)": 1.00, "Punjab_Haryana (R)": 1.90,
    "Rajasthan (U)": 1.32, "Rajasthan (R)": 1.24,
    "Uttar Pradesh (U)": 2.10, "Uttar Pradesh (R)": 1.87,
    "West Bengal (U)": 1.80, "West Bengal (R)": 1.62,
    "Bihar excl Jharkhand (U)": 1.00, "Bihar excl Jharkhand (R)": 1.00,
    "Jharkhand (U)": 1.00, "Jharkhand (R)": 1.00,
    "Guwahati (U)": 1.00, "Guwahati (R)": 1.00,
    "Delhi (R)": 1.00,
    "Orissa (U)": 1.00, "Orissa (R)": 1.70,
    "Maharashtra (U)": 1.85, "Maharashtra (R)": 1.85,
    "Gujarat (U)": 1.90, "Gujarat (R)": 1.85,
    "Madhya Pradesh excl Chha (U)": 1.40, "Madhya Pradesh excl Chha (R)": 1.30,
    "Chhattisgarh (U)": 1.00, "Chhattisgarh (R)": 1.00,
    "Tamil Nadu (U)": 2.84, "Tamil Nadu (R)": 3.90,
    "Karnataka (U)": 1.60, "Karnataka (R)": 1.73,
    "Kerala (U)": 1.10, "Kerala (R)": 7.88,
    "Andhra Pradesh excl Tela (U)": 1.50, "Andhra Pradesh excl Tela (R)": 1.55,
    "Telangana (U)": 1.00, "Telangana (R)": 1.63,
}

def compute_ur_factors(factor_dict):
    """Calculate U+R Individual Factor as simple average of U and R."""
    ur_factors = {}
    states = set()
    for region in factor_dict:
        state = region.replace(" (U)", "").replace(" (R)", "").strip()
        states.add(state)
    for state in states:
        u_val = factor_dict.get(f"{state} (U)")
        r_val = factor_dict.get(f"{state} (R)")
        if u_val is not None and r_val is not None:
            ur_factors[f"{state} (U+R)"] = round((u_val + r_val) / 2, 2)
        elif u_val is not None:
            ur_factors[f"{state} (U+R)"] = u_val
        elif r_val is not None:
            ur_factors[f"{state} (U+R)"] = r_val
    return ur_factors

def get_full_factor_dict(factor_dict):
    """Build complete factor dict including U+R."""
    full_dict = dict(factor_dict)
    ur_factors = compute_ur_factors(factor_dict)
    full_dict.update(ur_factors)
    return full_dict

def get_hh_periods(df):
    """Get all time periods from HH columns."""
    return [col.replace("HH__", "") for col in df.columns if col.startswith("HH__")]

def add_calculations(df, factor_dict):
    """
    Add all calculations:
    1. Individual Factor lookup per region
    2. Avg PPU = (Val * 1000) / (HH * Individual Factor)
    3. Units (for variance) = HH * Avg NOP  [at both SKU and Brand level]
    4. Units Estd = HH * Individual Factor * 1000
    5. Sales Derived = Units Estd * Avg PPU
    6. Brand_Units_Variance = Brand Units - Sum of SKU Units under that brand
    7. Value MS% and Units MS%
    """

    # Build complete factor lookup including U+R
    full_factor_dict = get_full_factor_dict(factor_dict)

    # Add Individual Factor per region
    df["Individual_Factor"] = df["Region"].map(full_factor_dict).fillna(1.0)

    # Get all time periods
    hh_periods = get_hh_periods(df)

    for period in hh_periods:
        hh_col = f"HH__{period}"
        val_col = f"Val__{period}"
        nop_col = f"Avg NOP__{period}"

        if hh_col not in df.columns or val_col not in df.columns:
            continue

        hh = pd.to_numeric(df[hh_col], errors="coerce").fillna(0)
        val = pd.to_numeric(df[val_col], errors="coerce").fillna(0)
        nop = pd.to_numeric(df[nop_col], errors="coerce").fillna(0) if nop_col in df.columns else pd.Series(0, index=df.index)
        factor = df["Individual_Factor"]

        # Units = HH * Avg NOP (for variance calculation at both SKU and Brand level)
        df[f"Units__{period}"] = (hh * nop).round(2)

        # Avg PPU = (Val * 1000) / (HH * Individual Factor)
        denominator = hh * factor
        df[f"Avg PPU__{period}"] = np.where(
            denominator != 0,
            (val * 1000) / denominator,
            0
        ).round(2)

        # Units Estd = HH * Individual Factor * 1000
        df[f"Units Estd__{period}"] = (hh * factor * 1000).round(2)

        # Sales Derived = Units Estd * Avg PPU
        df[f"Sales Derived__{period}"] = (
            df[f"Units Estd__{period}"] * df[f"Avg PPU__{period}"]
        ).round(2)

    # Add variance calculation
    df = add_variance(df, hh_periods)

    # Add MS% calculations
    df = add_market_share(df, hh_periods)

    # Add U+R rollup rows
    from cleaner import add_ur_rollup
    df = add_ur_rollup(df)

    return df

def add_variance(df, periods):
    """
    Variance = Brand Units - Sum of SKU Units under that brand.
    Brand Units = HH * Avg NOP at brand level
    Sum of SKU Units = sum of HH * Avg NOP for all SKUs under that brand
    """
    group_cols = ["Category", "Region", "TG_Segment", "Format", "Brand_Name", "Urban_Rural"]

    for period in periods:
        units_col = f"Units__{period}"
        if units_col not in df.columns:
            continue

        # Sum SKU units per brand group
        sku_rows = df[df["Flag"] == "Sub-brand"].copy()
        if sku_rows.empty:
            df[f"Variance__{period}"] = 0
            continue

        sku_sum = sku_rows.groupby(group_cols)[units_col].sum().reset_index()
        sku_sum = sku_sum.rename(columns={units_col: f"SKU_Sum_Units__{period}"})

        # Merge SKU sum back to brand rows
        df = df.merge(sku_sum, on=group_cols, how="left")

        # Variance = Brand Units - Sum of SKU Units (only meaningful at Brand level)
        df[f"Variance__{period}"] = np.where(
            df["Flag"] == "Brand",
            df[units_col] - df[f"SKU_Sum_Units__{period}"].fillna(0),
            0
        ).round(2)

        df = df.drop(columns=[f"SKU_Sum_Units__{period}"])

    return df

def add_market_share(df, periods):
    """
    Value MS% = Brand Sales Derived / Category Sales Derived * 100
    Units MS% = Brand Units Estd / Category Units Estd * 100
    For U+R: denominator = sum of U and R category rows
    """
    group_cols = ["Category", "Region", "TG_Segment", "Format", "Urban_Rural"]

    for period in periods:
        sales_col = f"Sales Derived__{period}"
        units_col = f"Units Estd__{period}"

        if sales_col not in df.columns:
            continue

        # Get category total for each group
        cat_rows = df[df["Flag"] == "Category"].copy()
        if cat_rows.empty:
            continue

        cat_sales = cat_rows.groupby(group_cols)[sales_col].sum().reset_index()
        cat_sales = cat_sales.rename(columns={sales_col: f"Cat_Sales__{period}"})

        cat_units = cat_rows.groupby(group_cols)[units_col].sum().reset_index()
        cat_units = cat_units.rename(columns={units_col: f"Cat_Units__{period}"})

        df = df.merge(cat_sales, on=group_cols, how="left")
        df = df.merge(cat_units, on=group_cols, how="left")

        # Value MS%
        df[f"Value MS%__{period}"] = np.where(
            df[f"Cat_Sales__{period}"].fillna(0) != 0,
            (df[sales_col] / df[f"Cat_Sales__{period}"]) * 100,
            0
        ).round(2)

        # Units MS%
        df[f"Units MS%__{period}"] = np.where(
            df[f"Cat_Units__{period}"].fillna(0) != 0,
            (df[units_col] / df[f"Cat_Units__{period}"]) * 100,
            0
        ).round(2)

        df = df.drop(columns=[f"Cat_Sales__{period}", f"Cat_Units__{period}"])

    return df
