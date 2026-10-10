import logging
import smtplib
from datetime import date, datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Optional, Tuple

from app.core.config import settings

logger = logging.getLogger(__name__)


def render_base_email_html(title: str, content_html: str) -> str:
    """Generate a clean, branded HTML email using a modern responsive layout."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #f1f5f9;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #1e293b;
      -webkit-font-smoothing: antialiased;
    }}
    .wrapper {{
      width: 100%;
      table-layout: fixed;
      background-color: #f1f5f9;
      padding: 40px 0;
    }}
    .container {{
      max-width: 580px;
      margin: 0 auto;
      background-color: #ffffff;
      border-radius: 12px;
      overflow: hidden;
      box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.07), 0 2px 4px -2px rgba(0, 0, 0, 0.05);
      border: 1px solid #e2e8f0;
    }}
    .header {{
      background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
      padding: 32px 36px;
      text-align: center;
    }}
    .header h1 {{
      margin: 0;
      color: #ffffff;
      font-size: 22px;
      font-weight: 700;
      letter-spacing: -0.02em;
    }}
    .header p {{
      margin: 6px 0 0 0;
      color: #bfdbfe;
      font-size: 13px;
      font-weight: 400;
    }}
    .body {{
      padding: 36px 36px 28px 36px;
      line-height: 1.6;
      font-size: 15px;
      color: #334155;
    }}
    .otp-box {{
      margin: 28px 0;
      padding: 24px;
      background: #eff6ff;
      border: 1.5px dashed #60a5fa;
      border-radius: 10px;
      text-align: center;
    }}
    .otp-label {{
      font-size: 12px;
      font-weight: 600;
      text-transform: uppercase;
      letter-spacing: 0.08em;
      color: #2563eb;
      margin-bottom: 8px;
    }}
    .otp-code {{
      font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, Courier, monospace;
      font-size: 36px;
      font-weight: 800;
      letter-spacing: 0.25em;
      color: #1e3a8a;
      display: inline-block;
      user-select: all;
    }}
    .warning {{
      background-color: #fffbeb;
      border-left: 4px solid #f59e0b;
      padding: 12px 16px;
      border-radius: 6px;
      font-size: 13px;
      color: #92400e;
      margin: 20px 0;
    }}
    .footer {{
      background-color: #f8fafc;
      padding: 24px 36px;
      text-align: center;
      border-top: 1px solid #f1f5f9;
      font-size: 12px;
      color: #64748b;
    }}
    .footer p {{
      margin: 4px 0;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <table class="container" role="presentation" cellpadding="0" cellspacing="0" width="100%">
      <tr>
        <td class="header">
          <h1>Smart Classroom Allocation System</h1>
          <p>Automated & Rule-Driven Campus Space Management</p>
        </td>
      </tr>
      <tr>
        <td class="body">
          {content_html}
        </td>
      </tr>
      <tr>
        <td class="footer">
          <p>This is an automated system notification from {settings.EMAILS_FROM_NAME}.</p>
          <p>If you did not request this email, please contact IT support immediately.</p>
        </td>
      </tr>
    </table>
  </div>
</body>
</html>"""


from email.mime.base import MIMEBase
from email import encoders

def send_email(
    to_email: str,
    subject: str,
    html_body: str,
    text_body: Optional[str] = None,
    attachments: Optional[List[Tuple[str, bytes, str]]] = None,
) -> bool:
    """Dispatch an email via SMTP (configured for Mailpit or production SMTP).
    attachments is an optional list of tuples: (filename, content_bytes, mime_type)
    """
    try:
        from_email = settings.MAIL_FROM or settings.EMAILS_FROM_EMAIL or "no-reply@smartclassroom.edu"
        msg = MIMEMultipart("mixed")
        msg["Subject"] = subject
        msg["From"] = f"{settings.EMAILS_FROM_NAME} <{from_email}>"
        msg["To"] = to_email

        body_part = MIMEMultipart("alternative")
        if text_body:
            body_part.attach(MIMEText(text_body, "plain", "utf-8"))
        body_part.attach(MIMEText(html_body, "html", "utf-8"))
        msg.attach(body_part)

        if attachments:
            for filename, content, mime_type in attachments:
                maintype, subtype = mime_type.split("/", 1) if "/" in mime_type else ("application", "octet-stream")
                part = MIMEBase(maintype, subtype)
                part.set_payload(content)
                encoders.encode_base64(part)
                part.add_header("Content-Disposition", f'attachment; filename="{filename}"')
                msg.attach(part)

        with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
            if settings.SMTP_TLS:
                server.starttls()
            if settings.SMTP_USER and settings.SMTP_PASSWORD:
                if server.has_extn("AUTH"):
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                else:
                    logger.debug("SMTP server does not support AUTH extension; skipping authentication.")
            server.sendmail(from_email, [to_email], msg.as_string())
        logger.info(f"Email successfully sent to {to_email} with subject: {subject}")
        return True
    except Exception as exc:
        logger.error(
            f"Could not send email to {to_email} via {settings.SMTP_HOST}:{settings.SMTP_PORT}: {exc}",
            exc_info=True,
        )
        return False


