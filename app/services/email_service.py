import smtplib
from app.logger import logger
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from dotenv import load_dotenv


def send_email_with_attachment(
        from_email: str,
        to_email: str,
        subject: str,
        message: str,
        pdf_path: str
        ):
    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    with open(pdf_path, "rb") as pdf_file:
        pdf_attachment = MIMEApplication(pdf_file.read(), _subtype="pdf")
        pdf_attachment.add_header('Content-Disposition', 'attachment', filename="attachment.pdf")
        msg.attach(pdf_attachment)

    smtp_server = "smtp.gmail.com"
    smtp_port = 587
    password = "iile fnhj pyct dgcf"

    try:
        with smtplib.SMTP(smtp_server, smtp_port) as server:
            server.starttls()
            server.login(from_email, password)
            server.send_message(msg)
        logger.info(f"Email with attachment sent successfully to {to_email}!")
    except Exception as e:
        logger.error(f"Failed to send email: {e}")

