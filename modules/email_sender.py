"""
Email Sender Module — SMTP-based transactional and broadcast emails.

Sends niche-branded HTML emails (welcome, product promo, broadcast)
via configurable SMTP. All emails include an unsubscribe link.

Environment variables:
    EMAIL_SMTP_HOST      SMTP server hostname (e.g. smtp.gmail.com)
    EMAIL_SMTP_PORT      SMTP port (default 587)
    EMAIL_SMTP_USER      SMTP login username
    EMAIL_SMTP_PASS      SMTP login password
    EMAIL_FROM_NAME      Sender display name (default "AI Video Factory")
    EMAIL_FROM_ADDRESS   Sender email address
    EMAIL_UNSUBSCRIBE_URL  Base URL for unsubscribe (default /unsubscribe)
"""

import logging
import os
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from urllib.parse import quote

logger = logging.getLogger(__name__)

# ── SMTP Configuration ──────────────────────────────────────────────

SMTP_HOST = os.getenv("EMAIL_SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("EMAIL_SMTP_PORT", "587"))
SMTP_USER = os.getenv("EMAIL_SMTP_USER", "")
SMTP_PASS = os.getenv("EMAIL_SMTP_PASS", "")
FROM_NAME = os.getenv("EMAIL_FROM_NAME", "AI Video Factory")
FROM_ADDRESS = os.getenv("EMAIL_FROM_ADDRESS", "")
UNSUBSCRIBE_URL = os.getenv("EMAIL_UNSUBSCRIBE_URL", "/unsubscribe")

# ── Niche Branding ──────────────────────────────────────────────────

NICHE_COLORS = {
    "ai_trading":      "#F59E0B",
    "ai_money":        "#10B981",
    "tech_news":       "#3B82F6",
    "motivation":      "#F97316",
    "health_wellness": "#059669",
    "blissful_moments": "#8B5CF6",
    "limitless_you":   "#06B6D4",
}

NICHE_NAMES = {
    "ai_trading":      "Beast Mode Academy",
    "ai_money":        "Smart Money AI",
    "tech_news":       "Tech Pulse Africa",
    "motivation":      "Elevate You",
    "health_wellness": "Herbal Organic Life",
    "blissful_moments": "Blissful Moments",
    "limitless_you":   "Limitless You",
}

NICHE_LEAD_MAGNETS = {
    "ai_trading":      "Free AI Trading Starter Kit",
    "ai_money":        "100 AI Money-Making Prompts",
    "tech_news":       "Tech Career Pivot Checklist",
    "motivation":      "90-Day Transformation Blueprint",
    "health_wellness": "Natural Remedies Quick Guide",
    "blissful_moments": "7-Day Mindfulness Challenge",
    "limitless_you":   "Unlock Your Limitless Potential Guide",
}

NICHE_WELCOME_BODY = {
    "ai_trading": (
        "You've just taken the first step toward smarter, AI-powered trading. "
        "Your <strong>Free AI Trading Starter Kit</strong> is ready for download."
    ),
    "ai_money": (
        "Welcome to the future of income. Your <strong>100 AI Money-Making Prompts</strong> "
        "pack is ready — copy, paste, and start earning."
    ),
    "tech_news": (
        "Your tech career pivot starts now. Download your <strong>Tech Career Pivot Checklist</strong> "
        "and make your next move with confidence."
    ),
    "motivation": (
        "The next 90 days will change everything. Your <strong>90-Day Transformation Blueprint</strong> "
        "is waiting for you."
    ),
    "health_wellness": (
        "Nature has the answers. Your <strong>Natural Remedies Quick Guide</strong> "
        "is ready to transform your wellness routine."
    ),
    "blissful_moments": (
        "Peace is just 7 days away. Your <strong>7-Day Mindfulness Challenge</strong> "
        "starts the moment you download it."
    ),
    "limitless_you": (
        "There are no limits except the ones you set. Your <strong>Unlock Your Limitless "
        "Potential Guide</strong> is ready."
    ),
}


# ── HTML Email Template ─────────────────────────────────────────────

def _build_html_email(
    subject: str,
    body_html: str,
    cta_text: str = "",
    cta_url: str = "",
    niche: str = "ai_trading",
    to_email: str = "",
) -> str:
    """
    Build a branded HTML email with header, body, optional CTA button,
    and unsubscribe footer.

    Args:
        subject: Email subject (used in preheader).
        body_html: Main body HTML content.
        cta_text: Call-to-action button label (omitted if empty).
        cta_url: CTA button link URL.
        niche: Niche key for branding colors.
        to_email: Recipient email for unsubscribe link.

    Returns:
        Complete HTML string for the email body.
    """
    accent = NICHE_COLORS.get(niche, "#F59E0B")
    brand_name = NICHE_NAMES.get(niche, FROM_NAME)
    unsub_link = f"{UNSUBSCRIBE_URL}?email={quote(to_email)}&niche={quote(niche)}"

    cta_block = ""
    if cta_text and cta_url:
        cta_block = f"""
        <table role="presentation" cellspacing="0" cellpadding="0" border="0" style="margin:28px auto 0;">
          <tr>
            <td style="border-radius:8px;background:{accent};">
              <a href="{cta_url}" target="_blank"
                 style="display:inline-block;padding:14px 32px;font-size:16px;font-weight:700;
                        color:#ffffff;text-decoration:none;border-radius:8px;">
                {cta_text}
              </a>
            </td>
          </tr>
        </table>
        """

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>{subject}</title>
</head>
<body style="margin:0;padding:0;background-color:#0F172A;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,'Helvetica Neue',Arial,sans-serif;">

<!-- Preheader (hidden) -->
<div style="display:none;max-height:0;overflow:hidden;font-size:1px;line-height:1px;color:#0F172A;">
  {subject}
</div>

<table role="presentation" cellspacing="0" cellpadding="0" border="0" width="100%"
       style="background-color:#0F172A;">
  <tr>
    <td align="center" style="padding:32px 16px;">

      <!-- Main Card -->
      <table role="presentation" cellspacing="0" cellpadding="0" border="0"
             width="100%" style="max-width:560px;background-color:#1E293B;border-radius:16px;
                                  border:1px solid rgba(148,163,184,0.12);">

        <!-- Header Bar -->
        <tr>
          <td style="background:linear-gradient(135deg,{accent},rgba(0,0,0,0.3));
                     padding:28px 32px;border-radius:16px 16px 0 0;">
            <h1 style="margin:0;font-size:22px;font-weight:800;color:#ffffff;letter-spacing:-0.01em;">
              {brand_name}
            </h1>
          </td>
        </tr>

        <!-- Body -->
        <tr>
          <td style="padding:32px;color:#CBD5E1;font-size:15px;line-height:1.7;">
            {body_html}
            {cta_block}
          </td>
        </tr>

        <!-- Footer -->
        <tr>
          <td style="padding:20px 32px;border-top:1px solid rgba(148,163,184,0.1);
                     text-align:center;font-size:12px;color:#64748B;">
            <p style="margin:0 0 8px;">You received this because you subscribed to {brand_name}.</p>
            <a href="{unsub_link}" style="color:#64748B;text-decoration:underline;">Unsubscribe</a>
          </td>
        </tr>

      </table>
      <!-- /Main Card -->

    </td>
  </tr>
</table>

</body>
</html>"""


# ── SMTP Transport ──────────────────────────────────────────────────

def _send_email(to_email: str, subject: str, html_body: str) -> bool:
    """
    Send an HTML email via SMTP with TLS.

    Args:
        to_email: Recipient email address.
        subject: Email subject line.
        html_body: Complete HTML email body.

    Returns:
        True if sent successfully, False on error.
    """
    if not SMTP_USER or not SMTP_PASS or not FROM_ADDRESS:
        logger.error(
            "Email not configured. Set EMAIL_SMTP_USER, EMAIL_SMTP_PASS, "
            "and EMAIL_FROM_ADDRESS environment variables."
        )
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"{FROM_NAME} <{FROM_ADDRESS}>"
    msg["To"] = to_email
    msg["List-Unsubscribe"] = f"<{UNSUBSCRIBE_URL}?email={quote(to_email)}>"

    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        context = ssl.create_default_context()
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls(context=context)
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_ADDRESS, to_email, msg.as_string())
        logger.info("Email sent to %s: %s", to_email, subject)
        return True
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("SMTP auth failed: %s", exc)
        return False
    except smtplib.SMTPException as exc:
        logger.error("SMTP error sending to %s: %s", to_email, exc)
        return False
    except OSError as exc:
        logger.error("Network error sending email to %s: %s", to_email, exc)
        return False


# ── Public API ──────────────────────────────────────────────────────

def send_welcome_email(to_email: str, name: str, niche: str) -> bool:
    """
    Send a niche-branded welcome email with lead magnet download link.

    Args:
        to_email: Recipient email address.
        name: Recipient's first name.
        niche: Content niche key (e.g. 'ai_trading').

    Returns:
        True if sent successfully, False on error.
    """
    brand_name = NICHE_NAMES.get(niche, FROM_NAME)
    lead_magnet = NICHE_LEAD_MAGNETS.get(niche, "Your Free Guide")
    greeting = name.strip().split()[0] if name and name.strip() else "there"

    welcome_body = NICHE_WELCOME_BODY.get(
        niche,
        f"Your <strong>{lead_magnet}</strong> is ready for download.",
    )

    body_html = f"""
    <p style="margin:0 0 16px;font-size:18px;font-weight:700;color:#F1F5F9;">
      Hey {greeting}!
    </p>
    <p style="margin:0 0 16px;">{welcome_body}</p>
    <p style="margin:0 0 4px;">Click below to grab your copy:</p>
    """

    subject = f"Welcome to {brand_name} — Your {lead_magnet} is Ready!"
    download_url = f"{UNSUBSCRIBE_URL.rsplit('/', 1)[0]}/download?niche={quote(niche)}&email={quote(to_email)}"

    html = _build_html_email(
        subject=subject,
        body_html=body_html,
        cta_text=f"Download {lead_magnet}",
        cta_url=download_url,
        niche=niche,
        to_email=to_email,
    )
    return _send_email(to_email, subject, html)


def send_product_email(
    to_email: str,
    name: str,
    niche: str,
    product_name: str,
    product_url: str,
    product_price: str = "",
) -> bool:
    """
    Send a product promotion email.

    Args:
        to_email: Recipient email address.
        name: Recipient's first name.
        niche: Content niche key.
        product_name: Name of the product being promoted.
        product_url: URL to the product page.
        product_price: Display price (e.g. "$49.99"). Optional.

    Returns:
        True if sent successfully, False on error.
    """
    greeting = name.strip().split()[0] if name and name.strip() else "there"
    brand_name = NICHE_NAMES.get(niche, FROM_NAME)
    price_line = f' for <strong>{product_price}</strong>' if product_price else ""

    body_html = f"""
    <p style="margin:0 0 16px;font-size:18px;font-weight:700;color:#F1F5F9;">
      Hey {greeting}!
    </p>
    <p style="margin:0 0 16px;">
      We wanted to share something special with you:
      <strong>{product_name}</strong>{price_line}.
    </p>
    <p style="margin:0 0 4px;">
      This is hand-picked for our {brand_name} community and we think you'll love it.
    </p>
    """

    subject = f"{greeting}, check out {product_name}"

    html = _build_html_email(
        subject=subject,
        body_html=body_html,
        cta_text="Learn More",
        cta_url=product_url,
        niche=niche,
        to_email=to_email,
    )
    return _send_email(to_email, subject, html)


def send_broadcast(
    niche: str,
    subject: str,
    html_content: str,
    cta_text: str = "",
    cta_url: str = "",
) -> dict:
    """
    Send an email broadcast to all subscribers of a given niche.

    Uses email_collector.get_subscribers() to fetch the recipient list.

    Args:
        niche: Target niche key.
        subject: Email subject line.
        html_content: HTML body content for the email.
        cta_text: Optional CTA button text.
        cta_url: Optional CTA button URL.

    Returns:
        Dict with keys: sent (int), failed (int), total (int).
    """
    from modules.email_collector import get_subscribers

    subscribers = get_subscribers(niche=niche)
    results = {"sent": 0, "failed": 0, "total": len(subscribers)}

    if not subscribers:
        logger.warning("No subscribers found for niche '%s'. Broadcast skipped.", niche)
        return results

    logger.info(
        "Sending broadcast to %d subscribers (niche=%s): %s",
        len(subscribers), niche, subject,
    )

    for sub in subscribers:
        email = sub["email"]
        name = sub.get("name", "")
        greeting = name.strip().split()[0] if name and name.strip() else "there"

        personalized_body = f"""
        <p style="margin:0 0 16px;font-size:18px;font-weight:700;color:#F1F5F9;">
          Hey {greeting}!
        </p>
        {html_content}
        """

        html = _build_html_email(
            subject=subject,
            body_html=personalized_body,
            cta_text=cta_text,
            cta_url=cta_url,
            niche=niche,
            to_email=email,
        )

        if _send_email(email, subject, html):
            results["sent"] += 1
        else:
            results["failed"] += 1

    logger.info(
        "Broadcast complete: %d sent, %d failed out of %d (niche=%s)",
        results["sent"], results["failed"], results["total"], niche,
    )
    return results
