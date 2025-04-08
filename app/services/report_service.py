from datetime import datetime
from dateutil.relativedelta import relativedelta
import boto3
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.clients.client_details import Client
from app.models.accounts.single_account import SingleAccount
from app.models.accounts.joint_account import JointAccount
from app.models.accounts.joint_account_mapping import JointAccountMapping
from app.logger import logger

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


class ReportService:
    def __init__(self, db: AsyncSession, s3_client):
        self.db = db
        self.s3_client = s3_client
        self.bucket_name = "plus91backoffice"

    async def verify_user(self, broker_code: str, pan_no: str) -> Client:
        """Verify the client based on broker_code and pan_no."""
        stmt = select(Client).where(
            Client.broker_code == broker_code,
            Client.pan_no == pan_no
        )
        result = await self.db.execute(stmt)
        client = result.scalars().first()
        if not client:
            raise ValueError("Client not found or PAN number does not match")
        return client

    async def get_accounts(self, client: Client) -> dict:
        """Retrieve single and joint accounts for the client."""
        stmt_single = select(SingleAccount).where(
            SingleAccount.single_account_id == client.account_id
        )
        result_single = await self.db.execute(stmt_single)
        single_account = result_single.scalars().first()

        stmt_mappings = select(JointAccountMapping).where(
            JointAccountMapping.account_id == single_account.single_account_id
        )
        result_mappings = await self.db.execute(stmt_mappings)
        mappings = result_mappings.scalars().all()
        joint_account_ids = [m.joint_account_id for m in mappings]

        stmt_joint = select(JointAccount).where(
            JointAccount.joint_account_id.in_(joint_account_ids)
        )
        result_joint = await self.db.execute(stmt_joint)
        joint_accounts = result_joint.scalars().all()

        return {"single": single_account, "joint": joint_accounts}

    def get_latest_report(self, broker_codes: list, is_joint: bool) -> bytes:
        """Fetch the latest report from S3 based on broker codes."""
        account_id = self._get_account_identifier(broker_codes, is_joint)
        current_date = datetime.now()
        for _ in range(60):
            year = current_date.strftime("%Y")
            month = current_date.strftime("%b").upper()
            file_name = f"{account_id} {month} {year} Report.pdf"
            s3_key = f"PLUS91_PMS/reports/{year}/{month}/{file_name}"
            try:
                obj = self.s3_client.get_object(Bucket=self.bucket_name, Key=s3_key)
                return obj['Body'].read()
            except self.s3_client.exceptions.NoSuchKey:
                current_date = current_date - relativedelta(months=1)
        return None

    def _get_account_identifier(self, broker_codes: list, is_joint: bool) -> str:
        """Generate the account identifier for the file name."""
        if is_joint:
            sorted_codes = sorted(broker_codes)
            return f"[{' - '.join(sorted_codes)}]"
        else:
            return f"[{broker_codes[0]}]"

    def send_reports_email(self, email: str, reports: list):
        """Send an email with the reports as attachments."""
        msg = MIMEMultipart()
        msg['From'] = " pratham@plus91.co"
        msg['To'] = email
        msg['Subject'] = "Latest Reports"
        body = "This mail is to test the report mailing to the clients. Incorrect values " \
        "will be corrected in sometime."
        msg.attach(MIMEText(body, 'plain'))

        for report_data, filename in reports:
            attachment = MIMEApplication(report_data, _subtype="pdf")
            attachment.add_header('Content-Disposition', 'attachment', filename=filename)
            msg.attach(attachment)

        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(msg['From'], "feok yolq wqgs ieoo")
            server.send_message(msg)
        
    