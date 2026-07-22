import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import fcsparser

# 1. Load the data you downloaded in Day 1
meta, data = fcsparser.parse('sample.fcs', reformat_meta=True)

# 2. Apply the Arcsinh transformation (a cofactor of 150 is the biological standard for flow cytometry)
cofactor = 150
transformed_data = np.arcsinh(data / cofactor)

# 3. Visualize the newly transformed data
plt.figure(figsize=(8, 6))
# We'll make this one green so you can easily tell the difference!
plt.scatter(transformed_data['FSC-A'], transformed_data['SSC-A'], s=1, alpha=0.2, color='green')

plt.title("Transformed Data: Notice the distinct clusters forming!")
plt.xlabel("FSC-A (Arcsinh)")
plt.ylabel("SSC-A (Arcsinh)")

print("\nGenerating transformed scatter plot...")
plt.show()