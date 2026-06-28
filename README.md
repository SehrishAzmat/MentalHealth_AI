# 🧠 Mental Health AI

A desktop application that analyses your written or spoken text, detects your emotional state using four AI models, tracks your mood history, and offers an AI-powered chat companion (MindBot).

---

## Features

- **Mood Analysis** — detects one of 10 emotions (joy, sadness, anger, fear, stress, surprise, disgust, neutral, love, anxiety)
- **4 NLP Models** — DistilRoBERTa, BERT, RoBERTa GoEmotions, BERTweet; compare all four at once
- **Voice Input** — speak your mood instead of typing
- **Mood History** — every analysis is saved and searchable
- **Trend Charts** — interactive Plotly charts for 7 / 14 / 30 / 90 day windows
- **MindBot Chat** — AI companion powered by Google Gemini
- **PDF Export** — download a full mood report
- **Light / Dark theme**

---

## Project Structure

```
mental_health_ai/
├── backend.py       # FastAPI REST server — NLP inference, database, Gemini AI
├── frontend.py      # PyQt5 desktop GUI
├── moods.db         # SQLite database (auto-created on first run)
└── README.md
```

---

## Requirements

- Python 3.9 or higher
- A Google Gemini API key (free at [aistudio.google.com](https://aistudio.google.com)) — **optional**, only needed for MindBot chat
- A working microphone — **optional**, only needed for voice input

---

## Installation

### 1. Clone or download the project

```bash
git clone https://github.com/SehrishAzmat/mental-health-ai.git
cd mental-health-ai
```

### 2. Create and activate a virtual environment (recommended)

```bash
# Windows
python -m venv venv
venv\Scripts\activate

# Mac / Linux
python -m venv venv
source venv/bin/activate
```

### 3. Install backend dependencies

```bash
pip install fastapi uvicorn pydantic transformers torch google-genai reportlab
```

### 4. Install frontend dependencies

```bash
pip install PyQt5 PyQtWebEngine requests SpeechRecognition pyaudio
```

> **Windows note:** if `pyaudio` fails, install it via pipwin:
> ```bash
> pip install pipwin
> pipwin install pyaudio
> ```

> **Optional:** suppress a BERTweet startup warning:
> ```bash
> pip install emoji==0.6.0
> ```

---

## Configuration

Set your Gemini API key as an environment variable **before** starting the backend.

```bash
# Windows (Command Prompt)
set GEMINI_API_KEY=your_api_key_here

# Windows (PowerShell)
$env:GEMINI_API_KEY="your_api_key_here"

# Mac / Linux
export GEMINI_API_KEY="your_api_key_here"
```

> If you skip this step the app still works — mood analysis runs fully offline. Only MindBot chat will use a fallback response.

---

## Running the App

You need **two terminal windows** open at the same time.

### Terminal 1 — Start the backend

```bash
cd mental-health-ai
python backend.py
```

Wait until you see all four models loaded and the server ready:

```
✅ 4/4 classifiers loaded.
✅ Database ready! (...)
INFO: Uvicorn running on http://127.0.0.1:8000
```

> The first run downloads the four HuggingFace models (~450 MB total). This only happens once — they are cached locally after that.

### Terminal 2 — Start the frontend

```bash
cd mental-health-ai
python frontend.py
```

The desktop window will open. The backend must already be running.

---

## How to Use

| Feature | Steps |
|---|---|
| **Analyse mood** | Type how you feel → select a model → click **Analyze** |
| **Compare models** | Type text → click **Compare All 4** |
| **Voice input** | Click **Start Voice** → speak → click **Stop Voice** |
| **View history** | Click **History** in the sidebar |
| **Chat with MindBot** | Click **Chat** in the sidebar → type a message |
| **See trends** | Home page right panel — use 7D / 14D / 30D / 90D buttons |
| **Export PDF** | Click **Export** in the sidebar |
| **Toggle theme** | Click **Light / Dark** button at the bottom of the sidebar |

---

## Emotion Classes

| Emotion | Emoji | Emotion | Emoji |
|---|---|---|---|
| Joy | 😊 | Disgust | 🤢 |
| Sadness | 😢 | Neutral | 😐 |
| Anger | 😠 | Love | 💕 |
| Fear | 😨 | Anxiety | 😟 |
| Stress | 😰 | Surprise | 😲 |

---

## Models Used

| Model | Parameters | Best for |
|---|---|---|
| DistilRoBERTa | 82M | Speed (default) |
| BERT Base | 110M | Accuracy (93.8%) |
| RoBERTa GoEmotions | 125M | Fine-grained emotions (28 classes → mapped to 10) |
| BERTweet | 135M | Social media / informal text |

---

## Troubleshooting

**Backend won't start / model download fails**
- Check your internet connection on first run
- Make sure `torch` and `transformers` are installed correctly

**"Cannot reach backend" error in the GUI**
- Make sure `python backend.py` is running in a separate terminal
- Check that nothing else is using port 8000

**Voice not working**
- Install `pyaudio` (see Installation step 4)
- Check that your microphone is connected and not muted
- Voice recognition requires an internet connection (uses Google Speech API)

**MindBot gives a generic reply**
- Set `GEMINI_API_KEY` before starting the backend (see Configuration)
- Free-tier Gemini has rate limits — the app automatically tries fallback models

**Pydantic warnings on startup**
- These are harmless deprecation notices; update to the latest version of this project to remove them

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + Uvicorn |
| NLP models | HuggingFace Transformers (PyTorch) |
| AI chat | Google Gemini (google-genai) |
| Database | SQLite |
| PDF generation | ReportLab |
| Desktop GUI | PyQt5 |
| Charts | Plotly.js (rendered in QWebEngineView) |
| Voice input | SpeechRecognition + PyAudio |

---

## License

This project is for personal and educational use only. It is not a substitute for professional mental health support.

If you are in crisis, please reach out:
- 🇺🇸 **988** (US Suicide & Crisis Lifeline)
- 🇬🇧 **116 123** (Samaritans UK)
- 📱 Text **HOME** to **741741** (Crisis Text Line)