def send_password_reset_otp_email(
    to_email: str,
    otp_code: str,
    user_name: Optional[str] = None,
) -> bool:
    """Send a password reset OTP email using the branded template."""
    greeting = f"Hello {user_name}," if user_name else "Hello,"
    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">{greeting}</p>
      <p>We received a request to reset the password for your account in the <strong>Smart Classroom Allocation System</strong>.</p>
      <p>Use the 6-digit verification code below to complete your password reset:</p>
      
      <div class="otp-box">
        <div class="otp-label">Verification Code</div>
        <div class="otp-code">{otp_code}</div>
      </div>
      
      <div class="warning">
        <strong>Security Notice:</strong> This code expires in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong> and can only be used once. Do not share this code with anyone.
      </div>
      
      <p style="margin-bottom: 0;">If you did not request a password reset, you can safely ignore this email; your account remains secure.</p>
    """
    
    html_body = render_base_email_html(
        title="Password Reset Verification Code",
        content_html=content_html,
    )
    
    text_body = (
        f"{greeting}\n\n"
        f"Your password reset verification code for the Smart Classroom Allocation System is: {otp_code}\n\n"
        f"This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.\n"
        f"If you did not request this, please ignore this email.\n"
    )
    
    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Your Password Reset Code",
        html_body=html_body,
        text_body=text_body,
    )


def send_user_welcome_email(
    to_email: str,
    user_name: str,
    role: str,
    temp_password: str,
) -> bool:
    """Send welcome email with auto-generated temporary password and password change instructions."""
    greeting = f"Hello {user_name}," if user_name else "Hello,"
    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">{greeting}</p>
      <p>An account has been created for you in the <strong>Smart Classroom Allocation System</strong> with the role: <strong>{role}</strong>.</p>
      <p>Here is your temporary password to access your portal:</p>
      
      <div class="otp-box">
        <div class="otp-label">Temporary Password</div>
        <div class="otp-code" style="font-size: 24px; letter-spacing: 0.1em;">{temp_password}</div>
      </div>
      
      <div class="warning">
        <strong>Important Security Notice:</strong> For security reasons, you will be required to change your password immediately upon your first login.
      </div>
      
      <p style="margin-bottom: 0;">Please log in to the portal and update your password to secure your account.</p>
    """
    
    html_body = render_base_email_html(
        title=f"Welcome to {settings.APP_NAME} - Account Created",
        content_html=content_html,
    )
    
    text_body = (
        f"{greeting}\n\n"
        f"An account has been created for you in {settings.APP_NAME} with role: {role}.\n\n"
        f"Your temporary password is: {temp_password}\n\n"
        f"For security reasons, you will be required to change your password upon your first login.\n\n"
        f"Please log in and update your password immediately.\n"
    )
    
    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Welcome - Your Temporary Account Credentials",
        html_body=html_body,
        text_body=text_body,
    )


