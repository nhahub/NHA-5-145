import os

# Ordinary automated tests explicitly select the deterministic, network-free adapter.
os.environ["LLM_PROVIDER"] = "scripted"
os.environ["LLM_MODEL"] = "scripted-v1"
