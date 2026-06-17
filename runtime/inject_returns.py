import json
from pathlib import Path
from bs4 import BeautifulSoup
import re
import requests
import datetime
import difflib
import time

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
            
        # 2. Update NAV with Live Data from mfapi.in
        max_retries = 3
        for attempt in range(max_retries):
            try:
                search_term = scheme_id.replace("-", " ").strip()
                search_res = requests.get(f"https://api.mfapi.in/mf/search?q={search_term}", timeout=10.0)
                if search_res.ok and search_res.json():
                    search_data = search_res.json()
                    
                    # Fuzzy Name Matching via Set Word Intersection
                    target_name = scheme_id.replace("-", " ").lower()
                    target_words = set(target_name.split())
                    best_match = None
                    best_score = -1
                    
                    for item in search_data:
                        name_lower = item['schemeName'].lower().replace("-", " ")
                        name_words = set(name_lower.split())
                        
                        common = target_words.intersection(name_words)
                        score = len(common) / len(target_words)
                        
                        # Tie-breaker logic: favor funds that don't have extra words like "Equity" or "Plan B"
                        penalty = len(name_words) * 0.01
                        score -= penalty
                        
                        if score > best_score:
                            best_score = score
                            best_match = item
                            
                    scheme_code = best_match['schemeCode'] if best_match else search_data[0]['schemeCode']
                        
                    nav_res = requests.get(f"https://api.mfapi.in/mf/{scheme_code}", timeout=10.0)
                    if nav_res.ok:
                        history = nav_res.json().get('data', [])
                        if history:
                            valid_history = []
                            today_dt = datetime.datetime.now()
                            for x in history:
                                try:
                                    dt = datetime.datetime.strptime(x['date'], "%d-%m-%Y")
                                    if dt <= today_dt and float(x['nav']) > 0:
                                        valid_history.append((dt, x))
                                except:
                                    pass
                            
                            if valid_history:
                                valid_history.sort(key=lambda x: x[0], reverse=True)
                                latest_item = valid_history[0][1]
                                latest_nav = latest_item['nav']
                                latest_date = latest_item['date']
                                facts_db[scheme_id]['nav'] = f"Rs {latest_nav} (as of {latest_date})"
                                print(f"Updated NAV for {scheme_id} (Matched: {best_match['schemeName']})")
                                break # Success, break retry loop
                
                if attempt == max_retries - 1:
                    print(f"Failed to fetch live NAV for {scheme_id} after {max_retries} attempts")
            except Exception as e:
                if attempt == max_retries - 1:
                    print(f"Failed to fetch live NAV for {scheme_id}: {e}")
                else:
                    time.sleep(1)
            
    with open(facts_path, 'w', encoding='utf-8') as f:
        json.dump(facts_db, f, indent=2)
        
    print(f"Successfully updated returns for {updated} funds.")

if __name__ == "__main__":
    inject_returns()
