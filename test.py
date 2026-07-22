import numpy as np

# Apply the numpy compatibility patch for older libraries like fcsparser
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int

import fcsparser

try:
    meta, data = fcsparser.parse('accuri.fcs', reformat_meta=True)
    print(f"SUCCESS! Parsed accuri.fcs successfully. Total cells: {data.shape[0]}")
except Exception as e:
    print(f"Error during test parse: {e}")