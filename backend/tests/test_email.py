from unittest.mock import MagicMock, patch
from app.services.email import render_base_email_html, send_password_reset_otp_email, send_email


def test_base_email_template_rendering():
    html = render_base_email_html(
        title="Test Notification",
        content_html="<p>Testing content rendering</p>",
    )
    assert "<!DOCTYPE html>" in html
    assert "Smart Classroom Allocation System" in html
    assert "Testing content rendering" in html
    assert "Test Notification" in html


def test_send_password_reset_otp_email_format():
    with patch("app.services.email.send_email") as mock_send:
        mock_send.return_value = True

        result = send_password_reset_otp_email(
            to_email="faculty@college.edu",
            otp_code="123456",
            user_name="Dr. Smith",
        )

        assert result is True
        assert mock_send.called
        kwargs = mock_send.call_args[1]
        assert kwargs["to_email"] == "faculty@college.edu"
        assert "123456" in kwargs["html_body"]
        assert "Dr. Smith" in kwargs["html_body"]
        assert "123456" in kwargs["text_body"]


def test_send_email_smtp_connection_error_handled_gracefully():
    # When SMTP server is unreachable, send_email catches the exception and returns False without crashing
    with patch("smtplib.SMTP") as mock_smtp:
        mock_smtp.side_effect = ConnectionRefusedError("Connection refused")
        result = send_email(
            to_email="test@example.com",
            subject="Test",
            html_body="<p>Hello</p>",
        )
        assert result is False

