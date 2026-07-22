import fcsparser
import numpy as np
import matplotlib.pyplot as plt
from sklearn.cluster import KMeans

# 1. Load and transform the data
meta, data = fcsparser.parse('sample.fcs', reformat_meta=True)
transformed_data = np.arcsinh(data / 150)

# 2. Isolate the two dimensions we care about for this test
features = transformed_data[['FSC-A', 'SSC-A']]

# 3. Initialize and run the K-Means algorithm
print("Running K-Means clustering...")
kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
data['Cluster'] = kmeans.fit_predict(features)

# 4. Visualize the automated gating
plt.figure(figsize=(8, 6))
# Notice we changed 'color' to 'c' to map the colors to the AI's clusters!
scatter = plt.scatter(transformed_data['FSC-A'], transformed_data['SSC-A'], 
                      c=data['Cluster'], cmap='viridis', s=1, alpha=0.5)
plt.title("Automated Gating: K-Means Clustering")
plt.xlabel("FSC-A")
plt.ylabel("SSC-A")
plt.colorbar(scatter, label="Cell Population")

print("\nGenerating clustered scatter plot...")
plt.show()