def send_booking_acknowledgement_email(
    to_email: str,
    reference: str,
    cancel_token: str,
    student_name: str,
    room_name: str,
    date_str: str,
    slot_label: str,
    purpose: str,
    expected_strength: int,
    requires_hod_approval: bool = False,
) -> bool:
    """Send immediate booking acknowledgement email with reference code and secure cancellation link."""
    cancel_url = f"{settings.BACKEND_CORS_ORIGINS[0] if isinstance(settings.BACKEND_CORS_ORIGINS, list) and settings.BACKEND_CORS_ORIGINS else 'http://localhost:3000'}/cancel?token={cancel_token}"
    approval_notice = (
        "<p style='color: #4338ca; background: #e0e7ff; padding: 10px; border-radius: 6px; font-size: 13px;'>"
        "<strong>Note:</strong> This booking requires Coordinator and Department HOD approvals prior to confirmation."
        "</p>"
        if requires_hod_approval
        else "<p style='color: #1e40af; background: #dbeafe; padding: 10px; border-radius: 6px; font-size: 13px;'>"
        "<strong>Status:</strong> Your request has been submitted and is currently <strong>PENDING</strong> Block Coordinator review."
        "</p>"
    )

    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">Hello {student_name},</p>
      <p>Thank you for submitting your room allocation request. Your booking request has been received and logged in the system.</p>
      
      <div class="otp-box" style="border: 1.5px solid #3b82f6; background: #f8fafc; text-align: left; padding: 20px;">
        <div style="font-size: 12px; font-weight: 700; color: #2563eb; text-transform: uppercase; margin-bottom: 8px;">Booking Reference</div>
        <div style="font-family: monospace; font-size: 24px; font-weight: 800; color: #1e3a8a; margin-bottom: 16px;">{reference}</div>
        
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr><td style="padding: 4px 0; color: #64748b; width: 140px;"><strong>Room:</strong></td><td style="color: #0f172a;">{room_name}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Date:</strong></td><td style="color: #0f172a;">{date_str}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Time Slot:</strong></td><td style="color: #0f172a;">{slot_label}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Purpose:</strong></td><td style="color: #0f172a;">{purpose}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Expected Size:</strong></td><td style="color: #0f172a;">{expected_strength} attendees</td></tr>
        </table>
      </div>

      {approval_notice}

      <div style="margin: 24px 0; padding: 16px; background: #fff1f2; border: 1px solid #fecdd3; border-radius: 8px;">
        <strong style="color: #9f1239;">Need to cancel this booking?</strong>
        <p style="margin: 6px 0 12px 0; font-size: 13px; color: #881337;">You can cancel your booking anytime before the event using your secure one-click cancellation link:</p>
        <a href="{cancel_url}" style="display: inline-block; background: #e11d48; color: #ffffff; text-decoration: none; padding: 10px 18px; border-radius: 6px; font-size: 13px; font-weight: 600;">Cancel My Booking</a>
        <p style="margin: 10px 0 0 0; font-size: 11px; color: #9f1239; word-break: break-all;">Link: {cancel_url}</p>
      </div>

      <p style="font-size: 13px; color: #64748b;">You will receive another email as soon as the coordinator decides on your allocation request.</p>
    """

    text_body = (
        f"Hello {student_name},\n\n"
        f"Your room allocation request has been received with reference: {reference}\n\n"
        f"Details:\n"
        f"- Room: {room_name}\n"
        f"- Date: {date_str}\n"
        f"- Slot: {slot_label}\n"
        f"- Purpose: {purpose}\n"
        f"- Attendees: {expected_strength}\n\n"
        f"To cancel this booking at any time, use this secure link:\n"
        f"{cancel_url}\n"
    )

    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Booking Acknowledged — {reference} ({room_name})",
        html_body=render_base_email_html(f"Booking Request Acknowledged: {reference}", content_html),
        text_body=text_body,
    )


def send_booking_cancellation_email(
    to_email: str,
    reference: str,
    student_name: str,
    room_name: str,
    date_str: str,
    slot_label: str,
) -> bool:
    """Send confirmation email when a booking has been cancelled."""
    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">Hello {student_name},</p>
      <p>Your room booking has been successfully <strong>CANCELLED</strong>.</p>

      <div class="otp-box" style="border: 1.5px solid #cbd5e1; background: #f8fafc; text-align: left; padding: 20px;">
        <div style="font-size: 12px; font-weight: 700; color: #64748b; text-transform: uppercase; margin-bottom: 8px;">Cancelled Booking Reference</div>
        <div style="font-family: monospace; font-size: 22px; font-weight: 800; color: #334155; margin-bottom: 12px;">{reference}</div>
        
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr><td style="padding: 4px 0; color: #64748b; width: 140px;"><strong>Room:</strong></td><td style="color: #0f172a;">{room_name}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Date:</strong></td><td style="color: #0f172a;">{date_str}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Time Slot:</strong></td><td style="color: #0f172a;">{slot_label}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Status:</strong></td><td style="color: #dc2626; font-weight: 700;">CANCELLED</td></tr>
        </table>
      </div>

      <p>The time slot for {room_name} has now been released and is available for other campus members.</p>
    """

    text_body = (
        f"Hello {student_name},\n\n"
        f"Your booking {reference} for {room_name} on {date_str} ({slot_label}) has been cancelled.\n"
        f"The slot has been released back into the available pool.\n"
    )

    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Booking Cancelled — {reference}",
        html_body=render_base_email_html(f"Booking Cancelled: {reference}", content_html),
        text_body=text_body,
    )


