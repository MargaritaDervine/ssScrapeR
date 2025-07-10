#!/usr/bin/env python3
"""
SS.LV Real Estate Monitoring Script

This script monitors specified ss.lv real estate listings and sends email notifications
for new advertisements that match the configured criteria.
"""

import os
import json
import time
import logging
import smtplib
import schedule
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import List, Dict, Set
import requests
from bs4 import BeautifulSoup
import re

# =============================================================================
# CONFIGURATION SECTION - Modify these variables as needed
# =============================================================================

# URLs to monitor
URLS_TO_MONITOR = [
    "https://www.ss.lv/lv/real-estate/homes-summer-residences/riga-region/olaines-pag/filter/",
    "https://www.ss.lv/lv/real-estate/plots-and-lands/riga-region/olaines-pag/filter/"
]

# Email configuration
EMAIL_SMTP_SERVER = "smtp.gmail.com"
EMAIL_SMTP_PORT = 587
EMAIL_FROM = os.getenv("EMAIL_FROM", "your_email@gmail.com")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "your_app_password")
EMAIL_TO = os.getenv("EMAIL_TO", "recipient@gmail.com")

# Search criteria - modify these to match your requirements
SEARCH_CRITERIA = {
    "max_price": 150000,  # Maximum price in EUR
    "min_price": 10000,   # Minimum price in EUR
    "keywords_include": ["māja", "zeme", "privātmāja", "dzīvoklis"],  # Keywords that should be present
    "keywords_exclude": ["bojāts", "avārijas", "slēgts"],  # Keywords to exclude
    "min_area": 50,       # Minimum area in m²
}

# Scheduling configuration
RUN_MODE = "single"      # "single" = run once and exit, "continuous" = keep running with schedule
RUN_INTERVAL_HOURS = 24  # How often to check for new listings (only used in continuous mode)
RUN_IMMEDIATELY = True   # Whether to run the check immediately when script starts

# File paths
DATA_FILE = "listings_data.json"

# Logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('ss_lv_monitor.log'),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# =============================================================================
# CORE FUNCTIONALITY
# =============================================================================

