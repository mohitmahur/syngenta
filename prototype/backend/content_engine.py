"""
Content Generation Engine
==========================
Generates hyper-personalized, context-aware marketing content using
real grower context. Uses Google Gemini API for generation, with fallback
to template-based generation when API is unavailable.

All context injected into prompts is REAL data from the datasets.
"""

import os
from typing import Dict, Any, Optional

# Try to import Gemini
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


# ──────────────────────────────────────────────────────
# Vernacular Templates (fallback when no API key)
# ──────────────────────────────────────────────────────
TEMPLATES = {
    "Hindi": {
        "whatsapp": "🌾 नमस्ते किसान भाई! आपकी {crop} फसल अभी {stage} अवस्था में है। {threat} का खतरा बढ़ रहा है। {product} का छिड़काव करें — आपके नज़दीकी {district} के दुकानदार पर उपलब्ध है। 📞 अधिक जानकारी के लिए मिस्ड कॉल करें।",
        "sms": "{crop} me {threat} ka khatra! {product} spray kare. Apne {district} dealer se sampark kare.",
        "voice_script": "नमस्कार किसान भाई, मैं सिंजेंटा की तरफ से बोल रहा हूँ। आपकी {crop} फसल में {threat} का खतरा है। {product} का उपयोग करें। अपने नज़दीकी दुकानदार से संपर्क करें।",
    },
    "Punjabi": {
        "whatsapp": "🌾 ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਕਿਸਾਨ ਵੀਰ! ਤੁਹਾਡੀ {crop} ਫ਼ਸਲ {stage} ਅਵਸਥਾ ਵਿੱਚ ਹੈ। {threat} ਦਾ ਖ਼ਤਰਾ ਵੱਧ ਰਿਹਾ ਹੈ। {product} ਦੀ ਸਪਰੇ ਕਰੋ — {district} ਦੇ ਡੀਲਰ ਤੋਂ ਲਵੋ।",
        "sms": "{crop} vich {threat} da khatra! {product} spray karo. {district} dealer to lo.",
        "voice_script": "ਸਤ ਸ੍ਰੀ ਅਕਾਲ ਕਿਸਾਨ ਵੀਰ, ਮੈਂ ਸਿੰਜੈਂਟਾ ਵੱਲੋਂ ਬੋਲ ਰਿਹਾ ਹਾਂ। ਤੁਹਾਡੀ {crop} ਫ਼ਸਲ ਵਿੱਚ {threat} ਦਾ ਖ਼ਤਰਾ ਹੈ। {product} ਵਰਤੋ।",
    },
    "Marathi": {
        "whatsapp": "🌾 नमस्कार शेतकरी बंधू! तुमच्या {crop} पिकावर सध्या {stage} अवस्था आहे। {threat} चा धोका वाढत आहे। {product} ची फवारणी करा — {district} मधील तुमच्या जवळच्या दुकानात उपलब्ध.",
        "sms": "{crop} var {threat} cha dhoka! {product} favarani kara. {district} dealer la bhetaa.",
        "voice_script": "नमस्कार शेतकरी बंधू, मी सिंजेंटा कडून बोलतो आहे. तुमच्या {crop} पिकावर {threat} चा धोका आहे. {product} वापरा.",
    },
    "Gujarati": {
        "whatsapp": "🌾 નમસ્તે ખેડૂત ભાઈ! તમારો {crop} પાક {stage} અવસ્થામાં છે. {threat} નો ખતરો વધી રહ્યો છે. {product} નો છંટકાવ કરો — {district} ના ડીલર પાસેથી મળશે.",
        "sms": "{crop} ma {threat} no khataro! {product} spray karo. {district} dealer ne mlo.",
        "voice_script": "નમસ્કાર ખેડૂત ભાઈ, હું સિન્જેન્ટા તરફથી બોલું છું. તમારા {crop} પાકમાં {threat} નો ખતરો છે. {product} વાપરો.",
    },
    "Kannada": {
        "whatsapp": "🌾 ನಮಸ್ಕಾರ ರೈತ ಬಂಧು! ನಿಮ್ಮ {crop} ಬೆಳೆ {stage} ಹಂತದಲ್ಲಿದೆ. {threat} ಅಪಾಯ ಹೆಚ್ಚಾಗಿದೆ. {product} ಸಿಂಪಡಿಸಿ — {district} ನ ಡೀಲರ್ ಹತ್ತಿರ ಲಭ್ಯ.",
        "sms": "{crop} bele {threat} apaya! {product} simpadisi. {district} dealer hattira.",
        "voice_script": "ನಮಸ್ಕಾರ ರೈತ ಬಂಧು, ನಾನು ಸಿಂಜೆಂಟಾ ಇಂದ ಮಾತನಾಡುತ್ತಿದ್ದೇನೆ. ನಿಮ್ಮ {crop} ಬೆಳೆಯಲ್ಲಿ {threat} ಅಪಾಯವಿದೆ. {product} ಬಳಸಿ.",
    },
    "Bengali": {
        "whatsapp": "🌾 নমস্কার কৃষক ভাই! আপনার {crop} ফসল {stage} পর্যায়ে আছে। {threat} এর ঝুঁকি বাড়ছে। {product} স্প্রে করুন — {district} এর ডিলারের কাছে পাওয়া যাবে।",
        "sms": "{crop} te {threat} er jhuki! {product} spray korun. {district} dealer e jan.",
        "voice_script": "নমস্কার কৃষক ভাই, আমি সিনজেন্টা থেকে বলছি। আপনার {crop} ফসলে {threat} এর ঝুঁকি আছে। {product} ব্যবহার করুন।",
    },
}