def send_cancellation_otp_email(
    to_email: str,
    reference: str,
    otp_code: str,
    student_name: Optional[str] = None,
) -> bool:
    """Send a cancellation verification OTP code."""
    greeting = f"Hello {student_name}," if student_name else "Hello,"
    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">{greeting}</p>
      <p>You requested a one-time verification code to cancel booking <strong>{reference}</strong>.</p>
      
      <div class="otp-box">
        <div class="otp-label">Cancellation Code</div>
        <div class="otp-code">{otp_code}</div>
      </div>
      
      <div class="warning">
        <strong>Security Notice:</strong> This code expires in <strong>{settings.OTP_EXPIRE_MINUTES} minutes</strong> and can only be used once. If you did not request this cancellation, please ignore this email.
      </div>
    """

    text_body = (
        f"{greeting}\n\n"
        f"Your cancellation verification code for booking {reference} is: {otp_code}\n"
        f"This code will expire in {settings.OTP_EXPIRE_MINUTES} minutes.\n"
    )

    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Cancellation Code for {reference}",
        html_body=render_base_email_html(f"Cancellation OTP: {reference}", content_html),
        text_body=text_body,
    )


def send_waitlist_notification_email(
    to_email: str,
    student_name: str,
    room_name: str,
    date_str: str,
    slot_label: str,
) -> bool:
    """Send alert to the waitlisted student when a room and slot become free."""
    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">Hello {student_name},</p>
      <p style="color: #047857; font-size: 15px; font-weight: 600;">Good news! A previously booked room and slot you were waitlisted for has just become available!</p>

      <div class="otp-box" style="border: 1.5px solid #10b981; background: #ecfdf5; text-align: left; padding: 20px;">
        <div style="font-size: 12px; font-weight: 700; color: #059669; text-transform: uppercase; margin-bottom: 8px;">Available Room & Slot</div>
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr><td style="padding: 4px 0; color: #065f46; width: 140px;"><strong>Room:</strong></td><td style="color: #0f172a; font-weight: 600;">{room_name}</td></tr>
          <tr><td style="padding: 4px 0; color: #065f46;"><strong>Date:</strong></td><td style="color: #0f172a;">{date_str}</td></tr>
          <tr><td style="padding: 4px 0; color: #065f46;"><strong>Time Slot:</strong></td><td style="color: #0f172a;">{slot_label}</td></tr>
        </table>
      </div>

      <p>Room allocations operate on a first-come, first-served basis. Please visit the Smart Classroom Allocation portal immediately to book this room before another request is approved.</p>
    """

    text_body = (
        f"Hello {student_name},\n\n"
        f"A room you were waitlisted for is now available!\n"
        f"- Room: {room_name}\n"
        f"- Date: {date_str}\n"
        f"- Time Slot: {slot_label}\n\n"
        f"Please visit the portal now to submit your booking request.\n"
    )

    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Slot Available Alert — {room_name} on {date_str}",
        html_body=render_base_email_html("Waitlist Slot Now Available", content_html),
        text_body=text_body,
    )


