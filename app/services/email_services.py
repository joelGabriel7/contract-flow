import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
from ..core.config import get_settings

settings = get_settings()

class EmailService:
    def __init__(self):
        self.smtp_server = settings.MAIL_SERVER
        self.smtp_port = settings.MAIL_PORT
        self.username = settings.MAIL_USERNAME
        self.password = settings.MAIL_PASSWORD
        self.from_email = settings.MAIL_FROM

    def _send_email(self, to_email: str, subject: str, html_content: str) -> None:
        message = MIMEMultipart()
        message["From"] = self.from_email
        message["To"] = to_email
        message["Subject"] = subject

        html_part = MIMEText(html_content, "html")
        message.attach(html_part)

        try:
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(message)
        except Exception as e:
            print(f"Error sending email: {e}")
            raise

    def _get_verification_template(self, code: str) -> str:
        return f"""
        <html>
            <body>
                <h2>Bienvenido a ContractFlow!</h2>
                <p>Para verificar tu cuenta, usa el siguiente código:</p>
                <h1 style="color: #4A90E2;">{code}</h1>
                <p>Este código expirará en 24 horas.</p>
            </body>
        </html>
        """
    def _get_reset_password_template(self, code: str) -> str:
        return f"""
        <html>
            <body>
                <h2>Reset Your Password</h2>
                <p>Your password reset code is:</p>
                <h1 style="color: #4A90E2;">{code}</h1>
                <p>This code will expire in 1 hour.</p>
                <p>If you didn't request this, please ignore this email.</p>
        </body>
        </html>
        """

    @staticmethod
    def generate_verification_code() -> str:
        return ''.join(secrets.choice('0123456789') for _ in range(6))

    def send_verification_email(self, to_email: str, code: str) -> None:
        html_content = self._get_verification_template(code)
        self._send_email(
            to_email=to_email,
            subject="Verifica tu cuenta de ContractFlow",
            html_content=html_content
        )
    def send_reset_password_email(self, to_email: str, code: str) -> None:
        html_content = self._get_reset_password_template(code)
        self._send_email(
            to_email=to_email,
            subject="Reset Your ContractFlow Password",
            html_content=html_content
        )

# Instancia global del servicio
email_service = EmailService()