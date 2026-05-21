"""
Analytics Engine
=================
Computes real conversion attribution and campaign performance metrics
from the provided datasets. No simulated KPIs — everything is computed
from actual POS, WhatsApp, digital funnel, and grower scan data.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, Any, List

from backend.data_loader import get_data_store


class AnalyticsEngine:
    """Computes campaign performance and conversion attribution from real data."""

    def __init__(self):
        self.store = get_data_store()

    @staticmethod
    def _resolve_column(df: pd.DataFrame, names: List[str]) -> str:
        """Return the first matching column name, allowing minor schema variants."""
        lookup = {str(col).strip().lower(): col for col in df.columns}
        for name in names:
            match = lookup.get(name.lower())
            if match is not None:
                return match
        return ""

    @staticmethod
    def _truthy_series(df: pd.DataFrame, col: str) -> pd.Series:
        """Convert a boolean-like column to a bool series; missing columns are false."""
        if not col or col not in df.columns:
            return pd.Series(False, index=df.index)
        true_values = {"true", "1", "yes", "y", "delivered", "opened", "clicked"}
        return df[col].apply(lambda x: str(x).strip().lower() in true_values)

    @staticmethod
    def _empty_whatsapp_metrics(missing_columns: List[str] = None) -> Dict[str, Any]:
        result = {
            "total_messages": 0,
            "delivered": 0,
            "opened": 0,
            "clicked": 0,
            "delivery_rate": 0,
            "open_rate": 0,
            "click_rate": 0,
            "by_product": {},
        }
        if missing_columns:
            result["missing_columns"] = missing_columns
        return result

    def get_whatsapp_funnel_metrics(self) -> Dict[str, Any]:
        """Compute real open/click/delivery rates from WhatsApp log."""
        wa = self.store.whatsapp_log.copy()

        if wa.empty:
            return self._empty_whatsapp_metrics()

        delivered_col = self._resolve_column(
            wa, ["delivered_status", "delivered", "delivery_status", "is_delivered"]
        )
        opened_col = self._resolve_column(
            wa, ["opened_status", "opened", "open_status", "read_status", "is_opened"]
        )
        clicked_col = self._resolve_column(
            wa, ["clicked_status", "clicked", "click_status", "is_clicked"]
        )
        product_col = self._resolve_column(
            wa,
            ["campaign_product", "product", "product_name", "sku_name", "campaign_sku"],
        )

        total = len(wa)
        delivered_series = self._truthy_series(wa, delivered_col)
        opened_series = self._truthy_series(wa, opened_col)
        clicked_series = self._truthy_series(wa, clicked_col)
        delivered = delivered_series.sum()
        opened = opened_series.sum()
        clicked = clicked_series.sum()

        # By product
        by_product = {}
        if product_col:
            products = wa[product_col].fillna("unknown").unique()
        else:
            products = ["all"]

        for product in products:
            subset = (
                wa[wa[product_col].fillna("unknown") == product] if product_col else wa
            )
            n = len(subset)
            d = int(delivered_series.loc[subset.index].sum())
            o = int(opened_series.loc[subset.index].sum())
            c = int(clicked_series.loc[subset.index].sum())
            by_product[product] = {
                "sent": int(n),
                "delivered": int(d),
                "opened": int(o),
                "clicked": int(c),
                "delivery_rate": round(d / n, 4) if n > 0 else 0,
                "open_rate": round(o / d, 4) if d > 0 else 0,
                "click_rate": round(c / o, 4) if o > 0 else 0,
                "ctr_overall": round(c / n, 4) if n > 0 else 0,
            }

        missing_columns = [
            name
            for name, col in {
                "delivered_status": delivered_col,
                "opened_status": opened_col,
                "clicked_status": clicked_col,
            }.items()
            if not col
        ]

        result = {
            "total_messages": int(total),
            "delivered": int(delivered),
            "opened": int(opened),
            "clicked": int(clicked),
            "delivery_rate": round(delivered / total, 4) if total else 0,
            "open_rate": round(opened / delivered, 4) if delivered else 0,
            "click_rate": round(clicked / opened, 4) if opened else 0,
            "by_product": by_product,
        }
        if missing_columns:
            result["missing_columns"] = missing_columns
        return result

    def get_digital_funnel_metrics(self) -> Dict[str, Any]:
        """Aggregate digital funnel performance by campaign."""
        df = self.store.digital_funnel.copy()

        campaigns = {}
        for cid in df["campaign_id"].unique():
            subset = df[df["campaign_id"] == cid]
            crop = subset["campaign_crop"].iloc[0]
            product = subset["campaign_product"].iloc[0]
            total_imps = int(subset["social_post_impression"].sum())
            total_visits = int(subset["landing_page_visits"].sum())
            total_leads = int(subset["lead_form_submission"].sum())

            # Weekly trend
            weekly_trend = []
            for _, row in subset.sort_values("week_start_date").iterrows():
                weekly_trend.append(
                    {
                        "week": row["week_start_date"].strftime("%Y-%m-%d"),
                        "impressions": int(row["social_post_impression"]),
                        "visits": int(row["landing_page_visits"]),
                        "leads": int(row["lead_form_submission"]),
                    }
                )

            campaigns[cid] = {
                "campaign_crop": crop,
                "campaign_product": product,
                "total_impressions": total_imps,
                "total_visits": total_visits,
                "total_leads": total_leads,
                "impression_to_visit_rate": (
                    round(total_visits / total_imps, 4) if total_imps else 0
                ),
                "visit_to_lead_rate": (
                    round(total_leads / total_visits, 4) if total_visits else 0
                ),
                "overall_conversion": (
                    round(total_leads / total_imps, 6) if total_imps else 0
                ),
                "weeks": len(subset),
                "weekly_trend": weekly_trend,
            }

        return {"campaigns": campaigns}

    def get_conversion_attribution(self) -> Dict[str, Any]:
        """
        Attribution: correlate WhatsApp campaigns with downstream product scans and POS.
        This is the core Campaign-to-Action metric.
        """
        store = self.store
        wa = store.whatsapp_log.copy()
        growers = store.growers.copy()

        if wa.empty or growers.empty:
            return {
                "total_messages": 0,
                "total_clicked": 0,
                "total_converted_scan": 0,
                "campaign_to_action_rate": 0,
                "click_to_scan_rate": 0,
                "by_crop": {},
            }

        clicked_col = self._resolve_column(
            wa, ["clicked_status", "clicked", "click_status", "is_clicked"]
        )
        sent_date_col = self._resolve_column(
            wa, ["message_sent_date", "sent_date", "campaign_date", "created_at"]
        )
        crop_col = self._resolve_column(wa, ["campaign_crop", "crop"])

        required_wa = ["grower_id"]
        if (
            not all(col in wa.columns for col in required_wa)
            or not clicked_col
            or not sent_date_col
        ):
            return {
                "total_messages": int(len(wa)),
                "total_clicked": int(self._truthy_series(wa, clicked_col).sum()),
                "total_converted_scan": 0,
                "campaign_to_action_rate": 0,
                "click_to_scan_rate": 0,
                "by_crop": {},
                "missing_columns": [
                    col
                    for col, present in {
                        "grower_id": "grower_id" in wa.columns,
                        "clicked_status": bool(clicked_col),
                        "message_sent_date": bool(sent_date_col),
                    }.items()
                    if not present
                ],
            }

        # Join WhatsApp messages with grower product scans
        grower_cols = [
            col
            for col in [
                "grower_id",
                "product_scan",
                "product_name",
                "product_scan_datetime",
                "tehsil",
                "crop",
            ]
            if col in growers.columns
        ]
        wa_grower = wa.merge(growers[grower_cols], on="grower_id", how="left")

        # Convert dates to check attribution window
        wa_grower["msg_date"] = pd.to_datetime(
            wa_grower[sent_date_col], errors="coerce"
        )
        if "product_scan_datetime" in wa_grower.columns:
            wa_grower["scan_date"] = pd.to_datetime(
                wa_grower["product_scan_datetime"], errors="coerce"
            )
        else:
            wa_grower["scan_date"] = pd.NaT

        # Clicked AND scanned within 14 days AFTER the message
        wa_grower["clicked"] = self._truthy_series(wa_grower, clicked_col)

        # Valid scan condition: happened, and occurred between msg_date and msg_date + 14 days
        # Use pandas isnull() to safely handle NaT
        product_scan = self._truthy_series(wa_grower, "product_scan")
        wa_grower["valid_scan"] = (
            product_scan
            & ~wa_grower["scan_date"].isnull()
            & (wa_grower["scan_date"] >= wa_grower["msg_date"])
            & (wa_grower["scan_date"] <= wa_grower["msg_date"] + timedelta(days=14))
        )

        total_messages = len(wa_grower)
        total_clicked = int(wa_grower["clicked"].sum())
        total_scanned_after_msg = int(
            (wa_grower["clicked"] & wa_grower["valid_scan"]).sum()
        )

        # Campaign-to-action rate
        cta_rate = (
            round(total_scanned_after_msg / total_messages, 4) if total_messages else 0
        )
        click_to_scan = (
            round(total_scanned_after_msg / total_clicked, 4) if total_clicked else 0
        )

        # By crop
        by_crop = {}
        if crop_col and crop_col in wa_grower.columns:
            crop_series = wa_grower[crop_col]
        elif "crop" in wa_grower.columns:
            crop_series = wa_grower["crop"]
        else:
            crop_series = pd.Series("unknown", index=wa_grower.index)

        for crop in crop_series.fillna("unknown").unique():
            subset = wa_grower[crop_series.fillna("unknown") == crop]
            n = len(subset)
            cl = int(subset["clicked"].sum())
            sc = int((subset["clicked"] & subset["valid_scan"]).sum())
            by_crop[crop] = {
                "messages": int(n),
                "clicked": cl,
                "scanned_after_click": sc,
                "campaign_to_action_rate": round(sc / n, 4) if n else 0,
            }

        return {
            "total_messages": total_messages,
            "total_clicked": total_clicked,
            "total_converted_scan": total_scanned_after_msg,
            "campaign_to_action_rate": cta_rate,
            "click_to_scan_rate": click_to_scan,
            "by_crop": by_crop,
        }

    def get_pos_trends(self, sku_name: str = None, state: str = None) -> Dict[str, Any]:
        """Get POS sales trends by week, optionally filtered."""
        pos = self.store.retailer_pos.copy()

        if sku_name:
            pos = pos[pos["sku_name"] == sku_name]
        if state:
            # Join with retailers to get state
            retailers = self.store.retailers[["retailer_id", "state"]]
            pos = pos.merge(retailers, on="retailer_id", how="left")
            pos = pos[pos["state"] == state]

        pos["week"] = (
            pos["transaction_date"].dt.to_period("W").apply(lambda x: x.start_time)
        )
        weekly = (
            pos.groupby("week")
            .agg(
                total_qty=("sku_qty", "sum"),
                total_revenue=(
                    "sku_price",
                    lambda x: (x * pos.loc[x.index, "sku_qty"]).sum(),
                ),
                transaction_count=("transaction_id", "nunique"),
            )
            .reset_index()
        )

        weekly_data = []
        for _, row in weekly.sort_values("week").iterrows():
            weekly_data.append(
                {
                    "week": row["week"].strftime("%Y-%m-%d"),
                    "total_qty": int(row["total_qty"]),
                    "total_revenue": round(float(row["total_revenue"]), 2),
                    "transactions": int(row["transaction_count"]),
                }
            )

        return {
            "filter_sku": sku_name,
            "filter_state": state,
            "total_weeks": len(weekly_data),
            "weekly_data": weekly_data,
        }

    def get_inventory_health(self) -> Dict[str, Any]:
        """Compute current inventory health: out-of-stock rates by product and region."""
        inv = self.store.retailer_inventory.copy()
        latest_week = inv["week_end_date"].max()
        current = inv[inv["week_end_date"] == latest_week]

        # Join with retailer locations
        retailers = self.store.retailers[["retailer_id", "state", "district", "tehsil"]]
        current = current.merge(retailers, on="retailer_id", how="left")

        # By SKU
        by_sku = {}
        for sku in current["sku_name"].unique():
            subset = current[current["sku_name"] == sku]
            total_retailers = len(subset)
            out_of_stock = int((subset["sku_qty"] == 0).sum())
            avg_stock = round(subset["sku_qty"].mean(), 1)
            by_sku[sku] = {
                "retailers_carrying": total_retailers,
                "out_of_stock_count": out_of_stock,
                "out_of_stock_rate": (
                    round(out_of_stock / total_retailers, 4) if total_retailers else 0
                ),
                "avg_stock_qty": avg_stock,
            }

        # By state
        by_state = {}
        for state in current["state"].unique():
            subset = current[current["state"] == state]
            total = len(subset)
            oos = int((subset["sku_qty"] == 0).sum())
            by_state[state] = {
                "total_sku_retailer_combos": total,
                "out_of_stock": oos,
                "oos_rate": round(oos / total, 4) if total else 0,
            }

        return {
            "snapshot_week": latest_week.strftime("%Y-%m-%d"),
            "by_sku": by_sku,
            "by_state": by_state,
        }

    def get_field_activity_summary(self) -> Dict[str, Any]:
        """Summarize rep field activities from visit logs."""
        visits = self.store.retailer_visits.copy()

        by_type = visits["visit_type"].value_counts().to_dict()
        by_product = visits["product_recommended"].value_counts().to_dict()

        # Monthly trend
        visits["month"] = (
            visits["visit_date"].dt.to_period("M").apply(lambda x: x.start_time)
        )
        monthly = visits.groupby("month").size().reset_index(name="visit_count")
        monthly_data = [
            {"month": row["month"].strftime("%Y-%m"), "visits": int(row["visit_count"])}
            for _, row in monthly.sort_values("month").iterrows()
        ]

        return {
            "total_visits": len(visits),
            "by_type": {k: int(v) for k, v in by_type.items()},
            "by_product": {k: int(v) for k, v in by_product.items()},
            "monthly_trend": monthly_data,
        }