def generate_ics_calendar(
    summary: str,
    description: str,
    location: str,
    event_date: str,
    start_time_str: str,
    end_time_str: str,
    uid: str,
) -> bytes:
    """Generate RFC 5545 compliant iCalendar (.ics) bytes."""
    import uuid
    from datetime import datetime

    # Parse date and times
    # date_str format: YYYY-MM-DD
    # start_time_str format: HH:MM or HH:MM:SS
    date_parts = event_date.split("-")
    year, month, day = int(date_parts[0]), int(date_parts[1]), int(date_parts[2])

    s_time_parts = start_time_str.split(":")
    e_time_parts = end_time_str.split(":")

    sh, sm = int(s_time_parts[0]), int(s_time_parts[1])
    eh, em = int(e_time_parts[0]), int(e_time_parts[1])

    dtstart = f"{year:04d}{month:02d}{day:02d}T{sh:02d}{sm:02d}00"
    dtend = f"{year:04d}{month:02d}{day:02d}T{eh:02d}{em:02d}00"
    now_stamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    # Clean description and summary for ics
    clean_summary = summary.replace("\n", " ").replace("\r", "")
    clean_desc = description.replace("\r", "").replace("\n", "\\n")
    clean_loc = location.replace("\n", " ").replace("\r", "")

    ics_content = (
        "BEGIN:VCALENDAR\r\n"
        "VERSION:2.0\r\n"
        "PRODID:-//Smart Classroom Allocation System//EN\r\n"
        "CALSCALE:GREGORIAN\r\n"
        "METHOD:REQUEST\r\n"
        "BEGIN:VEVENT\r\n"
        f"UID:{uid}@smartclassroom\r\n"
        f"DTSTAMP:{now_stamp}\r\n"
        f"DTSTART:{dtstart}\r\n"
        f"DTEND:{dtend}\r\n"
        f"SUMMARY:{clean_summary}\r\n"
        f"DESCRIPTION:{clean_desc}\r\n"
        f"LOCATION:{clean_loc}\r\n"
        "STATUS:CONFIRMED\r\n"
        "END:VEVENT\r\n"
        "END:VCALENDAR\r\n"
    )
    return ics_content.encode("utf-8")


