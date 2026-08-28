import time
import random
from typing import List, Dict, Optional, Tuple
import logging
import os
import shutil
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
        self.driver = None
        self.captcha_count = 0
        self.consecutive_failures = 0
        
        logger.info("AmazonScraper initialized")
    
    def create_driver(self) -> webdriver.Chrome:
        """Create Chrome driver with anti-detection measures"""
        logger.info("Creating Chrome driver...")
        chrome_options = Config.get_chrome_options()
        
        try:
            driver = webdriver.Chrome(options=chrome_options)
            logger.info("Chrome driver created successfully")
        except Exception as e:
            logger.warning(f"Failed to create driver: {e}")
            chromedriver_path = shutil.which('chromedriver')
            if chromedriver_path:
                service = Service(chromedriver_path, log_path=os.devnull)
                driver = webdriver.Chrome(service=service, options=chrome_options)
                logger.info(f"Chrome driver created using path: {chromedriver_path}")
            else:
                logger.error("ChromeDriver not found")
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
            logger.debug("Stealth scripts executed")
        except Exception as e:
            logger.warning(f"Failed to execute stealth scripts: {e}")
        
        return driver
    
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
        """Scrape detailed product information including video URL and thumbnail"""
        if not product_url or product_url == "N/A":
            return {}
        
        try:
            logger.info(f"Scraping product details: {product_url[:100]}...")
            
            self.driver.get(product_url)
            time.sleep(Config.get_random_delay())
            
            if self.is_captcha_page(self.driver):
                logger.warning("CAPTCHA detected on product page")
                return {}
            
            try:
                WebDriverWait(self.driver, 10).until(
                    EC.presence_of_element_located((By.ID, "productTitle"))
                )
            except TimeoutException:
                logger.warning("Timeout waiting for product title")
                return {}
            
            html_content = self.driver.page_source
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
            desc_elem = soup.find('div', {'id': 'productDescription'})
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
            
            # Technical details
            tech_details = {}
            tech_table = soup.find('table', {'id': 'productDetails_techSpec_section_1'})
            if tech_table:
                rows = tech_table.find_all('tr')
                for row in rows:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        tech_details[th.text.strip()] = td.text.strip()
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
            logger.error(f"Error scraping product details: {e}", exc_info=True)
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
                    # Remove "stars" text if present
                    review_title = re.sub(r'\d+\.\d+ out of 5 stars\s*', '', review_title)
                    review_title = review_title.strip()
                    if review_title and review_title != "N/A":
                        break
            
            # If title still not found, try to find it in a different way
            if review_title == "N/A":
                # Look for any element with review-title class
                title_elem = review_div.find(class_=re.compile(r'review-title', re.I))
                if title_elem:
                    review_title = title_elem.text.strip()
                    review_title = re.sub(r'\d+\.\d+ out of 5 stars\s*', '', review_title)
                    review_title = review_title.strip()
            
            # Extract review body with multiple selectors
            body_selectors = [
                ('span', {'data-hook': 'reviewText'}),
                ('div', {'data-hook': 'reviewText'}),
                ('p', {'data-hook': 'reviewText'}),
                ('span', {'class': 'reviewText'}),
                ('div', {'class': 'reviewText'}),
                ('span', {'class': 'a-size-base reviewText'}),
                ('div', {'class': 'a-size-base reviewText'}),
                ('span', {'class': 'a-size-base reviewText reviewText-content'}),
                ('div', {'class': 'a-size-base reviewText reviewText-content'}),
                ('span', {'class': 'cr-original-review-content'}),
                ('div', {'class': 'cr-original-review-content'}),
            ]
            
            for tag, attrs in body_selectors:
                body_elem = review_div.find(tag, attrs)
                if body_elem:
                    review_body = body_elem.text.strip()
                    if review_body and review_body != "N/A":
                        break
            
            # If body still not found, try to find it in a different way
            if review_body == "N/A":
                # Look for any element with review-text class
                body_elem = review_div.find(class_=re.compile(r'reviewRichContentContainer', re.I))
                if body_elem:
                    review_body = body_elem.text.strip()
                
                # Try to find in the review content area
                if review_body == "N/A":
                    content_area = review_div.find('div', {'class': 'a-row a-spacing-small review-data'})
                    if content_area:
                        # Find the text after the title
                        spans = content_area.find_all('span')
                        for span in spans:
                            text = span.text.strip()
                            if len(text) > 20:  # Assume body text is longer than 20 chars
                                review_body = text
                                break
            
            # Clean up the text
            if review_title != "N/A":
                review_title = review_title.strip()
                # Remove extra whitespace
                review_title = ' '.join(review_title.split())
            
            if review_body != "N/A":
                review_body = review_body.strip()
                # Remove extra whitespace
                review_body = ' '.join(review_body.split())
            
            return review_title, review_body
            
        except Exception as e:
            logger.error(f"Error extracting review text: {e}")
            return "N/A", "N/A"
    
    def scrape_product_reviews(self, product_url: str, product_title: str, product_id: Optional[int] = None) -> List[Dict]:
        """Scrape reviews from product page with improved extraction"""
        reviews = []
        
        if not product_url or product_url == "N/A":
            logger.warning("Invalid product URL for reviews")
            return reviews
        
        try:
            # Navigate to reviews page
            reviews_url = product_url.split('?')[0] + '?th=1&psc=1#customerReviews'
            logger.info(f"Scraping reviews from: {reviews_url[:100]}...")
            
            self.driver.get(reviews_url)
            time.sleep(Config.get_random_delay())
            
            if self.is_captcha_page(self.driver):
                logger.warning("CAPTCHA detected on reviews page")
                return reviews
            
            # Wait for reviews to load with multiple selector options
            review_selectors = [
                "[data-hook='review']",
                ".review",
                "#cm_cr-review_list [data-hook='review']",
                "div[data-hook='review']"
            ]
            
            reviews_loaded = False
            for selector in review_selectors:
                try:
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    reviews_loaded = True
                    logger.debug(f"Reviews loaded with selector: {selector}")
                    break
                except TimeoutException:
                    continue
            
            if not reviews_loaded:
                logger.warning("No reviews found or timeout")
                return reviews
            
            # Scroll to load more reviews
            for _ in range(3):
                self.driver.execute_script("window.scrollBy(0, 500);")
                time.sleep(random.uniform(0.5, 1))
            
            # Get page source
            html_content = self.driver.page_source
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Find all review containers with multiple selectors
            review_divs = soup.find_all('div', {'data-hook': 'review'})
            
            if not review_divs:
                review_divs = soup.find_all('div', {'class': 'review'})
            
            if not review_divs:
                review_divs = soup.find_all('div', {'class': re.compile(r'review', re.I)})
            
            logger.info(f"Found {len(review_divs)} reviews")
            
            for idx, review_div in enumerate(review_divs[:Config.MAX_REVIEWS_PER_PRODUCT], 1):
                try:
                    review = {}
                    
                    # Extract review title and body with improved methods
                    review_title, review_body = self.extract_review_text(review_div)
                    
                    # Extract review rating
                    review_rating = "N/A"
                    rating_elem = review_div.find('i', {'data-hook': 'review-star-rating'})
                    if rating_elem:
                        rating_text = rating_elem.find('span', {'class': 'a-icon-alt'})
                        if rating_text:
                            review_rating = rating_text.text.strip()
                            # Extract just the number
                            rating_match = re.search(r'(\d+\.?\d*)', review_rating)
                            if rating_match:
                                review_rating = rating_match.group(1)
                    else:
                        # Try alternative rating selectors
                        rating_elem = review_div.find('i', {'class': re.compile(r'a-icon-star', re.I)})
                        if rating_elem:
                            rating_text = rating_elem.find('span', {'class': 'a-icon-alt'})
                            if rating_text:
                                review_rating = rating_text.text.strip()
                                rating_match = re.search(r'(\d+\.?\d*)', review_rating)
                                if rating_match:
                                    review_rating = rating_match.group(1)
                    
                    # Extract review date
                    review_date = "N/A"
                    date_elem = review_div.find('span', {'data-hook': 'review-date'})
                    if date_elem:
                        review_date = date_elem.text.strip()
                    else:
                        # Try alternative date selectors
                        date_elem = review_div.find('span', {'class': 'review-date'})
                        if date_elem:
                            review_date = date_elem.text.strip()
                    
                    # Extract reviewer name
                    reviewer_name = "N/A"
                    reviewer_elem = review_div.find('span', {'class': 'a-profile-name'})
                    if reviewer_elem:
                        reviewer_name = reviewer_elem.text.strip()
                    else:
                        # Try alternative name selectors
                        reviewer_elem = review_div.find('div', {'class': 'a-profile-content'})
                        if reviewer_elem:
                            name_elem = reviewer_elem.find('span')
                            if name_elem:
                                reviewer_name = name_elem.text.strip()
                    
                    # Check verified purchase
                    verified_purchase = "No"
                    verified_elem = review_div.find('span', {'data-hook': 'avp-badge'})
                    if verified_elem:
                        verified_purchase = "Yes"
                    else:
                        # Try alternative verified badge selectors
                        verified_elem = review_div.find('span', {'class': re.compile(r'verified', re.I)})
                        if verified_elem:
                            verified_purchase = "Yes"
                    
                    # Extract helpful votes
                    helpful_votes = "N/A"
                    helpful_elem = review_div.find('span', {'data-hook': 'helpful-vote-statement'})
                    if helpful_elem:
                        helpful_votes = helpful_elem.text.strip()
                    else:
                        # Try alternative helpful votes selectors
                        helpful_elem = review_div.find('span', {'class': re.compile(r'helpful', re.I)})
                        if helpful_elem:
                            helpful_votes = helpful_elem.text.strip()
                    
                    # Set review data
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
                    
                    # Log review details
                    logger.debug(f"Review {idx}:")
                    logger.debug(f"  Title: {review_title[:50]}...")
                    logger.debug(f"  Rating: {review_rating}")
                    logger.debug(f"  Date: {review_date}")
                    logger.debug(f"  Reviewer: {reviewer_name}")
                    logger.debug(f"  Body length: {len(review_body)} characters")
                    
                    # Save to database
                    review_id = self.db_manager.insert_review(review, product_id)
                    
                    reviews.append(review)
                    
                except Exception as e:
                    logger.error(f"Error parsing review {idx}: {e}")
                    continue
            
            # Log summary
            successful_bodies = sum(1 for r in reviews if r.get('review_body') != 'N/A')
            successful_titles = sum(1 for r in reviews if r.get('review_title') != 'N/A')
            logger.info(f"Scraped {len(reviews)} reviews")
            logger.info(f"  - With body: {successful_bodies}")
            logger.info(f"  - With title: {successful_titles}")
            
            return reviews
            
        except Exception as e:
            logger.error(f"Error scraping reviews: {e}", exc_info=True)
            return reviews
    
    def scrape_keyword(self, keyword: str, keyword_index: int, total_keywords: int) -> Dict:
        """Scrape products and their details for a keyword"""
        logger.info(f"[{keyword_index}/{total_keywords}] Processing keyword: {keyword}")
        
        try:
            if self.driver is None:
                self.driver = self.create_driver()
            
            search_url = Config.SEARCH_URL.format(keyword=keyword.replace(' ', '+'))
            logger.info(f"Searching: {search_url}")
            
            self.driver.get(search_url)
            time.sleep(Config.get_random_delay())
            
            if self.is_captcha_page(self.driver):
                logger.warning(f"CAPTCHA detected for keyword: {keyword}")
                self.db_manager.insert_keyword_status(
                    keyword, 'failed', 0, 0, 'CAPTCHA detected'
                )
                return {'keyword': keyword, 'products': [], 'error': 'CAPTCHA'}
            
            try:
                WebDriverWait(self.driver, 15).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "[data-component-type='s-search-result']"))
                )
            except TimeoutException:
                logger.warning(f"No search results for: {keyword}")
                self.db_manager.insert_keyword_status(
                    keyword, 'failed', 0, 0, 'No results found'
                )
                return {'keyword': keyword, 'products': [], 'error': 'No results'}
            
            self.driver.execute_script("window.scrollBy(0, 500);")
            time.sleep(random.uniform(1, 2))
            
            html_content = self.driver.page_source
            products = self.parse_search_results(html_content)
            
            logger.info(f"Found {len(products)} products for keyword: {keyword}")
            
            all_products = []
            all_reviews = []
            
            for idx, product in enumerate(products[:Config.MAX_PRODUCTS_PER_KEYWORD], 1):
                logger.info(f"  [{idx}/{min(len(products), Config.MAX_PRODUCTS_PER_KEYWORD)}] Scraping: {product['title'][:50]}...")
                
                details = self.scrape_product_details(product['url'])
                
                full_product = {**product, **details}
                full_product['keyword'] = keyword
                full_product['scraped_at'] = datetime.now().isoformat()
                
                product_id = self.db_manager.insert_product(full_product)
                
                reviews = self.scrape_product_reviews(
                    product['url'], 
                    product['title'],
                    product_id
                )
                all_reviews.extend(reviews)
                
                all_products.append(full_product)
                
                if idx < len(products[:Config.MAX_PRODUCTS_PER_KEYWORD]):
                    delay = Config.get_delay_between_products()
                    logger.info(f"  Waiting {delay:.2f} seconds before next product...")
                    time.sleep(delay)
            
            self.db_manager.insert_keyword_status(
                keyword, 
                'success' if all_products else 'failed',
                len(all_products),
                len(all_reviews),
                None if all_products else 'No products scraped'
            )
            
            logger.info(f"Completed keyword '{keyword}': {len(all_products)} products, {len(all_reviews)} reviews")
            
            return {
                'keyword': keyword,
                'products': all_products,
                'reviews': all_reviews
            }
            
        except Exception as e:
            logger.error(f"Error scraping keyword {keyword}: {e}", exc_info=True)
            self.db_manager.insert_keyword_status(
                keyword, 'failed', 0, 0, str(e)[:200]
            )
            self.close_driver()
            raise
    
    def close_driver(self):
        """Close the driver"""
        if self.driver:
            try:
                self.driver.quit()
                logger.info("WebDriver closed")
            except Exception as e:
                logger.error(f"Error closing WebDriver: {e}")
            finally:
                self.driver = None