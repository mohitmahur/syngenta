# 🌾 KrishiConnect AI: Agricultural Marketing Intelligence

**A Multi-Modal, AI-Powered Marketing Orchestrator built for the Syngenta × IIT Madras Hackathon 2026**

---

## The Problem

Traditional marketing—mass media, generic campaigns, and one-size-fits-all content—fails in agriculture because:
1. **Hyper-Localization:** A farmer growing wheat in Punjab faces entirely different agronomic threats than one growing mustard in Gujarat.
2. **Episodic Outbreaks:** Pest and disease outbreaks are dynamic. Marketing a fungicide when there is no disease pressure (or wrong weather conditions) is a wasted effort.
3. **Accessibility:** Content must be vernacular, highly visual, and contextually relevant to resonate with farmers who have limited time, lower literacy rates, and disparate device access (smartphone vs. feature phone).
4. **Attribution:** It is incredibly difficult to map a WhatsApp message to an offline retail point-of-sale (POS) conversion.

##  The Solution

**KrishiConnect AI** is a production-grade, end-to-end intelligent orchestration engine. It ingests raw field telemetry (Grower profiles, POS data, Rep visits, and Digital logs), fuses it with **real-time weather APIs**, and dynamically sequences hyper-personalized marketing content across WhatsApp, SMS, and Voice Calls.

Rather than generating generic AI text, the system establishes a highly opinionated, safety-first pipeline capable of producing multi-modal artifacts (Text + Visuals + Video Storyboards) governed by strict chemical compliance guardrails.

---

## Core Architecture & Features

### 1. Receptivity Prediction Model v2
We moved beyond basic demographic filtering. The system trains a `HistGradientBoostingClassifier` on historical campaign engagement (WhatsApp opens/clicks). 
*   **Feature Engineering:** Incorporates `msg_fatigue`, `days_since_sowing`, `hist_open_rate`, and target-encodes high cardinality features like Tehsil and State.
*   **Outcome:** Segments farmers into High/Medium/Low engagement tiers to optimize channel spend.

### 2. Live Weather Trigger Engine
Agronomic threats are not static. The system integrates with the **Open-Meteo API** to fetch real-time temperature, humidity, and rainfall for the grower's exact district. 
*   It dynamically evaluates these conditions against established agronomic rules (e.g., *Late Blight risk elevates if humidity > 90% and temp 15-22°C*) to inject real-time urgency into the marketing copy.

### 3. Campaign Orchestrator & Multi-Channel Routing
The orchestrator ensures we don't spam unengaged farmers.
*   **Smart Sequencing:** If a farmer exhibits "WhatsApp fatigue" (low historical open rates), the orchestrator cascades the delivery route: `WhatsApp → SMS → Voice Call Script → Field Rep Action`.
*   **Optimal Send Times:** Schedules messages based on agrarian daily routines (e.g., 06:30 - 08:00 AM).

### 4. Multi-Modal Content Engine
Powered by **Google Gemini Flash**, the content engine produces highly vernacular outputs. For lower-literacy segments, text isn't enough. The system automatically synthesizes:
*   **Visual Concepts:** High-fidelity prompts ready to be fed into DALL-E or Stable Diffusion.
*   **Video Storyboards:** 30-second, 5-scene narrative scripts with visual cues and translated voice-over narrations designed for short-form video formats.

### 5.Strict Compliance Guardrails
AI hallucinations in Ag-Chem are dangerous. KrishiConnect runs generated payloads through rigorous RegEx guardrails that:
*   Verify the recommended chemical product is explicitly mentioned.
*   **Block forbidden claims** (e.g., blocking phrases like "100% guarantee", "triple your yield", or false "organic" claims for synthetic chemicals).

### 6. 14-Day Attribution Window
Moving away from naive lifetime joins, the analytics engine measures true Campaign-to-Action conversion. A POS transaction is only credited to a digital campaign if the product scan occurred **within exactly 14 days** of the message interaction.

### 7.Analog Surveillance Terminal UI
We actively rejected the "generic AI dashboard slop" aesthetic. The frontend is a bespoke **"Agricultural Data-Punk"** interface resembling an analog Syngenta control terminal—featuring CRT phosphor-orange data streams, chalk-white monospace metrics, and strict neobrutalist grid architecture.

---

##  Tech Stack

*   **Backend:** Python 3.10+, FastAPI, Uvicorn
*   **Machine Learning:** Scikit-Learn (`HistGradientBoostingClassifier`), Pandas, NumPy
*   **AI Integration:** `google-generativeai` (Gemini 2.0 Flash)
*   **External APIs:** Open-Meteo (Real-time weather)
*   **Frontend:** Vanilla JS, Custom CSS Grid Design System
*   **Data Source:** Custom synthetic `Syngenta_IITM_Hackathon_2026_dataset` representing the 2025-26 Rabi Season.

---

##  How to Run Locally

### Prerequisites
1. Python 3.9 or higher.
2. An active Google Gemini API Key.

### Installation

1. **Clone the repository and install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Set your API Key:**
   Export your Gemini API key to your environment variables. 
   *(Note: If the key is missing, the backend will gracefully fall back to hardcoded template responses so the application won't crash).*
   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```

3. **Start the Uvicorn Server:**
   Navigate to the `prototype` directory and start the FastAPI application:
   ```bash
   python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
   ```

4. **Access the Terminal:**
   Open your browser and navigate to:
   `http://localhost:8000`

# NOTE:-  unzip the dataset and then add the dataset folder in root dir

---

##  Future Roadmap

1. **Cloud Deployment:** Containerize the API with Docker for GCP/AWS deployment.
2. **Supply Chain Auto-Routing:** If a product is out of stock at a grower's local retailer, dynamically adjust the campaign to recommend the next closest retail node holding inventory.
3. **True Multimodality:** Connect the Visual Prompts directly to the Imagen 3 API to render the generated creatives directly in the UI. 

---
*Built for Track: AI-Powered Agricultural Marketing at Scale*
