# -*- coding: utf-8 -*-
"""
Mental Health AI - Complete Backend
====================================
FastAPI backend with:
  - Emotion classification (distilroberta)
  - SQLite persistence
  - Weekly trend analytics
  - Chat mode (via Claude API or rule-based fallback)
  - PDF report generation
  - Full CORS support for local desktop app
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transformers import pipeline
import uvicorn
import sqlite3
from datetime import datetime, timedelta
import json
import os

# ── PDF dependencies ──────────────────────────────────────────────────────────
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import io

# ═══════════════════════════════════════════════════════════════════════════════
app = FastAPI(title="🧠 Mental Health AI v3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── ML Model ──────────────────────────────────────────────────────────────────
print("⏳ Loading emotion classifier…")
classifier = pipeline(
    "text-classification",
    model="j-hartmann/emotion-english-distilroberta-base"
)
print("✅ Classifier ready!")

# ── Risk / suggestion config ──────────────────────────────────────────────────
RISK_MAP = {
    'joy':      10,
    'surprise': 20,
    'neutral':  15,
    'disgust':  65,
    'anger':    60,
    'stress':   75,
    'fear':     80,
    'sadness':  85,
}

SUGGESTIONS = {
    'joy':      "Keep spreading positivity! 🌟 Try journaling what made you happy.",
    'surprise': "Take a moment to breathe and process the unexpected. 🌬️",
    'neutral':  "Good balance! Consider a short mindfulness walk. 🚶",
    'disgust':  "Step away briefly, then try box-breathing (4-4-4-4). 🧘",
    'anger':    "Try the 5-4-3-2-1 grounding technique to calm down. 🌿",
    'stress':   "Progressive muscle relaxation can really help right now. 💆",
    'fear':     "You are safe. Write down your fears — it reduces their power. 📝",
    'sadness':  "Reach out to someone you trust. You deserve support. 🤗",
}

EMOTION_COLORS = {
    'joy':      '#F4A261',
    'sadness':  '#4A90D9',
    'anger':    '#E74C3C',
    'fear':     '#9B59B6',
    'stress':   '#E84393',
    'surprise': '#2ECC71',
    'disgust':  '#E67E22',
    'neutral':  '#7F8C8D',
}

# ── Chatbot responses (rule-based warm fallback) ──────────────────────────────
CHAT_RESPONSES = {
    'sad|sadness|crying|cry|depressed|depression|down|low': [
        "I hear you, and I'm really glad you reached out. 💙 Feeling sad is completely valid. Would you like to tell me more about what's weighing on you?",
        "It sounds like you're going through a tough time. Remember, every storm passes. I'm here to listen — what's on your mind?",
        "Sadness can feel so heavy. You don't have to carry it alone. Take a deep breath, and share what you're feeling.",
    ],
    'anxious|anxiety|worried|worry|stress|stressed|panic': [
        "Anxiety can be overwhelming, but you're doing great by acknowledging it. 🌿 Let's try 4-7-8 breathing: inhale 4 counts, hold 7, exhale 8. Ready?",
        "Stress is your body's signal that something matters to you. That's okay! Let's talk through what's causing this.",
        "When anxiety hits, ground yourself: name 5 things you see, 4 you can touch, 3 you hear. You've got this! 💪",
    ],
    'angry|anger|frustrated|rage|mad|furious': [
        "I understand you're feeling really frustrated. That anger is valid. 🌊 Before anything, take 3 slow breaths with me. What happened?",
        "Anger often comes from feeling unheard or hurt. I'm listening — tell me what's going on.",
    ],
    'happy|great|good|joy|excited|wonderful|amazing': [
        "That's wonderful to hear! 🌟 Positive emotions are so important for mental wellness. What's making you feel this way?",
        "Love to hear that you're doing well! 😊 These good moments are worth savoring. What's bringing you joy today?",
    ],
    'lonely|alone|isolated|nobody|no one': [
        "Loneliness can be really painful. Please know — you matter, and I'm here with you right now. 💙 Would you like to talk about it?",
        "You reached out, and that takes courage. You're not alone in this moment. Let's talk.",
    ],
    'help|suicide|hurt myself|self harm|end it': [
        "I'm really concerned about you right now. Please reach out to a professional immediately. 🆘\n\n📞 Crisis Helpline: 988 (US) | 116 123 (UK)\n💬 Crisis Text: Text HOME to 741741\n\nYou matter more than you know. Please talk to someone who can truly help. Are you safe right now?",
    ],
}

DEFAULT_CHAT = [
    "I'm here for you. 💙 Tell me more about how you're feeling?",
    "That sounds really meaningful. I'm listening — go on.",
    "Thank you for sharing that with me. How long have you been feeling this way?",
    "You're doing great by talking about this. What do you think might help you feel better today?",
    "I hear you. Sometimes just expressing our feelings is the first step to healing. What else is on your mind?",
]

# ── Database setup ────────────────────────────────────────────────────────────
def init_db():
    conn = sqlite3.connect('moods.db', check_same_thread=False)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS moods (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT    NOT NULL,
            text        TEXT    NOT NULL,
            emotion     TEXT    NOT NULL,
            confidence  REAL    NOT NULL,
            risk_score  INTEGER DEFAULT 0,
            risk_level  TEXT    DEFAULT "LOW",
            suggestion  TEXT    DEFAULT ""
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS chat_messages (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT    NOT NULL,
            role      TEXT    NOT NULL,
            content   TEXT    NOT NULL
        )
    ''')
    conn.commit()
    print("✅ Database ready — moods.db initialised!")
    return conn

conn = init_db()

# ── Pydantic models ───────────────────────────────────────────────────────────
class TextInput(BaseModel):
    text: str

class MoodSave(BaseModel):
    text: str
    emotion: str
    confidence: float
    risk_score: int = 0
    risk_level: str = "LOW"
    suggestion: str = ""

class ChatMessage(BaseModel):
    message: str
    history: list = []

# ═══════════════════════════════════════════════════════════════════════════════
# ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {
        "message": "🧠 Mental Health AI v3.0 Ready!",
        "endpoints": ["/predict", "/history", "/save_mood", "/trends", "/chat", "/export_pdf"],
        "docs": "http://127.0.0.1:8000/docs"
    }


@app.post("/predict")
async def predict_mood(input: TextInput):
    result   = classifier(input.text)[0]
    label    = result['label'].lower()
    score    = result['score']

    risk_score = RISK_MAP.get(label, 50)
    suggestion = SUGGESTIONS.get(label, "Take care of yourself today. 💙")
    risk_level = "HIGH" if risk_score >= 75 else "MEDIUM" if risk_score >= 40 else "LOW"
    color      = EMOTION_COLORS.get(label, '#7F8C8D')

    return {
        "text_preview": input.text[:60] + ("…" if len(input.text) > 60 else ""),
        "emotion":      label,
        "confidence":   round(score * 100, 1),
        "risk_score":   risk_score,
        "risk_level":   risk_level,
        "suggestion":   suggestion,
        "color":        color,
    }


@app.post("/save_mood")
async def save_mood(mood: MoodSave):
    try:
        conn.execute(
            """INSERT INTO moods
               (timestamp, text, emotion, confidence, risk_score, risk_level, suggestion)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                datetime.now().isoformat(),
                mood.text[:200],
                mood.emotion,
                mood.confidence / 100.0,
                mood.risk_score,
                mood.risk_level,
                mood.suggestion,
            )
        )
        conn.commit()
        total = conn.execute("SELECT COUNT(*) FROM moods").fetchone()[0]
        return {"status": "Mood saved!", "total_moods": total}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/history")
