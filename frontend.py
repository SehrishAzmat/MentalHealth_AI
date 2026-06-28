# -*- coding: utf-8 -*-
"""
Mental Health AI — Premium Desktop Application
================================================
PyQt5 frontend with:
  • Mood Analyzer with voice input
  • Real-time emotion detection
  • Plotly weekly trend chart (embedded WebView)
  • Full mood history with search
  • Warm chatbot mode
  • PDF export
  • Light / Dark mode toggle
  • Smooth animations & transitions
"""

import sys
import os
import json
import random
import tempfile
import threading
import requests
from datetime import datetime

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QTextEdit, QLineEdit, QScrollArea, QFrame,
    QSplitter, QStackedWidget, QMessageBox, QSizePolicy, QGraphicsOpacityEffect,
    QTabWidget, QTableWidget, QTableWidgetItem, QHeaderView, QFileDialog,
    QProgressBar, QComboBox
)
from PyQt5.QtCore import (
    Qt, QThread, pyqtSignal, QTimer, QPropertyAnimation,
    QEasingCurve, QSize, QPoint, QRect, pyqtProperty, QObject
)
from PyQt5.QtGui import (
    QFont, QFontDatabase, QPalette, QColor, QPixmap, QLinearGradient,
    QGradient, QPainter, QPainterPath, QBrush, QPen, QIcon
)
from PyQt5.QtWebEngineWidgets import QWebEngineView

# ── Optional: speech recognition ──────────────────────────────────────────────
try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except ImportError:
    SPEECH_AVAILABLE = False

BACKEND = "http://127.0.0.1:8000"

# ═══════════════════════════════════════════════════════════════════════════════
# THEMES
# ═══════════════════════════════════════════════════════════════════════════════

LIGHT_THEME = {
    "bg_primary":      "#F7F9FC",
    "bg_secondary":    "#FFFFFF",
    "bg_card":         "#FFFFFF",
    "bg_sidebar":      "#1E293B",
    "bg_sidebar_item": "#334155",
    "text_primary":    "#0F172A",
    "text_secondary":  "#64748B",
    "text_sidebar":    "#E2E8F0",
    "accent":          "#3B82F6",
    "accent_hover":    "#2563EB",
    "accent_soft":     "#EFF6FF",
    "border":          "#E2E8F0",
    "success":         "#10B981",
    "warning":         "#F59E0B",
    "danger":          "#EF4444",
    "input_bg":        "#F8FAFC",
    "chat_user":       "#3B82F6",
    "chat_bot":        "#F1F5F9",
    "chat_user_text":  "#FFFFFF",
    "chat_bot_text":   "#0F172A",
    "shadow":          "rgba(0,0,0,0.08)",
}