class SSLVMonitor:
    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        })
        self.known_listings = self.load_known_listings()

    def load_known_listings(self) -> Set[str]:
        """Load previously seen listing IDs from JSON file."""
        try:
            if os.path.exists(DATA_FILE):
                with open(DATA_FILE, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return set(data.get('known_listings', []))
        except Exception as e:
            logger.error(f"Error loading known listings: {e}")
        return set()

    def save_known_listings(self):
        """Save known listing IDs to JSON file."""
        try:
            data = {
                'known_listings': list(self.known_listings),
                'last_updated': datetime.now().isoformat()
            }
            with open(DATA_FILE, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error(f"Error saving known listings: {e}")

    def extract_price(self, price_text: str) -> float:
        """Extract numeric price from price text."""
        if not price_text:
            return 0
        
        # Remove currency symbols and spaces, extract numbers
        price_clean = re.sub(r'[^\d,.]', '', price_text)
        price_clean = price_clean.replace(',', '')
        
        try:
            return float(price_clean)
        except (ValueError, TypeError):
            return 0

    def extract_area(self, area_text: str) -> float:
        """Extract numeric area from area text."""
        if not area_text:
            return 0
        
        # Look for number followed by m² or similar
        area_match = re.search(r'(\d+(?:\.\d+)?)', area_text)
        if area_match:
            try:
                return float(area_match.group(1))
            except (ValueError, TypeError):
                pass
        return 0

    def meets_criteria(self, listing: Dict) -> bool:
        """Check if a listing meets the search criteria."""
        try:
            # Price check
            price = listing.get('price', 0)
            if price > 0:
                if price < SEARCH_CRITERIA['min_price'] or price > SEARCH_CRITERIA['max_price']:
                    return False

            # Area check
            area = listing.get('area', 0)
            if area > 0 and area < SEARCH_CRITERIA['min_area']:
                return False

            # Keyword checks
            text_content = f"{listing.get('title', '')} {listing.get('description', '')}".lower()
            
            # Check for required keywords
            if SEARCH_CRITERIA['keywords_include']:
                has_required = any(keyword.lower() in text_content for keyword in SEARCH_CRITERIA['keywords_include'])
                if not has_required:
                    return False

            # Check for excluded keywords
            if SEARCH_CRITERIA['keywords_exclude']:
                has_excluded = any(keyword.lower() in text_content for keyword in SEARCH_CRITERIA['keywords_exclude'])
                if has_excluded:
                    return False

            return True

        except Exception as e:
            logger.error(f"Error checking criteria for listing: {e}")
            return False

    def scrape_listings(self, url: str) -> List[Dict]:
        """Scrape listings from a given ss.lv URL."""
        listings = []
        
        try:
            logger.info(f"Scraping URL: {url}")
            response = self.session.get(url, timeout=30)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Find listing rows - ss.lv uses table structure
            listing_rows = soup.find_all('tr', id=lambda x: x and x.startswith('tr_'))
            
            for row in listing_rows:
                try:
                    listing_id = row.get('id', '').replace('tr_', '')
                    if not listing_id:
                        continue

                    # Extract listing details
                    cells = row.find_all('td')
                    if len(cells) < 4:
                        continue

                    # Title and link (usually in first or second cell)
                    title_cell = None
                    link = None
                    for cell in cells:
                        link_elem = cell.find('a')
                        if link_elem and link_elem.get('href'):
                            title_cell = cell
                            link = link_elem.get('href')
                            if not link.startswith('http'):
                                link = 'https://www.ss.lv' + link
                            break

                    if not title_cell or not link:
                        continue

                    title = title_cell.get_text(strip=True)
                    
                    # Extract price (usually in a cell with euro symbol)
                    price = 0
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if '€' in cell_text or 'EUR' in cell_text:
                            price = self.extract_price(cell_text)
                            break

                    # Extract area (look for m² symbol)
                    area = 0
                    for cell in cells:
                        cell_text = cell.get_text(strip=True)
                        if 'm²' in cell_text or 'm2' in cell_text:
                            area = self.extract_area(cell_text)
                            break

                    # Extract location/description from remaining cells
                    description_parts = []
                    for cell in cells:
                        text = cell.get_text(strip=True)
                        if text and text != title and '€' not in text and 'm²' not in text:
                            description_parts.append(text)

                    listing = {
                        'id': listing_id,
                        'title': title,
                        'price': price,
                        'area': area,
                        'description': ' | '.join(description_parts),
                        'link': link,
                        'source_url': url,
                        'scraped_at': datetime.now().isoformat()
                    }

                    listings.append(listing)

                except Exception as e:
                    logger.error(f"Error parsing listing row: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error scraping URL {url}: {e}")
        
        logger.info(f"Found {len(listings)} listings from {url}")
        return listings

    def check_for_new_listings(self) -> List[Dict]:
        """Check all monitored URLs for new listings that meet criteria."""
        new_matching_listings = []
        
        for url in URLS_TO_MONITOR:
            try:
                listings = self.scrape_listings(url)
                
                for listing in listings:
                    listing_id = listing['id']
                    
                    # Check if this is a new listing
                    if listing_id not in self.known_listings:
                        self.known_listings.add(listing_id)
                        
                        # Check if it meets our criteria
                        if self.meets_criteria(listing):
                            new_matching_listings.append(listing)
                            logger.info(f"New matching listing found: {listing['title']} - {listing['price']}€")
                
                # Small delay between requests to be respectful
                time.sleep(2)
                
            except Exception as e:
                logger.error(f"Error checking URL {url}: {e}")
        
        # Save updated known listings
        self.save_known_listings()
        
        return new_matching_listings

    def send_email_notification(self, listings: List[Dict]):
        """Send email notification for new listings."""
        if not listings:
            return

        try:
            # Create email content
            msg = MIMEMultipart()
            msg['From'] = EMAIL_FROM
            msg['To'] = EMAIL_TO
            msg['Subject'] = f"SS.LV Alert: {len(listings)} New Matching Listing(s) Found"

            # Create email body
            body = f"""
New real estate listings matching your criteria have been found on SS.LV:

"""
            
            for i, listing in enumerate(listings, 1):
                body += f"""
{i}. {listing['title']}
   Price: {listing['price']}€
   Area: {listing['area']} m²
   Description: {listing['description']}
   Link: {listing['link']}
   
"""

            body += f"""
Search Criteria:
- Price range: {SEARCH_CRITERIA['min_price']}€ - {SEARCH_CRITERIA['max_price']}€
- Minimum area: {SEARCH_CRITERIA['min_area']} m²
- Include keywords: {', '.join(SEARCH_CRITERIA['keywords_include'])}
- Exclude keywords: {', '.join(SEARCH_CRITERIA['keywords_exclude'])}

Happy house hunting!

---
This is an automated message from your SS.LV monitoring script.
"""

            msg.attach(MIMEText(body, 'plain', 'utf-8'))

            # Send email
            with smtplib.SMTP(EMAIL_SMTP_SERVER, EMAIL_SMTP_PORT) as server:
                server.starttls()
                server.login(EMAIL_FROM, EMAIL_PASSWORD)
                server.send_message(msg)

            logger.info(f"Email notification sent for {len(listings)} new listings")

        except Exception as e:
            logger.error(f"Error sending email notification: {e}")

    def run_check(self):
        """Run a complete check for new listings and send notifications if needed."""
        logger.info("Starting SS.LV listing check...")
        
        try:
            new_listings = self.check_for_new_listings()
            
            if new_listings:
                logger.info(f"Found {len(new_listings)} new matching listings")
                self.send_email_notification(new_listings)
            else:
                logger.info("No new matching listings found")
                
        except Exception as e:
            logger.error(f"Error during listing check: {e}")
        
        logger.info("SS.LV listing check completed")

def main():
    """Main function to set up and run the monitoring script."""
    logger.info("SS.LV Real Estate Monitor starting...")
    logger.info(f"Monitoring URLs: {URLS_TO_MONITOR}")
    logger.info(f"Search criteria: {SEARCH_CRITERIA}")
    logger.info(f"Run mode: {RUN_MODE}")
    
    monitor = SSLVMonitor()
    
    if RUN_IMMEDIATELY:
        logger.info("Running check...")
        monitor.run_check()
    
    if RUN_MODE == "continuous":
        # Schedule regular checks for continuous mode
        schedule.every(RUN_INTERVAL_HOURS).hours.do(monitor.run_check)
        logger.info(f"Scheduled to check every {RUN_INTERVAL_HOURS} hours. Press Ctrl+C to stop.")
        
        try:
            while True:
                schedule.run_pending()
                time.sleep(60)  # Check every minute for scheduled tasks
        except KeyboardInterrupt:
            logger.info("Monitoring stopped by user")
    else:
        # Single run mode - just exit after the check
        logger.info("Single run completed. Script will now exit.")
        logger.info("To run again, simply execute the script manually or set up a daily schedule.")

if __name__ == "__main__":
    main()
