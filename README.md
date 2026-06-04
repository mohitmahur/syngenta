# 🌾 KrishiConnect AI: Agricultural Marketing Intelligence

**A Multi-Modal, AI-Powered Marketing Orchestrator built for the Syngenta × IIT Madras Hackathon 2026**

---

## The Problem

Traditional marketing—mass media, generic campaigns, and one-size-fits-all content—fails in agriculture because:
1. **Hyper-Localization:** A farmer growing wheat in Punjab faces entirely different agronomic threats than one growing mustard in Gujarat.
2. **Episodic Outbreaks:** Pest and disease outbreaks are dynamic. Marketing a fungicide when there is no disease pressure (or wrong weather conditions) is a wasted effort.
3. **Accessibility:** Content must be vernacular, highly visual, and contextually relevant to resonate with farmers who have limited time, lower literacy rates, and disparate device access (smartphone vs. feature phone).
4. **Attribution:** It is incredibly difficult to map a WhatsApp message to an offline retail point-of-sale (POS) conversion.

## The Solution

**KrishiConnect AI** is a production-grade, end-to-end intelligent orchestration engine. It ingests raw field telemetry (Grower profiles, POS data, Rep visits, and Digital logs), fuses it with **real-time weather APIs**, and dynamically sequences hyper-personalized marketing content across WhatsApp, SMS, and Voice Calls.

Rather than generating generic AI text, the system establishes a highly opinionated, safety-first pipeline capable of producing multi-modal artifacts (Text + Native Audio + Visuals + Video Storyboards) governed by strict chemical compliance guardrails and a real-time human feedback loop.

---

## Core Architecture & Features

### 1. Lookalike Cohort Receptivity Stack (v7_stable)
To adapt to realistic, non-longitudinal agricultural datasets where deep individual message history is sparse, we bypassed naive, leak-prone user joins in favor of an enterprise **Lookalike Cohort Propensity Engine** running twin `HistGradientBoostingClassifier` pipelines:
* **Feature Engineering:** Features categorical lookalike groupings (`state` × `crop` × `device_type`) backed by Bayesian-smoothed target encoding alongside continuous features like `days_since_sowing` and `age_farm_ratio`.
* **Sequential Model Stacking:** Addresses extreme target class imbalances (23.5% baseline open rate) by passing out-of-fold predicted probabilities from the **Open Model** directly into the **Click Model** as a primary upstream signal.
* **Inference Stabilization:** Uses strict structural Tree Regularization (`max_depth=3`, `l2_regularization=10.0`, `min_samples_leaf=30`) to protect the model from edge-case variance, completely preventing probability collapses (0% bounds) during single-grower live inferences.

### 2. Live Weather Trigger Engine
Agronomic threats are not static. The system integrates with the **Open-Meteo API** to fetch real-time temperature, humidity, and rainfall for the grower's exact district. 
* It dynamically evaluates these conditions against established agronomic rules (e.g., *Late Blight risk elevates if humidity > 90% and temp 15-22°C*) to inject real-time urgency into the marketing copy.

### 3. Campaign Orchestrator & Multi-Channel Routing
The orchestrator ensures we don't spam unengaged farmers.
* **Smart Sequencing:** If a farmer exhibits "WhatsApp fatigue" (low lookalike historical open rates), the orchestrator cascades the delivery route: `WhatsApp → SMS → Voice Call Script → Field Rep Action`.
* **Optimal Send Times:** Schedules messages based on agrarian daily routines (e.g., 06:30 - 08:00 AM).

### 4. Multi-Modal Content Engine & Vernacular Audio Synthesis
Powered by **Google Gemini 2.0 Flash**, the content engine produces highly localized vernacular copy. For lower-literacy segments, text outputs are expanded via programmatic multi-modal asset synthesis:
* **Live Audio Synthesis (`gTTS`):** Converts generated native scripts (e.g., Gujarati, Hindi) into voice recordings in real time. These files are seamlessly encoded as a Base64 data URI string for zero-latency playback using standard frontend HTML5 `<audio>` tags.
* **Visual Concepts:** High-fidelity prompts ready to be fed into DALL-E or Stable Diffusion.
* **Video Storyboards:** 30-second, 5-scene narrative scripts with visual cues and translated voice-over narrations designed for short-form video formats.

