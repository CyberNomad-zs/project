# -*- coding: utf-8 -*-
"""身份确证版批量：装饰灯泡(01 DECO LED)。"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from src.pipeline import run_verified_batch

run_verified_batch(category_prefix="01 DECO LED")
