import pandas as pd
import logging
import time
import sys
import os
import random
from datetime import datetime
from config import Config
from retry_handler import RetryHandler
from scraper import AmazonScraper
from database import DatabaseManager

class LoggerSetup:
    """Setup and manage logging configuration"""
    
    @staticmethod
    def setup_logging():
        """Setup logging with file and console handlers"""
        # Create logs directory if it doesn't exist
        if not os.path.exists('logs'):
            os.makedirs('logs')
        
        # Generate log filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = f'logs/scraper_{timestamp}.log'
        
        # Create logger
        logger = logging.getLogger('AmazonScraper')
        logger.setLevel(logging.INFO)
        
        # Remove existing handlers if any
        logger.handlers.clear()
        
        # Create formatters
        file_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(message)s',
            datefmt='%H:%M:%S'
        )
        
        # File handler - logs everything
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(file_formatter)
        
        # Console handler - logs INFO and above
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(console_formatter)
        
        # Error file handler - logs only errors
        error_log_filename = f'logs/errors_{timestamp}.log'
        error_handler = logging.FileHandler(error_log_filename, encoding='utf-8')
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)
        
        # Add handlers to logger
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)
        logger.addHandler(error_handler)
        
        # Set specific loggers to WARNING level
        logging.getLogger('selenium').setLevel(logging.WARNING)
        logging.getLogger('urllib3').setLevel(logging.WARNING)
        logging.getLogger('requests').setLevel(logging.WARNING)
        
        return logger, log_filename, error_log_filename

def load_keywords(filename: str = "keywords.csv"):
    """Load keywords from CSV file"""
    try:
        df = pd.read_csv(filename)
        if 'keyword' in df.columns:
            keywords = df['keyword'].dropna().tolist()
        else:
            keywords = df.iloc[:, 0].dropna().tolist()
        
        keywords = list(dict.fromkeys([k.strip() for k in keywords if k.strip()]))
        logger.info(f"Loaded {len(keywords)} keywords from {filename}")
        return keywords
    except FileNotFoundError:
        logger.error(f"Keywords file {filename} not found")
        return []
    except Exception as e:
        logger.error(f"Error loading keywords: {e}")
        return []

def display_database_stats(db_manager: DatabaseManager):
    """Display database statistics"""
    try:
        stats = db_manager.get_statistics()
        
        logger.info("=" * 60)
        logger.info("DATABASE STATISTICS")
        logger.info("=" * 60)
        logger.info(f"Total products in database: {stats.get('total_products', 0)}")
        logger.info(f"Total reviews in database: {stats.get('total_reviews', 0)}")
        logger.info(f"Products with videos: {stats.get('products_with_videos', 0)}")
        logger.info(f"Successful keywords: {stats.get('successful_keywords', 0)}")
        logger.info(f"Failed keywords: {stats.get('failed_keywords', 0)}")
        logger.info(f"Average price: ${stats.get('average_price', 0)}")
        logger.info("=" * 60)
        
    except Exception as e:
        logger.error(f"Error displaying statistics: {e}")

