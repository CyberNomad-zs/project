# -*- coding: utf-8 -*-
"""批量运行入口。用法: python run_batch.py [limit]"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.pipeline import run_batch
from src.catalog import matched_skus

limit = int(sys.argv[1]) if len(sys.argv) > 1 else None
print(f"有图源的 SKU 总数: {len(matched_skus())}"
      + (f"，本次只跑前 {limit} 个" if limit else "，本次全跑"))
run_batch(limit=limit)
