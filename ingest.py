import fcsparser
import urllib.request
import pandas as pd
import matplotlib.pyplot as plt

# 1. Download a standard sample FCS file directly
print("Downloading sample .fcs file...")
# We will build the URL dynamically using a reliable sample dataset
host = "raw.githubusercontent.com"
path = "tlnagy/fcsexamples/master/BD-FACS-Aria-II.fcs"
url = f"https://{host}/{path}"

filename = "sample.fcs"
urllib.request.urlretrieve(url, filename)
print("Download complete.")

# 2. Parse the file
# meta is a dictionary of instrument settings, data is a Pandas DataFrame
meta, data = fcsparser.parse(filename, reformat_meta=True)

# 3. Prove we have the data
print(f"\n--- Data Extraction Successful ---")
print(f"Total Cells (Events) Analyzed: {data.shape[0]}")
print(f"Total Markers (Dimensions): {data.shape[1]}")
print("\nFirst 5 rows of the biological data:")
print(data.head())

# 4. Visualize the raw matrix
plt.figure(figsize=(8, 6))

# Plotting Size (FSC) vs Complexity (SSC)
# We use a small point size (s=1) and transparency (alpha=0.2) because there are thousands of overlapping cells
plt.scatter(data['FSC-A'], data['SSC-A'], s=1, alpha=0.2, color='blue')

plt.title("Cytometry Data: Cell Size vs. Complexity")
plt.xlabel("Forward Scatter (Size)")
plt.ylabel("Side Scatter (Complexity)")

print("\nGenerating scatter plot...")
plt.show()