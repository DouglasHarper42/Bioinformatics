import numpy as np

# Apply numpy compatibility patches
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int
if not hasattr(np, 'object'):
    np.object = object
if not hasattr(np, 'bool'):
    np.bool = bool

import fcsparser
import pandas as pd

def test_fcs_columns():
    try:
        # Load sample or accuri file
        filename = "accuri.fcs" if __import__('os').path.exists("accuri.fcs") else "sample.fcs"
        print(f"Loading file: {filename}")
        
        meta, data = fcsparser.parse(filename, reformat_meta=True)
        df = pd.DataFrame(data)
        
        # Normalize columns
        df.columns = [str(c).strip().upper() for c in df.columns]
        cols = list(df.columns)
        
        print(f"\n--- AVAILABLE COLUMNS ({len(cols)}) ---")
        for i, c in enumerate(cols):
            print(f"[{i}] {c}")
            
        print("\n--- TESTING UNIQUE COMBINATIONS ---")
        if len(cols) >= 2:
            col1 = cols[0]
            col2 = cols[1]
            
            s1 = df[col1]
            s2 = df[col2]
            
            print(f"Column 0 ({col1}) mean: {s1.mean():.2f}")
            print(f"Column 1 ({col2}) mean: {s2.mean():.2f}")
            
            if s1.equals(s2):
                print("⚠️ WARNING: Column 0 and Column 1 are identical!")
            else:
                print("SUCCESS: Column 0 and Column 1 contain distinct data.")
        else:
            print("Dataset has fewer than 2 columns.")

    except Exception as e:
        print(f"Error during test: {e}")

if __name__ == "__main__":
    test_fcs_columns()