async def get_history(limit: int = 50):
    cursor = conn.execute(
        "SELECT * FROM moods ORDER BY timestamp DESC LIMIT ?", (limit,)
    )
    rows = cursor.fetchall()
    return [
        {
            "id":         row[0],
            "time":       row[1][:16].replace("T", " "),
            "text":       row[2][:80] + ("…" if len(row[2]) > 80 else ""),
            "emotion":    row[3],
            "confidence": f"{row[4] * 100:.1f}%",
            "risk_score": row[5],
            "risk_level": row[6],
            "suggestion": row[7] if len(row) > 7 else "",
            "color":      EMOTION_COLORS.get(row[3], '#7F8C8D'),
        }
        for row in rows
    ]


@app.get("/trends")
async def get_trends(days: int = 7):
    """Return daily emotion counts for the last N days."""
    since = (datetime.now() - timedelta(days=days)).isoformat()
    cursor = conn.execute(
        """SELECT DATE(timestamp) as day, emotion, COUNT(*) as cnt
           FROM moods WHERE timestamp >= ?
           GROUP BY day, emotion
           ORDER BY day""",
        (since,)
    )
    rows = cursor.fetchall()

    # Build a structured response
    data: dict = {}
    for day, emotion, cnt in rows:
        if day not in data:
            data[day] = {}
        data[day][emotion] = cnt

    # Fill missing days
    all_emotions = list(RISK_MAP.keys())
    result = []
    for i in range(days):
        day = (datetime.now() - timedelta(days=days - 1 - i)).strftime("%Y-%m-%d")
        day_data = {"date": day}
        for em in all_emotions:
            day_data[em] = data.get(day, {}).get(em, 0)
        result.append(day_data)

    # Also return overall stats
    total = conn.execute("SELECT COUNT(*) FROM moods").fetchone()[0]
    most_common = conn.execute(
        "SELECT emotion, COUNT(*) as c FROM moods GROUP BY emotion ORDER BY c DESC LIMIT 1"
    ).fetchone()
    avg_risk = conn.execute("SELECT AVG(risk_score) FROM moods").fetchone()[0]

    return {
        "daily": result,
        "total_entries": total,
        "most_common_emotion": most_common[0] if most_common else "N/A",
        "avg_risk_score": round(avg_risk or 0, 1),
        "emotions": all_emotions,
        "colors": EMOTION_COLORS,
    }


