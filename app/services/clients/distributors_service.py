from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Dict, Any
from app.models.clients.distributor_details import Distributor
from app.logger import logger, log_function_call

class DistributorService:
    @staticmethod
    @log_function_call
    async def get_distributor_id(db: AsyncSession, distributor_name: str) -> str:
        """Retrieve distributor ID by name (exact match)."""
        logger.info(f"Looking up distributor ID for name: '{distributor_name}'")
        result = await db.execute(select(Distributor).where(Distributor.name == distributor_name))
        distributor = result.scalars().first()
        if not distributor:
            logger.error(f"Distributor '{distributor_name}' not found")
            raise Exception(f"Distributor '{distributor_name}' not found.")
        logger.debug(f"Found distributor ID: {distributor.distributor_id}")
        return distributor.distributor_id

    @staticmethod
    @log_function_call
    async def get_distributors(db: AsyncSession) -> List[Dict[str, Any]]:
        """Fetch all distributors from the database, ordered by distributor_id."""
        logger.info("Fetching all distributors")
        q = await db.execute(select(Distributor).order_by(Distributor.distributor_id))
        rows = q.scalars().all()
        data = [
            {
                "distributor_id": r.distributor_id,
                "name": r.name,
                "created_at": r.created_at
            }
            for r in rows
        ]
        logger.debug(f"Retrieved {len(data)} distributors")
        return data

    @staticmethod
    @log_function_call
    async def add_distributor(db: AsyncSession, name: str) -> Dict[str, Any]:
        """Add a new distributor if it doesn't already exist."""
        logger.info(f"Attempting to add distributor: '{name}'")
        result = await db.execute(select(Distributor).where(Distributor.name.ilike(name)))
        if result.scalars().first():
            logger.warning(f"Distributor '{name}' already exists")
            raise Exception("Distributor already exists")
        new_distributor = Distributor(name=name)
        db.add(new_distributor)
        await db.commit()
        await db.refresh(new_distributor)
        logger.info(f"Distributor added with ID: {new_distributor.distributor_id}")
        return {
            "distributor_id": new_distributor.distributor_id,
            "name": new_distributor.name,
            "created_at": new_distributor.created_at
        }

    @staticmethod
    @log_function_call
    async def update_distributor(db: AsyncSession, old_value: str, new_value: str) -> Dict[str, Any]:
        """Update an existing distributor's name."""
        logger.info(f"Updating distributor from '{old_value}' to '{new_value}'")
        result = await db.execute(select(Distributor).where(Distributor.name.ilike(old_value)))
        distributor = result.scalars().first()
        if not distributor:
            logger.error(f"Distributor '{old_value}' not found")
            raise Exception("Distributor not found")
        distributor.name = new_value
        await db.commit()
        await db.refresh(distributor)
        logger.info(f"Distributor updated to '{new_value}' with ID: {distributor.distributor_id}")
        return {
            "distributor_id": distributor.distributor_id,
            "name": distributor.name,
            "created_at": distributor.created_at
        }

    @staticmethod
    @log_function_call
    async def delete_distributor(db: AsyncSession, name: str) -> Dict[str, Any]:
        """Delete a distributor by name."""
        logger.info(f"Deleting distributor: '{name}'")
        result = await db.execute(select(Distributor).where(Distributor.name.ilike(name)))
        distributor = result.scalars().first()
        if not distributor:
            logger.error(f"Distributor '{name}' not found")
            raise Exception("Distributor not found")
        await db.delete(distributor)
        await db.commit()
        logger.info(f"Distributor '{name}' deleted successfully")
        return {"status": "ok"}