import json
import os
import time
import requests
import logging
from pathlib import Path

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 RAGBot/1.0',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
}
DELAY_BETWEEN_REQUESTS = 2  # seconds

def load_urls(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Failed to load URLs from {filepath}: {e}")
        return []

def scrape_and_save():
    base_dir = Path(__file__).parent.parent.parent
    urls_file = base_dir / 'runtime' / 'phase_4_0_scrape' / 'urls.json'
    raw_dir = base_dir / 'data' / 'raw'
    
    # Ensure data/raw directory exists
    raw_dir.mkdir(parents=True, exist_ok=True)
    
    # Cleanup stale files before scraping
    for f in raw_dir.glob("*.html"):
        try:
            f.unlink()
        except Exception as e:
            logger.warning(f"Could not delete {f}: {e}")
            
    urls = load_urls(urls_file)
    if not urls:
        logger.error("No URLs found. Exiting.")
        return

    logger.info(f"Starting scrape for {len(urls)} URLs")
    
    success_count = 0
    fail_count = 0

    for item in urls:
        scheme_id = item.get('id')
        url = item.get('url')
        
        if not scheme_id or not url:
            logger.warning(f"Invalid item format in urls.json: {item}")
            continue
            
        logger.info(f"Fetching: {scheme_id} ({url})")
        
        try:
            response = requests.get(url, headers=HEADERS, timeout=10)
            response.raise_for_status()
            
            output_file = raw_dir / f"{scheme_id}.html"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(response.text)
                
            logger.info(f"Successfully saved to {output_file}")
            success_count += 1
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to fetch {url}: {e}")
            fail_count += 1
            
        # Rate limiting
        time.sleep(DELAY_BETWEEN_REQUESTS)

    logger.info(f"Scrape complete. Success: {success_count}, Failures: {fail_count}")

if __name__ == "__main__":
    scrape_and_save()