@app.post("/chat")
async def chat(msg: ChatMessage):
    """Warm rule-based chatbot with keyword matching."""
    import random
    text_lower = msg.message.lower()

    for pattern, responses in CHAT_RESPONSES.items():
        keywords = pattern.split('|')
        if any(kw in text_lower for kw in keywords):
            return {"reply": random.choice(responses)}

    return {"reply": random.choice(DEFAULT_CHAT)}


@app.get("/export_pdf")
async def export_pdf():
    """Generate and return a PDF mood report."""
    from fastapi.responses import StreamingResponse

    cursor = conn.execute(
        "SELECT * FROM moods ORDER BY timestamp DESC LIMIT 30"
    )
    rows = cursor.fetchall()

    trends_cursor = conn.execute(
        """SELECT emotion, COUNT(*) as c, AVG(risk_score) as avg_risk
           FROM moods GROUP BY emotion ORDER BY c DESC"""
    )
    emotion_stats = trends_cursor.fetchall()

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        rightMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Title'],
        fontSize=24,
        textColor=colors.HexColor('#2E86AB'),
        spaceAfter=6,
        alignment=TA_CENTER,
    )
    heading_style = ParagraphStyle(
        'Heading',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=colors.HexColor('#1A5276'),
        spaceBefore=16,
        spaceAfter=6,
    )
    normal_style = ParagraphStyle(
        'Normal2',
        parent=styles['Normal'],
        fontSize=10,
        leading=14,
    )

    story = []

    # Title
    story.append(Paragraph("🧠 Mental Health AI — Mood Report", title_style))
    story.append(Paragraph(
        f"Generated: {datetime.now().strftime('%B %d, %Y %H:%M')}",
        ParagraphStyle('sub', parent=styles['Normal'], alignment=TA_CENTER,
                       textColor=colors.gray, fontSize=9)
    ))
    story.append(HRFlowable(width="100%", thickness=2, color=colors.HexColor('#2E86AB')))
    story.append(Spacer(1, 12))

    # Summary stats
    total = conn.execute("SELECT COUNT(*) FROM moods").fetchone()[0]
    avg_risk = conn.execute("SELECT AVG(risk_score) FROM moods").fetchone()[0] or 0
    most_common = emotion_stats[0][0].upper() if emotion_stats else "N/A"

    story.append(Paragraph("Summary Statistics", heading_style))
    summary_data = [
        ["Metric", "Value"],
        ["Total Entries", str(total)],
        ["Most Common Emotion", most_common],
        ["Average Risk Score", f"{avg_risk:.1f} / 100"],
    ]
    t = Table(summary_data, colWidths=[3 * inch, 3 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2E86AB')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EBF5FB')]),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t)
    story.append(Spacer(1, 12))

    # Emotion breakdown
    story.append(Paragraph("Emotion Breakdown", heading_style))
    em_data = [["Emotion", "Count", "Avg Risk"]]
    for em, cnt, avg_r in emotion_stats:
        em_data.append([em.capitalize(), str(cnt), f"{avg_r:.0f}"])
    t2 = Table(em_data, colWidths=[2.5 * inch, 2 * inch, 2 * inch])
    t2.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1A5276')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#EBF5FB')]),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(t2)
    story.append(Spacer(1, 12))

    # Recent entries
    story.append(Paragraph("Recent Mood Entries (Last 30)", heading_style))
    hist_data = [["Date & Time", "Emotion", "Confidence", "Risk", "Suggestion"]]
    for row in rows:
        hist_data.append([
            row[1][:16].replace("T", " "),
            row[3].capitalize(),
            f"{row[4] * 100:.1f}%",
            row[6],
            (row[7][:40] + "…") if len(row[7] if len(row) > 7 else "") > 40 else (row[7] if len(row) > 7 else ""),
        ])

    t3 = Table(hist_data, colWidths=[1.5 * inch, 1 * inch, 0.9 * inch, 0.8 * inch, 2.6 * inch])
    t3.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#117A65')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.lightgrey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#E8F8F5')]),
        ('PADDING', (0, 0), (-1, -1), 5),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('WORDWRAP', (4, 1), (4, -1), True),
    ]))
    story.append(t3)

    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "This report was generated by Mental Health AI. "
        "It is for personal awareness only and does not constitute medical advice. "
        "Please consult a licensed professional for clinical concerns.",
        ParagraphStyle('disclaimer', parent=styles['Normal'], fontSize=8,
                       textColor=colors.gray, alignment=TA_CENTER)
    ))

    doc.build(story)
    buf.seek(0)

    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={"Content-Disposition": "attachment; filename=mood_report.pdf"}
    )


# ═══════════════════════════════════════════════════════════════════════════════
if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000, reload=False)