"""Trove API package.

Set OpenMP guards before any heavy native lib (PyTorch for embeddings, LightGBM
for the learned reranker) loads. Both ship their own OpenMP runtime and on macOS
loading both in one process can segfault. Setting these at package import time
(the earliest point shared by the API server and the CLI scripts) keeps the
process stable. Single-threaded is fine: our per-request native work is tiny.
"""
import os

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")