def send_booking_approved_email(
    to_email: str,
    reference: str,
    student_name: str,
    room_name: str,
    block_name: str,
    date_str: str,
    slot_label: str,
    start_time_str: str,
    end_time_str: str,
    purpose: str,
    decision_note: Optional[str] = None,
) -> bool:
    """Send confirmation email with ICS calendar attachment upon full approval."""
    note_html = (
        f'<div style="margin: 16px 0; padding: 12px; background: #f0fdf4; border-left: 4px solid #22c419; font-size: 13px; color: #166534;">'
        f"<strong>Approver Note:</strong> {decision_note}</div>"
        if decision_note
        else ""
    )

    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">Hello {student_name},</p>
      <p style="color: #15803d; font-size: 15px; font-weight: 600;">Congratulations! Your room allocation request has been officially <strong>APPROVED</strong>.</p>
      
      <div class="otp-box" style="border: 1.5px solid #22c55e; background: #f0fdf4; text-align: left; padding: 20px;">
        <div style="font-size: 12px; font-weight: 700; color: #15803d; text-transform: uppercase; margin-bottom: 8px;">Confirmed Booking Reference</div>
        <div style="font-family: monospace; font-size: 24px; font-weight: 800; color: #14532d; margin-bottom: 16px;">{reference}</div>
        
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr><td style="padding: 4px 0; color: #4b5563; width: 140px;"><strong>Room:</strong></td><td style="color: #0f172a; font-weight: 600;">{room_name} ({block_name})</td></tr>
          <tr><td style="padding: 4px 0; color: #4b5563;"><strong>Date:</strong></td><td style="color: #0f172a;">{date_str}</td></tr>
          <tr><td style="padding: 4px 0; color: #4b5563;"><strong>Time Slot:</strong></td><td style="color: #0f172a;">{slot_label} ({start_time_str} - {end_time_str})</td></tr>
          <tr><td style="padding: 4px 0; color: #4b5563;"><strong>Purpose:</strong></td><td style="color: #0f172a;">{purpose}</td></tr>
          <tr><td style="padding: 4px 0; color: #4b5563;"><strong>Status:</strong></td><td style="color: #15803d; font-weight: 700;">APPROVED</td></tr>
        </table>
      </div>

      {note_html}

      <p style="font-size: 13px; color: #475569;">
        A calendar invite file (<code>booking_{reference}.ics</code>) is attached to this email. You can add it directly to Google Calendar, Apple Calendar, or Microsoft Outlook.
      </p>
    """

    text_body = (
        f"Hello {student_name},\n\n"
        f"Your booking {reference} has been APPROVED!\n\n"
        f"Details:\n"
        f"- Room: {room_name} ({block_name})\n"
        f"- Date: {date_str}\n"
        f"- Time Slot: {slot_label} ({start_time_str} - {end_time_str})\n"
        f"- Purpose: {purpose}\n"
        + (f"- Approver Note: {decision_note}\n\n" if decision_note else "\n")
        + f"An .ics calendar invitation is attached.\n"
    )

    ics_bytes = generate_ics_calendar(
        summary=f"Room Booking: {room_name} - {purpose}",
        description=f"Booking Reference: {reference}\\nRoom: {room_name} ({block_name})\\nPurpose: {purpose}",
        location=f"{room_name}, {block_name}",
        event_date=date_str,
        start_time_str=start_time_str,
        end_time_str=end_time_str,
        uid=reference,
    )

    attachments = [(f"booking_{reference}.ics", ics_bytes, "text/calendar")]

    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Booking Confirmed — {reference} ({room_name})",
        html_body=render_base_email_html(f"Booking Approved: {reference}", content_html),
        text_body=text_body,
        attachments=attachments,
    )


def send_booking_rejected_email(
    to_email: str,
    reference: str,
    student_name: str,
    room_name: str,
    date_str: str,
    slot_label: str,
    rejection_reason: Optional[str] = None,
) -> bool:
    """Send notification email when a booking has been rejected."""
    reason_text = rejection_reason or "No specific reason provided."
    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">Hello {student_name},</p>
      <p style="color: #b91c1c; font-size: 15px; font-weight: 600;">We regret to inform you that your room booking request has been <strong>REJECTED</strong>.</p>

      <div class="otp-box" style="border: 1.5px solid #f87171; background: #fef2f2; text-align: left; padding: 20px;">
        <div style="font-size: 12px; font-weight: 700; color: #b91c1c; text-transform: uppercase; margin-bottom: 8px;">Booking Reference</div>
        <div style="font-family: monospace; font-size: 22px; font-weight: 800; color: #991b1b; margin-bottom: 12px;">{reference}</div>
        
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr><td style="padding: 4px 0; color: #64748b; width: 140px;"><strong>Room:</strong></td><td style="color: #0f172a;">{room_name}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Date:</strong></td><td style="color: #0f172a;">{date_str}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Time Slot:</strong></td><td style="color: #0f172a;">{slot_label}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Status:</strong></td><td style="color: #b91c1c; font-weight: 700;">REJECTED</td></tr>
        </table>
      </div>

      <div style="margin: 16px 0; padding: 14px; background: #fff1f2; border-left: 4px solid #e11d48; font-size: 13px; color: #9f1239;">
        <strong>Reason for rejection:</strong><br />
        <span style="font-style: italic;">{reason_text}</span>
      </div>

      <p style="font-size: 13px; color: #64748b;">
        You may check availability and submit an alternate booking request on the portal.
      </p>
    """

    text_body = (
        f"Hello {student_name},\n\n"
        f"Your booking request {reference} for {room_name} on {date_str} ({slot_label}) has been REJECTED.\n\n"
        f"Reason for rejection:\n"
        f"{reason_text}\n\n"
        f"You may search for other available rooms on the Smart Classroom Allocation portal.\n"
    )

    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Booking Rejected — {reference}",
        html_body=render_base_email_html(f"Booking Rejected: {reference}", content_html),
        text_body=text_body,
    )


