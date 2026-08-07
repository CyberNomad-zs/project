# -*- coding: utf-8 -*-
"""
zapi 内容生成客户端（OpenAI 兼容网关，用于调 grok 生图/生视频）。

- 读取 config/zapi.json 里的 base_url / api_key / models / defaults。
- 目前实现：gen_image()（文生图）、edit_image()（图生图，本项目主用）。
- 生视频（Sora 异步协议）后续再补，接口路径已在 config 里记录。

设计原则：密钥只从 config 读取，绝不硬编码、绝不打印。
"""

import json
import base64
import re
import time
from pathlib import Path

import requests

# 项目根目录：本文件在 src/generate/ 下，向上两级即根。
ROOT = Path(__file__).resolve().parents[2]
CONFIG_PATH = ROOT / "config" / "zapi.json"


class ZapiClient:
    def __init__(self, config_path: Path = CONFIG_PATH, timeout: int = 120):
        cfg = json.loads(Path(config_path).read_text(encoding="utf-8"))
        self.base_url = cfg["base_url"].rstrip("/")
        self._api_key = cfg["api_key"]
        self.models = cfg.get("models", {})
        self.defaults = cfg.get("defaults", {})
        self.timeout = timeout

    @property
    def _auth_headers(self):
        return {"Authorization": f"Bearer {self._api_key}"}

    # ---- 带重试的 POST：网络/SSL 抖动或 5xx 时自动重试 ----
    def _post_retry(self, url, *, retries: int = 3, backoff: float = 2.0, **kwargs):
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.post(url, timeout=self.timeout, **kwargs)
                if resp.status_code >= 500:
                    raise requests.exceptions.HTTPError(f"{resp.status_code} 服务端错误", response=resp)
                return resp
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.SSLError,
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError) as e:
                last_exc = e
                if attempt < retries:
                    time.sleep(backoff * attempt)
        raise last_exc

    def _get_retry(self, url, *, retries: int = 3, backoff: float = 2.0, **kwargs):
        last_exc = None
        for attempt in range(1, retries + 1):
            try:
                resp = requests.get(url, timeout=self.timeout, **kwargs)
                if resp.status_code >= 500:
                    raise requests.exceptions.HTTPError(f"{resp.status_code} 服务端错误", response=resp)
                return resp
            except (requests.exceptions.ConnectionError,
                    requests.exceptions.SSLError,
                    requests.exceptions.Timeout,
                    requests.exceptions.HTTPError) as e:
                last_exc = e
                if attempt < retries:
                    time.sleep(backoff * attempt)
        raise last_exc

    # ---- 内部：把返回的一条 data 落地成本地图片文件 ----
    def _save_image_item(self, item: dict, out_path: Path) -> Path:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        if item.get("b64_json"):
            out_path.write_bytes(base64.b64decode(item["b64_json"]))
        elif item.get("url"):
            r = requests.get(item["url"], timeout=self.timeout)
            r.raise_for_status()
            out_path.write_bytes(r.content)
        else:
            raise ValueError(f"返回条目里既没有 b64_json 也没有 url: {list(item.keys())}")
        return out_path

    # ---- 文生图：POST /v1/images/generations ----
    def gen_image(self, prompt: str, out_path, model: str = None, aspect_ratio: str = None) -> Path:
        model = model or self.models.get("image_main")
        aspect_ratio = aspect_ratio or self.defaults.get("image_aspect_ratio", "1:1")
        payload = {
            "model": model,
            "prompt": prompt,
            "user": json.dumps({"aspect_ratio": aspect_ratio}),
        }
        resp = self._post_retry(
            f"{self.base_url}/v1/images/generations",
            headers={**self._auth_headers, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json().get("data") or []
        if not data:
            raise RuntimeError(f"生图返回空 data：{resp.text[:500]}")
        return self._save_image_item(data[0], Path(out_path))

    # ---- 图生图 / 改图：POST /v1/images/edits（本项目主用：白底图/原图 -> 主图）----
    def edit_image(self, image_paths, prompt: str, out_path, model: str = None,
                   aspect_ratio: str = None) -> Path:
        """image_paths: 单个路径或路径列表（多张输入图，字段名都叫 image）。"""
        if isinstance(image_paths, (str, Path)):
            image_paths = [image_paths]
        model = model or self.models.get("image_main")
        aspect_ratio = aspect_ratio or self.defaults.get("image_aspect_ratio", "1:1")

        data = {
            "model": model,
            "prompt": prompt,
            "user": json.dumps({"aspect_ratio": aspect_ratio}),
        }
        # 先把图读成字节（不是文件句柄），保证重试时能重发同样内容
        files = []
        for p in image_paths:
            content = Path(p).read_bytes()
            files.append(("image", (Path(p).name, content, "image/png")))
        resp = self._post_retry(
            f"{self.base_url}/v1/images/edits",
            headers=self._auth_headers,  # multipart 边界由 requests 自动设置
            data=data,
            files=files,
        )

        resp.raise_for_status()
        items = resp.json().get("data") or []
        if not items:
            raise RuntimeError(f"改图返回空 data：{resp.text[:500]}")
        return self._save_image_item(items[0], Path(out_path))

    # ---- 生视频（Sora 异步协议：提交 -> 轮询 -> 取 mp4）----
    @staticmethod
    def _data_uri(path: Path) -> str:
        """本地图片转 data URI（首帧无公网 URL 时用）。"""
        ext = Path(path).suffix.lower().lstrip(".")
        mime = "jpeg" if ext in ("jpg", "jpeg") else (ext or "png")
        b64 = base64.b64encode(Path(path).read_bytes()).decode()
        return f"data:image/{mime};base64,{b64}"

    def submit_video(self, prompt: str, first_frame=None, seconds=None,
                     model: str = None, aspect_ratio: str = None) -> str:
        """提交生视频任务，返回 video_id。first_frame: 本地首帧图路径(i2v)，None 则文生视频。"""
        model = model or self.models.get("video_main")
        seconds = seconds or self.defaults.get("video_seconds", 5)
        payload = {"model": model, "prompt": prompt, "seconds": str(seconds)}
        if aspect_ratio:
            payload["user"] = json.dumps({"aspect_ratio": aspect_ratio})
        if first_frame is not None:
            # 实测该网关：image 必须是字符串（公网 URL 或 data URI），不能是 {"url":...} 对象
            ff = str(first_frame)
            payload["image"] = ff if ff.startswith(("http://", "https://")) else self._data_uri(first_frame)
        resp = self._post_retry(
            f"{self.base_url}/v1/videos",
            headers={**self._auth_headers, "Content-Type": "application/json"},
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        vid = data.get("id") or (data.get("data") or {}).get("id")
        if not vid:
            raise RuntimeError(f"提交视频未返回 id：{resp.text[:500]}")
        return vid

    def poll_video(self, video_id: str, poll_interval: float = 5.0, max_wait: float = 600.0):
        """轮询直到完成/失败，返回最终状态 json。"""
        waited = 0.0
        while True:
            resp = self._get_retry(f"{self.base_url}/v1/videos/{video_id}",
                                   headers=self._auth_headers)
            resp.raise_for_status()
            st = resp.json()
            status = (st.get("status") or st.get("state") or "").lower()
            if status in ("completed", "succeeded", "success", "done"):
                return st
            if status in ("failed", "error", "cancelled"):
                raise RuntimeError(f"视频生成失败：{st}")
            if waited >= max_wait:
                raise TimeoutError(f"视频轮询超时({max_wait}s)，最后状态：{status or st}")
            time.sleep(poll_interval)
            waited += poll_interval

    def fetch_video(self, video_id: str, out_path) -> Path:
        """下载已完成视频的 mp4 内容。"""
        resp = self._get_retry(f"{self.base_url}/v1/videos/{video_id}/content",
                              headers=self._auth_headers)
        resp.raise_for_status()
        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)
        return out_path

    def gen_video(self, prompt: str, out_path, first_frame=None, seconds=None,
                  model: str = None, aspect_ratio: str = None,
                  poll_interval: float = 5.0, max_wait: float = 600.0) -> Path:
        """一步到位：提交 -> 轮询 -> 取 mp4。返回落地的 mp4 路径。"""
        vid = self.submit_video(prompt, first_frame=first_frame, seconds=seconds,
                                model=model, aspect_ratio=aspect_ratio)
        self.poll_video(vid, poll_interval=poll_interval, max_wait=max_wait)
        return self.fetch_video(vid, out_path)

    # ---- 视觉 OCR：读图中印刷的产品型号编码（用于图源型号核对）----
    _OCR_PROMPT = ("这是一张灯具产品图。只输出图中印刷的产品型号编码（如 ONE-RMC100162、VS-G125TBOA "
                   "这类字母数字编码），只输出编码本身，多个用逗号分隔；若图中没有任何型号编码，只输出 NONE。")

    def ocr_model_codes(self, image_path, model: str = "grok-4.3", max_tokens: int = 60):
        body = {"model": model, "max_tokens": max_tokens, "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": self._OCR_PROMPT},
                {"type": "image_url", "image_url": {"url": self._data_uri(image_path)}},
            ]}]}
        resp = self._post_retry(
            f"{self.base_url}/v1/chat/completions",
            headers={**self._auth_headers, "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        txt = (resp.json()["choices"][0]["message"]["content"] or "").strip()
        if not txt or txt.upper() == "NONE":
            return []
        return [t.strip() for t in re.split(r"[,，\s]+", txt)
                if t.strip() and t.strip().upper() != "NONE"]

    # ---- 视觉多图比对：给两张图 + prompt，返回模型文字判定（用于变体配对）----
    def vision_compare(self, image_a, image_b, prompt: str,
                       model: str = "grok-4.3", max_tokens: int = 160) -> str:
        body = {"model": model, "max_tokens": max_tokens, "messages": [
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": self._data_uri(image_a)}},
                {"type": "image_url", "image_url": {"url": self._data_uri(image_b)}},
            ]}]}
        resp = self._post_retry(
            f"{self.base_url}/v1/chat/completions",
            headers={**self._auth_headers, "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        return (resp.json()["choices"][0]["message"]["content"] or "").strip()