### 5. Strict Compliance Guardrails
AI hallucinations in Ag-Chem are dangerous. KrishiConnect runs generated payloads through rigorous, deterministic RegEx guardrails that:
* Verify the recommended chemical product is explicitly mentioned.
* **Block forbidden claims** (e.g., blocking phrases like "100% guarantee", "triple your yield", or false "organic" claims for synthetic chemicals).

### 6. Human-in-the-Loop RLHF Logging Console
To guarantee enterprise safety and continuous system alignment, we integrated a production-ready **Reinforcement Learning from Human Feedback (RLHF)** framework:
* Campaign managers can directly audit, approve, or reject generated payloads via the UI.
* Rejections prompt explicit categorization of model failures (e.g., *Tone Mismatch, Translation Error, Agronomic Hallucination*), appending the full context snapshot to a local, structured JSON Lines (`rlhf_feedback_logs.jsonl`) dataset for future fine-tuning pipelines.

### 7. 14-Day Attribution Window
Moving away from naive lifetime joins, the analytics engine measures true Campaign-to-Action conversion. A POS transaction is only credited to a digital campaign if the product scan occurred **within exactly 14 days** of the message interaction.

### 8. Analog Surveillance Terminal UI
We actively rejected the "generic AI dashboard slop" aesthetic. The frontend is a bespoke **"Agricultural Data-Punk"** interface resembling an analog Syngenta control terminal—featuring CRT phosphor-orange data streams, chalk-white monospace metrics, and strict neobrutalist grid architecture.

---

## Tech Stack

* **Backend:** Python 3.10+, FastAPI, Uvicorn
* **Machine Learning:** Scikit-Learn (`HistGradientBoostingClassifier`), Pandas, NumPy
* **Audio Pipeline:** `gTTS` (Google Text-to-Speech Engine), Base64 MP3 encoding
* **AI Integration:** `google-generativeai` (Gemini 2.0 Flash)
* **External APIs:** Open-Meteo (Real-time weather)
* **Frontend:** Vanilla JS, HTML5 Audio API, Custom CSS Grid Design System
* **Data Source:** Custom synthetic `Syngenta_IITM_Hackathon_2026_dataset` representing the 2025-26 Rabi Season.

---

## How to Run Locally

### Prerequisites
1. Python 3.9 or higher.
2. An active Google Gemini API Key.

### Installation

1. **Clone the repository:**
   ```bash
   git clone https://github.com/t6harsh/syngenta-agri-marketing-KrishiConnect
   cd .\syngenta-agri-marketing-KrishiConnect\prototype
   ```

2. **Download and place the dataset:**

   Download the hackathon dataset ZIP file and extract it.

   After extraction, you should get a folder named:

   ```bash
   Syngenta_IITM_Hackathon_2026_dataset
   ```

   Place this folder in the project root directory alongside:

   ```bash
   prototype/
   README.md
   .gitignore
   ```

   Final project structure:

   ```bash
   project-root/
   ├── prototype/
   ├── Syngenta_IITM_Hackathon_2026_dataset/
   ├── README.md
   └── .gitignore
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Set your API Key:**
   Export your Gemini API key to your environment variables.

   *(Note: If the key is missing, the backend will gracefully fall back to hardcoded template responses so the application won't crash).*

   ```bash
   export GEMINI_API_KEY="your_api_key_here"
   ```
   

5. **Start the Uvicorn Server:**
   Navigate to the `prototype` directory and start the FastAPI application:

   ```bash
   python3 -m uvicorn backend.app:app --host 0.0.0.0 --port 8000 --reload
   ```

6. **Access the Terminal:**
   Open your browser and navigate to:

   ```bash
   http://localhost:8000
   ```

---

## Future Roadmap

1. **Cloud Deployment:** Containerize the API with Docker for GCP/AWS deployment.
2. **True Multimodality:** Connect the Visual Prompts directly to the Imagen 3 API to render the generated creatives directly in the UI.
3. **Automated Batch Tuning:** Configure a nightly pipeline that reads the rlhf_feedback_logs.jsonl data matrix to dynamically alter standard system prompt templates.

---

*Built for Track: AI-Powered Agricultural Marketing at Scale*
