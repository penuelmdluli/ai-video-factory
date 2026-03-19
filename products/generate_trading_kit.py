"""
AI Trading Starter Kit - PDF Generator
Generates a professional 15-20 page digital product PDF.
Product price: $27 | By Beast Mode Academy | gettraderadar.com
"""

import os
import sys

# Ensure reportlab is available
try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch, mm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, KeepTogether, HRFlowable, ListFlowable, ListItem,
    )
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.pdfgen import canvas
except ImportError:
    print("Installing reportlab...")
    os.system(f"{sys.executable} -m pip install reportlab")
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.units import inch, mm
    from reportlab.lib.colors import HexColor, white, black
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_LEFT, TA_CENTER, TA_RIGHT, TA_JUSTIFY
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        PageBreak, KeepTogether, HRFlowable, ListFlowable, ListItem,
    )
    from reportlab.graphics.shapes import Drawing, Rect, String, Line
    from reportlab.pdfgen import canvas

# ---------------------------------------------------------------------------
# Color palette
# ---------------------------------------------------------------------------
NAVY = HexColor("#0F172A")
DARK_NAVY = HexColor("#020617")
GOLD = HexColor("#F59E0B")
LIGHT_GOLD = HexColor("#FDE68A")
SLATE = HexColor("#334155")
LIGHT_SLATE = HexColor("#94A3B8")
NEAR_WHITE = HexColor("#F8FAFC")
MEDIUM_BG = HexColor("#1E293B")
ACCENT_GREEN = HexColor("#10B981")
ACCENT_RED = HexColor("#EF4444")
LINK_BLUE = HexColor("#38BDF8")

PAGE_W, PAGE_H = letter  # 612 x 792
MARGIN = 54  # 0.75 inch


