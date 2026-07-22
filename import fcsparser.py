import fcsparser
import urllib.request
import pandas as pd
import matplotlib.pyplot as plt

# 1. Download a standard sample FCS file directly
print("Downloading sample .fcs file...")
url = "[https://raw.githubusercontent.com/eyurtsev/FlowCytometryTools/master/FlowCytometryTools/tests/data/FlowCytometers/BD-FACS-Aria/CytoTrol_CytoTrol_1.fcs](https://raw.githubusercontent.com/eyurtsev/FlowCytometryTools/master/FlowCytometryTools/tests/data/FlowCytometers/BD-FACS-Aria/CytoTrol_CytoTrol_1.fcs)"
filename = "sample.fcs"
urllib.request.urlretrieve(url, filename)
print("Download complete.")
