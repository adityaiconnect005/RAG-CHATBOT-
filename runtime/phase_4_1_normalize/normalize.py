import os
import json
import logging
from pathlib import Path
from bs4 import BeautifulSoup

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
    
    for div in soup.find_all(['div', 'td', 'th', 'span']):
        # We want leaf nodes or nodes with very little text
        if div.find('div') is not None and div.name == 'div':
            continue # skip parent divs to avoid grabbing concatenated text
            
        text = div.get_text(strip=True).lower()
        if not text: continue
        
        # Expense Ratio
        if 'expense ratio' in text and len(text) < 25 and not facts['expense_ratio']:
            val = div.find_next_sibling()
            if val: facts['expense_ratio'] = val.get_text(strip=True)[:20]
                
        # NAV
        if text.startswith('nav:') and len(text) < 25 and not facts['nav']:
            val = div.find_next_sibling()
            if val: facts['nav'] = val.get_text(strip=True)[:20]
                
        # Fund Size / AUM
        if ('fund size' in text or 'aum' in text) and len(text) < 25 and not facts['fund_size']:
            val = div.find_next_sibling()
            if val: facts['fund_size'] = val.get_text(strip=True)[:30]
                
        # Minimum SIP
        if ('min. for sip' in text or 'minimum sip' in text) and len(text) < 25 and not facts['minimum_sip']:
            val = div.find_next_sibling()
            if val: facts['minimum_sip'] = val.get_text(strip=True)[:20]
                
        # Rating
        if text == 'rating' and len(text) < 15 and not facts['rating']:
            val = div.find_next_sibling()
            if val: facts['rating'] = val.get_text(strip=True)[:10]
            
        # Riskometer
        if text in ['low risk', 'low to moderate risk', 'moderate risk', 'moderately high risk', 'high risk', 'very high risk'] and not facts.get('riskometer'):
            facts['riskometer'] = div.get_text(strip=True)[:30]
            
        # Benchmark
        if ('fund benchmark' in text or 'benchmark' in text) and len(text) < 25 and not facts.get('benchmark'):
            val = div.find_next_sibling()
            if val: facts['benchmark'] = val.get_text(strip=True)[:50]
            
        # Lock-in
        if ('lock-in' in text or 'lock in' in text) and len(text) < 30 and not facts.get('lock_in'):
            facts['lock_in'] = div.get_text(strip=True)[:30]
    
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