DARK_THEME = {
    "bg_primary":      "#0B1120",
    "bg_secondary":    "#111827",
    "bg_card":         "#1F2937",
    "bg_sidebar":      "#060D1A",
    "bg_sidebar_item": "#1E293B",
    "text_primary":    "#F1F5F9",
    "text_secondary":  "#94A3B8",
    "text_sidebar":    "#CBD5E1",
    "accent":          "#60A5FA",
    "accent_hover":    "#3B82F6",
    "accent_soft":     "#1E3A5F",
    "border":          "#374151",
    "success":         "#34D399",
    "warning":         "#FBBF24",
    "danger":          "#F87171",
    "input_bg":        "#111827",
    "chat_user":       "#3B82F6",
    "chat_bot":        "#1F2937",
    "chat_user_text":  "#FFFFFF",
    "chat_bot_text":   "#F1F5F9",
    "shadow":          "rgba(0,0,0,0.4)",
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

EMOTION_EMOJIS = {
    'joy':      '😊',
    'sadness':  '😢',
    'anger':    '😠',
    'fear':     '😨',
    'stress':   '😰',
    'surprise': '😲',
    'disgust':  '🤢',
    'neutral':  '😐',
}

# ═══════════════════════════════════════════════════════════════════════════════
# WORKER THREADS
# ═══════════════════════════════════════════════════════════════════════════════

class AnalyzeWorker(QThread):
    result  = pyqtSignal(dict)
    error   = pyqtSignal(str)

    def __init__(self, text):
        super().__init__()
        self.text = text

    def run(self):
        try:
            r = requests.post(f"{BACKEND}/predict", json={"text": self.text}, timeout=15)
            data = r.json()
            # Auto-save
            try:
                requests.post(f"{BACKEND}/save_mood", json={
                    "text": self.text,
                    "emotion":    data['emotion'],
                    "confidence": data['confidence'],
                    "risk_score": data['risk_score'],
                    "risk_level": data['risk_level'],
                    "suggestion": data['suggestion'],
                }, timeout=5)
            except Exception:
                pass
            self.result.emit(data)
        except Exception as e:
            self.error.emit(str(e))


class ChatWorker(QThread):
    result = pyqtSignal(str)
    error  = pyqtSignal(str)

    def __init__(self, message, history):
        super().__init__()
        self.message = message
        self.history = history

    def run(self):
        try:
            r = requests.post(
                f"{BACKEND}/chat",
                json={"message": self.message, "history": self.history},
                timeout=10
            )
            self.result.emit(r.json()['reply'])
        except Exception as e:
            self.error.emit(str(e))


class TrendsWorker(QThread):
    result = pyqtSignal(dict)
    error  = pyqtSignal(str)

    def run(self):
        try:
            r = requests.get(f"{BACKEND}/trends?days=7", timeout=10)
            self.result.emit(r.json())
        except Exception as e:
            self.error.emit(str(e))


class HistoryWorker(QThread):
    result = pyqtSignal(list)
    error  = pyqtSignal(str)

    def run(self):
        try:
            r = requests.get(f"{BACKEND}/history?limit=100", timeout=10)
            self.result.emit(r.json())
        except Exception as e:
            self.error.emit(str(e))


class VoiceWorker(QThread):
    result = pyqtSignal(str)
    error  = pyqtSignal(str)

    def run(self):
        if not SPEECH_AVAILABLE:
            self.error.emit("speech_recognition not installed.\nRun: pip install SpeechRecognition pyaudio")
            return
        try:
            recognizer = sr.Recognizer()
            with sr.Microphone() as source:
                recognizer.adjust_for_ambient_noise(source, duration=0.5)
                audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            text = recognizer.recognize_google(audio)
            self.result.emit(text)
        except Exception as e:
            self.error.emit(f"Voice error: {str(e)}")


# ═══════════════════════════════════════════════════════════════════════════════
# SIDEBAR BUTTON
# ═══════════════════════════════════════════════════════════════════════════════

class SidebarButton(QPushButton):
    def __init__(self, icon_text, label, theme, parent=None):
        super().__init__(parent)
        self.icon_text = icon_text
        self.label_text = label
        self.theme = theme
        self.active = False
        self.setFixedHeight(52)
        self.setCursor(Qt.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self._apply_style()

    def set_active(self, active):
        self.active = active
        self._apply_style()

    def _apply_style(self):
        bg = self.theme['accent'] if self.active else "transparent"
        fg = "#FFFFFF" if self.active else self.theme['text_sidebar']
        radius = "10px"
        self.setStyleSheet(f"""
            QPushButton {{
                background: {bg};
                color: {fg};
                border: none;
                border-radius: {radius};
                padding: 0 16px;
                text-align: left;
                font-size: 14px;
                font-weight: {'700' if self.active else '500'};
            }}
            QPushButton:hover {{
                background: {self.theme['bg_sidebar_item'] if not self.active else self.theme['accent_hover']};
            }}
        """)
        self.setText(f"  {self.icon_text}   {self.label_text}")


# ═══════════════════════════════════════════════════════════════════════════════
# ANIMATED CARD
# ═══════════════════════════════════════════════════════════════════════════════

class Card(QFrame):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self._update_style()

    def _update_style(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {self.theme['bg_card']};
                border-radius: 16px;
                border: 1px solid {self.theme['border']};
            }}
        """)


# ═══════════════════════════════════════════════════════════════════════════════
# RESULT CARD
# ═══════════════════════════════════════════════════════════════════════════════

class ResultCard(QFrame):
    def __init__(self, theme, parent=None):
        super().__init__(parent)
        self.theme = theme
        self.setMinimumHeight(160)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(10)

        # Emotion row
        self.emotion_row = QHBoxLayout()
        self.emoji_label = QLabel("🎭")
        self.emoji_label.setFont(QFont("Segoe UI Emoji", 36))
        self.emotion_label = QLabel("—")
        self.emotion_label.setFont(QFont("Georgia", 22, QFont.Bold))
        self.emotion_row.addWidget(self.emoji_label)
        self.emotion_row.addWidget(self.emotion_label)
        self.emotion_row.addStretch()
        self.risk_badge = QLabel("")
        self.risk_badge.setFixedHeight(28)
        self.risk_badge.setContentsMargins(12, 4, 12, 4)
        self.emotion_row.addWidget(self.risk_badge)
        layout.addLayout(self.emotion_row)

        # Confidence bar
        self.conf_label = QLabel("Confidence: —")
        self.conf_label.setFont(QFont("Segoe UI", 11))
        layout.addWidget(self.conf_label)

        self.progress = QProgressBar()
        self.progress.setFixedHeight(8)
        self.progress.setTextVisible(False)
        self.progress.setValue(0)
        layout.addWidget(self.progress)

        # Suggestion
        self.suggestion = QLabel("")
        self.suggestion.setWordWrap(True)
        self.suggestion.setFont(QFont("Segoe UI", 11))
        self.suggestion.setContentsMargins(0, 4, 0, 0)
        layout.addWidget(self.suggestion)

        self._apply_idle()

    def _apply_idle(self):
        self.setStyleSheet(f"""
            QFrame {{
                background: {self.theme['bg_card']};
                border-radius: 16px;
                border: 2px dashed {self.theme['border']};
            }}
        """)
        self.emotion_label.setStyleSheet(f"color: {self.theme['text_secondary']};")
        self.emotion_label.setText("Waiting for analysis…")
        self.conf_label.setStyleSheet(f"color: {self.theme['text_secondary']};")
        self.risk_badge.hide()
        self.suggestion.hide()
        self.progress.hide()

    def update_result(self, data):
        color   = data.get('color', '#7F8C8D')
        emotion = data.get('emotion', 'neutral')
        conf    = data.get('confidence', 0)
        risk    = data.get('risk_level', 'LOW')
        sug     = data.get('suggestion', '')
        emoji   = EMOTION_EMOJIS.get(emotion, '🎭')

        self.setStyleSheet(f"""
            QFrame {{
                background: {color}18;
                border-radius: 16px;
                border: 2px solid {color}60;
            }}
        """)
        self.emoji_label.setText(emoji)
        self.emotion_label.setText(emotion.upper())
        self.emotion_label.setStyleSheet(f"color: {color}; font-weight: bold;")
        self.conf_label.setText(f"Confidence: {conf}%")
        self.conf_label.setStyleSheet(f"color: {self.theme['text_primary']};")

        self.progress.setStyleSheet(f"""
            QProgressBar::chunk {{ background: {color}; border-radius: 4px; }}
            QProgressBar {{ background: {self.theme['border']}; border-radius: 4px; border: none; }}
        """)
        self.progress.setValue(int(conf))
        self.progress.show()

        risk_colors = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#10B981"}
        rc = risk_colors.get(risk, "#10B981")
        self.risk_badge.setStyleSheet(f"""
            QLabel {{
                background: {rc}20;
                color: {rc};
                border: 1px solid {rc}60;
                border-radius: 14px;
                font-size: 11px;
                font-weight: bold;
            }}
        """)
        self.risk_badge.setText(f"⚠ {risk} RISK")
        self.risk_badge.show()

        if sug:
            self.suggestion.setText(f"💡 {sug}")
            self.suggestion.setStyleSheet(f"""
                color: {self.theme['text_primary']};
                background: {self.theme['bg_secondary']};
                border-radius: 10px;
                padding: 10px 14px;
                border: 1px solid {self.theme['border']};
            """)
            self.suggestion.show()


# ═══════════════════════════════════════════════════════════════════════════════
# CHAT BUBBLE
# ═══════════════════════════════════════════════════════════════════════════════

class ChatBubble(QFrame):
    def __init__(self, text, role, theme, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 4, 0, 4)

        bubble = QLabel(text)
        bubble.setWordWrap(True)
        bubble.setFont(QFont("Segoe UI", 11))
        bubble.setMaximumWidth(480)
        bubble.setContentsMargins(14, 10, 14, 10)

        if role == "user":
            bubble.setStyleSheet(f"""
                background: {theme['chat_user']};
                color: {theme['chat_user_text']};
                border-radius: 16px 16px 4px 16px;
                font-size: 12px;
            """)
            layout.addStretch()
            layout.addWidget(bubble)
        else:
            bubble.setStyleSheet(f"""
                background: {theme['chat_bot']};
                color: {theme['chat_bot_text']};
                border-radius: 16px 16px 16px 4px;
                border: 1px solid {theme['border']};
                font-size: 12px;
            """)
            layout.addWidget(bubble)
            layout.addStretch()


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN WINDOW
# ═══════════════════════════════════════════════════════════════════════════════

class MentalHealthApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.dark_mode = False
        self.theme = LIGHT_THEME
        self.chat_history = []
        self.last_result = None
        self.voice_worker = None

        self.setWindowTitle("🧠 Mental Health AI — v3.0")
        self.setMinimumSize(1100, 720)
        self.resize(1280, 800)

        self._build_ui()
        self._apply_theme()
        self._load_trends()

    # ── UI Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        self.setCentralWidget(root)

        # Sidebar
        self.sidebar = self._build_sidebar()
        root_layout.addWidget(self.sidebar)

        # Main content
        self.stack = QStackedWidget()
        root_layout.addWidget(self.stack, 1)

        # Pages
        self.page_home    = self._build_home_page()
        self.page_history = self._build_history_page()
        self.page_chat    = self._build_chat_page()

        self.stack.addWidget(self.page_home)
        self.stack.addWidget(self.page_history)
        self.stack.addWidget(self.page_chat)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setFixedWidth(220)
        layout = QVBoxLayout(sidebar)
        layout.setContentsMargins(16, 24, 16, 24)
        layout.setSpacing(4)

        # Logo
        logo = QLabel("🧠 MindAI")
        logo.setFont(QFont("Georgia", 18, QFont.Bold))
        logo.setStyleSheet("color: #FFFFFF; margin-bottom: 8px;")
        logo.setAlignment(Qt.AlignCenter)
        layout.addWidget(logo)

        tagline = QLabel("Your mental wellness companion")
        tagline.setFont(QFont("Segoe UI", 9))
        tagline.setStyleSheet("color: #94A3B8; margin-bottom: 20px;")
        tagline.setAlignment(Qt.AlignCenter)
        tagline.setWordWrap(True)
        layout.addWidget(tagline)

        # Nav buttons
        self.nav_buttons = []
        nav_items = [
            ("🏠", "Home & Analyze"),
            ("📋", "Mood History"),
            ("💬", "Chat Mode"),
        ]
        for i, (icon, label) in enumerate(nav_items):
            btn = SidebarButton(icon, label, self.theme)
            btn.clicked.connect(lambda checked, idx=i: self._switch_page(idx))
            layout.addWidget(btn)
            self.nav_buttons.append(btn)

        self.nav_buttons[0].set_active(True)

        layout.addStretch()

        # Theme toggle
        self.theme_btn = QPushButton("☀️  Light Mode")
        self.theme_btn.setFixedHeight(44)
        self.theme_btn.setCursor(Qt.PointingHandCursor)
        self.theme_btn.clicked.connect(self._toggle_theme)
        layout.addWidget(self.theme_btn)

        # Export PDF
        export_btn = QPushButton("📄  Export PDF")
        export_btn.setFixedHeight(44)
        export_btn.setCursor(Qt.PointingHandCursor)
        export_btn.clicked.connect(self._export_pdf)
        layout.addWidget(export_btn)
        self.export_btn_ref = export_btn

        return sidebar

    def _build_home_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(20)

        # Header
        hdr = QHBoxLayout()
        title = QLabel("Mood Analyzer")
        title.setFont(QFont("Georgia", 22, QFont.Bold))
        hdr.addWidget(title)
        hdr.addStretch()
        date_lbl = QLabel(datetime.now().strftime("%A, %B %d"))
        date_lbl.setFont(QFont("Segoe UI", 11))
        hdr.addWidget(date_lbl)
        self.home_date = date_lbl
        layout.addLayout(hdr)

        # Input card
        input_card = QFrame()
        input_layout = QVBoxLayout(input_card)
        input_layout.setContentsMargins(20, 18, 20, 18)
        input_layout.setSpacing(12)

        lbl = QLabel("How are you feeling today?")
        lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        input_layout.addWidget(lbl)

        self.text_input = QTextEdit()
        self.text_input.setPlaceholderText(
            "Write freely… e.g. 'I'm feeling anxious about my presentation tomorrow, "
            "can't seem to calm down…'"
        )
        self.text_input.setFixedHeight(110)
        self.text_input.setFont(QFont("Segoe UI", 12))
        input_layout.addWidget(self.text_input)

        btn_row = QHBoxLayout()
        self.analyze_btn = QPushButton("🔍  Analyze Mood")
        self.analyze_btn.setFixedHeight(44)
        self.analyze_btn.setCursor(Qt.PointingHandCursor)
        self.analyze_btn.clicked.connect(self._do_analyze)
        btn_row.addWidget(self.analyze_btn, 3)

        self.voice_btn = QPushButton("🎤  Voice Input")
        self.voice_btn.setFixedHeight(44)
        self.voice_btn.setCursor(Qt.PointingHandCursor)
        self.voice_btn.clicked.connect(self._start_voice)
        btn_row.addWidget(self.voice_btn, 1)

        self.clear_btn = QPushButton("✕  Clear")
        self.clear_btn.setFixedHeight(44)
        self.clear_btn.setCursor(Qt.PointingHandCursor)
        self.clear_btn.clicked.connect(lambda: self.text_input.clear())
        btn_row.addWidget(self.clear_btn, 1)

        input_layout.addLayout(btn_row)
        layout.addWidget(input_card)
        self.input_card = input_card

        # Result card
        self.result_card = ResultCard(self.theme)
        layout.addWidget(self.result_card)

        # Trend chart
        chart_lbl = QLabel("📈  Weekly Mood Trends")
        chart_lbl.setFont(QFont("Segoe UI", 13, QFont.Bold))
        layout.addWidget(chart_lbl)

        self.webview = QWebEngineView()
        self.webview.setMinimumHeight(260)
        layout.addWidget(self.webview, 1)

        return page

    def _build_history_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        hdr = QHBoxLayout()
        title = QLabel("Mood History")
        title.setFont(QFont("Georgia", 22, QFont.Bold))
        hdr.addWidget(title)
        hdr.addStretch()
        refresh_btn = QPushButton("🔄  Refresh")
        refresh_btn.setFixedHeight(38)
        refresh_btn.setCursor(Qt.PointingHandCursor)
        refresh_btn.clicked.connect(self._load_history)
        hdr.addWidget(refresh_btn)
        layout.addLayout(hdr)

        # Search bar
        self.search_bar = QLineEdit()
        self.search_bar.setPlaceholderText("🔍  Search by text, emotion, or date…")
        self.search_bar.setFixedHeight(40)
        self.search_bar.textChanged.connect(self._filter_history)
        layout.addWidget(self.search_bar)

        # Table
        self.history_table = QTableWidget()
        self.history_table.setColumnCount(6)
        self.history_table.setHorizontalHeaderLabels(
            ["Date & Time", "Emotion", "Confidence", "Risk", "Suggestion", "Text Snippet"]
        )
        hh = self.history_table.horizontalHeader()
        hh.setSectionResizeMode(0, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(1, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(2, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(3, QHeaderView.ResizeToContents)
        hh.setSectionResizeMode(4, QHeaderView.Stretch)
        hh.setSectionResizeMode(5, QHeaderView.Stretch)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.history_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.history_table.setAlternatingRowColors(True)
        layout.addWidget(self.history_table)

        self._history_data = []
        return page

    def _build_chat_page(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(32, 28, 32, 28)
        layout.setSpacing(16)

        # Header
        hdr = QHBoxLayout()
        avatar = QLabel("🤗")
        avatar.setFont(QFont("Segoe UI Emoji", 28))
        name_col = QVBoxLayout()
        name = QLabel("MindBot")
        name.setFont(QFont("Georgia", 16, QFont.Bold))
        sub = QLabel("Your warm, supportive companion")
        sub.setFont(QFont("Segoe UI", 10))
        name_col.addWidget(name)
        name_col.addWidget(sub)
        hdr.addWidget(avatar)
        hdr.addLayout(name_col)
        hdr.addStretch()
        clear_chat_btn = QPushButton("Clear Chat")
        clear_chat_btn.setFixedHeight(36)
        clear_chat_btn.clicked.connect(self._clear_chat)
        hdr.addWidget(clear_chat_btn)
        layout.addLayout(hdr)

        # Chat scroll area
        self.chat_scroll = QScrollArea()
        self.chat_scroll.setWidgetResizable(True)
        self.chat_scroll.setFrameShape(QFrame.NoFrame)

        self.chat_container = QWidget()
        self.chat_layout = QVBoxLayout(self.chat_container)
        self.chat_layout.setContentsMargins(8, 8, 8, 8)
        self.chat_layout.setSpacing(4)
        self.chat_layout.addStretch()

        self.chat_scroll.setWidget(self.chat_container)
        layout.addWidget(self.chat_scroll, 1)

        # Initial greeting
        self._add_bot_message(
            "Hello! I'm MindBot 🤗 I'm here to listen and support you. "
            "Feel free to share how you're feeling — no judgment, just care. "
            "What's on your mind today?"
        )

        # Input row
        input_row = QHBoxLayout()
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your message here…")
        self.chat_input.setFixedHeight(48)
        self.chat_input.returnPressed.connect(self._send_chat)
        self.chat_input.setFont(QFont("Segoe UI", 12))
        input_row.addWidget(self.chat_input, 1)

        send_btn = QPushButton("Send ➤")
        send_btn.setFixedSize(100, 48)
        send_btn.setCursor(Qt.PointingHandCursor)
        send_btn.clicked.connect(self._send_chat)
        input_row.addWidget(send_btn)
        layout.addLayout(input_row)

        return page

    # ── Theme ─────────────────────────────────────────────────────────────────

    def _apply_theme(self):
        t = self.theme

        # App-wide base
        self.setStyleSheet(f"""
            QMainWindow, QWidget {{ background: {t['bg_primary']}; }}
            QScrollArea {{ background: transparent; border: none; }}
            QScrollBar:vertical {{
                background: {t['bg_primary']}; width: 6px; border: none;
            }}
            QScrollBar::handle:vertical {{
                background: {t['border']}; border-radius: 3px; min-height: 20px;
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
        """)

        # Sidebar
        self.sidebar.setStyleSheet(f"background: {t['bg_sidebar']}; border-right: 1px solid {t['border']};")
        self.theme_btn.setStyleSheet(f"""
            QPushButton {{
                background: {t['bg_sidebar_item']};
                color: {t['text_sidebar']};
                border: none;
                border-radius: 10px;
                font-size: 13px;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: {t['accent']}; }}
        """)
        self.export_btn_ref.setStyleSheet(f"""
            QPushButton {{
                background: {t['accent']}30;
                color: {t['accent']};
                border: 1px solid {t['accent']}60;
                border-radius: 10px;
                font-size: 13px;
                padding: 0 16px;
            }}
            QPushButton:hover {{ background: {t['accent']}; color: white; }}
        """)

        for btn in self.nav_buttons:
            btn.theme = t
            btn._apply_style()

        # Input card styling
        self.input_card.setStyleSheet(f"""
            QFrame {{
                background: {t['bg_card']};
                border-radius: 16px;
                border: 1px solid {t['border']};
            }}
        """)

        # Labels
        for lbl in self.findChildren(QLabel):
            if lbl.objectName() not in ('emoji_label',):
                if lbl.styleSheet() == "" or "color:" not in lbl.styleSheet():
                    lbl.setStyleSheet(f"color: {t['text_primary']};")

        # TextEdit / LineEdit
        input_style = f"""
            QTextEdit, QLineEdit {{
                background: {t['input_bg']};
                color: {t['text_primary']};
                border: 1.5px solid {t['border']};
                border-radius: 10px;
                padding: 8px 12px;
                selection-background-color: {t['accent']};
            }}
            QTextEdit:focus, QLineEdit:focus {{
                border-color: {t['accent']};
            }}
        """
        self.setStyleSheet(self.styleSheet() + input_style)

        # Buttons
        primary_btn_style = f"""
            QPushButton {{
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                    stop:0 {t['accent']}, stop:1 {t['accent_hover']});
                color: white;
                border: none;
                border-radius: 10px;
                font-size: 13px;
                font-weight: bold;
                padding: 0 20px;
            }}
            QPushButton:hover {{
                background: {t['accent_hover']};
            }}
            QPushButton:pressed {{
                background: {t['accent']};
            }}
        """
        self.analyze_btn.setStyleSheet(primary_btn_style)

        secondary_style = f"""
            QPushButton {{
                background: {t['bg_card']};
                color: {t['text_primary']};
                border: 1.5px solid {t['border']};
                border-radius: 10px;
                font-size: 12px;
                padding: 0 16px;
            }}
            QPushButton:hover {{
                border-color: {t['accent']};
                color: {t['accent']};
            }}
        """
        self.voice_btn.setStyleSheet(secondary_style)
        self.clear_btn.setStyleSheet(secondary_style)

        # Table
        self.history_table.setStyleSheet(f"""
            QTableWidget {{
                background: {t['bg_card']};
                color: {t['text_primary']};
                border: 1px solid {t['border']};
                border-radius: 12px;
                gridline-color: {t['border']};
                font-size: 12px;
            }}
            QHeaderView::section {{
                background: {t['bg_secondary']};
                color: {t['text_secondary']};
                border: none;
                border-bottom: 2px solid {t['border']};
                padding: 8px;
                font-weight: bold;
            }}
            QTableWidget::item:selected {{
                background: {t['accent']}30;
                color: {t['text_primary']};
            }}
            QTableWidget::item:alternate {{
                background: {t['bg_primary']};
            }}
        """)

        self.search_bar.setStyleSheet(f"""
            QLineEdit {{
                background: {t['input_bg']};
                color: {t['text_primary']};
                border: 1.5px solid {t['border']};
                border-radius: 10px;
                padding: 8px 14px;
                font-size: 12px;
            }}
        """)

        # Chat
        self.chat_scroll.setStyleSheet(f"background: {t['bg_primary']};")
        self.chat_container.setStyleSheet(f"background: {t['bg_primary']};")
        self.chat_input.setStyleSheet(f"""
            QLineEdit {{
                background: {t['input_bg']};
                color: {t['text_primary']};
                border: 1.5px solid {t['border']};
                border-radius: 12px;
                padding: 0 16px;
                font-size: 13px;
            }}
            QLineEdit:focus {{ border-color: {t['accent']}; }}
        """)

        self.home_date.setStyleSheet(f"color: {t['text_secondary']};")
        self.result_card.theme = t

        if not hasattr(self, '_trend_html'):
            pass
        else:
            self._render_chart(self._trend_html)

    def _toggle_theme(self):
        self.dark_mode = not self.dark_mode
        self.theme = DARK_THEME if self.dark_mode else LIGHT_THEME
        self.theme_btn.setText("🌙  Dark Mode" if not self.dark_mode else "☀️  Light Mode")
        self._apply_theme()

    # ── Navigation ────────────────────────────────────────────────────────────

    def _switch_page(self, idx):
        for i, btn in enumerate(self.nav_buttons):
            btn.set_active(i == idx)
        self.stack.setCurrentIndex(idx)
        if idx == 1:
            self._load_history()
        if idx == 0:
            self._load_trends()

    # ── Analyze ───────────────────────────────────────────────────────────────

    def _do_analyze(self):
        text = self.text_input.toPlainText().strip()
        if not text:
            self._flash_error("Please write something about how you're feeling.")
            return

        self.analyze_btn.setText("⏳  Analyzing…")
        self.analyze_btn.setEnabled(False)

        self.analyze_worker = AnalyzeWorker(text)
        self.analyze_worker.result.connect(self._on_analyze_done)
        self.analyze_worker.error.connect(self._on_analyze_error)
        self.analyze_worker.start()

    def _on_analyze_done(self, data):
        self.last_result = data
        self.result_card.update_result(data)
        self.analyze_btn.setText("🔍  Analyze Mood")
        self.analyze_btn.setEnabled(True)
        # Refresh trends after a short delay
        QTimer.singleShot(1500, self._load_trends)

    def _on_analyze_error(self, err):
        self.analyze_btn.setText("🔍  Analyze Mood")
        self.analyze_btn.setEnabled(True)
        QMessageBox.critical(self, "Backend Error",
            f"Could not connect to the backend.\n\nMake sure backend.py is running.\n\n{err}")

    # ── Voice ─────────────────────────────────────────────────────────────────

    def _start_voice(self):
        if not SPEECH_AVAILABLE:
            QMessageBox.information(self, "Voice Input",
                "Install speech recognition:\n\npip install SpeechRecognition pyaudio")
            return
        self.voice_btn.setText("🎤  Listening…")
        self.voice_btn.setEnabled(False)
        self.voice_worker = VoiceWorker()
        self.voice_worker.result.connect(self._on_voice_done)
        self.voice_worker.error.connect(self._on_voice_error)
        self.voice_worker.start()

    def _on_voice_done(self, text):
        self.text_input.setPlainText(text)
        self.voice_btn.setText("🎤  Voice Input")
        self.voice_btn.setEnabled(True)

    def _on_voice_error(self, err):
        self.voice_btn.setText("🎤  Voice Input")
        self.voice_btn.setEnabled(True)
        QMessageBox.warning(self, "Voice Error", err)

    # ── Trends chart ──────────────────────────────────────────────────────────

    def _load_trends(self):
        self.trends_worker = TrendsWorker()
        self.trends_worker.result.connect(self._on_trends_done)
        self.trends_worker.error.connect(lambda e: self._show_empty_chart())
        self.trends_worker.start()

    def _on_trends_done(self, data):
        self._render_plotly_chart(data)

    def _render_plotly_chart(self, data):
        daily = data.get('daily', [])
        emotions = data.get('emotions', list(EMOTION_COLORS.keys()))
        colors_map = data.get('colors', EMOTION_COLORS)
        total = data.get('total_entries', 0)
        most_common = data.get('most_common_emotion', 'N/A')
        avg_risk = data.get('avg_risk_score', 0)

        bg     = self.theme['bg_card']
        fg     = self.theme['text_primary']
        grid   = self.theme['border']
        accent = self.theme['accent']

        dates = [d['date'][-5:] for d in daily]  # MM-DD

        traces = []
        for em in emotions:
            vals = [d.get(em, 0) for d in daily]
            if sum(vals) == 0:
                continue
            color = colors_map.get(em, '#7F8C8D')
            traces.append(f"""{{
                x: {json.dumps(dates)},
                y: {json.dumps(vals)},
                name: '{em.capitalize()}',
                type: 'scatter',
                mode: 'lines+markers',
                line: {{ color: '{color}', width: 2.5, shape: 'spline' }},
                marker: {{ size: 7, color: '{color}' }},
                fill: 'tozeroy',
                fillcolor: '{color}22'
            }}""")

        traces_js = "[" + ",".join(traces) + "]" if traces else "[]"

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ background:{bg}; font-family:'Segoe UI',sans-serif; }}
  .stats {{ display:flex; gap:16px; padding:16px 20px 4px; }}
  .stat-card {{
    flex:1; background:{self.theme['bg_secondary']};
    border:1px solid {grid}; border-radius:12px;
    padding:12px 16px; text-align:center;
  }}
  .stat-val {{ font-size:22px; font-weight:700; color:{accent}; }}
  .stat-lbl {{ font-size:11px; color:{self.theme['text_secondary']}; margin-top:2px; }}
  #chart {{ width:100%; height:200px; }}
</style>
</head>
<body>
<div class="stats">
  <div class="stat-card">
    <div class="stat-val">{total}</div>
    <div class="stat-lbl">Total Entries</div>
  </div>
  <div class="stat-card">
    <div class="stat-val" style="font-size:16px;text-transform:capitalize">{most_common}</div>
    <div class="stat-lbl">Most Common Emotion</div>
  </div>
  <div class="stat-card">
    <div class="stat-val">{avg_risk:.0f}</div>
    <div class="stat-lbl">Avg Risk Score</div>
  </div>
</div>
<div id="chart"></div>
<script>
var traces = {traces_js};
var layout = {{
  margin: {{t:10, r:20, b:40, l:40}},
  paper_bgcolor: '{bg}',
  plot_bgcolor: '{bg}',
  font: {{ color: '{fg}', size: 11, family: 'Segoe UI' }},
  xaxis: {{
    gridcolor: '{grid}', tickcolor: '{fg}',
    zeroline: false, showline: false
  }},
  yaxis: {{
    gridcolor: '{grid}', tickcolor: '{fg}',
    zeroline: false, title: 'Count', dtick: 1
  }},
  legend: {{
    orientation: 'h', x: 0, y: -0.25,
    font: {{ size: 10 }}, bgcolor: 'transparent'
  }},
  hovermode: 'x unified'
}};
Plotly.newPlot('chart', traces, layout, {{
  responsive: true, displayModeBar: false
}});
</script>
</body>
</html>"""
        self.webview.setHtml(html)

    def _show_empty_chart(self):
        bg = self.theme['bg_card']
        fg = self.theme['text_secondary']
        html = f"""<html><body style='background:{bg};display:flex;
        align-items:center;justify-content:center;height:200px;
        font-family:Segoe UI;color:{fg};font-size:14px'>
        📊 No data yet — analyze your first mood to see trends!
        </body></html>"""
        self.webview.setHtml(html)

    # ── History ───────────────────────────────────────────────────────────────

    def _load_history(self):
        worker = HistoryWorker()
        worker.result.connect(self._on_history_done)
        worker.error.connect(lambda e: None)
        worker.start()
        self._history_worker = worker

    def _on_history_done(self, data):
        self._history_data = data
        self._populate_table(data)

    def _populate_table(self, data):
        t = self.theme
        self.history_table.setRowCount(0)
        for row_data in data:
            row = self.history_table.rowCount()
            self.history_table.insertRow(row)

            color = row_data.get('color', '#7F8C8D')
            items = [
                row_data.get('time', ''),
                row_data.get('emotion', '').capitalize(),
                row_data.get('confidence', ''),
                row_data.get('risk_level', ''),
                row_data.get('suggestion', ''),
                row_data.get('text', ''),
            ]
            for col, val in enumerate(items):
                item = QTableWidgetItem(str(val))
                item.setTextAlignment(Qt.AlignVCenter | Qt.AlignLeft)
                if col == 1:  # emotion cell colored
                    item.setForeground(QColor(color))
                    item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                if col == 3:  # risk badge
                    risk_colors = {"HIGH": "#EF4444", "MEDIUM": "#F59E0B", "LOW": "#10B981"}
                    item.setForeground(QColor(risk_colors.get(val, '#10B981')))
                    item.setFont(QFont("Segoe UI", 10, QFont.Bold))
                self.history_table.setItem(row, col, item)
        self.history_table.resizeRowsToContents()

    def _filter_history(self, query):
        q = query.lower()
        filtered = [
            r for r in self._history_data
            if q in r.get('text', '').lower()
            or q in r.get('emotion', '').lower()
            or q in r.get('time', '').lower()
            or q in r.get('suggestion', '').lower()
        ]
        self._populate_table(filtered)

    # ── Chat ─────────────────────────────────────────────────────────────────

    def _send_chat(self):
        msg = self.chat_input.text().strip()
        if not msg:
            return
        self.chat_input.clear()
        self._add_user_message(msg)
        self.chat_history.append({"role": "user", "content": msg})

        worker = ChatWorker(msg, self.chat_history[-10:])
        worker.result.connect(self._on_chat_reply)
        worker.error.connect(lambda e: self._add_bot_message("I'm having trouble connecting. Please check if the backend is running. 💙"))
        worker.start()
        self._chat_worker = worker

    def _on_chat_reply(self, reply):
        self._add_bot_message(reply)
        self.chat_history.append({"role": "assistant", "content": reply})

    def _add_user_message(self, text):
        bubble = ChatBubble(text, "user", self.theme)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_chat)

    def _add_bot_message(self, text):
        bubble = ChatBubble(text, "bot", self.theme)
        self.chat_layout.insertWidget(self.chat_layout.count() - 1, bubble)
        QTimer.singleShot(50, self._scroll_chat)

    def _scroll_chat(self):
        sb = self.chat_scroll.verticalScrollBar()
        sb.setValue(sb.maximum())

    def _clear_chat(self):
        self.chat_history = []
        for i in reversed(range(self.chat_layout.count() - 1)):
            item = self.chat_layout.itemAt(i)
            if item and item.widget():
                item.widget().deleteLater()
        self._add_bot_message("Chat cleared! I'm still here for you. 💙 What's on your mind?")

    # ── PDF export ────────────────────────────────────────────────────────────

    def _export_pdf(self):
        save_path, _ = QFileDialog.getSaveFileName(
            self, "Save Mood Report", "mood_report.pdf", "PDF Files (*.pdf)"
        )
        if not save_path:
            return
        try:
            r = requests.get(f"{BACKEND}/export_pdf", timeout=20, stream=True)
            with open(save_path, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            QMessageBox.information(self, "Export Complete",
                f"✅ PDF report saved to:\n{save_path}")
        except Exception as e:
            QMessageBox.critical(self, "Export Error",
                f"Failed to export PDF.\n\nMake sure the backend is running.\n\n{e}")

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _flash_error(self, msg):
        QMessageBox.warning(self, "Oops!", msg)


# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("Mental Health AI")
    app.setStyle("Fusion")

    # Enable High DPI
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    window = MentalHealthApp()
    window.show()
    sys.exit(app.exec_())