"""
Receptivity Model v7 (Production Stabilized)
===========================================
Trained strictly on provided campaign data.
Applies robust Bayesian smoothing and explicit structural tree regularization 
to guarantee smooth, non-zero continuous probability outputs.
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from typing import Dict, Any
from datetime import datetime

from backend.data_loader import get_data_store

class ReceptivityModel:
    """
    Predicts grower engagement using regularized decision boundary matrices.
    """

    def __init__(self):
        self.model_open: HistGradientBoostingClassifier = None
        self.model_click: HistGradientBoostingClassifier = None
        self.label_encoders: Dict[str, LabelEncoder] = {}
        self.target_encode_maps: Dict[str, Dict] = {}
        self.feature_cols_open = []
        self.feature_cols_click = []
        self.is_trained = False
        self.training_metrics = {}

    def _prepare_training_data(self) -> pd.DataFrame:
        """Join logs and extract verified numerical attributes."""
        store = get_data_store()

        wa = store.whatsapp_log.copy()
        growers = store.growers[
            [
                "grower_id", "grower_age", "grower_farm_size", "language",
                "device_type", "state", "district", "crop", "gender",
                "sowing_start", "offline_campaign_attended", "product_scan"
            ]
        ].copy()

        merged = wa.merge(growers, on="grower_id", how="inner")

        for col in ["delivered_status", "opened_status", "clicked_status"]:
            merged[col] = merged[col].apply(lambda x: 1 if str(x).strip().lower() == "true" else 0)

        merged = merged[merged["delivered_status"] == 1].copy()

        # Temporal Features
        merged["msg_date"] = pd.to_datetime(merged["message_sent_date"])
        merged["msg_day_of_week"] = merged["msg_date"].dt.dayofweek
        merged["msg_month"] = merged["msg_date"].dt.month

        # Base Continuous Metrics
        merged["sowing_dt"] = pd.to_datetime(merged["sowing_start"], errors="coerce")
        merged["days_since_sowing"] = (merged["msg_date"] - merged["sowing_dt"]).dt.days.fillna(45).clip(lower=0)
        merged["grower_age"] = merged["grower_age"].fillna(merged["grower_age"].median()).fillna(45)
        merged["grower_farm_size"] = merged["grower_farm_size"].fillna(merged["grower_farm_size"].median()).fillna(2.0)

        # Robust Interaction Terms
        merged["age_farm_ratio"] = merged["grower_farm_size"] / (merged["grower_age"] + 1)
        merged["offline_attended"] = merged["offline_campaign_attended"].apply(lambda x: 1 if str(x).strip().lower() == "true" else 0)
        merged["has_scanned"] = merged["product_scan"].apply(lambda x: 1 if str(x).strip().lower() == "true" else 0)

        # Grouping identity for Lookalike Target Encoding
        merged["grower_persona"] = (
            merged["state"].astype(str) + "_" + merged["crop"].astype(str)
        ).str.replace(" ", "_").str.lower()

        return merged

    def _encode_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """Apply categorical label encoding and high-smoothing target mapping."""
        simple_cats = {
            "language": "language_enc",
            "device_type": "device_enc",
            "gender": "gender_enc",
            "campaign_product": "product_enc",
        }
        for src, dest in simple_cats.items():
            if src not in df.columns:
                df[dest] = 0
                continue
            if fit:
                le = LabelEncoder()
                df[dest] = le.fit_transform(df[src].fillna("unknown").astype(str))
                self.label_encoders[src] = le
            else:
                le = self.label_encoders.get(src)
                if le:
                    df[dest] = df[src].fillna("unknown").astype(str).apply(
                        lambda x: le.transform([x])[0] if x in le.classes_ else -1
                    )
                else:
                    df[dest] = 0

        # Bayesian Target Encoding with high-smoothing weight to sustain non-zero fields
        if "grower_persona" in df.columns:
            if fit:
                global_open_mean = df["opened_status"].mean() if "opened_status" in df.columns else 0.235
                global_click_mean = df["clicked_status"].mean() if "clicked_status" in df.columns else 0.052
                
                agg = df.groupby("grower_persona").agg(
                    count=("opened_status", "count"),
                    open_mean=("opened_status", "mean"),
                    click_mean=("clicked_status", "mean")
                )
                
                weight = 20 # Sizable smoothing keeps predictions bound neatly to global baselines
                smoothed_open = ((agg["count"] * agg["open_mean"]) + (weight * global_open_mean)) / (agg["count"] + weight)
                smoothed_click = ((agg["count"] * agg["click_mean"]) + (weight * global_click_mean)) / (agg["count"] + weight)
                
                self.target_encode_maps["persona_open"] = {"map": smoothed_open.to_dict(), "default": global_open_mean}
                self.target_encode_maps["persona_click"] = {"map": smoothed_click.to_dict(), "default": global_click_mean}
                
                df["cohort_open_propensity"] = df["grower_persona"].map(smoothed_open).fillna(global_open_mean)
                df["cohort_click_propensity"] = df["grower_persona"].map(smoothed_click).fillna(global_click_mean)
            else:
                te_open = self.target_encode_maps.get("persona_open", {"map": {}, "default": 0.235})
                te_click = self.target_encode_maps.get("persona_click", {"map": {}, "default": 0.052})
                df["cohort_open_propensity"] = df["grower_persona"].map(te_open["map"]).fillna(te_open["default"])
                df["cohort_click_propensity"] = df["grower_persona"].map(te_click["map"]).fillna(te_click["default"])
        else:
            df["cohort_open_propensity"] = 0.235
            df["cohort_click_propensity"] = 0.052

        return df

    def train(self) -> Dict[str, Any]:
        """Train models using unified features and strict tree regularization structural targets."""
        print("[ReceptivityModel v7] Executing structured training pipeline...")
        df = self._prepare_training_data()
        df = self._encode_features(df, fit=True)

        self.feature_cols_open = [
            "grower_age", "grower_farm_size", "language_enc", "device_enc",
            "gender_enc", "product_enc", "msg_day_of_week", "msg_month",
            "days_since_sowing", "offline_attended", "has_scanned",
            "cohort_open_propensity", "age_farm_ratio"
        ]

        X_open = df[self.feature_cols_open].values
        y_open = df["opened_status"].values
        y_click = df["clicked_status"].values

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        # Open Classifier: Balanced capacity settings ensure continuous prediction distributions
        self.model_open = HistGradientBoostingClassifier(
            max_iter=80, 
            max_depth=3, 
            learning_rate=0.05,
            min_samples_leaf=30, 
            l2_regularization=10.0, 
            random_state=42
        )
        self.model_open.fit(X_open, y_open)
        open_cv = cross_val_score(self.model_open, X_open, y_open, cv=cv, scoring="roc_auc")

        # Sequenced Cascade Stacking
        df["predicted_open_prob"] = self.model_open.predict_proba(X_open)[:, 1]

        self.feature_cols_click = [
            "grower_age", "grower_farm_size", "language_enc", "device_enc",
            "gender_enc", "product_enc", "msg_day_of_week", "msg_month",
            "days_since_sowing", "offline_attended", "has_scanned",
            "cohort_click_propensity", "predicted_open_prob", "age_farm_ratio"
        ]
        X_click = df[self.feature_cols_click].values

        # Click Classifier: Clean structural regularization prevents hard 0 boundaries
        self.model_click = HistGradientBoostingClassifier(
            max_iter=80, 
            max_depth=3, 
            learning_rate=0.05,
            min_samples_leaf=30, 
            l2_regularization=10.0, 
            random_state=42
        )
        self.model_click.fit(X_click, y_click)
        click_cv = cross_val_score(self.model_click, X_click, y_click, cv=cv, scoring="roc_auc")

        self.is_trained = True

        from sklearn.inspection import permutation_importance
        open_pi = permutation_importance(self.model_open, X_open, y_open, n_repeats=2, random_state=42, scoring="roc_auc")
        click_pi = permutation_importance(self.model_click, X_click, y_click, n_repeats=2, random_state=42, scoring="roc_auc")
        
        open_importance = dict(zip(self.feature_cols_open, [round(v, 4) for v in open_pi.importances_mean.tolist()]))
        click_importance = dict(zip(self.feature_cols_click, [round(v, 4) for v in click_pi.importances_mean.tolist()]))

        self.training_metrics = {
            "model_version": "v7_stable",
            "training_samples": len(df),
            "open_rate_actual": round(float(y_open.mean()), 4),
            "click_rate_actual": round(float(y_click.mean()), 4),
            "open_model_auc_cv5": round(float(open_cv.mean()), 4),
            "click_model_auc_cv5": round(float(click_cv.mean()), 4),
            "open_feature_importance": open_importance,
            "click_feature_importance": click_importance,
        }

        print(f"[ReceptivityModel v7] Stable Open AUC: {self.training_metrics['open_model_auc_cv5']:.4f}")
        print(f"[ReceptivityModel v7] Stable Click AUC: {self.training_metrics['click_model_auc_cv5']:.4f}")
        return self.training_metrics

    def predict(self, grower_context: Dict[str, Any]) -> Dict[str, float]:
        """Predict continuous probability vectors smoothly across both dimensions."""
        if not self.is_trained:
            self.train()

        state_str = str(grower_context.get("state", "Uttar Pradesh"))
        crop_str = str(grower_context.get("crop", "wheat"))
        device_str = str(grower_context.get("device_type", "smartphone"))
        persona = f"{state_str}_{crop_str}".replace(" ", "_").lower()

        age = float(grower_context.get("age", 40))
        farm_size = float(grower_context.get("farm_size_acres", 2.0))

        row = {
            "grower_age": age,
            "grower_farm_size": farm_size,
            "language": str(grower_context.get("language", "Hindi")),
            "device_type": device_str,
            "state": state_str,
            "crop": crop_str,
            "gender": str(grower_context.get("gender", "male")),
            "campaign_product": "",
            "msg_day_of_week": datetime.now().weekday(),
            "msg_month": datetime.now().month,
            "days_since_sowing": 90.0,
            "offline_attended": 1 if grower_context.get("offline_attended", False) else 0,
            "has_scanned": 1 if grower_context.get("product_scanned", False) else 0,
            "grower_persona": persona,
            "age_farm_ratio": farm_size / (age + 1)
        }

        products = grower_context.get("recommended_products", [])
        if products:
            for p in products:
                if isinstance(p, dict) and p.get("in_stock"):
                    row["campaign_product"] = p["product"]
                    break
            if not row["campaign_product"] and products:
                row["campaign_product"] = products[0]["product"] if isinstance(products[0], dict) else str(products[0])

        df = pd.DataFrame([row])
        df = self._encode_features(df, fit=False)

        X_open = df[self.feature_cols_open].values
        open_prob = float(self.model_open.predict_proba(X_open)[0][1])
        
        df["predicted_open_prob"] = open_prob
        X_click = df[self.feature_cols_click].values
        click_prob = float(self.model_click.predict_proba(X_click)[0][1])

        return {
            "open_probability": round(open_prob, 4),
            "click_probability": round(click_prob, 4),
            "engagement_tier": "high" if open_prob > 0.45 else "medium" if open_prob > 0.20 else "low",
        }