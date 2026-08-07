# -*- coding: utf-8 -*-
"""M5 编排：批量把有图源的 SKU 跑出 5 张主图，出报告。单个失败不影响其它，可断点续跑。"""
import json
import shutil
import time
from pathlib import Path

from .catalog import matched_skus, norm, ROOT, IMG_EXT
from .generate.image import make_product_mains
from .generate.video import make_product_video, pick_first_frame
from .generate.detail import make_product_detail
from .generate.zapi_client import ZapiClient
from .match import resolve_source

OUT_ROOT = ROOT / "output" / "products"
EXPECTED_SLOTS = ["main_1_white", "main_2_detail", "main_3_scene", "main_4_scene", "main_5_white_last"]


def _safe(name: str) -> str:
    return name.strip().replace("/", "_").replace("\\", "_")


def _existing(out_dir: Path):
    return {s for s in EXPECTED_SLOTS if (out_dir / f"{s}.jpg").exists()}


def process_product(src_dir: Path, out_dir: Path, client: ZapiClient,
                    do_scene=True, do_video=True, do_detail=True) -> dict:
    """一个商品的完整 M1 产出：主图 -> 主视频 -> 详情段。分阶段续跑+错误隔离。"""
    out_dir = Path(out_dir)
    stages = {}

    # 1) 主图
    have = _existing(out_dir)
    if len(have) == len(EXPECTED_SLOTS):
        stages["images"] = {"status": "skip", "done": sorted(have)}
    else:
        res = make_product_mains(src_dir, out_dir, client=client, do_scene=do_scene)
        done = [k for k, v in res.items() if v]
        stages["images"] = {"status": "ok" if len(done) == 5 else ("no_clean" if not done else "partial"),
                            "done": done, "missing": [k for k in EXPECTED_SLOTS if not res.get(k)]}

    # 2) 主视频（需要至少一张主图作首帧）
    if do_video:
        vid = out_dir / "main_video.mp4"
        if vid.exists():
            stages["video"] = {"status": "skip"}
        else:
            try:
                pick_first_frame(out_dir)  # 无首帧则跳过
                make_product_video(out_dir, vid, client=client)
                stages["video"] = {"status": "ok", "mb": round(vid.stat().st_size / 1024 / 1024, 2)}
            except FileNotFoundError:
                stages["video"] = {"status": "no_frame"}
            except Exception as e:
                stages["video"] = {"status": "error", "error": f"{type(e).__name__}: {e}"}

    # 3) 详情段
    if do_detail:
        ddir = out_dir / "detail"
        if ddir.exists() and any(ddir.glob("detail_*.jpg")):
            stages["detail"] = {"status": "skip", "count": len(list(ddir.glob("detail_*.jpg")))}
        else:
            try:
                segs = make_product_detail(src_dir, out_dir)
                stages["detail"] = {"status": "ok", "count": len(segs)}
            except Exception as e:
                stages["detail"] = {"status": "error", "error": f"{type(e).__name__}: {e}"}

    return stages


def run_verified_batch(category_prefix: str = "01 DECO LED", out_root: Path = None,
                       do_video: bool = True, do_detail: bool = True) -> dict:
    """身份确证版：先 resolve_source 确证图源，再出全套素材。只跑指定品类(默认装饰灯泡)。
    变体(_2/_3)复用同型号已确证的图源，省重复 OCR/视觉。"""
    client = ZapiClient()
    out_root = Path(out_root) if out_root else (ROOT / "output" / "verified")
    skus = [(s, c, d) for s, c, d in matched_skus() if c.startswith(category_prefix)]

    report = {"total": len(skus), "full": 0, "partial": 0, "no_source": 0, "error": 0, "items": []}
    src_cache = {}   # (folder, norm(sku)) -> 已确证 source_main 路径
    t_start = time.time()

    for i, (sku, cat, src_dir) in enumerate(skus, 1):
        out_dir = out_root / _safe(sku)
        out_dir.mkdir(parents=True, exist_ok=True)
        key = (src_dir.name, norm(sku))
        print(f"[{i}/{len(skus)}] {sku}  <- {src_dir.name} ...", flush=True)
        t0 = time.time()
        try:
            # 1) 确证图源（变体命中缓存则复制复用）
            if key in src_cache and Path(src_cache[key]).exists():
                src_main = out_dir / "source_main.jpg"
                shutil.copyfile(src_cache[key], src_main)
                method = "cached"
            else:
                r = resolve_source(sku, src_dir, out_dir, client)
                method = r["method"]
                if method == "none":
                    report["no_source"] += 1
                    report["items"].append({"sku": sku, "status": "no_source",
                                            "reason": r.get("reason"), "source": src_dir.name})
                    print(f"    no_source: {r.get('reason')}")
                    continue
                src_main = Path(r["image"])
                src_cache[key] = str(src_main)

            # 2) 出 5 图 + 视频 + 详情（图源已确证）
            stages = _generate_all(sku, src_dir, out_dir, src_main, client, do_video, do_detail)
            ok = (stages["images"]["status"] == "ok"
                  and (not do_video or stages.get("video", {}).get("status") in ("ok", "skip"))
                  and (not do_detail or stages.get("detail", {}).get("status") in ("ok", "skip")))
            bucket = "full" if ok else "partial"
            report[bucket] += 1
            report["items"].append({"sku": sku, "category": cat, "source": src_dir.name,
                                    "resolve_method": method, "bucket": bucket, "stages": stages,
                                    "dir": str(out_dir), "seconds": round(time.time() - t0, 1)})
            print(f"    {bucket} [{method}]  视频{stages.get('video',{}).get('status','-')} "
                  f"详情{stages.get('detail',{}).get('count','-')}  ({time.time()-t0:.0f}s)")
        except Exception as e:
            report["error"] += 1
            report["items"].append({"sku": sku, "status": "error", "error": f"{type(e).__name__}: {e}"})
            print(f"    error: {type(e).__name__}: {e}")

    report["elapsed_seconds"] = round(time.time() - t_start, 1)
    (out_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n汇总: 完整{report['full']} 部分{report['partial']} 无图源{report['no_source']} "
          f"失败{report['error']} / 共{report['total']}，用时{report['elapsed_seconds']:.0f}s")
    print(f"报告: {out_root / 'report.json'}")
    return report


