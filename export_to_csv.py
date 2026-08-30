#!/usr/bin/env python3
"""
Convert SQLite database to CSV/Excel with products and reviews as JSON arrays
"""

import sqlite3
import pandas as pd
import json
import logging
import sys
from datetime import datetime
from typing import List, Dict, Optional
import os

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class DatabaseToCSVConverter:
    def __init__(self, db_path: str = "amazon_scraper.db"):
        self.db_path = db_path
        self.conn = None
        
    def connect(self):
        """Connect to the database"""
        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row
            logger.info(f"Connected to database: {self.db_path}")
        except Exception as e:
            logger.error(f"Error connecting to database: {e}")
            raise
    
    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")
    
    def get_all_products(self) -> List[Dict]:
        """Get all products from database"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT * FROM products
                ORDER BY created_at DESC
            ''')
            
            products = []
            for row in cursor.fetchall():
                product = dict(row)
                products.append(product)
            
            logger.info(f"Retrieved {len(products)} products")
            return products
            
        except Exception as e:
            logger.error(f"Error getting products: {e}")
            return []
    
    def get_reviews_for_product(self, product_id: int) -> List[Dict]:
        """Get all reviews for a specific product"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT 
                    review_title,
                    review_rating,
                    review_date,
                    reviewer_name,
                    verified_purchase,
                    review_body,
                    helpful_votes,
                    scraped_at
                FROM reviews
                WHERE product_id = ?
                ORDER BY created_at DESC
            ''', (product_id,))
            
            reviews = []
            for row in cursor.fetchall():
                review = dict(row)
                reviews.append(review)
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error getting reviews for product {product_id}: {e}")
            return []
    
    def get_reviews_by_product_url(self, product_url: str) -> List[Dict]:
        """Get reviews by product URL (alternative method)"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT 
                    review_title,
                    review_rating,
                    review_date,
                    reviewer_name,
                    verified_purchase,
                    review_body,
                    helpful_votes,
                    scraped_at
                FROM reviews
                WHERE product_url = ?
                ORDER BY created_at DESC
            ''', (product_url,))
            
            reviews = []
            for row in cursor.fetchall():
                review = dict(row)
                reviews.append(review)
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error getting reviews for URL {product_url}: {e}")
            return []
    
    def parse_technical_details(self, technical_details_str: str) -> Dict:
        """Parse technical details JSON string"""
        if not technical_details_str or technical_details_str == "N/A":
            return {}
        
        try:
            if isinstance(technical_details_str, str):
                return json.loads(technical_details_str)
            elif isinstance(technical_details_str, dict):
                return technical_details_str
            else:
                return {}
        except:
            return {}
    
    def build_combined_data(self) -> pd.DataFrame:
        """Build combined DataFrame with products and reviews"""
        products = self.get_all_products()
        
        if not products:
            logger.warning("No products found in database")
            return pd.DataFrame()
        
        combined_data = []
        
        for product in products:
            try:
                # Get reviews for this product
                product_id = product.get('id')
                reviews = self.get_reviews_for_product(product_id)
                
                # If no reviews by product_id, try by URL
                if not reviews and product.get('url'):
                    reviews = self.get_reviews_by_product_url(product['url'])
                
                # Parse technical details
                technical_details = self.parse_technical_details(product.get('technical_details'))
                
                # Build the combined row
                row = {
                    # Product ID and identification
                    'product_id': product.get('id', ''),
                    'asin': product.get('asin', ''),
                    
                    # Basic product info
                    'title': product.get('title', ''),
                    'full_title': product.get('full_title', product.get('title', '')),
                    'url': product.get('url', ''),
                    'image_url': product.get('image_url', ''),
                    
                    # Pricing
                    'price': product.get('price', ''),
                    'current_price': product.get('current_price', product.get('price', '')),
                    'original_price': product.get('original_price', ''),
                    'discount': product.get('discount', ''),
                    
                    # Ratings and reviews count
                    'rating': product.get('rating', product.get('detailed_rating', '')),
                    'detailed_rating': product.get('detailed_rating', ''),
                    'reviews_count': product.get('reviews_count', product.get('detailed_reviews_count', '')),
                    'detailed_reviews_count': product.get('detailed_reviews_count', ''),
                    
                    # Product details
                    'brand': product.get('brand', ''),
                    'manufacturer': product.get('manufacturer', ''),
                    'availability': product.get('availability', ''),
                    'description': product.get('description', ''),
                    'features': product.get('features', ''),
                    'dimensions': product.get('dimensions', ''),
                    'best_sellers_rank': product.get('best_sellers_rank', ''),
                    'date_first_available': product.get('date_first_available', ''),
                    
                    # Badges
                    'is_prime': product.get('is_prime', 'No'),
                    'is_sponsored': product.get('is_sponsored', 'No'),
                    
                    # Video
                    'video_url': product.get('video_url', ''),
                    'video_thumbnail': product.get('video_thumbnail', ''),
                    
                    # Search keyword
                    'keyword': product.get('keyword', ''),
                    
                    # Timestamps
                    'scraped_at': product.get('scraped_at', ''),
                    'created_at': product.get('created_at', ''),
                    'updated_at': product.get('updated_at', ''),
                    
                    # Technical details as JSON string
                    'technical_details': json.dumps(technical_details, ensure_ascii=False) if technical_details else '',
                    
                    # Reviews as JSON array
                    'reviews': json.dumps(reviews, ensure_ascii=False, indent=2) if reviews else '[]',
                    'reviews_count_actual': len(reviews),
                }
                
                # Add technical details as individual columns
                if technical_details:
                    for key, value in technical_details.items():
                        # Clean column name
                        column_name = key.lower().replace(' ', '_').replace('-', '_')
                        column_name = ''.join(c for c in column_name if c.isalnum() or c == '_')
                        if column_name and column_name not in row:
                            row[f'tech_{column_name}'] = value
                
                combined_data.append(row)
                
                logger.debug(f"Processed product: {product.get('title', 'N/A')[:50]}... with {len(reviews)} reviews")
                
            except Exception as e:
                logger.error(f"Error processing product {product.get('id')}: {e}")
                continue
        
        # Create DataFrame
        df = pd.DataFrame(combined_data)
        
        # Remove duplicate products based on ASIN
        if 'asin' in df.columns:
            df = df.drop_duplicates(subset=['asin'], keep='first')
        
        logger.info(f"Created DataFrame with {len(df)} products")
        logger.info(f"Total reviews across all products: {df['reviews_count_actual'].sum() if 'reviews_count_actual' in df.columns else 0}")
        
        return df
    
    def save_to_csv(self, df: pd.DataFrame, filename: str = "output/amazon_products_with_reviews.csv"):
        """Save DataFrame to CSV file"""
        try:
            if df.empty:
                logger.warning("No data to save")
                return False
            
            df.to_csv(filename, index=False, encoding='utf-8')
            logger.info(f"Data saved to: {filename}")
            logger.info(f"Rows: {len(df)}")
            logger.info(f"Columns: {len(df.columns)}")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving to CSV: {e}")
            return False
    
    def save_to_excel(self, df: pd.DataFrame, filename: str = "output/amazon_products_with_reviews.xlsx"):
        """Save DataFrame to Excel file"""
        try:
            if df.empty:
                logger.warning("No data to save")
                return False
            
            # Create Excel writer
            with pd.ExcelWriter(filename, engine='openpyxl') as writer:
                # Main products sheet
                df.to_excel(writer, sheet_name='Products', index=False)
                
                # Create a separate sheet for reviews if needed
                self.create_reviews_sheet(writer)
                
                # Create summary sheet
                self.create_summary_sheet(writer, df)
            
            logger.info(f"Data saved to: {filename}")
            logger.info(f"Sheets: Products, Reviews, Summary")
            
            return True
            
        except Exception as e:
            logger.error(f"Error saving to Excel: {e}")
            return False
    
    def create_reviews_sheet(self, writer):
        """Create a separate reviews sheet in Excel"""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
                SELECT 
                    r.id,
                    r.product_id,
                    p.asin,
                    p.title as product_title,
                    r.review_title,
                    r.review_rating,
                    r.review_date,
                    r.reviewer_name,
                    r.verified_purchase,
                    r.review_body,
                    r.helpful_votes,
                    r.scraped_at
                FROM reviews r
                LEFT JOIN products p ON r.product_id = p.id
                ORDER BY r.created_at DESC
            ''')
            
            reviews = []
            for row in cursor.fetchall():
                reviews.append(dict(row))
            
            if reviews:
                reviews_df = pd.DataFrame(reviews)
                reviews_df.to_excel(writer, sheet_name='Reviews', index=False)
                logger.info(f"Added {len(reviews)} reviews to Reviews sheet")
            
        except Exception as e:
            logger.error(f"Error creating reviews sheet: {e}")
    
    def create_summary_sheet(self, writer, df):
        """Create a summary sheet in Excel"""
        try:
            summary_data = []
            
            # Database statistics
            cursor = self.conn.cursor()
            
            # Total products
            cursor.execute('SELECT COUNT(*) FROM products')
            total_products = cursor.fetchone()[0]
            
            # Total reviews
            cursor.execute('SELECT COUNT(*) FROM reviews')
            total_reviews = cursor.fetchone()[0]
            
            # Products with reviews
            cursor.execute('''
                SELECT COUNT(DISTINCT product_id) 
                FROM reviews 
                WHERE product_id IS NOT NULL
            ''')
            products_with_reviews = cursor.fetchone()[0]
            
            # Products with videos
            cursor.execute('''
                SELECT COUNT(*) FROM products 
                WHERE video_url != 'N/A' AND video_url IS NOT NULL
            ''')
            products_with_videos = cursor.fetchone()[0]
            
            # Average rating
            cursor.execute('''
                SELECT AVG(CAST(review_rating AS FLOAT)) 
                FROM reviews 
                WHERE review_rating != 'N/A' AND review_rating IS NOT NULL
            ''')
            avg_rating = cursor.fetchone()[0]
            
            # Keywords summary
            cursor.execute('''
                SELECT keyword, COUNT(*) as product_count
                FROM products
                GROUP BY keyword
                ORDER BY product_count DESC
            ''')
            keyword_stats = cursor.fetchall()
            
            summary_data.append({
                'Metric': 'Total Products',
                'Value': total_products
            })
            summary_data.append({
                'Metric': 'Total Reviews',
                'Value': total_reviews
            })
            summary_data.append({
                'Metric': 'Products with Reviews',
                'Value': products_with_reviews
            })
            summary_data.append({
                'Metric': 'Products with Videos',
                'Value': products_with_videos
            })
            summary_data.append({
                'Metric': 'Average Review Rating',
                'Value': round(avg_rating, 2) if avg_rating else 'N/A'
            })
            
            # Create summary DataFrame
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            # Add keyword statistics
            if keyword_stats:
                keyword_df = pd.DataFrame(keyword_stats, columns=['Keyword', 'Product Count'])
                keyword_df.to_excel(writer, sheet_name='Keyword Stats', index=False)
            
        except Exception as e:
            logger.error(f"Error creating summary sheet: {e}")
    
    def convert(self, output_format: str = 'csv', filename: Optional[str] = None):
        """Main conversion method"""
        try:
            # Connect to database
            self.connect()
            
            # Build combined data
            df = self.build_combined_data()
            
            if df.empty:
                logger.error("No data to convert")
                return False
            
            # Generate default filename if not provided
            if not filename:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                if output_format.lower() == 'csv':
                    filename = f'amazon_products_with_reviews_{timestamp}.csv'
                elif output_format.lower() == 'excel':
                    filename = f'amazon_products_with_reviews_{timestamp}.xlsx'
                else:
                    logger.error(f"Unsupported format: {output_format}")
                    return False
            
            # Save based on format
            if output_format.lower() == 'csv':
                success = self.save_to_csv(df, filename)
            elif output_format.lower() == 'excel':
                success = self.save_to_excel(df, filename)
            else:
                logger.error(f"Unsupported format: {output_format}")
                success = False
            
            return success
            
        except Exception as e:
            logger.error(f"Error during conversion: {e}")
            return False
        
        finally:
            self.close()


def main():
    """Main execution function"""
    import argparse
    
    parser = argparse.ArgumentParser(description='Convert SQLite database to CSV/Excel with reviews as JSON')
    parser.add_argument('--db', default='amazon_scraper.db', help='Database file path')
    parser.add_argument('--format', choices=['csv', 'excel'], default='csv', help='Output format')
    parser.add_argument('--output', help='Output filename')
    
    args = parser.parse_args()
    
    logger.info("=" * 60)
    logger.info("DATABASE TO CSV/EXCEL CONVERTER")
    logger.info("=" * 60)
    logger.info(f"Database: {args.db}")
    logger.info(f"Format: {args.format}")
    
    # Check if database exists
    if not os.path.exists(args.db):
        logger.error(f"Database file not found: {args.db}")
        sys.exit(1)
    
    # Create converter
    converter = DatabaseToCSVConverter(args.db)
    
    # Convert
    success = converter.convert(args.format, args.output)
    
    if success:
        logger.info("=" * 60)
        logger.info("CONVERSION COMPLETED SUCCESSFULLY")
        logger.info("=" * 60)
    else:
        logger.error("=" * 60)
        logger.error("CONVERSION FAILED")
        logger.error("=" * 60)
        sys.exit(1)


if __name__ == "__main__":
    main()