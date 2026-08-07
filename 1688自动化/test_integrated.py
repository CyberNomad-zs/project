# -*- coding: utf-8 -*-
"""在独立目录跑1个SKU的完整M1流程(主图+视频+详情)，验证集成管线。"""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.pipeline import run_batch, ROOT

rep = run_batch(limit=1, out_root=ROOT / "output" / "_integ_test")
print("\n阶段详情:")
print(json.dumps(rep["items"][0]["stages"], ensure_ascii=False, indent=2))
