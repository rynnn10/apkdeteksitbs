!pip install -q roboflow

from roboflow import Roboflow
import os

# Ganti dengan API key Anda (dapat dari https://app.roboflow.com/settings/api)
rf = Roboflow(api_key="YOUR_API_KEY_HERE")
project = rf.workspace("achmad-fahri-x6r0k").project("oil-palm-fruit-ripeness-7r3zr")
version = project.version(1)
dataset = version.download("folder", location="/content/roboflow_data")

print("Downloaded to:", dataset.location)