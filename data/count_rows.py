"""
Quick script to count total rows in NPPES dataset.

Usage:
    python count_rows.py
"""

import pandas as pd
import os
import sys

def find_nppes_file():
    """Find the NPPES CSV file."""
    for root, dirs, files in os.walk('.'):
        for file in files:
            if 'npidata_pfile' in file and file.endswith('.csv'):
                return os.path.join(root, file)
    return None

def main():
    nppes_file = find_nppes_file()
    if not nppes_file:
        print("ERROR: Could not find npidata_pfile CSV file.")
        sys.exit(1)
    
    print(f"Counting rows in: {nppes_file}")
    print("This may take a minute for large files...\n")
    
    # Get file size first
    file_size = os.path.getsize(nppes_file)
    print(f"File size: {file_size / (1024**3):.2f} GB")
    
    # Count rows by reading in chunks
    print("Counting rows...")
    total_rows = 0
    chunk_size = 100000
    
    try:
        chunk_iterator = pd.read_csv(nppes_file, chunksize=chunk_size, low_memory=False)
        
        for chunk_num, chunk in enumerate(chunk_iterator, 1):
            total_rows += len(chunk)
            if chunk_num % 10 == 0:
                print(f"  Processed {total_rows:,} rows so far...")
        
        print(f"\n{'='*60}")
        print(f"Total rows in dataset: {total_rows:,}")
        print(f"{'='*60}")
        
        # Estimate number of pharmacies (roughly 1-2% based on test)
        estimated_pharmacies = int(total_rows * 0.012)  # ~1.2% based on test
        print(f"\nEstimated pharmacies: ~{estimated_pharmacies:,}")
        print(f"(Based on ~1.2% pharmacy rate from test sample)")
        
    except Exception as e:
        print(f"Error counting rows: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()