# ---------------------------------------------------------------------------
# Page number + footer callback
# ---------------------------------------------------------------------------
class FooterCanvas(canvas.Canvas):
    """Custom canvas that draws page numbers and a thin gold line in the footer."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_pages = []

    def showPage(self):
        self._saved_pages.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved_pages)
        for idx, state in enumerate(self._saved_pages):
            self.__dict__.update(state)
            if idx > 0:  # skip cover page
                self._draw_footer(idx + 1, total)
            super().showPage()
        super().save()

    def _draw_footer(self, page_num, total):
        self.saveState()
        # Gold accent line
        self.setStrokeColor(GOLD)
        self.setLineWidth(0.5)
        self.line(MARGIN, 36, PAGE_W - MARGIN, 36)
        # Page number
        self.setFont("Helvetica", 8)
        self.setFillColor(LIGHT_SLATE)
        self.drawCentredString(PAGE_W / 2, 22, f"Page {page_num} of {total}")
        # Brand
        self.setFont("Helvetica-Oblique", 7)
        self.drawString(MARGIN, 22, "Beast Mode Academy")
        self.drawRightString(PAGE_W - MARGIN, 22, "gettraderadar.com")
        self.restoreState()


# ---------------------------------------------------------------------------
# Reusable styles
# ---------------------------------------------------------------------------
def build_styles():
    ss = getSampleStyleSheet()

    styles = {
        "body": ParagraphStyle(
            "body", parent=ss["Normal"],
            fontName="Helvetica", fontSize=10.5, leading=16,
            textColor=SLATE, alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "body_white": ParagraphStyle(
            "body_white", parent=ss["Normal"],
            fontName="Helvetica", fontSize=10.5, leading=16,
            textColor=NEAR_WHITE, alignment=TA_JUSTIFY,
            spaceAfter=8,
        ),
        "h1": ParagraphStyle(
            "h1", fontName="Helvetica-Bold", fontSize=22, leading=28,
            textColor=NAVY, spaceAfter=12, spaceBefore=4,
        ),
        "h2": ParagraphStyle(
            "h2", fontName="Helvetica-Bold", fontSize=15, leading=20,
            textColor=NAVY, spaceAfter=8, spaceBefore=16,
        ),
        "h3": ParagraphStyle(
            "h3", fontName="Helvetica-Bold", fontSize=12, leading=16,
            textColor=GOLD, spaceAfter=6, spaceBefore=12,
        ),
        "bullet": ParagraphStyle(
            "bullet", fontName="Helvetica", fontSize=10.5, leading=15,
            textColor=SLATE, leftIndent=24, bulletIndent=12,
            spaceAfter=4,
        ),
        "number_item": ParagraphStyle(
            "number_item", fontName="Helvetica", fontSize=10.5, leading=15,
            textColor=SLATE, leftIndent=24, bulletIndent=12,
            spaceAfter=4,
        ),
        "tip_box": ParagraphStyle(
            "tip_box", fontName="Helvetica-Oblique", fontSize=10, leading=14,
            textColor=NAVY, leftIndent=14, rightIndent=14,
            spaceBefore=6, spaceAfter=6,
        ),
        "strategy_title": ParagraphStyle(
            "strategy_title", fontName="Helvetica-Bold", fontSize=13, leading=18,
            textColor=white, spaceAfter=4, spaceBefore=2,
        ),
        "strategy_body": ParagraphStyle(
            "strategy_body", fontName="Helvetica", fontSize=10, leading=14,
            textColor=NEAR_WHITE, spaceAfter=4,
        ),
        "center": ParagraphStyle(
            "center", fontName="Helvetica", fontSize=10.5, leading=15,
            textColor=SLATE, alignment=TA_CENTER,
        ),
        "disclaimer": ParagraphStyle(
            "disclaimer", fontName="Helvetica", fontSize=8, leading=11,
            textColor=LIGHT_SLATE, alignment=TA_JUSTIFY,
            spaceBefore=8,
        ),
        "cover_title": ParagraphStyle(
            "cover_title", fontName="Helvetica-Bold", fontSize=38, leading=46,
            textColor=white, alignment=TA_CENTER,
        ),
        "cover_subtitle": ParagraphStyle(
            "cover_subtitle", fontName="Helvetica", fontSize=16, leading=22,
            textColor=LIGHT_GOLD, alignment=TA_CENTER,
        ),
        "cover_author": ParagraphStyle(
            "cover_author", fontName="Helvetica-Bold", fontSize=14, leading=20,
            textColor=GOLD, alignment=TA_CENTER,
        ),
        "cover_url": ParagraphStyle(
            "cover_url", fontName="Helvetica", fontSize=12, leading=18,
            textColor=LIGHT_SLATE, alignment=TA_CENTER,
        ),
        "toc_item": ParagraphStyle(
            "toc_item", fontName="Helvetica", fontSize=11, leading=22,
            textColor=SLATE, leftIndent=20,
        ),
        "toc_chapter": ParagraphStyle(
            "toc_chapter", fontName="Helvetica-Bold", fontSize=12, leading=24,
            textColor=NAVY,
        ),
    }
    return styles


# ---------------------------------------------------------------------------
# Helper flowables
# ---------------------------------------------------------------------------
def gold_hr():
    return HRFlowable(
        width="100%", thickness=1.5, color=GOLD,
        spaceBefore=6, spaceAfter=10,
    )


def navy_header_bar(text, styles):
    """Full-width dark navy bar with gold text (used for chapter headers)."""
    tbl = Table(
        [[Paragraph(text, styles["strategy_title"])]],
        colWidths=[PAGE_W - 2 * MARGIN],
        rowHeights=[36],
    )
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, -1), white),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return tbl


def tip_box(text, styles, icon="PRO TIP"):
    """Gold-bordered tip/callout box."""
    inner = Paragraph(f"<b>{icon}:</b> {text}", styles["tip_box"])
    tbl = Table([[inner]], colWidths=[PAGE_W - 2 * MARGIN - 28])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FFFBEB")),
        ("BOX", (0, 0), (-1, -1), 1.5, GOLD),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return tbl


def warning_box(text, styles):
    inner = Paragraph(f"<b>WARNING:</b> {text}", styles["tip_box"])
    tbl = Table([[inner]], colWidths=[PAGE_W - 2 * MARGIN - 28])
    tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#FEF2F2")),
        ("BOX", (0, 0), (-1, -1), 1.5, ACCENT_RED),
        ("LEFTPADDING", (0, 0), (-1, -1), 12),
        ("RIGHTPADDING", (0, 0), (-1, -1), 12),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("ROUNDEDCORNERS", [4, 4, 4, 4]),
    ]))
    return tbl


def strategy_card(title, description, when, entry, exit_rule, risk, styles):
    """Dark card for each strategy."""
    elements = []
    elements.append(Paragraph(title, styles["strategy_title"]))
    elements.append(Paragraph(description, styles["strategy_body"]))
    elements.append(Spacer(1, 4))
    elements.append(Paragraph(f"<b>When to use:</b> {when}", styles["strategy_body"]))
    elements.append(Paragraph(f"<b>Entry rule:</b> {entry}", styles["strategy_body"]))
    elements.append(Paragraph(f"<b>Exit rule:</b> {exit_rule}", styles["strategy_body"]))
    risk_color = {"Low": "#10B981", "Medium": "#F59E0B", "High": "#EF4444"}.get(risk, "#F59E0B")
    elements.append(Paragraph(
        f'<b>Risk level:</b> <font color="{risk_color}">{risk}</font>',
        styles["strategy_body"],
    ))

    inner_tbl = Table([[e] for e in elements], colWidths=[PAGE_W - 2 * MARGIN - 28])
    inner_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), MEDIUM_BG),
        ("LEFTPADDING", (0, 0), (-1, -1), 14),
        ("RIGHTPADDING", (0, 0), (-1, -1), 14),
        ("TOPPADDING", (0, 0), (0, 0), 12),
        ("BOTTOMPADDING", (-1, -1), (-1, -1), 12),
        ("ROUNDEDCORNERS", [6, 6, 6, 6]),
    ]))
    return inner_tbl


def bullet_list(items, styles):
    """Return a list of bullet-point paragraphs."""
    return [
        Paragraph(f"\u2022  {item}", styles["bullet"])
        for item in items
    ]


def numbered_list(items, styles):
    return [
        Paragraph(f"<b>{i+1}.</b>  {item}", styles["number_item"])
        for i, item in enumerate(items)
    ]


# ---------------------------------------------------------------------------
# Cover page (drawn directly on canvas via onFirstPage)
# ---------------------------------------------------------------------------
def draw_cover(c, doc):
    w, h = PAGE_W, PAGE_H
    # Full navy background
    c.setFillColor(DARK_NAVY)
    c.rect(0, 0, w, h, fill=1, stroke=0)

    # Gold accent bar at top
    c.setFillColor(GOLD)
    c.rect(0, h - 8, w, 8, fill=1, stroke=0)

    # Decorative gold lines
    c.setStrokeColor(GOLD)
    c.setLineWidth(0.5)
    c.line(MARGIN + 40, h - 180, w - MARGIN - 40, h - 180)
    c.line(MARGIN + 40, h - 470, w - MARGIN - 40, h - 470)

    # Gold border rectangle
    c.setStrokeColor(GOLD)
    c.setLineWidth(2)
    c.roundRect(MARGIN - 10, 60, w - 2 * MARGIN + 20, h - 130, 8, fill=0, stroke=1)

    # Title
    c.setFillColor(white)
    c.setFont("Helvetica-Bold", 42)
    c.drawCentredString(w / 2, h - 240, "AI TRADING")
    c.drawCentredString(w / 2, h - 290, "STARTER KIT")

    # Subtitle
    c.setFillColor(LIGHT_GOLD)
    c.setFont("Helvetica", 17)
    c.drawCentredString(w / 2, h - 340, "Your Complete Guide to AI-Powered Trading")

    # Decorative diamond
    c.setFillColor(GOLD)
    cx, cy = w / 2, h - 380
    c.saveState()
    c.translate(cx, cy)
    c.rotate(45)
    c.rect(-5, -5, 10, 10, fill=1, stroke=0)
    c.restoreState()

    # Author
    c.setFillColor(GOLD)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(w / 2, h - 430, "By Beast Mode Academy")

    # URL
    c.setFillColor(LIGHT_SLATE)
    c.setFont("Helvetica", 13)
    c.drawCentredString(w / 2, h - 460, "gettraderadar.com")

    # Bottom tagline
    c.setFillColor(HexColor("#64748B"))
    c.setFont("Helvetica-Oblique", 10)
    c.drawCentredString(w / 2, 100,
                        "Master the Markets with Artificial Intelligence")

    # Version / year
    c.setFillColor(HexColor("#475569"))
    c.setFont("Helvetica", 9)
    c.drawCentredString(w / 2, 78, "2026 Edition  |  Version 1.0")


# ---------------------------------------------------------------------------
# Build the document content
# ---------------------------------------------------------------------------
def build_content(styles):
    S = styles
    story = []

    # Cover page placeholder (actual cover drawn via onFirstPage)
    story.append(Spacer(1, 1))
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # TABLE OF CONTENTS
    # -----------------------------------------------------------------------
    story.append(navy_header_bar("TABLE OF CONTENTS", S))
    story.append(Spacer(1, 16))

    toc_items = [
        ("Chapter 1", "Introduction to AI Trading", "4"),
        ("Chapter 2", "Setting Up Your Trading Environment", "6"),
        ("Chapter 3", "Top 5 AI Trading Strategies", "9"),
        ("Chapter 4", "Reading AI Signals", "13"),
        ("Chapter 5", "Risk Management Framework", "15"),
        ("Chapter 6", "Your First 30 Days Plan", "17"),
        ("Chapter 7", "Advanced Resources", "19"),
    ]

    toc_data = []
    for ch, title, pg in toc_items:
        toc_data.append([
            Paragraph(f"<b>{ch}:</b>", S["toc_chapter"]),
            Paragraph(title, S["toc_item"]),
            Paragraph(pg, ParagraphStyle("pg", fontName="Helvetica", fontSize=11,
                                          textColor=GOLD, alignment=TA_RIGHT)),
        ])

    toc_tbl = Table(toc_data, colWidths=[90, 340, 50])
    toc_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
        ("LINEBELOW", (0, 0), (-1, -2), 0.5, HexColor("#E2E8F0")),
    ]))
    story.append(toc_tbl)
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # CHAPTER 1: Introduction to AI Trading
    # -----------------------------------------------------------------------
    story.append(navy_header_bar("CHAPTER 1: INTRODUCTION TO AI TRADING", S))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Artificial Intelligence is transforming how traders analyze markets, execute trades, "
        "and manage risk. What was once available only to Wall Street hedge funds is now "
        "accessible to individual traders who understand how to leverage these powerful tools.",
        S["body"],
    ))
    story.append(Spacer(1, 6))

    story.append(Paragraph("<b>What Is AI Trading?</b>", S["h2"]))
    story.append(Paragraph(
        "AI trading uses machine learning algorithms and data analysis to identify trading "
        "opportunities, predict price movements, and automate trade execution. These systems "
        "process thousands of data points per second, including price data, volume, news sentiment, "
        "social media trends, and macroeconomic indicators, to generate actionable trading signals.",
        S["body"],
    ))

    story.append(Paragraph("<b>Why AI Trading Works</b>", S["h2"]))
    story.append(Paragraph(
        "Human traders are emotional. Fear and greed drive 90% of retail trading losses. "
        "AI systems eliminate emotional bias and trade purely on data-driven logic. Here is "
        "why AI gives you an edge:",
        S["body"],
    ))

    story.extend(bullet_list([
        "<b>Speed:</b> AI processes market data in milliseconds, reacting to opportunities "
        "before human traders can even read a chart.",
        "<b>Consistency:</b> Algorithms follow rules without exception. No revenge trading, "
        "no FOMO, no panic selling.",
        "<b>Pattern recognition:</b> Machine learning models identify subtle chart patterns "
        "and correlations invisible to the human eye.",
        "<b>24/7 monitoring:</b> AI never sleeps. Crypto markets run around the clock, "
        "and AI captures opportunities at any hour.",
        "<b>Backtesting:</b> Every strategy can be tested against years of historical data "
        "before risking real capital.",
    ], S))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>The 3 Pillars of Successful AI Trading</b>", S["h2"]))
    story.append(Paragraph(
        "Every profitable AI trader builds their approach on three foundational pillars:",
        S["body"],
    ))

    pillar_data = [
        ["Pillar", "Description", "Key Action"],
        ["DATA", "Quality data feeds, clean historical\ndata, real-time market streams",
         "Subscribe to reliable data\nproviders and APIs"],
        ["STRATEGY", "Backtested, rules-based systems\nwith clear entry/exit criteria",
         "Paper trade every strategy\nfor 30+ days first"],
        ["DISCIPLINE", "Strict risk management, no\noverrides, trust the system",
         "Set max daily loss limits\nand walk away when hit"],
    ]
    ptbl = Table(pillar_data, colWidths=[80, 210, 190])
    ptbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("BACKGROUND", (0, 1), (-1, -1), HexColor("#F1F5F9")),
        ("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
        ("ALIGN", (0, 0), (-1, -1), "LEFT"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (0, -1), NAVY),
    ]))
    story.append(ptbl)
    story.append(Spacer(1, 10))

    story.append(tip_box(
        "The biggest mistake new AI traders make is skipping the discipline pillar. "
        "A mediocre strategy with great risk management will always outperform a great "
        "strategy with no risk management.", S
    ))
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # CHAPTER 2: Setting Up Your Trading Environment
    # -----------------------------------------------------------------------
    story.append(navy_header_bar("CHAPTER 2: SETTING UP YOUR TRADING ENVIRONMENT", S))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Before you place your first AI-assisted trade, you need the right infrastructure. "
        "This chapter walks you through selecting platforms, essential tools, and configuring "
        "your environment for success.",
        S["body"],
    ))

    story.append(Paragraph("<b>Recommended Platforms</b>", S["h2"]))

    platforms = [
        ["Platform", "Best For", "Key Features"],
        ["Binance", "Crypto trading, spot\nand futures", "Low fees, API access, wide\nasset selection, staking"],
        ["TradingView", "Charting and analysis\nacross all markets", "Pine Script alerts, community\nstrategies, multi-timeframe"],
        ["MetaTrader 4/5", "Forex and CFDs,\nalgo trading", "Expert Advisors (EAs), free\nindicators, mobile support"],
        ["Interactive Brokers", "Stocks, options,\nmulti-asset", "Professional tools, API,\nglobal markets access"],
        ["Bybit", "Crypto derivatives\nand perps", "Copy trading, bot marketplace,\ncompetitive funding rates"],
    ]
    ptbl2 = Table(platforms, colWidths=[110, 155, 215])
    ptbl2.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("BACKGROUND", (0, 1), (-1, -1), NEAR_WHITE),
        ("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 1), (0, -1), NAVY),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    story.append(ptbl2)
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Essential Tools Checklist</b>", S["h2"]))
    story.extend(bullet_list([
        "<b>Charting platform</b> (TradingView recommended) with real-time data feeds",
        "<b>Trading journal</b> to log every trade with entry/exit reasons and emotions",
        "<b>Economic calendar</b> (ForexFactory, Investing.com) to avoid news-driven volatility",
        "<b>Signal dashboard</b> to monitor your AI-generated alerts in one place",
        "<b>Risk calculator</b> spreadsheet or app for position sizing",
        "<b>VPN service</b> for secure connection when trading on public networks",
        "<b>Two-factor authentication (2FA)</b> on every exchange and platform",
        "<b>Dedicated trading device</b> to keep your setup distraction-free",
    ], S))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Account Setup: Step by Step</b>", S["h2"]))
    story.extend(numbered_list([
        "<b>Choose your primary exchange</b> based on the assets you want to trade. "
        "For crypto: Binance or Bybit. For forex: a regulated MT4/MT5 broker.",
        "<b>Complete KYC verification</b> immediately. This unlocks higher withdrawal limits "
        "and full feature access. Have your ID and proof of address ready.",
        "<b>Enable all security features:</b> 2FA (Google Authenticator, not SMS), "
        "anti-phishing code, withdrawal whitelist, and email confirmation for transactions.",
        "<b>Fund with a small test amount</b> first (e.g., $50-$100) to verify deposits "
        "and withdrawals work correctly before committing larger capital.",
        "<b>Connect your charting tools</b> via API keys. Generate read-only API keys first "
        "to test connectivity. Only enable trading permissions when you are ready.",
        "<b>Set up your trading journal</b> from day one. Record every trade: date, asset, "
        "direction, entry, exit, P&L, and the reason for the trade.",
    ], S))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Risk Management Basics</b>", S["h2"]))
    story.append(Paragraph(
        "Before taking any trade, you must define your risk parameters. "
        "These are non-negotiable rules that protect your capital:",
        S["body"],
    ))

    story.append(warning_box(
        "Never risk more than 1-2% of your total account on a single trade. "
        "If your account is $1,000, your maximum loss per trade should be $10-$20. "
        "This is the single most important rule in trading.", S
    ))

    story.extend(bullet_list([
        "<b>Maximum daily loss:</b> 5% of account. If you hit this, stop trading for the day.",
        "<b>Maximum weekly loss:</b> 10% of account. Reassess your strategy if reached.",
        "<b>Always use stop-losses.</b> No exceptions. Ever.",
        "<b>Risk-reward ratio:</b> Only take trades with at least 1:2 risk-to-reward.",
    ], S))
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # CHAPTER 3: Top 5 AI Trading Strategies
    # -----------------------------------------------------------------------
    story.append(navy_header_bar("CHAPTER 3: TOP 5 AI TRADING STRATEGIES", S))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "These five strategies form the core of AI-assisted trading. Each has been "
        "backtested across multiple market conditions and asset classes. Start with "
        "Strategy 1 (simplest) and progress as your experience grows.",
        S["body"],
    ))
    story.append(Spacer(1, 8))

    # Strategy 1
    story.append(strategy_card(
        "STRATEGY 1: Moving Average Crossover with AI Confirmation",
        "The classic golden cross / death cross system, enhanced with AI-powered trend "
        "confirmation. The AI layer filters out false crossovers by analyzing volume, "
        "momentum, and multi-timeframe alignment before generating a signal.",
        "Trending markets (crypto, forex, stocks). Avoid during choppy, range-bound conditions.",
        "Fast MA (9 EMA) crosses above slow MA (21 EMA) AND the AI confidence score "
        "is above 70% AND the price is above the 200 EMA on the daily chart.",
        "Fast MA crosses below slow MA, OR take profit at 2x your risk, OR trail your "
        "stop-loss using the 21 EMA as dynamic support.",
        "Low",
        S,
    ))
    story.append(Spacer(1, 10))

    # Strategy 2
    story.append(strategy_card(
        "STRATEGY 2: RSI Divergence Scanner",
        "Uses AI to scan for bullish and bearish divergences between price and the Relative "
        "Strength Index (RSI). Divergences signal potential reversals before they happen. "
        "The AI model detects subtle divergences that manual traders frequently miss.",
        "Reversal setups at key support/resistance levels. Works on all timeframes.",
        "AI detects bullish divergence (price makes lower low, RSI makes higher low) at a "
        "key support zone. Enter on the next bullish candle close with confirmation.",
        "Stop-loss below the swing low. Take profit at the next resistance level "
        "or when RSI reaches overbought territory (above 70).",
        "Medium",
        S,
    ))
    story.append(Spacer(1, 10))

    # Strategy 3
    story.append(strategy_card(
        "STRATEGY 3: Volume Profile Analysis",
        "AI analyzes volume distribution at different price levels to identify high-value "
        "areas (high volume nodes) and low-value gaps. Trades are entered at volume-confirmed "
        "support/resistance levels where institutional players are active.",
        "Range-bound and breakout markets. Particularly effective on higher timeframes (4H, Daily).",
        "Price pulls back to the Point of Control (POC) or Value Area Low (VAL) with "
        "AI confirmation of accumulation patterns. Volume must be increasing on the bounce.",
        "Price reaches the Value Area High (VAH) or the next high-volume node above. "
        "Partial take-profit at 1:1 risk-reward, move stop to breakeven.",
        "Low",
        S,
    ))
    story.append(PageBreak())

    # Strategy 4
    story.append(strategy_card(
        "STRATEGY 4: Sentiment-Based Trading (News + Social)",
        "AI monitors news feeds, social media (X/Twitter, Reddit, Telegram), and on-chain data "
        "to gauge market sentiment in real time. Extreme fear often signals buying opportunities; "
        "extreme greed signals potential tops. The AI aggregates sentiment scores across sources.",
        "High-volatility events: earnings reports, regulatory news, project announcements. "
        "Especially powerful in crypto markets where sentiment shifts rapidly.",
        "Sentiment score drops below 20 (extreme fear) while price holds a key support level. "
        "AI confirms institutional accumulation on-chain. Enter with a tight stop.",
        "Sentiment score reaches 80+ (extreme greed) or price hits a major resistance level. "
        "Scale out in thirds: 1/3 at 1:1, 1/3 at 1:2, trail the remaining 1/3.",
        "High",
        S,
    ))
    story.append(Spacer(1, 10))

    # Strategy 5
    story.append(strategy_card(
        "STRATEGY 5: Multi-Timeframe AI Signals",
        "The most comprehensive strategy. AI analyzes alignment across three timeframes "
        "(e.g., Daily, 4H, 1H) to confirm trade direction. Trades are only taken when all "
        "three timeframes agree on trend direction and the AI confidence is above 80%.",
        "All market conditions. This strategy acts as a master filter, and it is the most "
        "reliable but generates fewer signals (quality over quantity).",
        "Daily trend is bullish (above 50 EMA), 4H shows a pullback to support with bullish "
        "reversal pattern, AND 1H confirms with a break of structure to the upside. All "
        "three timeframes must align before entry.",
        "Trail stop-loss on the 4H timeframe using swing lows. Take profit when the Daily "
        "timeframe shows exhaustion or when 4H trend shifts bearish.",
        "Low",
        S,
    ))

    story.append(Spacer(1, 12))
    story.append(tip_box(
        "Start with Strategy 1 and paper trade it for at least 30 days before risking real money. "
        "Only add additional strategies once you are consistently profitable with the first one.",
        S,
    ))
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # CHAPTER 4: Reading AI Signals
    # -----------------------------------------------------------------------
    story.append(navy_header_bar("CHAPTER 4: READING AI SIGNALS", S))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "AI signals are only valuable if you know how to read and act on them correctly. "
        "This chapter breaks down signal interpretation, position sizing, and knowing when "
        "to sit on the sidelines.",
        S["body"],
    ))

    story.append(Paragraph("<b>Understanding Signal Strength</b>", S["h2"]))
    story.append(Paragraph(
        "Every AI signal includes a confidence score from 0-100%. Here is how to interpret it:",
        S["body"],
    ))

    sig_data = [
        ["Score Range", "Strength", "Action", "Position Size"],
        ["80 - 100%", "STRONG", "Full entry with standard\nrisk allocation", "1.5 - 2% of account"],
        ["60 - 79%", "MODERATE", "Reduced entry, wait for\nadditional confirmation", "0.5 - 1% of account"],
        ["40 - 59%", "WEAK", "Paper trade only, do not\nrisk real capital", "Paper trade only"],
        ["Below 40%", "NO TRADE", "Skip entirely, the AI\nis not confident enough", "No position"],
    ]
    stbl = Table(sig_data, colWidths=[80, 80, 175, 145])
    stbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("BACKGROUND", (0, 1), (-1, 1), HexColor("#ECFDF5")),
        ("BACKGROUND", (0, 2), (-1, 2), HexColor("#FFFBEB")),
        ("BACKGROUND", (0, 3), (-1, 3), HexColor("#FEF3C7")),
        ("BACKGROUND", (0, 4), (-1, 4), HexColor("#FEF2F2")),
        ("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
        ("FONTNAME", (1, 1), (1, -1), "Helvetica-Bold"),
    ]))
    story.append(stbl)
    story.append(Spacer(1, 12))

    story.append(Paragraph("<b>Entry, Stop-Loss, and Take-Profit</b>", S["h2"]))
    story.append(Paragraph("Every trade has three critical price levels:", S["body"]))

    story.extend(numbered_list([
        "<b>Entry price:</b> The exact price at which you open your position. Use limit orders "
        "rather than market orders to avoid slippage. Set your entry slightly above resistance "
        "(for longs) or slightly below support (for shorts) for confirmation.",
        "<b>Stop-loss:</b> Your maximum acceptable loss on the trade. Place it at a logical "
        "level, typically below the most recent swing low (for longs) or above the recent "
        "swing high (for shorts). Never widen your stop-loss after entering a trade.",
        "<b>Take-profit:</b> Your target exit price. Set it at the next significant resistance "
        "(for longs) or support (for shorts). Consider scaling out: take 50% profit at the "
        "first target and trail the rest.",
    ], S))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>Position Sizing Calculator</b>", S["h2"]))
    story.append(Paragraph("Use this formula for every trade:", S["body"]))

    formula_tbl = Table(
        [[Paragraph(
            "<b>Position Size = (Account Balance x Risk %) / (Entry Price - Stop Loss Price)</b>",
            ParagraphStyle("formula", fontName="Helvetica-Bold", fontSize=11,
                           textColor=NAVY, alignment=TA_CENTER),
        )]],
        colWidths=[PAGE_W - 2 * MARGIN],
    )
    formula_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), HexColor("#F1F5F9")),
        ("BOX", (0, 0), (-1, -1), 1, NAVY),
        ("TOPPADDING", (0, 0), (-1, -1), 14),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 14),
    ]))
    story.append(formula_tbl)
    story.append(Spacer(1, 6))

    story.append(Paragraph(
        "<b>Example:</b> Account = $5,000 | Risk = 2% ($100) | Entry = $50,000 | Stop = $49,000 "
        "| Distance = $1,000. Position size = $100 / $1,000 = 0.1 BTC.",
        S["body"],
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph("<b>When NOT to Trade</b>", S["h2"]))
    story.append(Paragraph(
        "Knowing when to stay out of the market is just as important as knowing when to enter. "
        "Do not trade when:", S["body"],
    ))
    story.extend(bullet_list([
        "Major economic events are imminent (FOMC, NFP, CPI releases)",
        "The AI signal confidence is below 60% on your primary strategy",
        "You have already hit your daily or weekly loss limit",
        "You are feeling emotional, stressed, tired, or distracted",
        "The market is in a low-volume, choppy, indecisive range",
        "Multiple timeframes are conflicting in direction",
        "It is a Friday afternoon or a holiday period (thin liquidity)",
    ], S))

    story.append(Spacer(1, 6))
    story.append(warning_box(
        "Overtrading is the number one account killer. Profitable traders often have more "
        "days with zero trades than days with trades. Quality setups only.", S
    ))
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # CHAPTER 5: Risk Management Framework
    # -----------------------------------------------------------------------
    story.append(navy_header_bar("CHAPTER 5: RISK MANAGEMENT FRAMEWORK", S))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Risk management is not optional. It is the foundation that determines whether you "
        "survive long enough to become profitable. This framework is your safety net.",
        S["body"],
    ))

    story.append(Paragraph("<b>The 2% Rule: Your Non-Negotiable</b>", S["h2"]))
    story.append(Paragraph(
        "Never risk more than 2% of your total trading capital on any single trade. "
        "Here is why this works:", S["body"],
    ))
    story.extend(bullet_list([
        "With 2% risk, you would need 50 consecutive losing trades to wipe out your account. "
        "This is statistically near-impossible with a sound strategy.",
        "Even a 10-trade losing streak (which happens) only draws down your account by ~18%.",
        "Small position sizes keep emotions in check. You can think clearly when a trade "
        "represents 2% of your portfolio instead of 20%.",
        "Professional fund managers typically risk 0.5-1% per trade. As a retail trader, "
        "2% gives you room to grow while staying safe.",
    ], S))

    story.append(Paragraph("<b>Portfolio Allocation by Risk Level</b>", S["h2"]))

    alloc_data = [
        ["Category", "Allocation", "Description"],
        ["Core Holdings\n(Low Risk)", "40-50%", "Blue-chip assets, BTC/ETH, index funds.\nHold long-term, rarely traded."],
        ["Active Trading\n(Medium Risk)", "30-40%", "Your AI strategy capital.\nThis is where the 2% rule applies."],
        ["High-Risk / Moonshots\n(High Risk)", "10-15%", "Small-cap, new tokens, speculative plays.\nMoney you can afford to lose entirely."],
        ["Cash Reserve", "10-15%", "Dry powder for opportunities.\nNever fully deployed."],
    ]
    atbl = Table(alloc_data, colWidths=[120, 70, 290])
    atbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("BACKGROUND", (0, 1), (-1, -1), NEAR_WHITE),
        ("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
    ]))
    story.append(atbl)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Drawdown Management</b>", S["h2"]))
    story.append(Paragraph(
        "Drawdowns are inevitable. How you handle them separates professionals from amateurs:",
        S["body"],
    ))

    dd_data = [
        ["Drawdown Level", "Action Required"],
        ["5% (Daily)", "Stop trading for the day. Review your trades. Identify mistakes."],
        ["10% (Weekly)", "Reduce position sizes by 50%. Review strategy parameters."],
        ["15% (Monthly)", "Stop live trading. Return to paper trading for 1 week minimum."],
        ["20% (Quarterly)", "Full strategy audit. Consult with a mentor or community.\nDo not resume until root cause is identified."],
    ]
    dtbl = Table(dd_data, colWidths=[110, 370])
    dtbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), NAVY),
        ("TEXTCOLOR", (0, 0), (-1, 0), GOLD),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9.5),
        ("LEADING", (0, 0), (-1, -1), 13),
        ("BACKGROUND", (0, 1), (-1, 1), HexColor("#FEF9C3")),
        ("BACKGROUND", (0, 2), (-1, 2), HexColor("#FED7AA")),
        ("BACKGROUND", (0, 3), (-1, 3), HexColor("#FECACA")),
        ("BACKGROUND", (0, 4), (-1, 4), HexColor("#FCA5A5")),
        ("TEXTCOLOR", (0, 1), (-1, -1), SLATE),
        ("GRID", (0, 0), (-1, -1), 0.5, HexColor("#CBD5E1")),
        ("LEFTPADDING", (0, 0), (-1, -1), 8),
        ("TOPPADDING", (0, 0), (-1, -1), 7),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("FONTNAME", (0, 1), (0, -1), "Helvetica-Bold"),
    ]))
    story.append(dtbl)
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Emotional Trading Red Flags</b>", S["h2"]))
    story.append(Paragraph("Stop trading immediately if you notice any of these behaviors:", S["body"]))
    story.extend(bullet_list([
        "<b>Revenge trading:</b> Trying to win back losses by increasing position size or "
        "taking lower-quality setups.",
        "<b>FOMO entries:</b> Jumping into trades because the price is moving fast and you "
        "feel like you are missing out.",
        "<b>Moving your stop-loss:</b> Widening your stop because you do not want to accept "
        "the loss. This always leads to bigger losses.",
        "<b>Ignoring your system:</b> Overriding AI signals because you have a gut feeling. "
        "Your gut is wrong more often than the data.",
        "<b>Trading while emotional:</b> After a fight, bad news, or during high stress. "
        "Your decision-making is impaired.",
        "<b>Checking P&L obsessively:</b> If you are refreshing your balance every few minutes, "
        "your position size is too large.",
    ], S))

    story.append(tip_box(
        "Create a pre-trade checklist with 5 criteria that must be met before entering "
        "any trade. Tape it to your monitor. Follow it without exception.", S
    ))
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # CHAPTER 6: Your First 30 Days Plan
    # -----------------------------------------------------------------------
    story.append(navy_header_bar("CHAPTER 6: YOUR FIRST 30 DAYS PLAN", S))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "This step-by-step plan transforms you from complete beginner to confident, "
        "disciplined AI trader in 30 days. Follow each week precisely, and do not skip ahead.",
        S["body"],
    ))

    # Week 1
    story.append(Paragraph('<font color="#F59E0B"><b>WEEK 1: Paper Trading Setup (Days 1-7)</b></font>', S["h2"]))
    story.append(Paragraph("Goal: Build your infrastructure and practice without risk.", S["body"]))
    story.extend(bullet_list([
        "<b>Day 1-2:</b> Set up your exchange account, complete KYC, enable all security features. "
        "Create a free TradingView account and explore the charting interface.",
        "<b>Day 3-4:</b> Activate paper trading mode. Learn to place market orders, limit orders, "
        "and stop-loss orders on your platform. Practice until the process is automatic.",
        "<b>Day 5-6:</b> Study Strategy 1 (Moving Average Crossover). Set up the 9 EMA, 21 EMA, "
        "and 200 EMA on your charts. Identify 5 historical crossover signals and note what happened.",
        "<b>Day 7:</b> Take your first 3 paper trades using Strategy 1. Record every detail in "
        "your trading journal: entry, exit, reason, result, and what you learned.",
    ], S))

    # Week 2
    story.append(Paragraph('<font color="#F59E0B"><b>WEEK 2: Small Position Testing (Days 8-14)</b></font>', S["h2"]))
    story.append(Paragraph(
        "Goal: Transition to real money with minimal risk to build confidence.", S["body"],
    ))
    story.extend(bullet_list([
        "<b>Day 8-9:</b> Continue paper trading. You should have 8-10 paper trades logged by now. "
        "Review your journal: What patterns do you see? Where did you make mistakes?",
        "<b>Day 10-11:</b> Fund your account with a small amount you can afford to lose entirely "
        "(recommended: $100-$500). This is tuition money, not investment capital.",
        "<b>Day 12-13:</b> Take your first real trade with the absolute minimum position size "
        "your platform allows. The goal is not profit; it is experiencing real emotions.",
        "<b>Day 14:</b> Review your first week of real trading. How did it feel compared to paper "
        "trading? Document the emotional differences in your journal.",
    ], S))

    # Week 3
    story.append(Paragraph('<font color="#F59E0B"><b>WEEK 3: Strategy Refinement (Days 15-21)</b></font>', S["h2"]))
    story.append(Paragraph(
        "Goal: Optimize your approach based on real market experience.", S["body"],
    ))
    story.extend(bullet_list([
        "<b>Day 15-16:</b> Analyze all trades taken so far. Calculate your win rate, average "
        "win size, average loss size, and risk-reward ratio. Are you following your rules?",
        "<b>Day 17-18:</b> Introduce Strategy 2 (RSI Divergence) on paper while continuing "
        "Strategy 1 with real money. Compare performance in your journal.",
        "<b>Day 19-20:</b> Refine your entry criteria. Are there specific conditions that "
        "improve your win rate? Add these as filters to your trading plan.",
        "<b>Day 21:</b> Write out your complete trading plan: strategies used, entry rules, "
        "exit rules, risk management rules, and schedule. This is your trading bible.",
    ], S))

    # Week 4
    story.append(Paragraph('<font color="#F59E0B"><b>WEEK 4: Live Trading with Guard Rails (Days 22-30)</b></font>', S["h2"]))
    story.append(Paragraph(
        "Goal: Trade with discipline and protect your capital.", S["body"],
    ))
    story.extend(bullet_list([
        "<b>Day 22-24:</b> Increase position sizes slightly (still within 2% risk rule). "
        "Focus on execution quality: are you entering and exiting at the planned levels?",
        "<b>Day 25-27:</b> Implement your guard rails: maximum 3 trades per day, mandatory "
        "stop-loss on every trade, walk away after hitting daily loss limit.",
        "<b>Day 28-29:</b> Full performance review. Calculate all metrics. If you are profitable, "
        "continue. If not, identify the top 3 mistakes and create rules to prevent them.",
        "<b>Day 30:</b> Write your Month 2 plan. Set specific goals for the next 30 days. "
        "Consider joining the Beast Mode Academy community for ongoing support and signals.",
    ], S))

    story.append(Spacer(1, 8))
    story.append(tip_box(
        "The traders who succeed are the ones who treat this like a business from day one. "
        "Keep a strict schedule, review your performance weekly, and never stop learning.",
        S, icon="SUCCESS KEY",
    ))
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # CHAPTER 7: Advanced Resources
    # -----------------------------------------------------------------------
    story.append(navy_header_bar("CHAPTER 7: ADVANCED RESOURCES", S))
    story.append(Spacer(1, 12))

    story.append(Paragraph(
        "Your learning journey does not end here. These resources will help you continue "
        "developing your skills and staying ahead of the market.",
        S["body"],
    ))

    story.append(Paragraph("<b>Recommended Books</b>", S["h2"]))
    story.extend(bullet_list([
        '<b>"Trading in the Zone"</b> by Mark Douglas \u2014 The psychology bible for traders.',
        '<b>"Technical Analysis of the Financial Markets"</b> by John Murphy \u2014 '
        'The comprehensive reference for chart patterns and indicators.',
        '<b>"The Intelligent Investor"</b> by Benjamin Graham \u2014 Timeless principles '
        'of value and risk management.',
        '<b>"Advances in Financial Machine Learning"</b> by Marcos Lopez de Prado \u2014 '
        'The definitive guide to applying ML in trading.',
        '<b>"Market Wizards"</b> by Jack Schwager \u2014 Interviews with the world\'s top '
        'traders. Learn from their mistakes and breakthroughs.',
    ], S))

    story.append(Paragraph("<b>YouTube Channels</b>", S["h2"]))
    story.extend(bullet_list([
        "<b>Beast Mode Academy</b> \u2014 AI trading signals, strategy breakdowns, live market "
        "analysis, and weekly performance reviews. Subscribe for daily content.",
        "<b>Technical analysis channels</b> that focus on education over hype. "
        "Avoid channels that only show winning trades.",
    ], S))

    story.append(Paragraph("<b>Tools and Platforms</b>", S["h2"]))
    story.extend(bullet_list([
        "<b>TradingView</b> \u2014 Best-in-class charting with a massive community indicator library.",
        "<b>CoinGecko / CoinMarketCap</b> \u2014 Fundamental research and market data for crypto.",
        "<b>Glassnode</b> \u2014 On-chain analytics for Bitcoin and Ethereum market intelligence.",
        "<b>Fear & Greed Index</b> \u2014 Real-time market sentiment gauge. Bookmark it.",
        "<b>Notion / Spreadsheet</b> \u2014 For your trading journal and performance tracking.",
    ], S))

    story.append(Spacer(1, 16))

    # VIP CTA box
    vip_text = Paragraph(
        '<font color="#FBBF24"><b>UPGRADE TO VIP AI SIGNALS</b></font><br/><br/>'
        '<font color="#F8FAFC">Get real-time AI-powered trading signals delivered straight '
        'to your dashboard. Our algorithms scan the market 24/7 so you do not have to.</font><br/><br/>'
        '<font color="#FBBF24"><b>gettraderadar.com/signals</b></font>',
        ParagraphStyle("vip", fontName="Helvetica", fontSize=12, leading=18,
                        alignment=TA_CENTER),
    )
    vip_tbl = Table([[vip_text]], colWidths=[PAGE_W - 2 * MARGIN])
    vip_tbl.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), NAVY),
        ("BOX", (0, 0), (-1, -1), 2, GOLD),
        ("TOPPADDING", (0, 0), (-1, -1), 20),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 20),
        ("LEFTPADDING", (0, 0), (-1, -1), 20),
        ("RIGHTPADDING", (0, 0), (-1, -1), 20),
        ("ROUNDEDCORNERS", [8, 8, 8, 8]),
    ]))
    story.append(vip_tbl)
    story.append(PageBreak())

    # -----------------------------------------------------------------------
    # BACK COVER
    # -----------------------------------------------------------------------
    story.append(Spacer(1, 60))

    # Join CTA
    join_text = Paragraph(
        '<font color="#FBBF24" size="20"><b>JOIN BEAST MODE ACADEMY</b></font>',
        ParagraphStyle("join", alignment=TA_CENTER),
    )
    story.append(join_text)
    story.append(Spacer(1, 20))
    story.append(Paragraph(
        "Your journey to AI-powered trading starts now. Join thousands of traders "
        "who are leveraging artificial intelligence to trade smarter, not harder.",
        ParagraphStyle("bc", fontName="Helvetica", fontSize=12, leading=18,
                        textColor=SLATE, alignment=TA_CENTER),
    ))

    story.append(Spacer(1, 30))

    # Social links
    social_items = [
        ["YouTube", "Beast Mode Academy"],
        ["Facebook", "Beast Mode Academy (29,700+ followers)"],
        ["Website", "gettraderadar.com"],
        ["VIP Signals", "gettraderadar.com/signals"],
    ]
    soc_data = []
    for platform, handle in social_items:
        soc_data.append([
            Paragraph(f"<b>{platform}:</b>",
                      ParagraphStyle("sp", fontName="Helvetica-Bold", fontSize=11,
                                      textColor=NAVY, alignment=TA_RIGHT)),
            Paragraph(handle,
                      ParagraphStyle("sh", fontName="Helvetica", fontSize=11,
                                      textColor=GOLD)),
        ])
    soc_tbl = Table(soc_data, colWidths=[180, 300])
    soc_tbl.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
    ]))
    story.append(soc_tbl)

    story.append(Spacer(1, 40))
    story.append(gold_hr())
    story.append(Spacer(1, 10))

    # Disclaimer
    story.append(Paragraph("<b>DISCLAIMER</b>", ParagraphStyle(
        "disc_h", fontName="Helvetica-Bold", fontSize=9, textColor=SLATE,
        alignment=TA_CENTER, spaceAfter=6,
    )))
    story.append(Paragraph(
        "Trading involves substantial risk of loss and is not suitable for every investor. "
        "The information provided in this guide is for educational purposes only and should "
        "not be considered financial advice. Past performance of any trading strategy or AI "
        "system does not guarantee future results. You should consult with a licensed financial "
        "advisor before making any investment decisions. Never trade with money you cannot "
        "afford to lose. The authors and publishers of this guide accept no liability for any "
        "losses incurred through the use of the strategies, tools, or information described "
        "herein. AI trading systems can and do produce losing trades. Always use proper risk "
        "management and position sizing as outlined in this guide.",
        S["disclaimer"],
    ))
    story.append(Spacer(1, 16))
    story.append(Paragraph(
        "\u00a9 2026 Beast Mode Academy. All rights reserved.",
        ParagraphStyle("copy", fontName="Helvetica", fontSize=8,
                        textColor=LIGHT_SLATE, alignment=TA_CENTER),
    ))

    return story


# ---------------------------------------------------------------------------
# Main generator
# ---------------------------------------------------------------------------
def generate_pdf():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    output_dir = os.path.join(script_dir, "output")
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "ai_trading_starter_kit.pdf")

    styles = build_styles()
    story = build_content(styles)

    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 10,
        title="AI Trading Starter Kit",
        author="Beast Mode Academy",
        subject="Your Complete Guide to AI-Powered Trading",
        creator="Beast Mode Academy - gettraderadar.com",
    )

    doc.build(
        story,
        onFirstPage=draw_cover,
        canvasmaker=FooterCanvas,
    )

    print(f"PDF generated successfully: {output_path}")
    print(f"File size: {os.path.getsize(output_path) / 1024:.1f} KB")
    return output_path


if __name__ == "__main__":
    generate_pdf()
