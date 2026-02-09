import smtplib
from email.message import EmailMessage


def send_reset_code_email(to_email, code):
    msg = EmailMessage()
    msg["Subject"] = "Password Reset Code"
    msg["From"] = "myudayipmail@gmail.com"
    msg["To"] = to_email

    msg.set_content(f"""
Hi,

Your password reset verification code is:

{code}

This code is valid for 10 minutes.

If you didn’t request this, you can ignore this email.
""")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login("myudayipmail@gmail.com", "cdph irgk xbdk fvzt")
        server.send_message(msg)
