import json
from pathlib import Path
from bs4 import BeautifulSoup
import re

BASE_DIR = Path(__file__).resolve().parent.parent

def inject_returns():
    raw_dir = BASE_DIR / 'data' / 'raw'
    structured_dir = BASE_DIR / 'data' / 'structured'
    facts_path = structured_dir / 'scheme_facts.json'
    
    with open(facts_path, 'r', encoding='utf-8') as f:
        facts_db = json.load(f)
        
    updated = 0
    
    for file_path in raw_dir.glob("*.html"):
        scheme_id = file_path.stem
        if scheme_id not in facts_db:
            continue
            
        with open(file_path, 'r', encoding='utf-8') as f:
            html_content = f.read()
            
        soup = BeautifulSoup(html_content, 'html.parser')
        
        found_data = False
        for table in soup.find_all('table'):
            if 'Fund returns' in table.text:
                # Find headers
                headers = []
                thead = table.find('thead')
                if thead:
                    headers = [th.get_text(strip=True) for th in thead.find_all(['th', 'td'])]
                else:
                    first_tr = table.find('tr')
                    if first_tr:
                        headers = [th.get_text(strip=True) for th in first_tr.find_all(['th', 'td'])]
                
                # Find the row with 'Fund returns'
                for row in table.find_all('tr'):
                    cells = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                    if cells and cells[0] == 'Fund returns':
                        for i, header in enumerate(headers):
                            if i < len(cells):
                                if '1Y' in header:
                                    facts_db[scheme_id]['return1y'] = cells[i]
                                elif '3Y' in header:
                                    facts_db[scheme_id]['return3y'] = cells[i]
                                elif '5Y' in header:
                                    facts_db[scheme_id]['return5y'] = cells[i]
                        found_data = True
                        break
                if found_data:
                    break
                    
        if found_data:
            updated += 1
        else:
            print(f"No table found for {scheme_id}")
            
    with open(facts_path, 'w', encoding='utf-8') as f:
        json.dump(facts_db, f, indent=2)
        
    print(f"Successfully updated returns for {updated} funds.")

if __name__ == "__main__":
    inject_returns()
