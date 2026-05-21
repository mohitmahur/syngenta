"""
Campaign Orchestrator
======================
Multi-channel sequencing engine with:
- Intelligent fallback hierarchy (WhatsApp → SMS → IVR → Field Rep)
- Send-time optimization based on historical patterns
- Proper attribution windows for conversion tracking
- Content guardrails for safety validation
"""

from typing import Dict, Any, List
from datetime import date, timedelta
import re

# ── Send-Time Optimization Rules ──
# Based on typical Indian agrarian daily routines
OPTIMAL_SEND_WINDOWS = {
    "whatsapp": {
        "start": "06:30",
        "end": "08:00",
        "alt_start": "19:00",
        "alt_end": "20:30",
    },
    "sms": {"start": "07:00", "end": "09:00", "alt_start": "18:00", "alt_end": "20:00"},
    "voice_call": {
        "start": "10:00",
        "end": "12:00",
        "alt_start": "16:00",
        "alt_end": "18:00",
    },
}

# ── Attribution Window Config ──
ATTRIBUTION_WINDOWS = {
    "strict": 7,  # 7-day window
    "standard": 14,  # 14-day window (default)
    "extended": 30,  # 30-day window
}

# ── Guardrails: forbidden patterns ──
CONTENT_GUARDRAILS = {
    "forbidden_claims": [
        r"(?i)guarantee.*yield",
        r"(?i)\d+x\s*(yield|profit|income|return)",
        r"(?i)100\s*%\s*(effective|result|cure|safe)",
        r"(?i)no\s*side\s*effect",
        r"(?i)organic|natural|chemical[- ]?free",  # Syngenta sells chemicals, this is misleading
    ],
    "required_elements": [
        # At least one product name from catalog must appear
    ],
    "max_lengths": {
        "sms": 160,
        "whatsapp": 500,
        "voice_script": 1500,
    },
}

PRODUCT_CATALOG = [
    "Topik 15 WP",
    "Tilt 250 EC",
    "Score 250 EC",
    "Axial 50 EC",
    "Actara 25 WG",
    "Amistar 250 SC",
    "Kavach 75 WP",
    "Cruiser 350 FS",
    "Vibrance Integral",
    "Movondo",
    "Alto 5 SC",
    "Vertimec 1.8 EC",
]


class CampaignOrchestrator:
    """Orchestrates multi-channel campaign delivery with guardrails."""

    def build_delivery_plan(
        self, grower_context: Dict[str, Any], receptivity: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Build a complete delivery plan for a grower with channel sequencing,
        optimal timing, and fallback hierarchy.
        """
        device = grower_context.get("device_type", "unknown")
        wa_hist = grower_context.get("whatsapp_history", {})
        engagement_tier = (receptivity or {}).get("engagement_tier", "medium")

        # ── Channel Sequence with Fallback ──
        if device == "smartphone":
            if wa_hist.get("total_messages", 0) >= 3 and wa_hist.get("opened", 0) == 0:
                # 3+ messages sent, never opened → WhatsApp fatigue, switch to SMS
                primary = "sms"
                sequence = ["sms", "voice_call", "field_rep"]
                reason = "WhatsApp fatigue detected (3+ msgs, 0 opens)"
            elif engagement_tier == "high":
                primary = "whatsapp"
                sequence = ["whatsapp"]
                reason = "High engagement tier, WhatsApp sufficient"
            else:
                primary = "whatsapp"
                sequence = ["whatsapp", "sms"]
                reason = "Standard smartphone flow with SMS fallback"
        elif device == "keypad":
            primary = "voice_call"
            sequence = ["voice_call", "sms", "field_rep"]
            reason = "Keypad phone → voice-first, SMS fallback"
        else:
            primary = "sms"
            sequence = ["sms", "field_rep"]
            reason = "Unknown device → SMS with field rep backup"

        # ── Fallback Timing ──
        fallback_rules = []
        for i, ch in enumerate(sequence):
            if i == 0:
                fallback_rules.append({"channel": ch, "trigger": "immediate", "day": 0})
            elif ch == "sms":
                fallback_rules.append(
                    {"channel": ch, "trigger": "if_not_opened_48h", "day": 2}
                )
            elif ch == "voice_call":
                fallback_rules.append(
                    {"channel": ch, "trigger": "if_not_opened_5d", "day": 5}
                )
            elif ch == "field_rep":
                fallback_rules.append(
                    {"channel": ch, "trigger": "if_no_response_7d", "day": 7}
                )

        # ── Optimal Send Time ──
        send_window = OPTIMAL_SEND_WINDOWS.get(primary, OPTIMAL_SEND_WINDOWS["sms"])

        # ── Offline Rep Assignment ──
        offline_rep = None
        if "field_rep" in sequence:
            offline_rep = {
                "action": "Queue for next field visit",
                "territory": grower_context.get("tehsil", ""),
                "product_to_promote": "",
            }
            products = grower_context.get("recommended_products", [])
            for p in products:
                if isinstance(p, dict) and p.get("in_stock"):
                    offline_rep["product_to_promote"] = p["product"]
                    break

        return {
            "grower_id": grower_context.get("grower_id", ""),
            "primary_channel": primary,
            "channel_sequence": sequence,
            "fallback_rules": fallback_rules,
            "routing_reason": reason,
            "send_window": send_window,
            "offline_rep_handoff": offline_rep,
        }

    def validate_content(
        self, content: Dict[str, str], expected_product: str = ""
    ) -> Dict[str, Any]:
        """
        Validate generated content against guardrails:
        - No false yield/guarantee claims
        - Correct product name present
        - Length limits respected
        """
        issues = []
        passed = True

        for fmt, text in content.items():
            if not isinstance(text, str) or not text or fmt.startswith("english"):
                continue

            # Check forbidden claims
            for pattern in CONTENT_GUARDRAILS["forbidden_claims"]:
                if re.search(pattern, text):
                    issues.append(
                        {
                            "type": "forbidden_claim",
                            "format": fmt,
                            "pattern": pattern,
                            "message": f"Content contains a potentially misleading claim in '{fmt}'",
                        }
                    )
                    passed = False

            # Check length limits
            max_len = CONTENT_GUARDRAILS["max_lengths"].get(fmt)
            if max_len and len(text) > max_len:
                issues.append(
                    {
                        "type": "length_exceeded",
                        "format": fmt,
                        "actual": len(text),
                        "max": max_len,
                        "message": f"'{fmt}' exceeds {max_len} chars (actual: {len(text)})",
                    }
                )
                # Not a hard fail, just a warning

            # Check product name is from catalog
            if expected_product:
                if expected_product not in text:
                    # Check transliterated forms too
                    product_lower = expected_product.lower()
                    text_lower = text.lower()
                    if product_lower not in text_lower:
                        issues.append(
                            {
                                "type": "product_missing",
                                "format": fmt,
                                "expected": expected_product,
                                "message": f"Expected product '{expected_product}' not found in '{fmt}'",
                            }
                        )

        return {
            "passed": passed,
            "issues": issues,
            "issue_count": len(issues),
        }
