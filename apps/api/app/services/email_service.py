import asyncio
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from app.core.config import settings
from app.models.user import User

logger = logging.getLogger(__name__)


class EmailService:
    """SMTP-based email service with a console logging fallback for local development."""

    def _get_verification_html(
        self, name: str, verification_link: str, expiry_hours: int = 24
    ) -> str:
        """Generate a modern, responsive HTML template for email verification."""
        current_year = datetime.now().year
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Verify your {settings.BRAND_NAME} Email</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #f7f7f5;
      color: #0d0d0d;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      width: 100%;
      background-color: #f7f7f5;
      padding: 40px 20px;
      box-sizing: border-box;
    }}
    .container {{
      max-width: 570px;
      margin: 0 auto;
      background-color: #ffffff;
      border: 1px solid #e8e8e8;
      border-radius: 16px;
      padding: 40px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
    }}
    .header {{
      text-align: center;
      margin-bottom: 30px;
    }}
    .logo-container {{
      display: inline-flex;
      align-items: center;
      text-decoration: none;
    }}
    .logo-icon {{
      width: 38px;
      height: 38px;
      background-color: {settings.BRAND_COLOR_PRIMARY};
      border-radius: 10px;
      display: inline-block;
      vertical-align: middle;
      text-align: center;
      line-height: 38px;
      color: #ffffff;
      font-size: 20px;
      font-weight: bold;
    }}
    .logo-text {{
      font-size: 22px;
      font-weight: 700;
      color: #0d0d0d;
      vertical-align: middle;
      margin-left: 10px;
      letter-spacing: -0.02em;
    }}
    .content {{
      font-size: 16px;
      line-height: 1.6;
      color: #3f3f46;
    }}
    h1 {{
      font-size: 24px;
      font-weight: 600;
      color: #0d0d0d;
      margin-top: 0;
      margin-bottom: 16px;
      letter-spacing: -0.02em;
    }}
    p {{
      margin-top: 0;
      margin-bottom: 20px;
    }}
    .btn-container {{
      text-align: center;
      margin: 32px 0;
    }}
    .btn {{
      display: inline-block;
      background-color: {settings.BRAND_COLOR_PRIMARY};
      color: #ffffff !important;
      text-decoration: none;
      font-weight: 600;
      font-size: 15px;
      padding: 14px 32px;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(196, 30, 58, 0.18);
    }}
    .fallback-box {{
      background-color: #f7f7f5;
      border-radius: 10px;
      padding: 16px;
      margin: 24px 0;
      word-break: break-all;
      border: 1px solid #e8e8e8;
    }}
    .fallback-title {{
      font-size: 11px;
      font-weight: 600;
      color: #71717a;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}
    .fallback-link {{
      font-size: 13px;
      color: {settings.BRAND_COLOR_PRIMARY};
      text-decoration: none;
    }}
    .footer {{
      margin-top: 36px;
      border-top: 1px solid #e8e8e8;
      padding-top: 24px;
      font-size: 12px;
      color: #71717a;
      line-height: 1.6;
    }}
    .security-notice {{
      font-style: italic;
      margin-bottom: 12px;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <a href="{settings.FRONTEND_URL}" class="logo-container">
          <span class="logo-icon">{settings.BRAND_ICON}</span>
          <span class="logo-text">{settings.BRAND_NAME}</span>
        </a>
      </div>
      <div class="content">
        <h1>Verify your email address</h1>
        <p>Hello {name},</p>
        <p>Thank you for signing up for {settings.BRAND_NAME}! To complete your registration and activate your account, please verify your email address by clicking the button below.</p>

        <div class="btn-container">
          <a href="{verification_link}" class="btn" target="_blank">Verify Email</a>
        </div>

        <p>This verification link is time-sensitive and will expire in <strong>{expiry_hours} hours</strong>.</p>

        <p>If you're having trouble clicking the button, copy and paste the URL below into your web browser:</p>
        <div class="fallback-box">
          <div class="fallback-title">Direct Link</div>
          <a href="{verification_link}" class="fallback-link" target="_blank">{verification_link}</a>
        </div>

        <div class="footer">
          <p class="security-notice"><strong>Security Notice:</strong> If you did not sign up for a {settings.BRAND_NAME} account, you can safely ignore this email. Someone may have entered your email address by mistake.</p>
          <p>&copy; {current_year} {settings.BRAND_NAME}. All rights reserved.</p>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

    def _get_password_reset_html(self, name: str, reset_link: str, expiry_hours: int = 1) -> str:
        """Generate a modern, responsive HTML template for password reset."""
        current_year = datetime.now().year
        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Reset your {settings.BRAND_NAME} Password</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #f7f7f5;
      color: #0d0d0d;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      width: 100%;
      background-color: #f7f7f5;
      padding: 40px 20px;
      box-sizing: border-box;
    }}
    .container {{
      max-width: 570px;
      margin: 0 auto;
      background-color: #ffffff;
      border: 1px solid #e8e8e8;
      border-radius: 16px;
      padding: 40px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
    }}
    .header {{
      text-align: center;
      margin-bottom: 30px;
    }}
    .logo-container {{
      display: inline-flex;
      align-items: center;
      text-decoration: none;
    }}
    .logo-icon {{
      width: 38px;
      height: 38px;
      background-color: {settings.BRAND_COLOR_PRIMARY};
      border-radius: 10px;
      display: inline-block;
      vertical-align: middle;
      text-align: center;
      line-height: 38px;
      color: #ffffff;
      font-size: 20px;
      font-weight: bold;
    }}
    .logo-text {{
      font-size: 22px;
      font-weight: 700;
      color: #0d0d0d;
      vertical-align: middle;
      margin-left: 10px;
      letter-spacing: -0.02em;
    }}
    .content {{
      font-size: 16px;
      line-height: 1.6;
      color: #3f3f46;
    }}
    h1 {{
      font-size: 24px;
      font-weight: 600;
      color: #0d0d0d;
      margin-top: 0;
      margin-bottom: 16px;
      letter-spacing: -0.02em;
    }}
    p {{
      margin-top: 0;
      margin-bottom: 20px;
    }}
    .btn-container {{
      text-align: center;
      margin: 32px 0;
    }}
    .btn {{
      display: inline-block;
      background-color: {settings.BRAND_COLOR_PRIMARY};
      color: #ffffff !important;
      text-decoration: none;
      font-weight: 600;
      font-size: 15px;
      padding: 14px 32px;
      border-radius: 10px;
      box-shadow: 0 4px 12px rgba(196, 30, 58, 0.18);
    }}
    .fallback-box {{
      background-color: #f7f7f5;
      border-radius: 10px;
      padding: 16px;
      margin: 24px 0;
      word-break: break-all;
      border: 1px solid #e8e8e8;
    }}
    .fallback-title {{
      font-size: 11px;
      font-weight: 600;
      color: #71717a;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 6px;
    }}
    .fallback-link {{
      font-size: 13px;
      color: {settings.BRAND_COLOR_PRIMARY};
      text-decoration: none;
    }}
    .footer {{
      margin-top: 36px;
      border-top: 1px solid #e8e8e8;
      padding-top: 24px;
      font-size: 12px;
      color: #71717a;
      line-height: 1.6;
    }}
    .security-notice {{
      font-style: italic;
      margin-bottom: 12px;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <a href="{settings.FRONTEND_URL}" class="logo-container">
          <span class="logo-icon">{settings.BRAND_ICON}</span>
          <span class="logo-text">{settings.BRAND_NAME}</span>
        </a>
      </div>
      <div class="content">
        <h1>Reset your password</h1>
        <p>Hello {name},</p>
        <p>We received a request to reset your {settings.BRAND_NAME} account password. Click the button below to choose a new password.</p>

        <div class="btn-container">
          <a href="{reset_link}" class="btn" target="_blank">Reset Password</a>
        </div>

        <p>This password reset link is time-sensitive and will expire in <strong>{expiry_hours} hour</strong>.</p>

        <p>If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged.</p>

        <p>If you're having trouble clicking the button, copy and paste the URL below into your web browser:</p>
        <div class="fallback-box">
          <div class="fallback-title">Direct Link</div>
          <a href="{reset_link}" class="fallback-link" target="_blank">{reset_link}</a>
        </div>

        <div class="footer">
          <p>&copy; {current_year} {settings.BRAND_NAME}. All rights reserved.</p>
        </div>
      </div>
    </div>
  </div>
</body>
</html>
"""

    async def send_verification_email(self, user: User, token: str) -> None:
        """Send a beautiful verification HTML email to the user."""
        verification_link = f"{settings.FRONTEND_URL}/verify-email?token={token}"
        name = user.name or "User"
        subject = f"Verify your {settings.BRAND_NAME} account"

        html_content = self._get_verification_html(name, verification_link)
        text_content = f"Hello {name},\n\nPlease verify your email by opening the following link in your browser:\n{verification_link}\n\nThis link will expire in 24 hours."

        await self._send(user.email, subject, html_content, text_content, "verification", token)

    async def send_password_reset_email(self, user: User, token: str) -> None:
        """Send a beautiful password reset HTML email to the user."""
        reset_link = f"{settings.FRONTEND_URL}/reset-password?token={token}"
        name = user.name or "User"

        self._get_password_reset_html(name, reset_link)

    def _get_digest_html(self, name: str, title: str, stories: list[dict]) -> str:
        """Generate a modern, beautiful responsive HTML template for a news digest."""
        current_year = datetime.now().year
        story_cards_html = ""

        for index, story in enumerate(stories):
            headline = story.get("headline", "")
            one_line = story.get("one_line_summary", "")
            short_sum = story.get("short_summary", "")
            story_id = story.get("story_id", "")
            link = f"{settings.FRONTEND_URL}/story/{story_id}"

            story_cards_html += f"""
            <div class="story-card">
              <div class="story-tag">Story #{index + 1}</div>
              <h2 class="story-title"><a href="{link}" target="_blank">{headline}</a></h2>
              <div class="story-one-line">&ldquo;{one_line}&rdquo;</div>
              <p class="story-desc">{short_sum}</p>
              <div class="story-footer">
                <a href="{link}" class="story-link" target="_blank">Explore Full Coverage &rarr;</a>
              </div>
            </div>
            """

        return f"""<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
      background-color: #f7f7f5;
      color: #0d0d0d;
      margin: 0;
      padding: 0;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      width: 100%;
      background-color: #f7f7f5;
      padding: 40px 20px;
      box-sizing: border-box;
    }}
    .container {{
      max-width: 600px;
      margin: 0 auto;
      background-color: #ffffff;
      border: 1px solid #e8e8e8;
      border-radius: 16px;
      padding: 40px;
      box-shadow: 0 4px 20px rgba(0, 0, 0, 0.02);
    }}
    .header {{
      text-align: center;
      margin-bottom: 30px;
      border-bottom: 1px solid #f1f1f0;
      padding-bottom: 20px;
    }}
    .logo-container {{
      display: inline-flex;
      align-items: center;
      text-decoration: none;
    }}
    .logo-icon {{
      width: 38px;
      height: 38px;
      background-color: {settings.BRAND_COLOR_PRIMARY};
      border-radius: 10px;
      display: inline-block;
      vertical-align: middle;
      text-align: center;
      line-height: 38px;
      color: #ffffff;
      font-size: 20px;
      font-weight: bold;
    }}
    .logo-text {{
      font-size: 22px;
      font-weight: 700;
      color: #0d0d0d;
      vertical-align: middle;
      margin-left: 10px;
      letter-spacing: -0.02em;
    }}
    .digest-meta {{
      font-size: 12px;
      color: #71717a;
      margin-top: 8px;
      text-transform: uppercase;
      letter-spacing: 0.05em;
    }}
    h1 {{
      font-size: 26px;
      font-weight: 800;
      color: #0d0d0d;
      margin-top: 10px;
      margin-bottom: 5px;
      letter-spacing: -0.03em;
    }}
    .story-card {{
      margin-bottom: 30px;
      padding: 24px;
      background-color: #fafafa;
      border: 1px solid #f1f1f0;
      border-radius: 12px;
    }}
    .story-tag {{
      display: inline-block;
      font-size: 10px;
      font-weight: 700;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      color: #7c3aed;
      background-color: rgba(124, 58, 237, 0.05);
      padding: 3px 8px;
      border-radius: 99px;
      margin-bottom: 12px;
    }}
    .story-title {{
      font-size: 18px;
      font-weight: 700;
      line-height: 1.35;
      margin-top: 0;
      margin-bottom: 12px;
      letter-spacing: -0.01em;
    }}
    .story-title a {{
      color: #0d0d0d;
      text-decoration: none;
    }}
    .story-title a:hover {{
      color: {settings.BRAND_COLOR_PRIMARY};
    }}
    .story-one-line {{
      font-size: 13px;
      font-weight: 500;
      font-style: italic;
      color: #4b5563;
      background-color: rgba(124, 58, 237, 0.02);
      border-left: 3px solid #7c3aed;
      padding: 8px 12px;
      margin-bottom: 12px;
      border-radius: 0 8px 8px 0;
    }}
    .story-desc {{
      font-size: 14px;
      line-height: 1.5;
      color: #52525b;
      margin-top: 0;
      margin-bottom: 16px;
    }}
    .story-footer {{
      text-align: right;
    }}
    .story-link {{
      font-size: 13px;
      font-weight: 600;
      color: {settings.BRAND_COLOR_PRIMARY};
      text-decoration: none;
    }}
    .footer {{
      margin-top: 40px;
      border-top: 1px solid #e8e8e8;
      padding-top: 24px;
      font-size: 12px;
      color: #71717a;
      line-height: 1.6;
      text-align: center;
    }}
    .footer a {{
      color: {settings.BRAND_COLOR_PRIMARY};
      text-decoration: none;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <a href="{settings.FRONTEND_URL}" class="logo-container">
          <span class="logo-icon">{settings.BRAND_ICON}</span>
          <span class="logo-text">{settings.BRAND_NAME}</span>
        </a>
        <h1>{title}</h1>
        <p class="digest-meta">Personalized Briefing for {name}</p>
      </div>

      <div class="content">
        {story_cards_html}
      </div>

      <div class="footer">
        <p>You received this email because you are subscribed to the {title}.</p>
        <p><a href="{settings.FRONTEND_URL}/settings?tab=notif">Manage Subscription Settings</a> | <a href="{settings.FRONTEND_URL}/settings?tab=notif">Unsubscribe</a></p>
        <p>&copy; {current_year} {settings.BRAND_NAME}. All rights reserved.</p>
      </div>
    </div>
  </div>
</body>
</html>
"""

    async def send_digest_email(self, user: User, edition_title: str, stories: list[dict]) -> None:
        """Send a beautiful news digest HTML email to the user."""
        name = user.name or "Subscriber"
        subject = f"Your {settings.BRAND_NAME} {edition_title}"

        html_content = self._get_digest_html(name, edition_title, stories)

        # Simple plain text version
        story_texts = []
        for index, story in enumerate(stories):
            headline = story.get("headline", "")
            one_line = story.get("one_line_summary", "")
            story_id = story.get("story_id", "")
            link = f"{settings.FRONTEND_URL}/story/{story_id}"
            story_texts.append(f'{index + 1}. {headline}\n   "{one_line}"\n   Link: {link}')
        text_content = (
            f"Hello {name},\n\nHere is your {settings.BRAND_NAME} {edition_title}:\n\n"
            + "\n\n".join(story_texts)
            + f"\n\nManage your settings here: {settings.FRONTEND_URL}/settings?tab=notif"
        )

        await self._send(user.email, subject, html_content, text_content, "digest", "")

    async def _send(
        self,
        recipient: str,
        subject: str,
        html_content: str,
        text_content: str,
        email_type: str,
        raw_token: str,
    ) -> None:
        """Sends the email using SMTP or logs to console if unconfigured."""
        if not settings.SMTP_HOST or not settings.SMTP_PORT:
            logger.info(
                "AUDIT: %s email requested for user (%s). Raw Token: %s",
                email_type.capitalize(),
                recipient,
                raw_token,
            )
            # Log full content in local debug mode to capture the token easily
            print("\n==================== MOCK EMAIL START ====================")
            print(f"Recipient: {recipient}")
            print(f"Subject: {subject}")
            print(f"Raw Token: {raw_token}")
            print(f"Text Content:\n{text_content}")
            print("====================  MOCK EMAIL END  ====================\n")
            return

        try:
            # Build message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = f"{settings.SMTP_FROM_NAME} <{settings.SMTP_FROM_EMAIL}>"
            message["To"] = recipient

            # Attach plain text and HTML versions
            message.attach(MIMEText(text_content, "plain"))
            message.attach(MIMEText(html_content, "html"))

            # Send asynchronously in a background thread executor to avoid blocking the event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(None, self._send_smtp_sync, recipient, message.as_string())
            logger.info("Successfully sent %s email to %s", email_type, recipient)
        except Exception as e:
            logger.error("Failed to send %s email to %s: %s", email_type, recipient, e)

    def _send_smtp_sync(self, recipient: str, message_str: str) -> None:
        """Synchronous SMTP connection and send handler executed in background thread."""
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=15)
        try:
            server.ehlo()
            if server.has_extn("STARTTLS"):
                server.starttls()
                server.ehlo()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
            server.sendmail(settings.SMTP_FROM_EMAIL, recipient, message_str)
        finally:
            server.close()