def _generate_all(sku, src_dir, out_dir, src_main, client, do_video, do_detail) -> dict:
    """用已确证图源 src_main 出 5 图 + 视频 + 详情。"""
    stages = {}
    res = make_product_mains(src_dir, out_dir, client=client, clean_source=src_main)
    done = [k for k, v in res.items() if v]
    stages["images"] = {"status": "ok" if len(done) == 5 else "partial",
                        "done": done, "missing": [k for k in EXPECTED_SLOTS if not res.get(k)]}
    if do_video:
        vid = out_dir / "main_video.mp4"
        if vid.exists():
            stages["video"] = {"status": "skip"}
        else:
            try:
                make_product_video(out_dir, vid, client=client)
                stages["video"] = {"status": "ok", "mb": round(vid.stat().st_size / 1024 / 1024, 2)}
            except Exception as e:
                stages["video"] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
    if do_detail:
        try:
            segs = make_product_detail(src_dir, out_dir)
            stages["detail"] = {"status": "ok", "count": len(segs)}
        except Exception as e:
            stages["detail"] = {"status": "error", "error": f"{type(e).__name__}: {e}"}
    return stages


def run_batch(limit: int = None, resume: bool = True, do_scene: bool = True,
              do_video: bool = True, do_detail: bool = True, out_root: Path = None) -> dict:
    skus = matched_skus()
    if limit:
        skus = skus[:limit]
    client = ZapiClient()
    out_root = Path(out_root) if out_root else OUT_ROOT

    report = {"total": len(skus), "full": 0, "partial": 0, "error": 0, "items": []}
    t_start = time.time()

    for i, (sku, cat, src_dir) in enumerate(skus, 1):
        out_dir = out_root / _safe(sku)
        print(f"[{i}/{len(skus)}] {sku}  <- {src_dir.name} ...", flush=True)
        t0 = time.time()
        try:
            stages = process_product(src_dir, out_dir, client,
                                     do_scene=do_scene, do_video=do_video, do_detail=do_detail)
            img_ok = stages["images"]["status"] in ("ok", "skip")
            vid_ok = (not do_video) or stages.get("video", {}).get("status") in ("ok", "skip")
            det_ok = (not do_detail) or stages.get("detail", {}).get("status") in ("ok", "skip")
            if img_ok and vid_ok and det_ok:
                bucket = "full"
            else:
                bucket = "partial"
            report[bucket] += 1
            report["items"].append({"sku": sku, "category": cat, "source": src_dir.name,
                                     "bucket": bucket, "stages": stages, "dir": str(out_dir),
                                     "seconds": round(time.time() - t0, 1)})
            img = stages["images"]
            n_img = len(img.get("done", [])) if img["status"] != "skip" else 5
            print(f"    {bucket}  图{n_img}/5 视频{stages.get('video',{}).get('status','-')} "
                  f"详情{stages.get('detail',{}).get('count','-')}  ({time.time()-t0:.0f}s)")
        except Exception as e:
            report["error"] += 1
            report["items"].append({"sku": sku, "category": cat, "source": src_dir.name,
                                    "bucket": "error", "error": f"{type(e).__name__}: {e}"})
            print(f"    error: {type(e).__name__}: {e}")

    report["elapsed_seconds"] = round(time.time() - t_start, 1)
    out_root.mkdir(parents=True, exist_ok=True)
    (out_root / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n汇总: 完整{report['full']} 部分{report['partial']} 失败{report['error']} "
          f"/ 共{report['total']}，用时{report['elapsed_seconds']:.0f}s")
    print(f"报告: {out_root / 'report.json'}")
    return report
