import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import secrets
from ..core.config import get_settings
from ..models.organization import OrganizationRole
from typing import Optional

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

    def send_invitation_email(
        self,
        to_email: str,
        organization_name: str,
        inviter_name: str,
        invitation_token: str,
        role: OrganizationRole,
        custom_message: Optional[str] = None,
    ) -> None:
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2C5282;">Invitación a {organization_name}</h2>
                    
                    <p>Hola,</p>
                    
                    <p>{inviter_name} te ha invitado a unirte a <strong>{organization_name}</strong> como <strong>{role.value}</strong>.</p>
                    
                    {f'<p style="background-color: #F7FAFC; padding: 15px; border-radius: 5px;">Mensaje del invitador:<br/>{custom_message}</p>' if custom_message else ""}
                    
                    <div style="background-color: #EBF8FF; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p><strong>¿Cómo aceptar la invitación?</strong></p>
                        <ol>
                            <li>Inicia sesión en ContractFlow (<a href="{"http://localhost:8000/api/auth/login"}">ir al login</a>)</li>
                            <li>Ve a la sección "Invitaciones Pendientes" (<a href="{"http://localhost:8000/api/auth/login"}/invitations">ir a invitaciones</a>)</li>
                            <li>Ingresa el siguiente código cuando se te solicite:</li>
                        </ol>
                        
                        <div style="background: white; padding: 15px; text-align: center; border-radius: 5px; margin: 15px 0;">
                            <code style="font-size: 24px; color: #4A90E2; letter-spacing: 2px;">{invitation_token}</code>
                        </div>
                    </div>
                    
                    <p><strong>Información importante:</strong></p>
                    <ul style="padding-left: 20px;">
                        <li>Esta invitación expirará en 7 días</li>
                        <li>El código solo puede usarse una vez</li>
                        <li>Como {role.value}, podrás {self._get_role_description(role)}</li>
                    </ul>
                    
                    <p style="color: #666; font-size: 0.9em; margin-top: 30px;">
                        Si no esperabas esta invitación, puedes ignorar este correo.
                        Para más información, visita nuestra pagina ContractFlow.com
                    </p>
                </div>
            </body>
        </html>
        """

        self._send_email(
            to_email=to_email,
            subject=f"Invitación para unirte a {organization_name} en ContractFlow",
            html_content=html_content,
        )

    def _get_role_description(self, role: OrganizationRole) -> str:
        """Retorna una descripción de las capacidades del rol."""
        descriptions = {
            OrganizationRole.ADMIN: "gestionar miembros, contratos y configuraciones de la organización",
            OrganizationRole.EDITOR: "crear y editar contratos, ver miembros del equipo",
            OrganizationRole.VIEWER: "ver contratos y miembros del equipo",
        }
        return descriptions.get(role, "acceder a funcionalidades básicas")

    @staticmethod
    def generate_verification_code() -> str:
        return "".join(secrets.choice("0123456789") for _ in range(6))

    def send_verification_email(self, to_email: str, code: str) -> None:
        html_content = self._get_verification_template(code)
        self._send_email(
            to_email=to_email,
            subject="Verifica tu cuenta de ContractFlow",
            html_content=html_content,
        )

    def send_reset_password_email(self, to_email: str, code: str) -> None:
        html_content = self._get_reset_password_template(code)
        self._send_email(
            to_email=to_email,
            subject="Reset Your ContractFlow Password",
            html_content=html_content,
        )

    def send_invitation_cancelled_email(self, to_email: str, organization_name: str):
        html_content = f"""
                <h2>Invitacion Cancelada</h2>
                <p>La invitación para unirte a {organization_name} ha sido cancelada.</p>
                <p>Si crees que esto es un error, contacta al administrador de la organización.</p>
        """
        self._send_email(
            to_email=to_email,
            subject=f"Invitación a {organization_name} Cancelada",
            html_content=html_content,
        )

    def send_member_remove_email(self, to_email: str, organization_name: str):
        html_content = f"""
                <h2>Membresia Finalizada</h2>
                <p>Ya no eres miembro de: {organization_name}</p>
                <p>Si tienes preguntas, por favor contacta al administrador de la organización.</p>
        """
        self._send_email(
            to_email=to_email,
            subject=f"Membresia en {organization_name} Finalizada",
            html_content=html_content,
        )

    def send_role_update_email(self, to_email: str, organization_name: str, new_role: OrganizationRole):
        html_content = f"""
                <h2>Su Rol ha sido actualizadp en {organization_name} </h2>
                <p>Tu rol ha sido actualizado a {new_role.value}</p>
                <p>Este cambio afecta tus permisos en la organización.</p>
        """
        self._send_email(
            to_email=to_email,
            subject=f"Actualización de rol en {organization_name}",
            html_content=html_content,
        )

    def send_invitation_to_unregistered_email(
    self,
    to_email: str,
    organization_name: str,
    inviter_name: str,
    invitation_token: str,
    role: OrganizationRole,
    custom_message: Optional[str] = None
    ) -> None:
        html_content = f"""
        <html>
            <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
                <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                    <h2 style="color: #2C5282;">Invitación a {organization_name}</h2>
                    
                    <p>Hola,</p>
                    
                    <p>{inviter_name} te ha invitado a unirte a <strong>{organization_name}</strong> como <strong>{role.value}</strong>.</p>
                    
                    {f'<p style="background-color: #F7FAFC; padding: 15px; border-radius: 5px;">Mensaje del invitador:<br/>{custom_message}</p>' if custom_message else ''}
                    
                    <div style="background-color: #EBF8FF; padding: 20px; border-radius: 8px; margin: 20px 0;">
                        <p><strong>¿Cómo aceptar la invitación?</strong></p>
                        <ol>
                            <li>Primero, necesitas <a href="{''}/register">crear una cuenta</a> en ContractFlow</li>
                            <li>Después de registrarte, inicia sesión</li>
                            <li>Ve a la sección "Invitaciones Pendientes"</li>
                            <li>Ingresa el siguiente código cuando se te solicite:</li>
                        </ol>
                        
                        <div style="background: white; padding: 15px; text-align: center; border-radius: 5px; margin: 15px 0;">
                            <code style="font-size: 24px; color: #4A90E2; letter-spacing: 2px;">{invitation_token}</code>
                        </div>
                    </div>
                    
                    <p><strong>Información importante:</strong></p>
                    <ul style="padding-left: 20px;">
                        <li>Esta invitación expirará en 7 días</li>
                        <li>El código solo puede usarse una vez</li>
                        <li>Debes usar el mismo email para registrarte ({to_email})</li>
                    </ul>
                </div>
            </body>
        </html>
        """
    
        self._send_email(
            to_email=to_email,
            subject=f"Invitación para unirte a {organization_name} en ContractFlow",
            html_content=html_content
        )
# Instancia global del servicio
email_service = EmailService()
