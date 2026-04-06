import socket
from datetime import timedelta

from celery import shared_task
from flask import current_app
from flask_mail import Mail, Message

from internal.extension.redis_extension import redis_client


@shared_task
def send_verification_email_task(
    email: str,
    scene: str,
    client_ip: str,
) -> None:
    from app.http.app import injector
    from internal.service.email_service import EmailService

    mail = injector.get(Mail)
    original_server = getattr(mail, "server", None)
    service = EmailService(mail=mail)
    code = service.generate_verification_code()
    subject, body, html = EmailService.build_verification_email_content(code, scene)
    try:
        timeout = current_app.config.get("MAIL_TIMEOUT")
    except RuntimeError:
        timeout = None

    old_timeout = socket.getdefaulttimeout()

    try:
        socket.setdefaulttimeout(timeout)

        if original_server:
            try:
                address_infos = socket.getaddrinfo(original_server, None)
                ipv4_infos = [item for item in address_infos if item[0] == socket.AF_INET]
                if ipv4_infos:
                    mail.server = ipv4_infos[0][4][0]
            except OSError:
                mail.server = original_server

        msg = Message(
            subject=subject,
            recipients=[email],
            body=body,
            html=html,
        )
        mail.send(msg)
        redis_client.setex(EmailService._code_key(email, scene), timedelta(seconds=EmailService.CODE_TTL_SECONDS), code)
        redis_client.setex(
            EmailService._send_cooldown_key(email, scene),
            timedelta(seconds=EmailService.SEND_COOLDOWN_SECONDS),
            "1",
        )
        redis_client.setex(
            EmailService._send_cooldown_ip_key(client_ip, scene),
            timedelta(seconds=EmailService.SEND_COOLDOWN_SECONDS),
            "1",
        )
        redis_client.delete(EmailService._verify_attempt_key(email, scene))
        redis_client.delete(EmailService._verify_lock_key(email, scene))
        redis_client.delete(EmailService._send_pending_key(email, scene))
        redis_client.delete(EmailService._send_pending_ip_key(client_ip, scene))
    except Exception:
        redis_client.delete(EmailService._send_pending_key(email, scene))
        redis_client.delete(EmailService._send_pending_ip_key(client_ip, scene))
        raise
    finally:
        if original_server:
            mail.server = original_server
        socket.setdefaulttimeout(old_timeout)
