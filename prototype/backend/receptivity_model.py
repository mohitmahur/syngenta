"""
Receptivity Model v2
=====================
A real ML model trained on actual WhatsApp campaign data with rich
feature engineering. Predicts open/click probabilities per grower.

v2 improvements:
- User-level historical engagement features (past_open_ratio, msg_fatigue)
- Temporal features (day_of_week, month, days_since_sowing)
- SKU/campaign-level features
- Target-encoded high-cardinality features (state, crop)
- Proper train/test evaluation
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.model_selection import cross_val_score, StratifiedKFold
from sklearn.preprocessing import LabelEncoder
from sklearn.metrics import roc_auc_score, precision_score, recall_score
from typing import Dict, Any
from datetime import datetime
import json

from backend.data_loader import get_data_store


class ReceptivityModel:
    """
    v2: Predicts grower engagement with rich engineered features.
    Trained on real WhatsApp log + grower demographics + temporal signals.
    """

    def __init__(self):
        self.model_open: HistGradientBoostingClassifier = None
        self.model_click: HistGradientBoostingClassifier = None
        self.label_encoders: Dict[str, LabelEncoder] = {}
        self.target_encode_maps: Dict[str, Dict] = {}
        self.feature_cols = []
        self.is_trained = False
        self.training_metrics = {}

    def _prepare_training_data(self) -> pd.DataFrame:
        """Join WhatsApp log with grower profiles and engineer features."""
        store = get_data_store()

        wa = store.whatsapp_log.copy()
        growers = store.growers[
            [
                "grower_id",
                "grower_age",
                "grower_farm_size",
                "language",
                "device_type",
                "state",
                "district",
                "crop",
                "gender",
                "sowing_start",
                "offline_campaign_attended",
                "product_scan",
            ]
        ].copy()

        merged = wa.merge(growers, on="grower_id", how="inner")

        # Convert boolean strings
        for col in ["delivered_status", "opened_status", "clicked_status"]:
            merged[col] = merged[col].apply(
                lambda x: 1 if str(x).strip().lower() == "true" else 0
            )

        # Only delivered messages
        merged = merged[merged["delivered_status"] == 1].copy()

        # ── Temporal Features ──
        merged["msg_date"] = pd.to_datetime(merged["message_sent_date"])
        merged["msg_day_of_week"] = merged["msg_date"].dt.dayofweek  # 0=Mon
        merged["msg_month"] = merged["msg_date"].dt.month
        merged["msg_week_of_year"] = (
            merged["msg_date"].dt.isocalendar().week.astype(int)
        )

        # Days since sowing
        merged["sowing_dt"] = pd.to_datetime(merged["sowing_start"], errors="coerce")
        merged["days_since_sowing"] = (merged["msg_date"] - merged["sowing_dt"]).dt.days
        merged["days_since_sowing"] = (
            merged["days_since_sowing"].fillna(0).clip(lower=0)
        )

        # ── User-Level Historical Features ──
        # Compute per-grower historical engagement rates
        grower_history = (
            merged.groupby("grower_id")
            .agg(
                total_msgs=("delivered_status", "sum"),
                total_opens=("opened_status", "sum"),
                total_clicks=("clicked_status", "sum"),
            )
            .reset_index()
        )
        grower_history["hist_open_rate"] = grower_history[
            "total_opens"
        ] / grower_history["total_msgs"].clip(lower=1)
        grower_history["hist_click_rate"] = grower_history[
            "total_clicks"
        ] / grower_history["total_msgs"].clip(lower=1)
        grower_history["msg_fatigue"] = grower_history[
            "total_msgs"
        ]  # more msgs = more fatigue

        merged = merged.merge(
            grower_history[
                ["grower_id", "hist_open_rate", "hist_click_rate", "msg_fatigue"]
            ],
            on="grower_id",
            how="left",
        )

        # ── Boolean Engagement Signals ──
        merged["offline_attended"] = merged["offline_campaign_attended"].apply(
            lambda x: 1 if str(x).strip().lower() == "true" else 0
        )
        merged["has_scanned"] = merged["product_scan"].apply(
            lambda x: 1 if str(x).strip().lower() == "true" else 0
        )

        # ── Fill NaN ──
        merged["grower_age"] = merged["grower_age"].fillna(
            merged["grower_age"].median()
        )
        merged["grower_farm_size"] = merged["grower_farm_size"].fillna(
            merged["grower_farm_size"].median()
        )

        return merged

    def _encode_features(self, df: pd.DataFrame, fit: bool = False) -> pd.DataFrame:
        """Encode categorical + target-encode high-cardinality features."""
        # Simple label encoding for low-cardinality
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
                    df[dest] = (
                        df[src]
                        .fillna("unknown")
                        .astype(str)
                        .apply(
                            lambda x: le.transform([x])[0] if x in le.classes_ else -1
                        )
                    )
                else:
                    df[dest] = 0

        # Target encoding for high-cardinality (state, crop)
        target_cats = ["state", "crop"]
        for col in target_cats:
            if col not in df.columns:
                df[f"{col}_te"] = 0
                continue
            if fit:
                global_mean = (
                    df["opened_status"].mean() if "opened_status" in df.columns else 0.5
                )
                te_map = df.groupby(col)["opened_status"].mean().to_dict()
                self.target_encode_maps[col] = {"map": te_map, "default": global_mean}
                df[f"{col}_te"] = df[col].map(te_map).fillna(global_mean)
            else:
                te_info = self.target_encode_maps.get(col, {"map": {}, "default": 0.5})
                df[f"{col}_te"] = df[col].map(te_info["map"]).fillna(te_info["default"])

        return df

    def train(self) -> Dict[str, Any]:
        """Train the receptivity model on real data with engineered features."""
        print(
            "[ReceptivityModel v2] Preparing training data with feature engineering ..."
        )
        df = self._prepare_training_data()
        print(f"[ReceptivityModel v2] Training samples: {len(df)}")

        df = self._encode_features(df, fit=True)

        self.feature_cols = [
            "grower_age",
            "grower_farm_size",
            "language_enc",
            "device_enc",
            "gender_enc",
            "product_enc",
            "state_te",
            "crop_te",
            "msg_day_of_week",
            "msg_month",
            "days_since_sowing",
            "hist_open_rate",
            "hist_click_rate",
            "msg_fatigue",
            "offline_attended",
            "has_scanned",
        ]

        X = df[self.feature_cols].values
        y_open = df["opened_status"].values
        y_click = df["clicked_status"].values

        cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=42)

        # Train open model
        print("[ReceptivityModel v2] Training open-rate model ...")
        self.model_open = HistGradientBoostingClassifier(
            max_iter=200,
            max_depth=5,
            learning_rate=0.05,
            min_samples_leaf=20,
            l2_regularization=1.0,
            random_state=42,
        )
        self.model_open.fit(X, y_open)
        open_cv = cross_val_score(self.model_open, X, y_open, cv=cv, scoring="roc_auc")

        # Train click model
        print("[ReceptivityModel v2] Training click-rate model ...")
        self.model_click = HistGradientBoostingClassifier(
            max_iter=200,
            max_depth=5,
            learning_rate=0.05,
            min_samples_leaf=20,
            l2_regularization=1.0,
            random_state=42,
        )
        self.model_click.fit(X, y_click)
        click_cv = cross_val_score(
            self.model_click, X, y_click, cv=cv, scoring="roc_auc"
        )

        self.is_trained = True

        # Permutation importance
        from sklearn.inspection import permutation_importance

        open_pi = permutation_importance(
            self.model_open, X, y_open, n_repeats=5, random_state=42, scoring="roc_auc"
        )
        click_pi = permutation_importance(
            self.model_click,
            X,
            y_click,
            n_repeats=5,
            random_state=42,
            scoring="roc_auc",
        )
        open_importance = dict(
            zip(
                self.feature_cols,
                [round(v, 4) for v in open_pi.importances_mean.tolist()],
            )
        )
        click_importance = dict(
            zip(
                self.feature_cols,
                [round(v, 4) for v in click_pi.importances_mean.tolist()],
            )
        )

        self.training_metrics = {
            "model_version": "v2",
            "training_samples": len(df),
            "feature_count": len(self.feature_cols),
            "features_used": self.feature_cols,
            "open_rate_actual": round(float(y_open.mean()), 4),
            "click_rate_actual": round(float(y_click.mean()), 4),
            "open_model_auc_cv5": round(float(open_cv.mean()), 4),
            "open_model_auc_std": round(float(open_cv.std()), 4),
            "click_model_auc_cv5": round(float(click_cv.mean()), 4),
            "click_model_auc_std": round(float(click_cv.std()), 4),
            "open_feature_importance": open_importance,
            "click_feature_importance": click_importance,
        }

        print(
            f"[ReceptivityModel v2] Open AUC: {self.training_metrics['open_model_auc_cv5']:.4f} "
            f"(±{self.training_metrics['open_model_auc_std']:.4f})"
        )
        print(
            f"[ReceptivityModel v2] Click AUC: {self.training_metrics['click_model_auc_cv5']:.4f} "
            f"(±{self.training_metrics['click_model_auc_std']:.4f})"
        )

        return self.training_metrics

    def predict(self, grower_context: Dict[str, Any]) -> Dict[str, float]:
        """Predict open & click probability for a single grower."""
        if not self.is_trained:
            self.train()

        row = {
            "grower_age": grower_context.get("age", 40),
            "grower_farm_size": grower_context.get("farm_size_acres", 2.0),
            "language": grower_context.get("language", "Hindi"),
            "device_type": grower_context.get("device_type", "smartphone"),
            "state": grower_context.get("state", "Uttar Pradesh"),
            "crop": grower_context.get("crop", "wheat"),
            "gender": grower_context.get("gender", "male"),
            "campaign_product": "",  # not always known at prediction time
            "msg_day_of_week": datetime.now().weekday(),
            "msg_month": datetime.now().month,
            "days_since_sowing": 90,  # mid-season default
            "hist_open_rate": 0.0,
            "hist_click_rate": 0.0,
            "msg_fatigue": 0,
            "offline_attended": (
                1 if grower_context.get("offline_attended", False) else 0
            ),
            "has_scanned": 1 if grower_context.get("product_scanned", False) else 0,
        }

        # Compute actual historical rates from WhatsApp history
        wa = grower_context.get("whatsapp_history", {})
        total = wa.get("total_messages", 0)
        if total > 0:
            row["hist_open_rate"] = wa.get("opened", 0) / total
            row["hist_click_rate"] = wa.get("clicked", 0) / total
            row["msg_fatigue"] = total

        # Pick best product from recommendations
        products = grower_context.get("recommended_products", [])
        if products:
            for p in products:
                if isinstance(p, dict) and p.get("in_stock"):
                    row["campaign_product"] = p["product"]
                    break
            if not row["campaign_product"] and products:
                row["campaign_product"] = (
                    products[0]["product"]
                    if isinstance(products[0], dict)
                    else str(products[0])
                )

        df = pd.DataFrame([row])
        df = self._encode_features(df, fit=False)

        X = df[self.feature_cols].values
        open_prob = float(self.model_open.predict_proba(X)[0][1])
        click_prob = float(self.model_click.predict_proba(X)[0][1])

        return {
            "open_probability": round(open_prob, 4),
            "click_probability": round(click_prob, 4),
            "engagement_tier": (
                "high" if open_prob > 0.4 else "medium" if open_prob > 0.2 else "low"
            ),
        }

    def batch_predict(self, grower_ids: list) -> list:
        """Predict receptivity for a batch of growers."""
        from backend.segmentation import SegmentationEngine

        engine = SegmentationEngine()
        results = []
        for gid in grower_ids:
            ctx = engine.get_grower_context(gid)
            if "error" not in ctx:
                pred = self.predict(ctx)
                results.append({"grower_id": gid, **pred})
        return results