def send_booking_relocated_email(
    to_email: str,
    recipient_name: str,
    reference: str,
    original_room_name: str,
    replacement_room_name: Optional[str],
    replacement_block_name: Optional[str],
    booking_date: date,
    slot_label: str,
    reason: str,
) -> bool:
    """Send an automated notification when a booking is relocated due to room maintenance or exam block."""
    date_str = booking_date.strftime("%A, %B %d, %Y")
    replacement_info = (
        f"{replacement_room_name} ({replacement_block_name})"
        if replacement_room_name
        else "Pending manual coordinator assignment"
    )

    content_html = f"""
      <p style="font-size: 15px; line-height: 1.6; color: #334155;">
        Dear <strong>{recipient_name}</strong>,
      </p>
      <p style="font-size: 14px; line-height: 1.6; color: #334155;">
        Due to scheduled <strong>{reason}</strong>, your venue for booking <strong>{reference}</strong> has been adjusted.
      </p>

      <div style="background-color: #fffbeb; border: 1px solid #fde68a; border-radius: 8px; padding: 20px; margin: 20px 0;">
        <div style="font-size: 12px; font-weight: 700; color: #b45309; text-transform: uppercase; margin-bottom: 8px;">Booking Update: RELOCATED</div>
        <div style="font-family: monospace; font-size: 20px; font-weight: 800; color: #92400e; margin-bottom: 12px;">{reference}</div>
        
        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr><td style="padding: 4px 0; color: #64748b; width: 160px;"><strong>Original Venue:</strong></td><td style="color: #0f172a; text-decoration: line-through;">{original_room_name}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>New Proposed Room:</strong></td><td style="color: #15803d; font-weight: 700;">{replacement_info}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Date:</strong></td><td style="color: #0f172a;">{date_str}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Time Slot:</strong></td><td style="color: #0f172a;">{slot_label}</td></tr>
          <tr><td style="padding: 4px 0; color: #64748b;"><strong>Status:</strong></td><td style="color: #d97706; font-weight: 700;">RELOCATED (Pending Confirmation)</td></tr>
        </table>
      </div>

      <p style="font-size: 13px; color: #64748b;">
        The block coordinator will finalize the updated room reservation shortly. You will be notified once confirmed.
      </p>
    """

    text_body = (
        f"Hello {recipient_name},\n\n"
        f"Your booking {reference} on {date_str} ({slot_label}) has been relocated due to {reason}.\n"
        f"Original Room: {original_room_name}\n"
        f"Proposed Replacement Room: {replacement_info}\n"
        f"Status: RELOCATED (Pending coordinator confirmation)\n\n"
        f"Thank you for your patience.\n"
    )

    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Notice: Venue Relocated for Booking {reference}",
        html_body=render_base_email_html(f"Venue Relocation: {reference}", content_html),
        text_body=text_body,
    )


def send_booking_reminder_email(
    to_email: str,
    reference: str,
    student_name: str,
    room_name: str,
    block_name: str,
    date_str: str,
    slot_label: str,
    start_time_str: str,
    end_time_str: str,
    purpose: str,
) -> bool:
    """Send reminder email 1 hour before scheduled booking start time."""
    content_html = f"""
      <p style="font-size: 16px; font-weight: 600; color: #0f172a; margin-top: 0;">Hello {student_name},</p>
      <p style="color: #0369a1; font-size: 15px; font-weight: 600;">
        This is a friendly reminder that your booking starts in <strong>1 hour</strong>.
      </p>

      <div class="otp-box" style="border: 1.5px solid #0284c7; background: #f0f9ff; text-align: left; padding: 20px;">
        <div style="font-size: 12px; font-weight: 700; color: #0369a1; text-transform: uppercase; margin-bottom: 8px;">Upcoming Booking Reference</div>
        <div style="font-family: monospace; font-size: 24px; font-weight: 800; color: #0c4a6e; margin-bottom: 16px;">{reference}</div>

        <table style="width: 100%; border-collapse: collapse; font-size: 14px;">
          <tr><td style="padding: 4px 0; color: #4b5563; width: 140px;"><strong>Room:</strong></td><td style="color: #0f172a; font-weight: 600;">{room_name} ({block_name})</td></tr>
          <tr><td style="padding: 4px 0; color: #4b5563;"><strong>Date:</strong></td><td style="color: #0f172a;">{date_str}</td></tr>
          <tr><td style="padding: 4px 0; color: #4b5563;"><strong>Time:</strong></td><td style="color: #0f172a; font-weight: 600;">{slot_label} ({start_time_str} - {end_time_str})</td></tr>
          <tr><td style="padding: 4px 0; color: #4b5563;"><strong>Purpose:</strong></td><td style="color: #0f172a;">{purpose}</td></tr>
        </table>
      </div>

      <p style="font-size: 13px; color: #64748b; margin-top: 20px;">
        Please ensure you arrive on time. If your plans have changed and you no longer need this venue, please cancel your booking so that other students can utilize the room.
      </p>
    """

    text_body = (
        f"Hello {student_name},\n\n"
        f"Reminder: Your booking {reference} for room {room_name} ({block_name}) starts in 1 hour!\n"
        f"Date: {date_str}\n"
        f"Time: {slot_label} ({start_time_str} - {end_time_str})\n"
        f"Purpose: {purpose}\n\n"
        f"Please arrive on time or cancel if you no longer require the room.\n"
    )

    return send_email(
        to_email=to_email,
        subject=f"[{settings.APP_NAME}] Reminder: Your Booking {reference} Starts in 1 Hour",
        html_body=render_base_email_html(f"Booking Reminder: {reference}", content_html),
        text_body=text_body,
    )




