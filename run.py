#!/usr/bin/env python3
"""
Simple script to run the Amazon scraper
"""

import subprocess
import sys
import os

def install_requirements():
    """Install required packages"""
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])

def run_scraper():
    """Run the main scraper"""
    print("Starting Amazon scraper...")
    from main import main
    main()

if __name__ == "__main__":
    # Check if requirements are installed
    try:
        import selenium
        import bs4
        import pandas
    except ImportError:
        print("Installing missing dependencies...")
        install_requirements()
    
    # Run the scraper
    run_scraper()