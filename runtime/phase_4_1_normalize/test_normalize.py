import os
import json
import re
from pathlib import Path

def test_normalization():
    base_dir = Path(__file__).parent.parent.parent
    norm_dir = base_dir / 'data' / 'normalized'
    struct_file = base_dir / 'data' / 'structured' / 'scheme_facts.json'
    
    print("--- Running Tests for Phase 4.1 ---")
    
    # Test 1: Directory and File Count
    assert norm_dir.exists(), "Normalized directory does not exist!"
    txt_files = list(norm_dir.glob('*.txt'))
    print(f"[PASS] Found {len(txt_files)} normalized text files.")
    assert len(txt_files) > 0, "No text files generated!"
    
    # Test 2: HTML Tag Stripping
    sample_file = txt_files[0]
    with open(sample_file, 'r', encoding='utf-8') as f:
        content = f.read()
        
    html_tags = re.findall(r'<[a-z]+[^>]*>', content)
    assert len(html_tags) == 0, f"Found HTML tags in normalized text: {html_tags[:5]}"
    print(f"[PASS] No HTML tags found in sample file ({sample_file.name}).")
    
    # Test 3: Markdown Table Formatting
    markdown_table_pattern = re.search(r'\|---\|', content)
    assert markdown_table_pattern is not None, "No Markdown tables found in the document!"
    print(f"[PASS] Successfully verified Markdown table conversion in {sample_file.name}.")
    
    # Test 4: Structured Data Validation
    assert struct_file.exists(), "Structured JSON facts file does not exist!"
    with open(struct_file, 'r', encoding='utf-8') as f:
        facts = json.load(f)
        
    assert isinstance(facts, dict), "Facts file is not a valid JSON dictionary."
    assert len(facts.keys()) > 0, "Facts dictionary is empty."
    
    # Check if a known key exists in the JSON output
    first_key = list(facts.keys())[0]
    assert "expense_ratio" in facts[first_key], "Expense Ratio field missing from facts."
    print(f"[PASS] Structured JSON contains valid data for {len(facts.keys())} schemes.")
    print("\nAll Phase 4.1 Tests Passed Successfully! [OK]")

if __name__ == "__main__":
    test_normalization()
