import boto3
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from typing import List, Dict, Any
from app.database import get_db
from app.services.report_service import ReportService
from app.models.report import RequestData
from app.models.accounts.joint_account_mapping import JointAccountMapping
from app.models.clients.client_details import Client


report_router = APIRouter(prefix="/reports", tags=["Reports"])

@report_router.post("/send-report")
async def send_report(data: RequestData, db: AsyncSession = Depends(get_db)):
    """API endpoint to send reports based on broker_code and pan_no."""
    service = ReportService(db, boto3.client('s3'))
    try:
        client = await service.verify_user(data.broker_code, data.pan_no)
        accounts = await service.get_accounts(client)
        single_report = service.get_latest_report([client.broker_code], is_joint=False)

        joint_reports = []
        for joint_account in accounts["joint"]:
            stmt_mappings = select(JointAccountMapping).where(
                JointAccountMapping.joint_account_id == joint_account.joint_account_id
            )
            result_mappings = await db.execute(stmt_mappings)
            joint_mappings = result_mappings.scalars().all()
            joint_single_account_ids = [m.account_id for m in joint_mappings]
            
            stmt_clients = select(Client).where(
                Client.account_id.in_(joint_single_account_ids)
            )
            result_clients = await db.execute(stmt_clients)
            joint_clients = result_clients.scalars().all()
            joint_broker_codes = [c.broker_code for c in joint_clients]
            joint_report = service.get_latest_report(joint_broker_codes, is_joint=True)
            if joint_report:
                joint_reports.append((joint_report, f"JointAccount_{joint_account.joint_account_id}_report.pdf"))

        reports = []
        if single_report:
            reports.append((single_report, f"{client.broker_code}_report.pdf"))
        reports.extend(joint_reports)

        if reports:
            service.send_reports_email(client.email_id, reports)
            return {"status": "success", "message": "Reports sent successfully"}
        else:
            raise HTTPException(status_code=404, detail="No reports found")
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")
    
@report_router.post("/dummy-report")
async def dummy_report(data: RequestData, db: AsyncSession = Depends(get_db)):
    """API endpoint to send reports based on broker_code and pan_no."""
    service = ReportService(db, boto3.client('s3'))
    try:
        client = await service.verify_user(data.broker_code, data.pan_no)
        accounts = await service.get_accounts(client)
        single_report = service.get_latest_report([client.broker_code], is_joint=False)

        joint_reports = []
        for joint_account in accounts["joint"]:
            stmt_mappings = select(JointAccountMapping).where(
                JointAccountMapping.joint_account_id == joint_account.joint_account_id
            )
            result_mappings = await db.execute(stmt_mappings)
            joint_mappings = result_mappings.scalars().all()
            joint_single_account_ids = [m.account_id for m in joint_mappings]
            
            stmt_clients = select(Client).where(
                Client.account_id.in_(joint_single_account_ids)
            )
            result_clients = await db.execute(stmt_clients)
            joint_clients = result_clients.scalars().all()
            joint_broker_codes = [c.broker_code for c in joint_clients]
            joint_report = service.get_latest_report(joint_broker_codes, is_joint=True)
            if joint_report:
                joint_reports.append((joint_report, f"JointAccount_{joint_account.joint_account_id}_report.pdf"))

        reports = []
        if single_report:
            reports.append((single_report, f"{client.broker_code}_report.pdf"))
        reports.extend(joint_reports)

        if reports:
            # service.send_reports_email(client.email_id, reports)
            return {
                "status": "success",
                "message": "Reports sent successfully",
                "data": data
            }
        else:
            raise HTTPException(status_code=404, detail="No reports found")
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")