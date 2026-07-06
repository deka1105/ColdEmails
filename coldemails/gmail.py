"""Email delivery. Gmail API first, behind a Sender interface.

Auth uses an installed-app OAuth flow: point ``GMAIL_CREDENTIALS_FILE`` at the
OAuth client secret downloaded from Google Cloud; the token is cached at
``GMAIL_TOKEN_FILE`` after first consent.
"""

from __future__ import annotations

import base64
import mimetypes
import os
from abc import ABC, abstractmethod
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import encoders

from .config import env
from .models import Message

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def build_mime(sender: str, to: str, message: Message):
    """Assemble the MIME email: plain text, multipart when attachments exist."""
    if not message.attachments:
        mime = MIMEText(message.body)
    else:
        mime = MIMEMultipart()
        mime.attach(MIMEText(message.body))
        for path in message.attachments:
            ctype, encoding = mimetypes.guess_type(path)
            if ctype is None or encoding is not None:
                ctype = "application/octet-stream"
            maintype, subtype = ctype.split("/", 1)
            part = MIMEBase(maintype, subtype)
            with open(path, "rb") as f:
                part.set_payload(f.read())
            encoders.encode_base64(part)
            part.add_header(
                "Content-Disposition", "attachment",
                filename=os.path.basename(path),
            )
            mime.attach(part)
    mime["To"] = to
    mime["From"] = sender
    mime["Subject"] = message.subject
    return mime


class Sender(ABC):
    name: str = "base"

    @abstractmethod
    def send(self, to: str, message: Message) -> None:
        ...


class GmailSender(Sender):
    name = "gmail"

    def __init__(self) -> None:
        self.sender_email = env("SENDER_EMAIL", required=True)
        self.sender_name = env("SENDER_NAME") or self.sender_email
        self._service = None

    def _get_service(self):
        if self._service is not None:
            return self._service
        # Lazy imports so template/dry-run flows don't need Google libs.
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build

        token_file = env("GMAIL_TOKEN_FILE", "token.json")
        creds_file = env("GMAIL_CREDENTIALS_FILE", "credentials.json")

        creds = None
        import os

        if os.path.exists(token_file):
            creds = Credentials.from_authorized_user_file(token_file, SCOPES)
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(creds_file, SCOPES)
                creds = flow.run_local_server(port=0)
            with open(token_file, "w") as f:
                f.write(creds.to_json())

        self._service = build("gmail", "v1", credentials=creds)
        return self._service

    def send(self, to: str, message: Message) -> None:
        mime = MIMEText(message.body)
        mime["To"] = to
        mime["From"] = f"{self.sender_name} <{self.sender_email}>"
        mime["Subject"] = message.subject
        raw = base64.urlsafe_b64encode(mime.as_bytes()).decode()
        self._get_service().users().messages().send(
            userId="me", body={"raw": raw}
        ).execute()


class ConsoleSender(Sender):
    """Dry-run sender: prints instead of sending. Used by ``preview``."""

    name = "console"

    def send(self, to: str, message: Message) -> None:
        print(f"\n--- (dry-run) to: {to} ---")
        print(f"Subject: {message.subject}\n")
        print(message.body)
        print("--- end ---")