# Gemini system prompt
SYSTEM_PROMPT = """You are an agricultural marketing content specialist for Syngenta India.
You create hyper-personalized, culturally sensitive marketing messages for Indian farmers.

Rules:
1. Always use the EXACT product name provided — never invent product names.
2. Keep WhatsApp messages under 300 characters.
3. Keep SMS under 160 characters (transliterated Roman script).
4. Voice scripts should be conversational, 30-second read time.
5. Use respectful farmer-addressing conventions for the language.
6. Include a clear call-to-action (visit dealer, call number, scan product).
7. Never make unsubstantiated yield claims.
8. Mention the specific crop stage and threat to establish credibility.
"""


import os
from typing import Dict, Any, Optional

# Try to import Gemini
try:
    import google.generativeai as genai

    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False


class ContentEngine:
    """Generates personalized marketing content from real grower context."""

    def __init__(self, gemini_api_key: str = None):
        self.api_key = gemini_api_key or os.environ.get("GEMINI_API_KEY", "")
        self.gemini_model = None

        if self.api_key and GEMINI_AVAILABLE:
            try:
                genai.configure(api_key=self.api_key)
                self.gemini_model = genai.GenerativeModel("gemini-2.0-flash")
                print("[ContentEngine] Gemini API configured successfully.")
            except Exception as e:
                print(
                    f"[ContentEngine] Gemini init failed: {e}. Falling back to templates."
                )
                self.gemini_model = None
        else:
            print("[ContentEngine] No Gemini API key. Using template-based generation.")

    def generate(
        self,
        grower_context: Dict[str, Any],
        format_type: str = "auto",
        weather_triggers: list = None,
    ) -> Dict[str, Any]:
        """
        Generate marketing content for a grower.

        Args:
            grower_context: Output from SegmentationEngine.get_grower_context()
            format_type: 'whatsapp', 'sms', 'voice_script', or 'auto'
            weather_triggers: Optional list of active disease triggers from WeatherTriggerEngine

        Returns:
            Dict with generated content for each format + visual + video.
        """
        # Determine format
        if format_type == "auto":
            channel = grower_context.get("recommended_channel", "sms")
            format_type = {
                "whatsapp": "whatsapp",
                "sms": "sms",
                "voice_call": "voice_script",
            }.get(channel, "sms")

        # Pick best available product (in stock preferred)
        products = grower_context.get("recommended_products", [])
        best_product = "Syngenta product"
        for p in products:
            if isinstance(p, dict) and p.get("in_stock", False):
                best_product = p["product"]
                break
        if best_product == "Syngenta product" and products:
            best_product = (
                products[0]["product"]
                if isinstance(products[0], dict)
                else str(products[0])
            )

        # Use weather trigger if available for more specific threat
        threat = grower_context.get("threat", "pest/disease")
        if weather_triggers:
            # Pick highest severity trigger
            severity_order = {"critical": 0, "high": 1, "medium": 2}
            sorted_triggers = sorted(
                weather_triggers,
                key=lambda t: severity_order.get(t.get("severity", "medium"), 3),
            )
            if sorted_triggers:
                threat = sorted_triggers[0]["disease"]
                best_product = sorted_triggers[0].get(
                    "recommended_product", best_product
                )

        context_vars = {
            "crop": grower_context.get("crop", "crop"),
            "stage": grower_context.get("current_stage", "growth"),
            "threat": threat,
            "product": best_product,
            "district": grower_context.get("district", ""),
            "state": grower_context.get("state", ""),
            "language": grower_context.get("language", "Hindi"),
            "farm_size": grower_context.get("farm_size_acres", 0),
        }

        result = {
            "grower_id": grower_context.get("grower_id", ""),
            "language": context_vars["language"],
            "channel": grower_context.get("recommended_channel", "sms"),
            "product_recommended": best_product,
            "generation_method": "template",
            "weather_triggers": weather_triggers or [],
        }

        if self.gemini_model:
            result["generation_method"] = "gemini"
            try:
                result["content"] = self._generate_with_gemini(
                    context_vars, format_type
                )
            except Exception as e:
                print(f"[ContentEngine] Gemini generation failed: {e}. Falling back.")
                result["generation_method"] = "template"
                result["content"] = self._generate_from_template(
                    context_vars, format_type
                )
        else:
            result["content"] = self._generate_from_template(context_vars, format_type)

        # ── Add Visual Concept Prompt ──
        result["content"]["visual_prompt"] = self._generate_visual_prompt(context_vars)

        # HACKATHON DAY PATCH: Inject a dynamic placeholder image URL based on crop/threat
        # so the frontend has something real to render during the demo.
        threat_lower = context_vars["threat"].lower()
        if "blight" in threat_lower or "rust" in threat_lower or "wilt" in threat_lower:
            # Show a diseased crop image for active threats
            demo_image = "https://images.unsplash.com/photo-1592843997784-07e33dc3a105?q=80&w=400&auto=format&fit=crop"
        else:
            # Show a general healthy crop image
            demo_image = "https://images.unsplash.com/photo-1625246333195-78d9c38ad449?q=80&w=400&auto=format&fit=crop"

        result["content"]["generated_image_url"] = demo_image

        # ── Add Video Storyboard ──
        result["content"]["video_storyboard"] = self._generate_video_storyboard(
            context_vars
        )

        # ── Run Content Guardrails ──
        from backend.orchestrator import CampaignOrchestrator

        orch = CampaignOrchestrator()
        result["guardrail_check"] = orch.validate_content(
            result["content"], best_product
        )

        return result

    def _generate_with_gemini(self, ctx: Dict, format_type: str) -> Dict[str, str]:
        """Generate content using Gemini API."""
        user_prompt = f"""Generate a {format_type} marketing message with these EXACT parameters:
- Crop: {ctx['crop']}
- Current Stage: {ctx['stage']}
- Active Threat: {ctx['threat']}
- Product to Promote: {ctx['product']}
- Target Language: {ctx['language']}
- Region: {ctx['district']}, {ctx['state']}
- Farm Size: {ctx['farm_size']} acres

Generate the message in {ctx['language']} language.
Also provide an English translation.
Format your response as:
ORIGINAL: <message in target language>
ENGLISH: <english translation>
"""
        response = self.gemini_model.generate_content(
            [
                {
                    "role": "user",
                    "parts": [{"text": SYSTEM_PROMPT + "\n\n" + user_prompt}],
                }
            ]
        )
        text = response.text.strip()

        # Parse response
        original = text
        english = ""
        if "ORIGINAL:" in text and "ENGLISH:" in text:
            parts = text.split("ENGLISH:")
            original = parts[0].replace("ORIGINAL:", "").strip()
            english = parts[1].strip()

        return {
            format_type: original,
            "english_translation": english,
        }

    def _generate_from_template(self, ctx: Dict, format_type: str) -> Dict[str, str]:
        """Generate content using pre-built vernacular templates."""
        lang = ctx["language"]
        templates = TEMPLATES.get(lang, TEMPLATES["Hindi"])

        result = {}
        for fmt in ["whatsapp", "sms", "voice_script"]:
            template = templates.get(fmt, "")
            result[fmt] = template.format(**ctx) if template else ""

        return result

    def _generate_visual_prompt(self, ctx: Dict) -> str:
        """
        Generate a detailed image prompt for WhatsApp flyer / social media visual.
        Designed to be fed to Imagen, DALL-E, or Stable Diffusion.
        """
        lang_script = {
            "Hindi": "Devanagari script",
            "Punjabi": "Gurmukhi script",
            "Marathi": "Devanagari script",
            "Gujarati": "Gujarati script",
            "Kannada": "Kannada script",
            "Bengali": "Bengali script",
        }
        script = lang_script.get(ctx["language"], "Devanagari script")

        return (
            f"Agricultural marketing infographic, professional clean design, Syngenta green brand colors. "
            f"Split layout: LEFT SIDE shows a close-up photograph of {ctx['threat']} damage on "
            f"{ctx['crop']} leaves during {ctx['stage']} stage — wilting, discoloration, spots visible. "
            f"RIGHT SIDE shows a healthy, vibrant {ctx['crop']} field after treatment, lush green. "
            f"CENTER: Product packaging of '{ctx['product']}' prominently displayed with Syngenta logo. "
            f"BOTTOM BANNER: Text overlay in {script} ({ctx['language']} language) reading the product name "
            f"'{ctx['product']}' and a call-to-action 'Ask your local dealer'. "
            f"Region context: {ctx['district']}, {ctx['state']}. "
            f"Style: photorealistic crop imagery, flat-design infographic elements, high contrast for "
            f"mobile viewing. Aspect ratio: 1:1 square for WhatsApp status / social media."
        )

    def _generate_video_storyboard(self, ctx: Dict) -> list:
        """
        Generate a 30-second video storyboard for IVR visual or social media.
        Designed for low-literacy audiences: heavy on visuals, simple narration.
        """
        return [
            {
                "scene": 1,
                "duration_sec": 5,
                "visual": f"Wide shot of a {ctx['crop']} field in {ctx['district']}, {ctx['state']}. "
                f"Camera slowly zooms in to show early signs of {ctx['threat']}.",
                "narration_lang": ctx["language"],
                "narration_en": f"Attention {ctx['crop']} farmers of {ctx['district']}! "
                f"Your crop is in the {ctx['stage']} stage.",
                "text_overlay": f"⚠️ {ctx['threat']}",
            },
            {
                "scene": 2,
                "duration_sec": 8,
                "visual": f"Close-up of {ctx['threat']} symptoms on {ctx['crop']} — "
                f"damaged leaves, discoloration, pest activity. "
                f"Red warning graphics overlay.",
                "narration_lang": ctx["language"],
                "narration_en": f"{ctx['threat']} is spreading in your area. "
                f"If untreated, it can reduce your yield significantly.",
                "text_overlay": f"Yield at risk!",
            },
            {
                "scene": 3,
                "duration_sec": 7,
                "visual": f"Product shot: {ctx['product']} packaging held by a farmer's hands. "
                f"Syngenta logo visible. Cut to sprayer applying the product on the field.",
                "narration_lang": ctx["language"],
                "narration_en": f"Use {ctx['product']} from Syngenta. "
                f"Proven protection for your {ctx['crop']} crop.",
                "text_overlay": f"✅ {ctx['product']}",
            },
            {
                "scene": 4,
                "duration_sec": 5,
                "visual": f"Before/after split screen: LEFT damaged {ctx['crop']}, "
                f"RIGHT healthy treated {ctx['crop']}. Bright, positive imagery.",
                "narration_lang": ctx["language"],
                "narration_en": f"Protect your crop. Protect your income.",
                "text_overlay": f"Healthy crop = Better harvest",
            },
            {
                "scene": 5,
                "duration_sec": 5,
                "visual": f"Syngenta branding screen with dealer locator QR code. "
                f"Text in {ctx['language']}: 'Available at your nearest dealer'.",
                "narration_lang": ctx["language"],
                "narration_en": f"Visit your nearest dealer in {ctx['district']} today. "
                f"Or give a missed call to know more.",
                "text_overlay": f"📞 Missed call: 1800-XXX-XXXX",
            },
        ]

    def generate_batch(self, grower_contexts: list, format_type: str = "auto") -> list:
        """Generate content for a batch of growers."""
        results = []
        for ctx in grower_contexts:
            content = self.generate(ctx, format_type)
            results.append(content)
        return results
