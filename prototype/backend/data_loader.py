"""
Data Loader Module
==================
Loads and indexes all 8 Syngenta datasets into memory with proper parsing.
All data is REAL from the provided CSV files — zero simulation.
"""

import os
import csv
import json
import pandas as pd
from datetime import datetime, date
from typing import Dict, List, Optional

DATA_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "Syngenta_IITM_Hackathon_2026_dataset"
)


class DataStore:
    """Central data store that loads and indexes all datasets."""

    def __init__(self):
        self.growers: pd.DataFrame = pd.DataFrame()
        self.retailers: pd.DataFrame = pd.DataFrame()
        self.reps_territory: pd.DataFrame = pd.DataFrame()
        self.retailer_pos: pd.DataFrame = pd.DataFrame()
        self.retailer_inventory: pd.DataFrame = pd.DataFrame()
        self.retailer_visits: pd.DataFrame = pd.DataFrame()
        self.whatsapp_log: pd.DataFrame = pd.DataFrame()
        self.digital_funnel: pd.DataFrame = pd.DataFrame()

        # Lookup indices
        self.grower_index: Dict[str, dict] = {}
        self.retailer_by_tehsil: Dict[str, List[str]] = {}
        self.territory_by_tehsil: Dict[str, str] = {}

    def load_all(self):
        """Load all datasets and build indices."""
        print("[DataStore] Loading growers.csv ...")
        self.growers = pd.read_csv(os.path.join(DATA_DIR, "growers.csv"))
        self._parse_grower_calendars()

        print("[DataStore] Loading retailers.csv ...")
        self.retailers = pd.read_csv(os.path.join(DATA_DIR, "retailers.csv"))

        print("[DataStore] Loading reps_territory.csv ...")
        self.reps_territory = pd.read_csv(os.path.join(DATA_DIR, "reps_territory.csv"))

        print("[DataStore] Loading retailer_pos.csv ...")
        self.retailer_pos = pd.read_csv(os.path.join(DATA_DIR, "retailer_pos.csv"))
        self.retailer_pos["transaction_date"] = pd.to_datetime(
            self.retailer_pos["transaction_date"]
        )

        print("[DataStore] Loading retailer_inventory_weekly.csv ...")
        self.retailer_inventory = pd.read_csv(
            os.path.join(DATA_DIR, "retailer_inventory_weekly.csv")
        )
        self.retailer_inventory["week_end_date"] = pd.to_datetime(
            self.retailer_inventory["week_end_date"]
        )

        print("[DataStore] Loading retailer_visit_log.csv ...")
        self.retailer_visits = pd.read_csv(
            os.path.join(DATA_DIR, "retailer_visit_log.csv")
        )
        self.retailer_visits["visit_date"] = pd.to_datetime(
            self.retailer_visits["visit_date"]
        )

        print("[DataStore] Loading whatsapp_campaign.csv ...")
        self.whatsapp_log = pd.read_csv(os.path.join(DATA_DIR, "whatsapp_campaign.csv"))
        self.whatsapp_log["message_sent_date"] = pd.to_datetime(
            self.whatsapp_log["message_sent_date"]
        )

        print("[DataStore] Loading digital_funnel_weekly.csv ...")
        self.digital_funnel = pd.read_csv(
            os.path.join(DATA_DIR, "digital_funnel_weekly.csv")
        )
        self.digital_funnel["week_start_date"] = pd.to_datetime(
            self.digital_funnel["week_start_date"]
        )

        self._build_indices()
        print(
            f"[DataStore] All datasets loaded. {len(self.growers)} growers, {len(self.retailers)} retailers."
        )

    def _parse_grower_calendars(self):
        """Parse the JSON crop calendar column into structured fields."""
        crops, stages_list, sowing_starts, harvest_ends = [], [], [], []
        for _, row in self.growers.iterrows():
            try:
                cal = json.loads(row["grower_crop_calendar"])
                crops.append(cal.get("crop", "unknown"))
                stages_list.append(cal.get("stages", []))
                sowing_starts.append(cal.get("sowing", {}).get("start", ""))
                harvest_ends.append(cal.get("harvest", {}).get("end", ""))
            except (json.JSONDecodeError, TypeError):
                crops.append("unknown")
                stages_list.append([])
                sowing_starts.append("")
                harvest_ends.append("")
        self.growers["crop"] = crops
        self.growers["crop_stages"] = stages_list
        self.growers["sowing_start"] = sowing_starts
        self.growers["harvest_end"] = harvest_ends

    def _build_indices(self):
        """Build lookup indices for fast access."""
        # Grower index
        for _, row in self.growers.iterrows():
            self.grower_index[row["grower_id"]] = row.to_dict()

        # Retailer by tehsil
        for _, row in self.retailers.iterrows():
            tehsil = row["tehsil"]
            if tehsil not in self.retailer_by_tehsil:
                self.retailer_by_tehsil[tehsil] = []
            self.retailer_by_tehsil[tehsil].append(row["retailer_id"])

        # Territory by tehsil (from reps)
        for _, row in self.reps_territory.iterrows():
            try:
                tehsils = json.loads(row["tehsil_list"])
                for t in tehsils:
                    self.territory_by_tehsil[t] = row["territory_id"]
            except (json.JSONDecodeError, TypeError):
                pass

    def get_grower_current_stage(
        self, grower_id: str, reference_date: date = None
    ) -> Optional[str]:
        """Determine the current crop stage for a grower based on date."""
        if reference_date is None:
            reference_date = date.today()
        grower = self.grower_index.get(grower_id)
        if not grower:
            return None
        stages = grower.get("crop_stages", [])
        if not stages:
            return "unknown"

        # Find the most recent stage before reference_date
        current_stage = "sowing"
        for stage in stages:
            try:
                stage_date = datetime.strptime(stage["approx"], "%Y-%m-%d").date()
                if stage_date <= reference_date:
                    current_stage = stage["stage"]
            except (KeyError, ValueError):
                continue
        # Check if past harvest
        harvest_end = grower.get("harvest_end", "")
        if harvest_end:
            try:
                if reference_date > datetime.strptime(harvest_end, "%Y-%m-%d").date():
                    current_stage = "harvested"
            except ValueError:
                pass
        return current_stage

    def get_local_inventory(self, tehsil: str, sku_name: str = None) -> pd.DataFrame:
        """Get the latest inventory snapshot for retailers in a given tehsil."""
        retailer_ids = self.retailer_by_tehsil.get(tehsil, [])
        if not retailer_ids:
            return pd.DataFrame()
        inv = self.retailer_inventory[
            self.retailer_inventory["retailer_id"].isin(retailer_ids)
        ]
        if inv.empty:
            return inv
        latest_week = inv["week_end_date"].max()
        inv = inv[inv["week_end_date"] == latest_week]
        if sku_name:
            inv = inv[inv["sku_name"] == sku_name]
        return inv

    def get_grower_whatsapp_history(self, grower_id: str) -> pd.DataFrame:
        """Get all WhatsApp messages sent to a grower."""
        return self.whatsapp_log[self.whatsapp_log["grower_id"] == grower_id]

    def get_pos_for_tehsil(
        self, tehsil: str, start_date: str = None, end_date: str = None
    ) -> pd.DataFrame:
        """Get POS transactions for retailers in a given tehsil."""
        retailer_ids = self.retailer_by_tehsil.get(tehsil, [])
        if not retailer_ids:
            return pd.DataFrame()
        pos = self.retailer_pos[self.retailer_pos["retailer_id"].isin(retailer_ids)]
        if start_date:
            pos = pos[pos["transaction_date"] >= pd.to_datetime(start_date)]
        if end_date:
            pos = pos[pos["transaction_date"] <= pd.to_datetime(end_date)]
        return pos


# Singleton
_store = None


def get_data_store() -> DataStore:
    global _store
    if _store is None:
        _store = DataStore()
        _store.load_all()
    return _store
