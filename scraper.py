import time
import random
from typing import List, Dict, Optional, Tuple
import logging
import os
import shutil
import threading
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    WebDriverException,
    NoSuchElementException
)
from selenium.webdriver.chrome.service import Service
from bs4 import BeautifulSoup
from datetime import datetime
import json
import re
from config import Config
from retry_handler import RetryHandler
from database import DatabaseManager

logger = logging.getLogger('AmazonScraper')

class AmazonScraper:
    def __init__(self, retry_handler: RetryHandler, db_manager: DatabaseManager):
        self.retry_handler = retry_handler
        self.db_manager = db_manager
        self.captcha_count = 0
        self.consecutive_failures = 0
        # Thread-local storage for drivers
        self.thread_local = threading.local()
        
        logger.info("AmazonScraper initialized with multi-threading support")
    
    def get_driver(self) -> webdriver.Chrome:
        """Get thread-local driver instance"""
        if not hasattr(self.thread_local, 'driver') or self.thread_local.driver is None:
            self.thread_local.driver = self.create_driver()
            thread_name = threading.current_thread().name
            logger.info(f"Created new driver for thread: {thread_name}")
        return self.thread_local.driver
    
    def create_driver(self) -> webdriver.Chrome:
        """Create Chrome driver with anti-detection measures"""
        thread_name = threading.current_thread().name
        logger.info(f"[{thread_name}] Creating Chrome driver...")
        chrome_options = Config.get_chrome_options()
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            logger.info(f"[{thread_name}] Chrome driver created successfully")
        except Exception as e:
            logger.warning(f"[{thread_name}] Failed to create driver: {e}")
            chromedriver_path = shutil.which('chromedriver')
            if chromedriver_path:
                service = Service(chromedriver_path, log_path=os.devnull)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info(f"[{thread_name}] Chrome driver created using path: {chromedriver_path}")
            else:
                logger.error(f"[{thread_name}] ChromeDriver not found")
                raise Exception("ChromeDriver not found")
        
        driver.set_page_load_timeout(Config.PAGE_LOAD_TIMEOUT)
        
        # Stealth scripts
        stealth_js = """
        Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
        Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
        Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        window.chrome = {runtime: {}};
        """
        try:
            driver.execute_script(stealth_js)
            logger.debug(f"[{thread_name}] Stealth scripts executed")
        except Exception as e:
            logger.warning(f"[{thread_name}] Failed to execute stealth scripts: {e}")
        
        return driver
    
    def close_thread_driver(self):
        """Close thread-local driver"""
        if hasattr(self.thread_local, 'driver') and self.thread_local.driver:
            try:
                self.thread_local.driver.quit()
                thread_name = threading.current_thread().name
                logger.info(f"[{thread_name}] WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.thread_local.driver = None
    
    def close_all_drivers(self):
        """Close all thread-local drivers"""
        self.close_thread_driver()
        logger.info("All drivers closed")
    
    def is_captcha_page(self, driver: webdriver.Chrome) -> bool:
        """Check if current page is a CAPTCHA page"""
        try:
            current_url = driver.current_url.lower()
            if 'captcha' in current_url or 'robot' in current_url:
                return True
            
            page_title = driver.title.lower()
            if 'robot check' in page_title or 'captcha' in page_title:
                return True
            
            captcha_selectors = [
                "//input[@id='captchacharacters']",
                "//img[contains(@src, 'captcha')]",
                "//div[contains(@class, 'g-recaptcha')]",
                "//form[contains(@action, 'captcha')]",
            ]
            
            for selector in captcha_selectors:
                if driver.find_elements(By.XPATH, selector):
                    return True
            
            page_text = driver.page_source.lower()
            captcha_phrases = [
                'enter the characters you see below',
                'sorry, we just need to make sure',
                'type the characters you see'
            ]
            
            for phrase in captcha_phrases:
                if phrase in page_text:
                    return True
            
            return False
        except:
            return False
    
    def parse_search_results(self, html_content: str) -> List[Dict]:
        """Parse search results to get basic product info and URLs"""
        soup = BeautifulSoup(html_content, 'html.parser')
        products = []
        
        product_divs = soup.find_all('div', {'data-component-type': 's-search-result'})
        
        if not product_divs:
            product_divs = soup.find_all('div', {'class': 's-result-item'})
        
        logger.info(f"Found {len(product_divs)} products in search results")
        
        for div in product_divs[:Config.MAX_PRODUCTS_PER_KEYWORD]:
            try:
                product = {}
                
                # Title
                title_elem = div.find('span', {'class': 'a-text-normal'})
                if not title_elem:
                    title_elem = div.find('h2').find('span') if div.find('h2') else None
                product['title'] = title_elem.text.strip() if title_elem else "N/A"
                
                if product['title'] == "N/A":
                    continue
                
                # URL
                link_elem = div.find('a', {'class': 'a-link-normal s-no-outline'})
                if link_elem and 'href' in link_elem.attrs:
                    product['url'] = 'https://www.amazon.com' + link_elem['href']
                else:
                    link_elem = div.find('a', {'class': 'a-link-normal', 'href': True})
                    product['url'] = 'https://www.amazon.com' + link_elem['href'] if link_elem else "N/A"
                
                # ASIN from URL
                asin_match = re.search(r'/dp/([A-Z0-9]{10})', product['url'])
                product['asin'] = asin_match.group(1) if asin_match else "N/A"
                
                # Basic info
                price_elem = div.find('span', {'class': 'a-price'})
                if price_elem:
                    price_span = price_elem.find('span', {'class': 'a-offscreen'})
                    product['price'] = price_span.text.strip() if price_span else "N/A"
                else:
                    product['price'] = "N/A"
                
                rating_elem = div.find('span', {'class': 'a-icon-alt'})
                product['rating'] = rating_elem.text.strip() if rating_elem else "N/A"
                reviews_elem = div.find('span', {'class': 'a-size-mini puis-normal-weight-text s-underline-text'})
                product['reviews_count'] = reviews_elem.text.strip() if reviews_elem else "N/A"
                
                img_elem = div.find('img', {'class': 's-image'})
                product['image_url'] = img_elem['src'] if img_elem and 'src' in img_elem.attrs else "N/A"
                
                prime_elem = div.find('i', {'class': 'a-icon-prime'})
                product['is_prime'] = "Yes" if prime_elem else "No"
                
                sponsored_elem = div.find('span', {'class': 'puis-sponsored-label-text'})
                product['is_sponsored'] = "Yes" if sponsored_elem else "No"
                
                products.append(product)
                
            except Exception as e:
                logger.error(f"Error parsing search result: {e}")
                continue
        
        return products
    
    def extract_video_info(self, soup: BeautifulSoup) -> Tuple[str, str]:
        """Extract just video URL and thumbnail from HTML"""
        video_url = "N/A"
        video_thumbnail = "N/A"
        
        try:
            # Method 1: Look for video tags
            video_tags = soup.find_all('video')
            for video in video_tags:
                source_elem = video.find('source')
                if source_elem and 'src' in source_elem.attrs:
                    video_url = source_elem['src']
                elif 'src' in video.attrs:
                    video_url = video['src']
                
                if 'poster' in video.attrs:
                    video_thumbnail = video['poster']
                
                if video_url != "N/A":
                    break
            
            # Method 2: Look for video data attributes
            if video_url == "N/A":
                video_containers = soup.find_all(['div', 'span'], attrs={'data-video-url': True})
                for container in video_containers:
                    video_url = container.get('data-video-url', 'N/A')
                    video_thumbnail = container.get('data-video-thumbnail', 'N/A')
                    
                    if video_thumbnail == "N/A":
                        img_elem = container.find('img')
                        if img_elem and 'src' in img_elem.attrs:
                            video_thumbnail = img_elem['src']
                    
                    if video_url != "N/A":
                        break
            
            # Method 3: Look for video in JSON data
            if video_url == "N/A":
                script_tags = soup.find_all('script', {'type': 'application/json'})
                for script in script_tags:
                    try:
                        json_data = json.loads(script.string)
                        json_str = json.dumps(json_data)
                        
                        video_match = re.search(r'https?://[^"\']+\.(?:mp4|webm|m3u8)[^"\']*', json_str)
                        if video_match:
                            video_url = video_match.group(0)
                            break
                    except:
                        continue
            
            # Method 4: Look for iframe embeds (YouTube)
            if video_url == "N/A":
                iframes = soup.find_all('iframe')
                for iframe in iframes:
                    src = iframe.get('src', '')
                    if 'youtube.com' in src or 'youtu.be' in src or 'vimeo.com' in src:
                        video_url = src
                        
                        if 'youtube.com' in src or 'youtu.be' in src:
                            video_id_match = re.search(r'(?:youtube\.com/(?:watch\?v=|embed/)|youtu\.be/)([a-zA-Z0-9_-]+)', src)
                            if video_id_match:
                                video_id = video_id_match.group(1)
                                video_thumbnail = f'https://img.youtube.com/vi/{video_id}/hqdefault.jpg'
                        break
            
            return video_url, video_thumbnail
            
        except Exception as e:
            logger.error(f"Error extracting video info: {e}")
            return "N/A", "N/A"
    
    def scrape_product_details(self, product_url: str) -> Dict:
        """Scrape detailed product information (thread-safe)"""
        if not product_url or product_url == "N/A":
            return {}
        
        thread_name = threading.current_thread().name
        driver = self.get_driver()
        
        try:
            logger.info(f"[{thread_name}] Scraping product details: {product_url[:100]}...")
            
            driver.get(product_url)
            time.sleep(Config.get_random_delay())
            
            if self.is_captcha_page(driver):
                logger.warning(f"[{thread_name}] CAPTCHA detected on product page")
                return {}
            
            try:
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "productTitle"))
                )
            except TimeoutException:
                logger.warning(f"[{thread_name}] Timeout waiting for product title")
                return {}
            
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')
            
            details = {}
            
            asin_match = re.search(r'/dp/([A-Z0-9]{10})', product_url)
            asin = asin_match.group(1) if asin_match else "N/A"
            details['asin'] = asin
            
            title_elem = soup.find('span', {'id': 'productTitle'})
            details['full_title'] = title_elem.text.strip() if title_elem else "N/A"
            
            # Price
            price_elem = soup.find('span', {'class': 'a-price aok-align-center'})
            if not price_elem:
                price_elem = soup.find('span', {'class': 'a-price'})
            if price_elem:
                price_span = price_elem.find('span', {'class': 'a-offscreen'})
                details['current_price'] = price_span.text.strip() if price_span else "N/A"
            else:
                details['current_price'] = "N/A"
            
            # Original price
            original_price_elem = soup.find('span', {'class': 'a-price a-text-price'})
            if original_price_elem:
                price_span = original_price_elem.find('span', {'class': 'a-offscreen'})
                details['original_price'] = price_span.text.strip() if price_span else "N/A"
            else:
                details['original_price'] = "N/A"
            
            # Discount
            discount_elem = soup.find('span', {'class': 'savingsPercentage'})
            details['discount'] = discount_elem.text.strip() if discount_elem else "N/A"
            
            # Rating
            rating_elem = soup.find('span', {'class': 'a-icon-alt'})
            details['detailed_rating'] = rating_elem.text.strip() if rating_elem else "N/A"
            
            # Reviews count
            ratings_count_elem = soup.find('span', {'id': 'acrCustomerReviewText'})
            details['detailed_reviews_count'] = ratings_count_elem.text.strip() if ratings_count_elem else "N/A"
            
            # Availability
            availability_elem = soup.find('div', {'id': 'availability'})
            if availability_elem:
                availability_span = availability_elem.find('span')
                details['availability'] = availability_span.text.strip() if availability_span else "N/A"
            else:
                details['availability'] = "N/A"
            
            # Brand
            brand_elem = soup.find('a', {'id': 'bylineInfo'})
            details['brand'] = brand_elem.text.strip() if brand_elem else "N/A"
            
            # Description
            desc_elem = soup.find('ul', {'class': 'a-unordered-list a-vertical a-spacing-mini'})
            if desc_elem:
                details['description'] = desc_elem.text.strip()[:500] if desc_elem else "N/A"
            else:
                details['description'] = "N/A"
            
            # Features
            features_list = []
            features_container = soup.find('div', {'id': 'feature-bullets'})
            if features_container:
                feature_items = features_container.find_all('span', {'class': 'a-list-item'})
                features_list = [item.text.strip() for item in feature_items[:10]]
            details['features'] = ' | '.join(features_list) if features_list else "N/A"
            
            # Technical details - Extract entire table
            tech_details = {}
            details_container = soup.find('div', {'id': 'productDetails_expanderSectionTables'})
            if details_container:
                tables = details_container.find_all('table', {'class': 'a-keyvalue prodDetTable'})
                for table in tables:
                    rows = table.find_all('tr')
                    for row in rows:
                        th = row.find('th', {'class': 'a-color-secondary a-size-base prodDetSectionEntry'})
                        td = row.find('td', {'class': 'a-size-base prodDetAttrValue'})
                        if th and td:
                            key = th.text.strip()
                            value = td.text.strip()
                            if key and value:
                                tech_details[key] = value
            details['technical_details'] = json.dumps(tech_details) if tech_details else "N/A"
            
            # Dimensions
            dimensions_elem = soup.find('div', {'id': 'productDetails_detailBullets_sections1'})
            if dimensions_elem:
                details['dimensions'] = dimensions_elem.text.strip()[:300]
            else:
                details['dimensions'] = "N/A"
            
            # Best sellers rank
            rank_elem = soup.find('th', string=re.compile('Best Sellers Rank'))
            if rank_elem and rank_elem.parent:
                rank_td = rank_elem.parent.find('td')
                details['best_sellers_rank'] = rank_td.text.strip() if rank_td else "N/A"
            else:
                details['best_sellers_rank'] = "N/A"
            
            # Date first available
            date_elem = soup.find('th', string=re.compile('Date First Available'))
            if date_elem and date_elem.parent:
                date_td = date_elem.parent.find('td')
                details['date_first_available'] = date_td.text.strip() if date_td else "N/A"
            else:
                details['date_first_available'] = "N/A"
            
            # Manufacturer
            manufacturer_elem = soup.find('th', string=re.compile('Manufacturer'))
            if manufacturer_elem and manufacturer_elem.parent:
                manufacturer_td = manufacturer_elem.parent.find('td')
                details['manufacturer'] = manufacturer_td.text.strip() if manufacturer_td else "N/A"
            else:
                details['manufacturer'] = "N/A"
            
            # Video
            video_url, video_thumbnail = self.extract_video_info(soup)
            details['video_url'] = video_url
            details['video_thumbnail'] = video_thumbnail
            
            return details
            
        except Exception as e:
            logger.error(f"[{thread_name}] Error scraping product details: {e}", exc_info=True)
            return {}
    
    def extract_review_text(self, review_div) -> Tuple[str, str]:
        """Extract review title and body with multiple fallback methods"""
        review_title = "N/A"
        review_body = "N/A"
        
        try:
            # Extract review title with multiple selectors
            title_selectors = [
                ('a', {'data-hook': 'reviewTitle'}),
                ('span', {'data-hook': 'reviewTitle'}),
                ('div', {'data-hook': 'reviewTitle'}),
                ('a', {'class': 'reviewTitle'}),
                ('span', {'class': 'reviewTitle'}),
                ('div', {'class': 'reviewTitle'}),
                ('a', {'class': 'a-size-base a-link-normal reviewTitle a-color-base reviewTitle-content a-text-bold'}),
                ('span', {'class': 'a-size-base a-link-normal reviewTitle a-color-base reviewTitle-content a-text-bold'}),
            ]
            
            for tag, attrs in title_selectors:
                title_elem = review_div.find(tag, attrs)
                if title_elem:
                    review_title = title_elem.text.strip()
                    review_title = re.sub(r'\d+\.\d+ out of 5 stars\s*', '', review_title)
                    review_title = review_title.strip()
                    if review_title and review_title != "N/A":
                        break
            
            if review_title == "N/A":
                title_elem = review_div.find(class_=re.compile(r'review-title', re.I))
                if title_elem:
                    review_title = title_elem.text.strip()
                    review_title = re.sub(r'\d+\.\d+ out of 5 stars\s*', '', review_title)
                    review_title = review_title.strip()
            
            # Extract review body
            # First try the specific container structure
            rich_content_container = review_div.find('div', {'data-hook': 'reviewRichContentContainer'})
            if rich_content_container:
                p_elem = rich_content_container.find('p')
                if p_elem:
                    span_elem = p_elem.find('span')
                    if span_elem:
                        review_body = span_elem.get_text(strip=True)
                    else:
                        review_body = p_elem.get_text(strip=True)
                else:
                    span_elem = rich_content_container.find('span')
                    if span_elem:
                        review_body = span_elem.get_text(strip=True)
                    else:
                        review_body = rich_content_container.get_text(strip=True)
                
                if review_body and review_body != "N/A":
                    return review_title, review_body
            
            # Try other selectors
            body_selectors = [
                ('span', {'data-hook': 'reviewText'}),
                ('div', {'data-hook': 'reviewText'}),
                ('p', {'data-hook': 'reviewText'}),
                ('span', {'class': 'reviewText'}),
                ('div', {'class': 'reviewText'}),
                ('span', {'class': 'a-size-base reviewText'}),
                ('div', {'class': 'a-size-base reviewText'}),
                ('span', {'class': 'cr-original-review-content'}),
                ('div', {'class': 'cr-original-review-content'}),
            ]
            
            for tag, attrs in body_selectors:
                body_elem = review_div.find(tag, attrs)
                if body_elem:
                    review_body = body_elem.text.strip()
                    if review_body and review_body != "N/A":
                        break
            
            if review_body == "N/A":
                body_elem = review_div.find(class_=re.compile(r'reviewRichContentContainer', re.I))
                if body_elem:
                    review_body = body_elem.text.strip()
            
            # Clean up text
            if review_title != "N/A":
                review_title = ' '.join(review_title.split())
            
            if review_body != "N/A":
                review_body = ' '.join(review_body.split())
                review_body = re.sub(r'\s+', ' ', review_body).strip()
            
            return review_title, review_body
            
        except Exception as e:
            logger.error(f"Error extracting review text: {e}")
            return "N/A", "N/A"
    
    def scrape_product_reviews(self, product_url: str, product_title: str, product_id: Optional[int] = None) -> List[Dict]:
        """Scrape reviews from product page (thread-safe)"""
        reviews = []
        
        if not product_url or product_url == "N/A":
            return reviews
        
        thread_name = threading.current_thread().name
        driver = self.get_driver()
        
        try:
            reviews_url = product_url.split('?')[0] + '?th=1&psc=1#customerReviews'
            logger.info(f"[{thread_name}] Scraping reviews...")
            
            driver.get(reviews_url)
            time.sleep(Config.get_random_delay())
            
            if self.is_captcha_page(driver):
                logger.warning(f"[{thread_name}] CAPTCHA detected on reviews page")
                return reviews
            
            review_selectors = [
                "[data-hook='review']",
                ".review",
                "#cm_cr-review_list [data-hook='review']",
                "div[data-hook='review']"
            ]
            
            reviews_loaded = False
            for selector in review_selectors:
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    reviews_loaded = True
                    break
                except TimeoutException:
                    continue
            
            if not reviews_loaded:
                logger.warning(f"[{thread_name}] No reviews found")
                return reviews
            
            for _ in range(3):
                driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(random.uniform(0.5, 1))
            
            html_content = driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')
            
            review_divs = soup.find_all('div', {'data-hook': 'review'})
            if not review_divs:
                review_divs = soup.find_all('div', {'class': 'review'})
            
            logger.info(f"[{thread_name}] Found {len(review_divs)} reviews")
            
            for idx, review_div in enumerate(review_divs[:Config.MAX_REVIEWS_PER_PRODUCT], 1):
                try:
                    review = {}
                    
                    review_title, review_body = self.extract_review_text(review_div)
                    
                    # Rating
                    review_rating = "N/A"
                    rating_elem = review_div.find('i', {'data-hook': 'review-star-rating'})
                    if rating_elem:
                        rating_text = rating_elem.find('span', {'class': 'a-icon-alt'})
                        if rating_text:
                            rating_value = rating_text.text.strip()
                            rating_match = re.search(r'(\d+\.?\d*)', rating_value)
                            if rating_match:
                                review_rating = rating_match.group(1)
                    
                    # Date
                    review_date = "N/A"
                    date_elem = review_div.find('span', {'data-hook': 'review-date'})
                    if date_elem:
                        review_date = date_elem.text.strip()
                    
                    # Reviewer name
                    reviewer_name = "N/A"
                    reviewer_elem = review_div.find('span', {'class': 'a-profile-name'})
                    if reviewer_elem:
                        reviewer_name = reviewer_elem.text.strip()
                    
                    # Verified purchase
                    verified_purchase = "No"
                    verified_elem = review_div.find('span', {'data-hook': 'avp-badge'})
                    if verified_elem:
                        verified_purchase = "Yes"
                    
                    # Helpful votes
                    helpful_votes = "N/A"
                    helpful_elem = review_div.find('span', {'data-hook': 'helpful-vote-statement'})
                    if helpful_elem:
                        helpful_votes = helpful_elem.text.strip()
                    
                    review['review_title'] = review_title
                    review['review_body'] = review_body
                    review['review_rating'] = review_rating
                    review['review_date'] = review_date
                    review['reviewer_name'] = reviewer_name
                    review['verified_purchase'] = verified_purchase
                    review['helpful_votes'] = helpful_votes
                    review['product_title'] = product_title
                    review['product_url'] = product_url
                    review['scraped_at'] = datetime.now().isoformat()
                    
                    review_id = self.db_manager.insert_review(review, product_id)
                    reviews.append(review)
                    
                except Exception as e:
                    logger.error(f"[{thread_name}] Error parsing review {idx}: {e}")
                    continue
            
            logger.info(f"[{thread_name}] Scraped {len(reviews)} reviews")
            return reviews
            
        except Exception as e:
            logger.error(f"[{thread_name}] Error scraping reviews: {e}", exc_info=True)
            return reviews
    
    def scrape_keyword(self, keyword: str, keyword_index: int, total_keywords: int) -> Dict:
        """Scrape products and details for a keyword (thread-safe)"""
        thread_name = threading.current_thread().name
        logger.info(f"[{thread_name}] [{keyword_index}/{total_keywords}] Processing: {keyword}")
        
        driver = self.get_driver()
        
        try:
            search_url = Config.SEARCH_URL.format(keyword=keyword.replace(' ', '+'))
            logger.info(f"[{thread_name}] Searching: {search_url}")
            
            driver.get(search_url)
            time.sleep(Config.get_random_delay())
            
            if self.is_captcha_page(driver):
                logger.warning(f"[{thread_name}] CAPTCHA for keyword: {keyword}")
                self.db_manager.insert_keyword_status(keyword, 'failed', 0, 0, 'CAPTCHA detected')
                return {'keyword': keyword, 'products': [], 'error': 'CAPTCHA'}
            
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-component-type='s-search-result']"))
                )
            except TimeoutException:
                logger.warning(f"[{thread_name}] No results for: {keyword}")
                self.db_manager.insert_keyword_status(keyword, 'failed', 0, 0, 'No results')
                return {'keyword': keyword, 'products': [], 'error': 'No results'}
            
            driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(random.uniform(1, 2))
            
            products = self.parse_search_results(driver.page_source)
            logger.info(f"[{thread_name}] Found {len(products)} products for: {keyword}")
            
            all_products = []
            all_reviews = []
            
            for idx, product in enumerate(products[:Config.MAX_PRODUCTS_PER_KEYWORD], 1):
                logger.info(f"[{thread_name}] [{idx}/{len(products[:Config.MAX_PRODUCTS_PER_KEYWORD])}] {product['title'][:40]}...")
                
                details = self.scrape_product_details(product['url'])
                full_product = {**product, **details}
                full_product['keyword'] = keyword
                full_product['scraped_at'] = datetime.now().isoformat()
                
                product_id = self.db_manager.insert_product(full_product)
                
                reviews = self.scrape_product_reviews(product['url'], product['title'], product_id)
                all_reviews.extend(reviews)
                all_products.append(full_product)
                
                if idx < len(products[:Config.MAX_PRODUCTS_PER_KEYWORD]):
                    time.sleep(Config.get_delay_between_products())
            
            self.db_manager.insert_keyword_status(
                keyword, 'success' if all_products else 'failed',
                len(all_products), len(all_reviews)
            )
            
            logger.info(f"[{thread_name}] Completed '{keyword}': {len(all_products)} products, {len(all_reviews)} reviews")
            
            return {'keyword': keyword, 'products': all_products, 'reviews': all_reviews}
            
        except Exception as e:
            logger.error(f"[{thread_name}] Error scraping {keyword}: {e}", exc_info=True)
            self.db_manager.insert_keyword_status(keyword, 'failed', 0, 0, str(e)[:200])
            self.close_thread_driver()
            raise