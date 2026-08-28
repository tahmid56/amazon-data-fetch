#!/usr/bin/env python3
"""
Utility script to query the SQLite database
"""

import sqlite3
import pandas as pd
import sys

def query_products(db_path='amazon_scraper.db', limit=10):
    """Query products with video information"""
    conn = sqlite3.connect(db_path)
    
    query = f'''
        SELECT id, asin, title, price, rating, reviews_count, 
               brand, keyword, video_url, video_thumbnail
        FROM products
        ORDER BY created_at DESC
        LIMIT {limit}
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def query_products_with_videos(db_path='amazon_scraper.db', limit=10):
    """Query only products that have videos"""
    conn = sqlite3.connect(db_path)
    
    query = f'''
        SELECT id, asin, title, price, video_url, video_thumbnail, keyword
        FROM products
        WHERE video_url != 'N/A' AND video_url IS NOT NULL
        ORDER BY created_at DESC
        LIMIT {limit}
    '''
    
    df = pd.read_sql_query(query, conn)
    conn.close()
    return df

def query_statistics(db_path='amazon_scraper.db'):
    """Get database statistics"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    print("\n" + "=" * 60)
    print("DATABASE STATISTICS")
    print("=" * 60)
    
    # Products
    cursor.execute('SELECT COUNT(*) FROM products')
    total_products = cursor.fetchone()[0]
    print(f"Total Products: {total_products}")
    
    cursor.execute('SELECT COUNT(*) FROM products WHERE video_url != "N/A" AND video_url IS NOT NULL')
    products_with_videos = cursor.fetchone()[0]
    print(f"Products with Videos: {products_with_videos}")
    
    cursor.execute('SELECT COUNT(*) FROM products WHERE video_thumbnail != "N/A" AND video_thumbnail IS NOT NULL')
    products_with_thumbnails = cursor.fetchone()[0]
    print(f"Products with Video Thumbnails: {products_with_thumbnails}")
    
    # Reviews
    cursor.execute('SELECT COUNT(*) FROM reviews')
    print(f"Total Reviews: {cursor.fetchone()[0]}")
    
    # Show some products with videos
    cursor.execute('''
        SELECT title, video_url, video_thumbnail
        FROM products
        WHERE video_url != 'N/A' AND video_url IS NOT NULL
        LIMIT 3
    ''')
    
    print("\nSample Products with Videos:")
    for title, video_url, thumbnail in cursor.fetchall():
        print(f"\n  Title: {title[:50]}...")
        print(f"  Video URL: {video_url[:80]}...")
        print(f"  Thumbnail: {thumbnail[:80]}...")
    
    conn.close()
    print("\n" + "=" * 60)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        command = sys.argv[1]
        if command == 'products':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            df = query_products(limit=limit)
            print(df.to_string())
        elif command == 'videos':
            limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10
            df = query_products_with_videos(limit=limit)
            print(df.to_string())
        elif command == 'stats':
            query_statistics()
        else:
            print("Usage:")
            print("  python query_db.py products [limit]")
            print("  python query_db.py videos [limit]")
            print("  python query_db.py stats")
    else:
        query_statistics()