def save_scraping_summary(logger, summary_data: dict, log_filename: str):
    """Save scraping summary to a separate summary file"""
    try:
        summary_filename = log_filename.replace('.log', '_summary.txt')
        
        with open(summary_filename, 'w', encoding='utf-8') as f:
            f.write("=" * 80 + "\n")
            f.write("AMAZON SCRAPER - EXECUTION SUMMARY\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Execution Date: {summary_data.get('start_time', 'N/A')}\n")
            f.write(f"Duration: {summary_data.get('duration', 'N/A')}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("KEYWORD STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Keywords: {summary_data.get('total_keywords', 0)}\n")
            f.write(f"Successful Keywords: {summary_data.get('successful', 0)}\n")
            f.write(f"Failed Keywords: {summary_data.get('failed', 0)}\n")
            f.write(f"Success Rate: {summary_data.get('success_rate', 'N/A')}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("DATA STATISTICS\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total Products Scraped: {summary_data.get('total_products', 0)}\n")
            f.write(f"Total Reviews Scraped: {summary_data.get('total_reviews', 0)}\n")
            f.write(f"Average Products per Keyword: {summary_data.get('avg_products', 0):.1f}\n")
            f.write(f"Average Reviews per Product: {summary_data.get('avg_reviews', 0):.1f}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("DATABASE INFORMATION\n")
            f.write("-" * 40 + "\n")
            f.write(f"Database Path: {summary_data.get('database_path', 'N/A')}\n")
            f.write(f"Log File: {summary_data.get('log_file', 'N/A')}\n\n")
            
            f.write("-" * 40 + "\n")
            f.write("DETAILED KEYWORD RESULTS\n")
            f.write("-" * 40 + "\n")
            
            for keyword_result in summary_data.get('keyword_results', []):
                f.write(f"\nKeyword: {keyword_result.get('keyword', 'N/A')}\n")
                f.write(f"  Status: {keyword_result.get('status', 'N/A')}\n")
                f.write(f"  Products: {keyword_result.get('products', 0)}\n")
                f.write(f"  Reviews: {keyword_result.get('reviews', 0)}\n")
                if keyword_result.get('error'):
                    f.write(f"  Error: {keyword_result.get('error', '')}\n")
            
            f.write("\n" + "=" * 80 + "\n")
            f.write("END OF SUMMARY\n")
            f.write("=" * 80 + "\n")
        
        logger.info(f"Summary saved to: {summary_filename}")
        
    except Exception as e:
        logger.error(f"Error saving summary: {e}")

def main():
    """Main execution - Single thread with SQLite database"""
    
    # Setup logging
    global logger
    logger, log_filename, error_log_filename = LoggerSetup.setup_logging()
    
    start_time = datetime.now()
    keyword_results = []  # Track individual keyword results
    
    logger.info("=" * 80)
    logger.info("AMAZON SCRAPER - STARTING EXECUTION")
    logger.info("=" * 80)
    logger.info(f"Start Time: {start_time}")
    logger.info(f"Log File: {log_filename}")
    logger.info(f"Error Log File: {error_log_filename}")
    
    try:
        # Load keywords
        keywords = load_keywords()
        if not keywords:
            logger.error("No keywords found. Create keywords.csv file.")
            return
        
        total_keywords = len(keywords)
        logger.info(f"Processing {total_keywords} keywords")
        logger.info(f"Max products per keyword: {Config.MAX_PRODUCTS_PER_KEYWORD}")
        logger.info(f"Max reviews per product: {Config.MAX_REVIEWS_PER_PRODUCT}")
        logger.info(f"Database: {Config.DATABASE_PATH}")
        
        # Initialize database
        logger.info("Initializing database...")
        db_manager = DatabaseManager(Config.DATABASE_PATH)
        logger.info("Database initialized successfully")
        
        # Create scraping session
        session_id = db_manager.create_session(total_keywords)
        logger.info(f"Created scraping session: {session_id}")
        
        # Initialize scraper
        logger.info("Initializing scraper...")
        retry_handler = RetryHandler()
        scraper = AmazonScraper(retry_handler, db_manager)
        logger.info("Scraper initialized successfully")
        
        successful = 0
        failed = 0
        total_products = 0
        total_reviews = 0
        
        # Process each keyword
        for index, keyword in enumerate(keywords, 1):
            keyword_start_time = datetime.now()
            
            logger.info("-" * 80)
            logger.info(f"[{index}/{total_keywords}] Processing keyword: {keyword}")
            logger.info("-" * 80)
            
            try:
                # Initial delay for first keyword
                if index == 1:
                    initial_delay = random.uniform(5, 10)
                    logger.info(f"Initial delay: {initial_delay:.2f} seconds")
                    time.sleep(initial_delay)
                
                # Scrape keyword
                result = scraper.scrape_keyword(keyword, index, total_keywords)
                
                keyword_end_time = datetime.now()
                keyword_duration = keyword_end_time - keyword_start_time
                
                if result.get('products'):
                    successful += 1
                    num_products = len(result['products'])
                    num_reviews = len(result.get('reviews', []))
                    total_products += num_products
                    total_reviews += num_reviews
                    
                    logger.info(f"✓ {keyword}: {num_products} products, {num_reviews} reviews")
                    logger.info(f"  Time taken: {keyword_duration}")
                    
                    keyword_results.append({
                        'keyword': keyword,
                        'status': 'success',
                        'products': num_products,
                        'reviews': num_reviews,
                        'duration': str(keyword_duration),
                        'error': None
                    })
                else:
                    failed += 1
                    error_msg = result.get('error', 'No products')
                    logger.warning(f"⚠ {keyword}: {error_msg}")
                    logger.info(f"  Time taken: {keyword_duration}")
                    
                    keyword_results.append({
                        'keyword': keyword,
                        'status': 'failed',
                        'products': 0,
                        'reviews': 0,
                        'duration': str(keyword_duration),
                        'error': error_msg
                    })
                
                # Save intermediate results every 2 keywords
                if index % 2 == 0 or index == total_keywords:
                    logger.info("Saving intermediate results...")
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    db_manager.export_to_csv('products', f'progress_products_{timestamp}.csv')
                    db_manager.export_to_csv('reviews', f'progress_reviews_{timestamp}.csv')
                    logger.info("Intermediate results saved")
                
                # Delay between keywords
                if index < total_keywords:
                    delay = Config.get_delay_between_keywords()
                    logger.info(f"Waiting {delay:.2f} seconds before next keyword...")
                    time.sleep(delay)
                
            except Exception as e:
                failed += 1
                error_msg = str(e)[:200]
                logger.error(f"✗ {keyword}: {error_msg}")
                logger.error(f"Full error: {e}", exc_info=True)
                
                keyword_results.append({
                    'keyword': keyword,
                    'status': 'error',
                    'products': 0,
                    'reviews': 0,
                    'duration': str(datetime.now() - keyword_start_time),
                    'error': error_msg
                })
                
                # Close and recreate driver
                scraper.close_driver()
                time.sleep(random.uniform(5, 10))
        
        # Calculate final statistics
        end_time = datetime.now()
        duration = end_time - start_time
        success_rate = (successful/total_keywords*100) if total_keywords > 0 else 0
        avg_products = (total_products/successful) if successful > 0 else 0
        avg_reviews = (total_reviews/total_products) if total_products > 0 else 0
        
        # Display database statistics
        display_database_stats(db_manager)
        
        # Update session
        logger.info("Updating session information...")
        db_manager.update_session(
            session_id, successful, failed, total_products, total_reviews
        )
        
        # Export to CSV for backup
        logger.info("Exporting data to CSV for backup...")
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        db_manager.export_to_csv('products', f'backup_products_{timestamp}.csv')
        db_manager.export_to_csv('reviews', f'backup_reviews_{timestamp}.csv')
        
        # Prepare summary data
        summary_data = {
            'start_time': start_time.strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': end_time.strftime('%Y-%m-%d %H:%M:%S'),
            'duration': str(duration),
            'total_keywords': total_keywords,
            'successful': successful,
            'failed': failed,
            'success_rate': f"{success_rate:.1f}%",
            'total_products': total_products,
            'total_reviews': total_reviews,
            'avg_products': avg_products,
            'avg_reviews': avg_reviews,
            'database_path': Config.DATABASE_PATH,
            'log_file': log_filename,
            'keyword_results': keyword_results
        }
        
        # Save summary
        save_scraping_summary(logger, summary_data, log_filename)
        
        # Close database
        db_manager.close()
        
        # Final summary
        logger.info("=" * 80)
        logger.info("SCRAPING EXECUTION COMPLETED")
        logger.info("=" * 80)
        logger.info(f"Total keywords: {total_keywords}")
        logger.info(f"Successful: {successful}")
        logger.info(f"Failed: {failed}")
        logger.info(f"Total products scraped: {total_products}")
        logger.info(f"Total reviews scraped: {total_reviews}")
        logger.info(f"Success rate: {success_rate:.1f}%")
        logger.info(f"Average products per keyword: {avg_products:.1f}")
        logger.info(f"Average reviews per product: {avg_reviews:.1f}")
        logger.info(f"Total duration: {duration}")
        logger.info(f"Database: {Config.DATABASE_PATH}")
        logger.info(f"Log file: {log_filename}")
        logger.info(f"Error log file: {error_log_filename}")
        logger.info("=" * 80)
        
    except KeyboardInterrupt:
        logger.info("Scraper interrupted by user")
        logger.info("Saving partial results...")
        
        try:
            if 'db_manager' in locals():
                display_database_stats(db_manager)
                db_manager.close()
        except:
            pass
        
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        
        try:
            if 'db_manager' in locals():
                db_manager.close()
        except:
            pass
        
    finally:
        logger.info(f"Execution completed at: {datetime.now()}")
        logger.info(f"Logs saved to: {log_filename}")
        if 'error_log_filename' in locals():
            logger.info(f"Errors saved to: {error_log_filename}")

if __name__ == "__main__":
    main()