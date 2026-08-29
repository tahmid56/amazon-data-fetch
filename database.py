import sqlite3
import logging
from datetime import datetime
from typing import List, Dict, Optional
import pandas as pd
import json
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, db_path: str = "amazon_scraper.db"):
        self.db_path = db_path
        self.conn = None
        self.cursor = None
        self.lock = threading.Lock()  # Thread safety lock
        self.init_database()
    
    def init_database(self):
        """Initialize database connection and create tables"""
        try:
            self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self.conn.row_factory = sqlite3.Row
            self.cursor = self.conn.cursor()
            self.cursor.execute("PRAGMA foreign_keys = ON")
            self.create_tables()
            logger.info(f"Database initialized at {self.db_path}")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
            raise
    
    def create_tables(self):
        """Create all necessary tables"""
        try:
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS products (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    asin TEXT UNIQUE,
                    title TEXT,
                    full_title TEXT,
                    url TEXT,
                    image_url TEXT,
                    price TEXT,
                    original_price TEXT,
                    current_price TEXT,
                    discount TEXT,
                    rating TEXT,
                    detailed_rating TEXT,
                    reviews_count TEXT,
                    detailed_reviews_count TEXT,
                    brand TEXT,
                    availability TEXT,
                    description TEXT,
                    features TEXT,
                    technical_details TEXT,
                    dimensions TEXT,
                    best_sellers_rank TEXT,
                    date_first_available TEXT,
                    manufacturer TEXT,
                    is_prime TEXT,
                    is_sponsored TEXT,
                    video_url TEXT,
                    video_thumbnail TEXT,
                    keyword TEXT,
                    scraped_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    product_id INTEGER,
                    review_title TEXT,
                    review_rating TEXT,
                    review_date TEXT,
                    reviewer_name TEXT,
                    verified_purchase TEXT,
                    review_body TEXT,
                    helpful_votes TEXT,
                    product_title TEXT,
                    product_url TEXT,
                    scraped_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (product_id) REFERENCES products (id) ON DELETE CASCADE
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword TEXT UNIQUE,
                    status TEXT,
                    products_found INTEGER DEFAULT 0,
                    reviews_found INTEGER DEFAULT 0,
                    error_message TEXT,
                    scraped_at TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.cursor.execute('''
                CREATE TABLE IF NOT EXISTS scraping_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_start TEXT,
                    session_end TEXT,
                    total_keywords INTEGER,
                    successful_keywords INTEGER,
                    failed_keywords INTEGER,
                    total_products INTEGER,
                    total_reviews INTEGER,
                    status TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_asin ON products(asin)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_products_keyword ON products(keyword)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_reviews_product_id ON reviews(product_id)')
            self.cursor.execute('CREATE INDEX IF NOT EXISTS idx_keywords_keyword ON keywords(keyword)')
            
            self.conn.commit()
            logger.info("Database tables created successfully")
        except Exception as e:
            logger.error(f"Error creating tables: {e}")
            raise
    
    def insert_product(self, product_data: Dict) -> Optional[int]:
        """Insert or update product data (thread-safe)"""
        with self.lock:
            try:
                asin = product_data.get('asin', 'N/A')
                if asin != 'N/A':
                    self.cursor.execute('SELECT id FROM products WHERE asin = ?', (asin,))
                    existing = self.cursor.fetchone()
                    
                    if existing:
                        product_id = existing['id']
                        update_fields = []
                        update_values = []
                        
                        for key, value in product_data.items():
                            if key != 'asin' and key != 'id':
                                update_fields.append(f"{key} = ?")
                                update_values.append(value)
                        
                        if update_fields:
                            update_fields.append("updated_at = ?")
                            update_values.append(datetime.now().isoformat())
                            update_query = f"UPDATE products SET {', '.join(update_fields)} WHERE id = ?"
                            update_values.append(product_id)
                            self.cursor.execute(update_query, update_values)
                            self.conn.commit()
                        
                        return product_id
                
                columns = list(product_data.keys())
                placeholders = ['?' for _ in columns]
                insert_query = f'''
                    INSERT OR REPLACE INTO products ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                '''
                self.cursor.execute(insert_query, [product_data.get(col) for col in columns])
                self.conn.commit()
                return self.cursor.lastrowid
            except Exception as e:
                logger.error(f"Error inserting product: {e}")
                self.conn.rollback()
                return None
    
    def insert_review(self, review_data: Dict, product_id: Optional[int] = None) -> Optional[int]:
        """Insert review data (thread-safe)"""
        with self.lock:
            try:
                if product_id:
                    review_data['product_id'] = product_id
                
                columns = list(review_data.keys())
                placeholders = ['?' for _ in columns]
                insert_query = f'''
                    INSERT INTO reviews ({', '.join(columns)})
                    VALUES ({', '.join(placeholders)})
                '''
                self.cursor.execute(insert_query, [review_data.get(col) for col in columns])
                self.conn.commit()
                return self.cursor.lastrowid
            except Exception as e:
                logger.error(f"Error inserting review: {e}")
                self.conn.rollback()
                return None
    
    def insert_keyword_status(self, keyword: str, status: str, products_found: int = 0, 
                             reviews_found: int = 0, error_message: str = None):
        """Insert or update keyword status (thread-safe)"""
        with self.lock:
            try:
                self.cursor.execute('''
                    INSERT OR REPLACE INTO keywords 
                    (keyword, status, products_found, reviews_found, error_message, scraped_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (keyword, status, products_found, reviews_found, 
                      error_message, datetime.now().isoformat()))
                self.conn.commit()
            except Exception as e:
                logger.error(f"Error inserting keyword status: {e}")
                self.conn.rollback()
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")