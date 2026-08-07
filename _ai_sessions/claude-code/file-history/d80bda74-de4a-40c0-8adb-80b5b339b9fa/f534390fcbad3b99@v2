from __future__ import annotations

import hashlib
import hmac
import logging
import random
import time
from typing import Any, Iterator
from urllib.parse import urlencode

import httpx

from app.config import Settings, get_settings
from app.store.db import Database

logger = logging.getLogger(__name__)

TOKEN_KV_KEY = "sellfox_access_token"
TOKEN_EXP_KV_KEY = "sellfox_token_expire_at"


class SellfoxError(Exception):
    def __init__(self, code: int | str, message: str, payload: Any = None) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.payload = payload


class RateLimiter:
    """Simple client-side gap between requests (official ~1 req/s)."""

    def __init__(self, min_interval: float = 1.1) -> None:
        self.min_interval = max(0.0, min_interval)
        self._last = 0.0

    def wait(self) -> None:
        if self.min_interval <= 0:
            return
        now = time.monotonic()
        delta = now - self._last
        if delta < self.min_interval:
            time.sleep(self.min_interval - delta)
        self._last = time.monotonic()


class SellfoxClient:
    def __init__(
        self,
        settings: Settings | None = None,
        db: Database | None = None,
        *,
        min_interval: float = 1.1,
        timeout: float = 60.0,
    ) -> None:
        self.settings = settings or get_settings()
        if not self.settings.has_sellfox:
            raise SellfoxError(
                "config",
                "缺少 SELLFOX_CLIENT_ID / SELLFOX_CLIENT_SECRET，请配置 .env",
            )
        self.db = db
        self.base_url = self.settings.sellfox_base_url.rstrip("/")
        self.client_id = self.settings.sellfox_client_id
        self.client_secret = self.settings.sellfox_client_secret
        self.limiter = RateLimiter(min_interval)
        self._http = httpx.Client(timeout=timeout, trust_env=False)
        self._token: str | None = None
        self._token_expire_at: float = 0.0
        self._load_cached_token()

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> SellfoxClient:
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def _load_cached_token(self) -> None:
        if not self.db:
            return
        token = self.db.get_kv(TOKEN_KV_KEY)
        exp = self.db.get_kv(TOKEN_EXP_KV_KEY)
        if token and exp:
            try:
                exp_f = float(exp)
            except ValueError:
                return
            # refresh 60s early
            if exp_f - 60 > time.time():
                self._token = token
                self._token_expire_at = exp_f

    def _cache_token(self, token: str, expires_in_ms: int) -> None:
        self._token = token
        # expires_in is milliseconds per official docs
        self._token_expire_at = time.time() + max(expires_in_ms, 0) / 1000.0
        if self.db:
            self.db.set_kv(TOKEN_KV_KEY, token)
            self.db.set_kv(TOKEN_EXP_KV_KEY, str(self._token_expire_at))

    def get_access_token(self, *, force: bool = False) -> str:
        if (
            not force
            and self._token
            and self._token_expire_at - 60 > time.time()
        ):
            return self._token

        self.limiter.wait()
        url = f"{self.base_url}/api/oauth/v2/token.json"
        params = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "grant_type": "client_credentials",
        }
        logger.info("Refreshing Sellfox access_token")
        resp = self._http.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        if data.get("code") not in (0, 200, "0", "200"):
            raise SellfoxError(
                data.get("code", -1),
                data.get("msg") or "token failed",
                data,
            )
        payload = data.get("data") or {}
        token = payload.get("access_token")
        expires_in = int(payload.get("expires_in") or 86400000)
        if not token:
            raise SellfoxError("token", "响应无 access_token", data)
        self._cache_token(token, expires_in)
        return token

    @staticmethod
    def sign(
        *,
        access_token: str,
        client_id: str,
        client_secret: str,
        url_path: str,
        timestamp: int | None = None,
        nonce: int | None = None,
    ) -> tuple[dict[str, str], str]:
        ts = timestamp if timestamp is not None else int(time.time() * 1000)
        n = nonce if nonce is not None else random.randint(1, 999999)
        params = {
            "access_token": access_token,
            "client_id": client_id,
            "method": "post",
            "nonce": str(n),
            "timestamp": str(ts),
            "url": url_path,
        }
        param_str = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        signature = hmac.new(
            client_secret.encode("utf-8"),
            param_str.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        query = {
            "access_token": access_token,
            "client_id": client_id,
            "timestamp": str(ts),
            "nonce": str(n),
            "sign": signature,
        }
        return query, signature

    def request(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        max_retries: int = 3,
    ) -> dict[str, Any]:
        if not path.startswith("/"):
            path = "/" + path
        body = body if body is not None else {}

        last_err: Exception | None = None
        for attempt in range(max_retries):
            token = self.get_access_token(force=attempt > 0 and isinstance(last_err, SellfoxError) and getattr(last_err, "code", None) == 40001)
            query, _ = self.sign(
                access_token=token,
                client_id=self.client_id,
                client_secret=self.client_secret,
                url_path=path,
            )
            url = f"{self.base_url}{path}?{urlencode(query)}"
            self.limiter.wait()
            try:
                resp = self._http.post(
                    url,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPError as e:
                last_err = e
                logger.warning("HTTP error %s attempt %s: %s", path, attempt + 1, e)
                time.sleep(1.5 * (attempt + 1))
                continue

            code = data.get("code")
            if code in (0, 200, "0", "200"):
                return data

            code_int = int(code) if str(code).lstrip("-").isdigit() else code
            msg = data.get("msg") or "business error"

            if code_int == 40001:
                last_err = SellfoxError(code_int, msg, data)
                self.get_access_token(force=True)
                continue
            if code_int == 40019:
                last_err = SellfoxError(code_int, msg, data)
                sleep_s = 2.0 * (attempt + 1)
                logger.warning("Rate limited, sleep %.1fs", sleep_s)
                time.sleep(sleep_s)
                continue
            if code_int == 40005:
                raise SellfoxError(
                    code_int,
                    f"{msg}（IP 不在白名单，请将出口 IP 加入赛狐白名单）",
                    data,
                )
            raise SellfoxError(code_int, msg, data)

        raise last_err or SellfoxError("retry", f"request failed: {path}")

    def iter_pages(
        self,
        path: str,
        body: dict[str, Any],
        *,
        page_no_key: str = "pageNo",
        page_size_key: str = "pageSize",
        page_size: int = 100,
        rows_key: str = "rows",
    ) -> Iterator[dict[str, Any]]:
        """Yield each row from paginated list APIs."""
        page = 1
        total_size: int | None = None
        while True:
            payload = dict(body)
            payload[page_no_key] = str(page)
            payload[page_size_key] = str(min(page_size, 100))
            data = self.request(path, payload)
            page_data = data.get("data") or {}
            rows = page_data.get(rows_key) or page_data.get("list") or []
            if total_size is None:
                total_size = int(page_data.get("totalSize") or page_data.get("total") or 0)
                logger.info(
                    "%s page=%s totalSize=%s pageSize=%s",
                    path,
                    page,
                    total_size,
                    page_size,
                )
            for row in rows:
                yield row
            if not rows:
                break
            total_page = page_data.get("totalPage")
            if total_page is not None and page >= int(total_page):
                break
            if total_size is not None and page * page_size >= total_size:
                break
            if len(rows) < page_size:
                break
            page += 1

    # --- business helpers ---
    def product_analyze_v2_page(
        self,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        return self.request("/api/productAnalyze/V2/pageList.json", body)

    def product_analyze_v2_iter(
        self,
        body: dict[str, Any],
        *,
        page_size: int = 100,
    ) -> Iterator[dict[str, Any]]:
        return self.iter_pages(
            "/api/productAnalyze/V2/pageList.json",
            body,
            page_size=page_size,
        )
