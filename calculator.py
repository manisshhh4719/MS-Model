import pandas as pd
import numpy as np

# ─── INDIVIDUAL FACTOR ────────────────────────────────────────────────────────
# Only state-level U and R regions have Individual Factors
# U+R, Zone, and All India levels do NOT have their own IF
# Their Sales Derived = sum of state U and R Sales Derived (handled by pivot)

DEFAULT_INDIVIDUAL_FACTOR = {
    "All India Urban": 1.50, "All India Rural": 1.80,
    "Delhi (U)": 0.00, "Delhi (R)": 1.00,
    "Punjab_Haryana (U)": 1.00, "Punjab_Haryana (R)": 1.90,
    "Rajasthan (U)": 1.32, "Rajasthan (R)": 1.24,
    "Uttar Pradesh (U)": 2.10, "Uttar Pradesh (R)": 1.87,
    "West Bengal (U)": 1.80, "West Bengal (R)": 1.62,
    "Bihar excl Jharkhand (U)": 1.00, "Bihar excl Jharkhand (R)": 1.00,
    "Jharkhand (U)": 1.00, "Jharkhand (R)": 1.00,
    "Guwahati (U)": 1.00, "Guwahati (R)": 1.00,
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

def get_hh_periods(df):
    """Get all time periods from HH columns."""
    return [col.replace("HH__", "") for col in df.columns if col.startswith("HH__")]

def add_calculations(df, factor_dict):
    """
    Calculate Avg PPU, Units Estd, Sales Derived, Variance and MS%
    directly for every row at every level (State U/R, Zone U+R, All India U+R).

    Key principle (per Sagar):
    - Individual Factor only applies at state U and R level
    - For U+R, Zone, All India: IF=1 (no adjustment needed since their raw
      HH/Val/NOP already reflect the correct aggregate survey values)
    - Sales Derived = Val * IF * 1,000,000
    - U+R totals come directly from raw U+R sheets (not rolled up by us)

    Formulas:
    - Avg PPU = (Val * 1000) / (HH * Avg NOP)
    - Units Estd = HH * IF * Avg NOP * 1000
    - Sales Derived = Units Estd * Avg PPU = Val * IF * 1,000,000
    - Value MS% = Brand Sales Derived / Category Sales Derived * 100
    - Units MS% = Brand Units Estd / Category Units Estd * 100
    - Variance = Brand Units Estd - Sum of Sub-brand Units Estd
    """

    # Assign Individual Factor per region
    # U+R, Zone, All India rows get IF=1 (their raw data is already correct)
    def get_if(region):
        return factor_dict.get(region, 1.0)

    df["Individual_Factor"] = df["Region"].apply(get_if)

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

        # Units = HH * Avg NOP (for variance)
        df[f"Units__{period}"] = (hh * nop).round(2)

        # Avg PPU = (Val * 1000) / (HH * Avg NOP)
        denom_ppu = hh * nop
        df[f"Avg PPU__{period}"] = np.where(
            denom_ppu != 0,
            (val * 1000) / denom_ppu,
            0
        ).round(2)

        # Units Estd = HH * IF * Avg NOP * 1000
        df[f"Units Estd__{period}"] = (hh * factor * nop * 1000).round(2)

        # Sales Derived = Units Estd * Avg PPU = Val * IF * 1,000,000
        df[f"Sales Derived__{period}"] = (
            df[f"Units Estd__{period}"] * df[f"Avg PPU__{period}"]
        ).round(2)

    # Variance and MS% only meaningful at State level
    # but we calculate for all levels so pivot works at any level
    df = add_variance(df, hh_periods)
    df = add_market_share(df, hh_periods)

    return df

def add_variance(df, periods):
    """
    Variance = Brand Units Estd - Sum of Sub-brand Units Estd under that brand.
    Calculated within each Region + TG_Segment + Format group.
    """
    group_cols = ["Category", "Region", "TG_Segment", "Format", "Brand_Name", "Urban_Rural", "Level"]
    group_cols = [c for c in group_cols if c in df.columns]

    for period in periods:
        units_col = f"Units Estd__{period}"
        if units_col not in df.columns:
            continue

        sub_rows = df[df["Flag"] == "Sub-brand"].copy()
        if sub_rows.empty:
            df[f"Variance__{period}"] = 0
            continue

        sku_sum = sub_rows.groupby(group_cols)[units_col].sum().reset_index()
        sku_sum = sku_sum.rename(columns={units_col: f"SKU_Sum__{period}"})

        df = df.merge(sku_sum, on=group_cols, how="left")
        df[f"Variance__{period}"] = np.where(
            df["Flag"] == "Brand",
            df[units_col] - df[f"SKU_Sum__{period}"].fillna(0),
            0
        ).round(2)
        df = df.drop(columns=[f"SKU_Sum__{period}"])

    return df

def add_market_share(df, periods):
    """
    Value MS% = Brand Sales Derived / Category Sales Derived * 100
    Units MS% = Brand Units Estd / Category Units Estd * 100
    Calculated within each Region + TG_Segment + Format group.
    """
    group_cols = ["Category", "Region", "TG_Segment", "Format", "Urban_Rural"]
    group_cols = [c for c in group_cols if c in df.columns]

    for period in periods:
        sales_col = f"Sales Derived__{period}"
        units_col = f"Units Estd__{period}"

        if sales_col not in df.columns:
            continue

        cat_rows = df[df["Flag"] == "Category"].copy()
        if cat_rows.empty:
            continue

        cat_sales = cat_rows.groupby(group_cols)[sales_col].sum().reset_index()
        cat_sales = cat_sales.rename(columns={sales_col: f"Cat_Sales__{period}"})

        cat_units = cat_rows.groupby(group_cols)[units_col].sum().reset_index()
        cat_units = cat_units.rename(columns={units_col: f"Cat_Units__{period}"})

        df = df.merge(cat_sales, on=group_cols, how="left")
        df = df.merge(cat_units, on=group_cols, how="left")

        df[f"Value MS%__{period}"] = np.where(
            df[f"Cat_Sales__{period}"].fillna(0) != 0,
            (df[sales_col] / df[f"Cat_Sales__{period}"]) * 100,
            0
        ).round(2)

        df[f"Units MS%__{period}"] = np.where(
            df[f"Cat_Units__{period}"].fillna(0) != 0,
            (df[units_col] / df[f"Cat_Units__{period}"]) * 100,
            0
        ).round(2)

        df = df.drop(columns=[f"Cat_Sales__{period}", f"Cat_Units__{period}"])

    return df
