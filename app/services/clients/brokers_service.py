from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.clients.broker_details import Broker
from app.models.clients.client_details import Client
from app.logger import logger, log_function_call

class BrokerService:
    @staticmethod
    @log_function_call
    async def get_broker_id(db: AsyncSession, broker_name: str) -> str:
        """Retrieve broker ID by name (case-insensitive)."""
        logger.info(f"Looking up broker ID for broker_name: '{broker_name}'")
        result = await db.execute(select(Broker).where(Broker.broker_name.ilike(broker_name.strip())))
        broker = result.scalars().first()
        if not broker:
            logger.error(f"Broker '{broker_name}' not found")
            raise Exception(f"Broker '{broker_name}' not found.")
        logger.debug(f"Found broker ID: {broker.broker_id}")
        return broker.broker_id

    @staticmethod
    @log_function_call
    async def get_broker_name(db: AsyncSession, broker_id: int) -> str:
        """Retrieve broker name by ID (case-insensitive)."""
        logger.info(f"Looking up broker name for broker_id: {broker_id}")
        result = await db.execute(select(Broker).where(Broker.broker_id.ilike(str(broker_id))))
        broker = result.scalars().first()
        if not broker:
            logger.error(f"Broker '{broker_id}' not found")
            raise Exception(f"Broker '{broker_id}' not found.")
        logger.debug(f"Found broker name: {broker.broker_name}")
        return broker.broker_name

    @staticmethod
    @log_function_call
    async def get_brokers(db: AsyncSession) -> List[Dict[str, Any]]:
        """Fetch all brokers from the database, ordered by broker_id."""
        logger.info("Fetching all brokers")
        q = await db.execute(select(Broker).order_by(Broker.broker_id))
        rows = q.scalars().all()
        data = [
            {
                "broker_id": r.broker_id,
                "broker_name": r.broker_name,
                "created_at": r.created_at
            }
            for r in rows
        ]
        logger.debug(f"Retrieved {len(data)} brokers")
        return data

    @staticmethod
    @log_function_call
    async def add_broker(db: AsyncSession, broker_name: str) -> Dict[str, Any]:
        """Add a new broker if it doesn't already exist."""
        logger.info(f"Attempting to add broker: '{broker_name}'")
        result = await db.execute(select(Broker).where(Broker.broker_name.ilike(broker_name)))
        if result.scalars().first():
            logger.warning(f"Broker '{broker_name}' already exists")
            raise Exception("Broker already exists")
        new_broker = Broker(broker_name=broker_name)
        db.add(new_broker)
        await db.commit()
        await db.refresh(new_broker)
        logger.info(f"Broker added with ID: {new_broker.broker_id}")
        return {
            "broker_id": new_broker.broker_id,
            "broker_name": new_broker.broker_name,
            "created_at": new_broker.created_at
        }

    @staticmethod
    @log_function_call
    async def update_broker(db: AsyncSession, old_value: str, new_value: str) -> Dict[str, Any]:
        """Update an existing broker's name."""
        logger.info(f"Updating broker from '{old_value}' to '{new_value}'")
        result = await db.execute(select(Broker).where(Broker.broker_name.ilike(old_value)))
        broker = result.scalars().first()
        if not broker:
            logger.error(f"Broker '{old_value}' not found")
            raise Exception("Broker not found")
        broker.broker_name = new_value
        await db.commit()
        await db.refresh(broker)
        logger.info(f"Broker updated to '{new_value}' with ID: {broker.broker_id}")
        return {
            "broker_id": broker.broker_id,
            "broker_name": broker.broker_name,
            "created_at": broker.created_at
        }

    @staticmethod
    @log_function_call
    async def delete_broker(db: AsyncSession, broker_name: str) -> Dict[str, Any]:
        """Delete a broker and update clients to a default broker (BROKER_0003)."""
        logger.info(f"Deleting broker: '{broker_name}'")
        result = await db.execute(select(Broker).where(Broker.broker_name.ilike(broker_name)))
        broker = result.scalars().first()
        if not broker:
            logger.error(f"Broker '{broker_name}' not found")
            raise Exception("Broker not found")
        
        logger.debug(f"Reassigning clients from broker '{broker.broker_id}' to 'BROKER_0003'")
        await db.execute(
            update(Client)
            .where(Client.broker_id == broker.broker_id)
            .values(broker_id='BROKER_0003')
        )
        await db.delete(broker)
        await db.commit()
        logger.info(f"Broker '{broker_name}' deleted successfully")
        return {"status": "ok"}