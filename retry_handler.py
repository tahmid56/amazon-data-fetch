import time
import random
from functools import wraps
from typing import Callable, Any
import logging
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type, before_sleep_log
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RetryHandler:
    def __init__(self, max_retries: int = Config.MAX_RETRIES):
        self.max_retries = max_retries
        
    def with_retry(self, func: Callable) -> Callable:
        """Decorator for retry mechanism with exponential backoff"""
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(self.max_retries):
                try:
                    # Add random delay before each attempt (except first)
                    if attempt > 0:
                        delay = Config.get_random_delay() * (2 ** (attempt - 1))
                        logger.info(f"Attempt {attempt + 1} - Waiting {delay:.2f} seconds...")
                        time.sleep(delay)
                    
                    return func(*args, **kwargs)
                    
                except Exception as e:
                    logger.error(f"Attempt {attempt + 1} failed: {str(e)}")
                    
                    if attempt == self.max_retries - 1:
                        logger.error(f"All {self.max_retries} retries exhausted for {func.__name__}")
                        raise
                    
                    # Add jitter to avoid thundering herd problem
                    backoff_time = random.uniform(2, 5) * (2 ** attempt)
                    logger.info(f"Retrying in {backoff_time:.2f} seconds...")
                    time.sleep(backoff_time)
        
        return wrapper
    
    @staticmethod
    def retry_decorator(max_attempts: int = 3, min_wait: int = 3, max_wait: int = 10):
        """Retry decorator using tenacity library"""
        return retry(
            stop=stop_after_attempt(max_attempts),
            wait=wait_exponential(multiplier=1, min=min_wait, max=max_wait),
            retry=retry_if_exception_type(Exception),
            before_sleep=before_sleep_log(logger, logging.INFO),
            reraise=True
        )