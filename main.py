import pandas as pd
import logging
import time
import sys
import os
import random
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from config import Config
from retry_handler import RetryHandler
from scraper import AmazonScraper
from database import DatabaseManager

class LoggerSetup:
    @staticmethod
    def setup_logging():
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f'logs/scraper_{timestamp}.log'
        
        logger = logging.getLogger('AmazonScraper')
        logger.setLevel(logging.INFO)
        logger.handlers.clear()
        
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(threadName)s] - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        error_log_filename = f'logs/errors_{timestamp}.log'
        error_handler = logging.FileHandler(error_log_filename, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.addHandler(error_handler)
        
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        
        return logger, log_filename, error_log_filename

def load_keywords(filename: str = "keywords.csv"):
    try:
        df = pd.read_csv(filename)
        if 'keyword' in df.columns:
            keywords = df['keyword'].dropna().tolist()
        else:
            keywords = df.iloc[:, 0].dropna().tolist()
        
        keywords = list(dict.fromkeys([k.strip() for k in keywords if k.strip()]))
        logger.info(f"Loaded {len(keywords)} keywords")
        return keywords
    except FileNotFoundError:
        logger.error(f"Keywords file {filename} not found")
        return []

def main():
    global logger
    logger, log_filename, error_log_filename = LoggerSetup.setup_logging()
    
    start_time = datetime.now()
    
    logger.info("=" * 80)
    logger.info("AMAZON SCRAPER - MULTI-THREADED")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time}")
    logger.info(f"Max Threads: {Config.MAX_THREADS}")
    logger.info(f"Log File: {log_filename}")
    
    keywords = load_keywords()
    if not keywords:
        logger.error("No keywords found")
        return
    
    total_keywords = len(keywords)
    logger.info(f"Processing {total_keywords} keywords with {Config.MAX_THREADS} threads")
    
    db_manager = DatabaseManager(Config.DATABASE_PATH)
    retry_handler = RetryHandler()
    scraper = AmazonScraper(retry_handler, db_manager)
    
    successful = 0
    failed = 0
    total_products = 0
    total_reviews = 0
    
    # Thread-safe counters
    stats_lock = threading.Lock()
    
    def process_keyword(keyword, index):
        """Process a single keyword (runs in thread)"""
        nonlocal successful, failed, total_products, total_reviews
        
        try:
            result = scraper.scrape_keyword(keyword, index, total_keywords)
            
            with stats_lock:
                if result.get('products'):
                    successful += 1
                    num_products = len(result['products'])
                    num_reviews = len(result.get('reviews', []))
                    total_products += num_products
                    total_reviews += num_reviews
                    logger.info(f"✓ {keyword}: {num_products} products, {num_reviews} reviews")
                else:
                    failed += 1
                    logger.warning(f"⚠ {keyword}: {result.get('error', 'No products')}")
            
            return result
            
        except Exception as e:
            with stats_lock:
                failed += 1
            logger.error(f"✗ {keyword}: {str(e)[:150]}")
            return {'keyword': keyword, 'products': [], 'error': str(e)}
        finally:
            # Close thread driver
            scraper.close_thread_driver()
    
    try:
        # Use ThreadPoolExecutor for concurrent processing
        with ThreadPoolExecutor(max_workers=Config.MAX_THREADS) as executor:
            # Submit all keywords
            future_to_keyword = {
                executor.submit(process_keyword, keyword, idx): keyword 
                for idx, keyword in enumerate(keywords, 1)
            }
            
            # Process completed futures
            for future in as_completed(future_to_keyword):
                keyword = future_to_keyword[future]
                try:
                    result = future.result()
                except Exception as e:
                    logger.error(f"Error processing {keyword}: {e}")
        
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        scraper.close_all_drivers()
        
        db_manager.close()
        
        end_time = datetime.now()
        duration = end_time - start_time
        
        # Summary
        logger.info("=" * 80)
        logger.info("SCRAPING COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Total keywords: {total_keywords}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total products: {total_products}")
        logger.info(f"Total reviews: {total_reviews}")
        logger.info(f"Success rate: {(successful/total_keywords*100):.1f}%")
        logger.info(f"Duration: {duration}")
        logger.info(f"Threads used: {Config.MAX_THREADS}")
        logger.info("=" * 80)

if __name__ == "__main__":
    main()