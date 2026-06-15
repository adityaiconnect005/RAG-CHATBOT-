import json
import os
import time
import logging
from pathlib import Path
from playwright.sync_api import sync_playwright

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
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

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 RAGBot/1.0',
            viewport={'width': 1280, 'height': 720}
        )
        page = context.new_page()

        for item in urls:
            scheme_id = item.get('id')
            url = item.get('url')
            
            if not scheme_id or not url:
                logger.warning(f"Invalid item format in urls.json: {item}")
                continue
                
            logger.info(f"Fetching: {scheme_id} ({url})")
            
            try:
                # Wait until network is idle to ensure client-side rendering is complete
                page.goto(url, wait_until='networkidle', timeout=60000)
                
                # Sleep briefly to allow any final JS rendering (like NAV updates) to paint
                time.sleep(3)
                
                html_content = page.content()
                
                output_file = raw_dir / f"{scheme_id}.html"
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(html_content)
                    
                logger.info(f"Successfully saved to {output_file}")
                success_count += 1
                
            except Exception as e:
                logger.error(f"Failed to fetch {url}: {e}")
                fail_count += 1
                
            # Rate limiting
            time.sleep(DELAY_BETWEEN_REQUESTS)
            
        browser.close()

    logger.info(f"Scrape complete. Success: {success_count}, Failures: {fail_count}")

if __name__ == "__main__":
    scrape_and_save()
