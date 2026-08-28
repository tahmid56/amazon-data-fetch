import random
import os
import logging
import warnings

# Suppress warnings
warnings.filterwarnings('ignore')
os.environ['WDM_LOG_LEVEL'] = '0'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'

class Config:
    # Scraping settings
    MAX_RETRIES = 2
    MIN_DELAY = 3
    MAX_DELAY = 7
    PAGE_LOAD_TIMEOUT = 30
    
    # Image loading
    LOAD_IMAGES = True
    
    # Amazon settings
    BASE_URL = "https://www.amazon.com"
    SEARCH_URL = "https://www.amazon.com/s?k={keyword}"
    
    # Browser settings
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    # Database settings
    DATABASE_PATH = "amazon_scraper.db"
    
    # Delay settings
    DELAY_BETWEEN_KEYWORDS_MIN = 5
    DELAY_BETWEEN_KEYWORDS_MAX = 10
    DELAY_BETWEEN_PRODUCTS_MIN = 3
    DELAY_BETWEEN_PRODUCTS_MAX = 6
    
    # Scraping limits
    MAX_PRODUCTS_PER_KEYWORD = 30
    MAX_REVIEWS_PER_PRODUCT = 50
    
    # CAPTCHA handling
    CAPTCHA_WAIT_TIME = 60
    MAX_CAPTCHA_RETRIES = 2
    
    @classmethod
    def get_random_user_agent(cls):
        return random.choice(cls.USER_AGENTS)
    
    @classmethod
    def get_random_delay(cls):
        return random.uniform(cls.MIN_DELAY, cls.MAX_DELAY)
    
    @classmethod
    def get_delay_between_keywords(cls):
        return random.uniform(cls.DELAY_BETWEEN_KEYWORDS_MIN, cls.DELAY_BETWEEN_KEYWORDS_MAX)
    
    @classmethod
    def get_delay_between_products(cls):
        return random.uniform(cls.DELAY_BETWEEN_PRODUCTS_MIN, cls.DELAY_BETWEEN_PRODUCTS_MAX)
    
    @classmethod
    def get_chrome_options(cls):
        from selenium.webdriver.chrome.options import Options
        
        chrome_options = Options()
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-gpu')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-extensions')
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--log-level=3')
        chrome_options.add_argument('--silent')
        chrome_options.add_argument('--disable-logging')
        chrome_options.add_argument('--disable-gcm')
        chrome_options.add_argument('--disable-background-networking')
        chrome_options.add_argument('--disable-component-update')
        chrome_options.add_argument('--disable-domain-reliability')
        chrome_options.add_argument('--disable-sync')
        chrome_options.add_argument('--disable-default-apps')
        chrome_options.add_argument('--metrics-recording-only')
        chrome_options.add_argument('--no-first-run')
        chrome_options.add_argument('--safebrowsing-disable-auto-update')
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        prefs = {
            "profile.default_content_setting_values.notifications": 2,
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.images": 1 if cls.LOAD_IMAGES else 2,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        return chrome_options