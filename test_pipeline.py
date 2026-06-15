import os
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"

def run_step(name, script_path):
    print(f"\n--- Running {name} ---")
    try:
        result = subprocess.run([sys.executable, script_path], cwd=BASE_DIR, check=True)
        print(f"[OK] {name} completed successfully.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"[ERROR] {name} failed with exit code {e.returncode}.")
        print("STDOUT:", e.stdout)
        print("STDERR:", e.stderr)
        return False

def verify_data():
    all_passed = True
    
    # Check 4.0
    raw_dir = DATA_DIR / "raw"
    if not raw_dir.exists() or len(list(raw_dir.glob("*.html"))) == 0:
        print("[ERROR] Phase 4.0: No raw HTML files found.")
        all_passed = False
    else:
        print(f"[OK] Phase 4.0: Found {len(list(raw_dir.glob('*.html')))} raw HTML files.")
        
    # Check 4.1
    norm_dir = DATA_DIR / "normalized"
    if not norm_dir.exists() or len(list(norm_dir.glob("*.txt"))) == 0:
        print("[ERROR] Phase 4.1: No normalized TXT files found.")
        all_passed = False
    else:
        print(f"[OK] Phase 4.1: Found {len(list(norm_dir.glob('*.txt')))} normalized files.")
        
    # Check 4.2
    embed_dir = DATA_DIR / "embedded"
    chunks_file = embed_dir / "chunks.jsonl"
    if not chunks_file.exists():
        print("[ERROR] Phase 4.2: chunks.jsonl not found.")
        all_passed = False
    else:
        print(f"[OK] Phase 4.2: chunks.jsonl generated.")

    return all_passed

def main():
    print("Starting End-to-End Pipeline Test...\n")
    
    steps = [
        ("Phase 4.0 (Scrape)", "runtime/phase_4_0_scrape/scrape.py"),
        ("Phase 4.1 (Normalize)", "runtime/phase_4_1_normalize/normalize.py"),
        ("Inject Returns", "runtime/inject_returns.py"),
        ("Phase 4.2 (Embed)", "runtime/phase_4_2_embed/embed.py"),
        ("Phase 4.3 (Index)", "runtime/phase_4_3_index/index.py")
    ]
    
    for name, path in steps:
        if not run_step(name, path):
            print("\n[ERROR] Pipeline aborted due to error.")
            sys.exit(1)
            
    print("\n--- Running Final Data Verification ---")
    if verify_data():
        print("\n[SUCCESS] PERFECT! All phases executed and verified successfully.")
    else:
        print("\n[ERROR] Errors found during data verification.")

if __name__ == "__main__":
    main()
