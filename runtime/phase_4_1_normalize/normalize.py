import os
import json
import logging
from pathlib import Path
from bs4 import BeautifulSoup
import re

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def convert_table_to_markdown(table):
    """Converts a BeautifulSoup table object into a Markdown table string."""
    markdown = ""
    
    # Process headers
    headers = []
    thead = table.find('thead')
    if thead:
        headers = [th.get_text(strip=True) for th in thead.find_all(['th', 'td'])]
    else:
        # If no thead, check the first row for th
        first_tr = table.find('tr')
        if first_tr:
            headers = [th.get_text(strip=True) for th in first_tr.find_all('th')]
            
    if headers:
        markdown += "| " + " | ".join(headers) + " |\n"
        markdown += "|" + "|".join(["---"] * len(headers)) + "|\n"
    
    # Process rows
    tbody = table.find('tbody')
    rows = tbody.find_all('tr') if tbody else table.find_all('tr')
    
    for row in rows:
        # Skip row if it contains headers we already processed
        if row.find('th') and headers and [th.get_text(strip=True) for th in row.find_all('th')] == headers:
            continue
            
        cells = [td.get_text(strip=True).replace('\n', ' ').replace('\r', '') for td in row.find_all(['td', 'th'])]
        if cells and any(cells): # Ensure not empty
            markdown += "| " + " | ".join(cells) + " |\n"
            
    return markdown

def extract_structured_data(soup, scheme_id):
    """Heuristic-based extraction of key numbers from the DOM."""
    import re
    
    facts = {
        "scheme_id": scheme_id,
        "nav": None,
        "expense_ratio": None,
        "fund_size": None,
        "minimum_sip": None,
        "rating": None,
        "riskometer": None,
        "benchmark": None,
        "lock_in": None
    }
    
    def get_next_value(label_regex):
        tags = soup.find_all(string=re.compile(label_regex, re.I))
        for tag in tags:
            if len(tag.strip()) > 35: continue
            parent = tag.parent
            while parent and parent.name != 'body':
                sibling = parent.find_next_sibling()
                while sibling:
                    text = sibling.get_text(strip=True)
                    if text: return text[:50]
                    sibling = sibling.find_next_sibling()
                parent = parent.parent
        return None

    facts['expense_ratio'] = get_next_value(r'expense ratio')
    facts['nav'] = get_next_value(r'^nav(:|$)')
    facts['fund_size'] = get_next_value(r'fund size|aum')
    facts['minimum_sip'] = get_next_value(r'minimum sip|min\. for sip')
    facts['rating'] = get_next_value(r'^rating$')
    
    riskometer_tags = soup.find_all(string=re.compile(r'low risk|low to moderate risk|moderate risk|moderately high risk|high risk|very high risk', re.I))
    if riskometer_tags:
        facts['riskometer'] = riskometer_tags[0].strip()[:30]
        
    facts['benchmark'] = get_next_value(r'fund benchmark|benchmark')
    
    lock_in_tags = soup.find_all(string=re.compile(r'lock-in|lock in', re.I))
    if lock_in_tags:
        for t in lock_in_tags:
            text = t.parent.get_text(strip=True)
            if len(text) < 30:
                facts['lock_in'] = text
                break

    return facts

def process_html_file(file_path):
    logger.info(f"Processing {file_path.name}...")
    
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
    except Exception as e:
        logger.error(f"Failed to read {file_path.name}: {e}")
        return None, None
        
    soup = BeautifulSoup(html_content, 'html.parser')
    scheme_id = file_path.stem
    
    # 1. Boilerplate Stripping (Scripts/Styles only first)
    for element in soup(["script", "style", "svg", "iframe", "noscript"]):
        element.decompose()
        
    # 2. Extract Structured Data
    facts = extract_structured_data(soup, scheme_id)
    
    # 3. Boilerplate Stripping (UI elements)
    for element in soup(["nav", "footer", "header", "aside", "button"]):
        element.decompose()
        
    # Remove obvious UI elements (generic class names typical in SPAs)
    # Note: We keep main content divs
    
    # 3. Table-to-Markdown Algorithm
    for table in soup.find_all('table'):
        markdown_str = convert_table_to_markdown(table)
        # Create a new tag to hold the text to avoid escaping issues
        new_tag = soup.new_tag("div")
        new_tag.string = f"\n\n{markdown_str}\n\n"
        table.replace_with(new_tag)
        
    # 4. Output Generation
    clean_text = soup.get_text(separator='\n\n', strip=True)
    
    # Strip stale NAV dates from Groww (e.g. "NAV: 12 Jun '26") so Chatbot doesn't hallucinate old dates
    clean_text = re.sub(r"NAV:\s+\d{1,2}\s+[a-zA-Z]{3}\s+'\d{2}", "NAV:", clean_text)
    
    # Strip stale "as of" dates for Expense Ratio, AUM, etc. (e.g. "as of 13 Jun 2026")
    clean_text = re.sub(r"\s*as of \d{1,2}\s+[a-zA-Z]{3}\s+\d{2,4}", "", clean_text, flags=re.IGNORECASE)
    
    # Basic cleanup of excessive newlines
    lines = [line.strip() for line in clean_text.splitlines() if line.strip()]
    final_text = '\n\n'.join(lines)
    
    return final_text, facts

def main():
    base_dir = Path(__file__).parent.parent.parent
    raw_dir = base_dir / 'data' / 'raw'
    norm_dir = base_dir / 'data' / 'normalized'
    struct_dir = base_dir / 'data' / 'structured'
    
    if not raw_dir.exists():
        logger.error(f"Raw directory not found: {raw_dir}")
        return
        
    norm_dir.mkdir(parents=True, exist_ok=True)
    struct_dir.mkdir(parents=True, exist_ok=True)
    
    # Cleanup stale files before normalizing
    for f in norm_dir.glob("*.txt"):
        try:
            f.unlink()
        except Exception as e:
            logger.warning(f"Could not delete {f}: {e}")
            
    for f in struct_dir.glob("*.json"):
        try:
            f.unlink()
        except Exception as e:
            logger.warning(f"Could not delete {f}: {e}")
            
    all_facts = {}
    
    for html_file in raw_dir.glob('*.html'):
        clean_text, facts = process_html_file(html_file)
        
        if clean_text:
            # Save clean text
            output_file = norm_dir / f"{html_file.stem}.txt"
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(clean_text)
                
        if facts:
            all_facts[html_file.stem] = facts
            
    # Save structured facts
    facts_file = struct_dir / 'scheme_facts.json'
    with open(facts_file, 'w', encoding='utf-8') as f:
        json.dump(all_facts, f, indent=4)
        
    logger.info(f"Normalization complete. Clean text saved to {norm_dir}. Facts saved to {facts_file}")

if __name__ == "__main__":
    main()
