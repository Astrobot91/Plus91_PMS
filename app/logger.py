import logging
import watchtower
import boto3
from functools import wraps

boto3.setup_default_session(region_name='ap-south-1')

logger = logging.getLogger("plus91_backend_ops")
logger.setLevel(logging.DEBUG)

handler = watchtower.CloudWatchLogHandler(
    log_group='PortfolioManagerLogs',
    stream_name='BackendStream'
)
handler.setFormatter(logging.Formatter(
    "%(asctime)s - %(levelname)s - %(filename)s - %(funcName)s - %(message)s"
))
logger.addHandler(handler)

def log_function_call(func):
    @wraps(func)
    async def wrapper(*args, **kwargs):
        logger.info(
            f"Function '{func.__name__}' called with args: {args}, kwargs: {kwargs}"
        )
        try:
            result = await func(*args, **kwargs)
            logger.info(f"Function '{func.__name__}' completed successfully")
            return result
        except Exception as e:
            logger.error(
                f"Function '{func.__name__}' failed with error: {str(e)}", exc_info=True
            )
            raise
    return wrapper