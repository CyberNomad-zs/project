"""赛狐 OpenAPI 客户端（只读 TK 商品/利润；httpx 异步）。

签名规则与 sellfox-bridge 一致：
  data = 字典序 k=v 用 & 拼接（access_token/client_id/method/nonce/timestamp/url）
  sign = HmacSHA256(client_secret, data).hexdigest()
业务参数在 JSON body，不参与签名。
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import random
import time
from typing import Any

import httpx

log = logging.getLogger(__name__)


class SellfoxError(Exception):
    def __init__(self, code: Any, msg: str, request_id: str | None = None):
        super().__init__(f"sellfox code={code} msg={msg} requestId={request_id}")
        self.code = code
        self.msg = msg
        self.request_id = request_id


class SellfoxClient:
    def __init__(
        self,
        base_url: str,
        client_id: str,
        client_secret: str,
        *,
        timeout: float = 40.0,
        min_interval_sec: float = 1.1,
    ):
        self.base_url = (base_url or "https://openapi.sellfox.com").rstrip("/")
        self.client_id = client_id
        self.client_secret = client_secret
        self.timeout = timeout
        self.min_interval_sec = min_interval_sec
        self._token: str | None = None
        self._token_expire_at = 0.0
        self._last_call_at = 0.0
        # trust_env=False：不走系统代理，出口 IP 稳定（白名单）
        self._http = httpx.AsyncClient(timeout=timeout, trust_env=False)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> "SellfoxClient":
        return self

    async def __aexit__(self, *args: object) -> None:
        await self.aclose()

    async def _throttle(self) -> None:
        now = time.monotonic()
        wait = self.min_interval_sec - (now - self._last_call_at)
        if wait > 0:
            import asyncio

            await asyncio.sleep(wait)
        self._last_call_at = time.monotonic()

    async def get_token(self) -> str:
        now = time.time()
        if self._token and now < self._token_expire_at - 600:
            return self._token
        await self._throttle()
        r = await self._http.get(
            f"{self.base_url}/api/oauth/v2/token.json",
            params={
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "client_credentials",
            },
        )
        r.raise_for_status()
        body = r.json()
        if body.get("code") != 0:
            raise SellfoxError(body.get("code"), str(body.get("msg")), body.get("requestId"))
        data = body.get("data") or {}
        self._token = str(data["access_token"])
        # expires_in 文档为毫秒
        expires_in_ms = float(data.get("expires_in") or 86_400_000)
        self._token_expire_at = now + expires_in_ms / 1000.0
        log.info("sellfox token ok, expires_in_ms=%s", expires_in_ms)
        return self._token

    def _sign(self, url_path: str, token: str, timestamp: int, nonce: int) -> str:
        params = {
            "url": url_path,
            "method": "post",
            "access_token": token,
            "client_id": self.client_id,
            "timestamp": timestamp,
            "nonce": nonce,
        }
        data = "&".join(f"{k}={v}" for k, v in sorted(params.items()))
        return hmac.new(
            self.client_secret.encode(), data.encode(), hashlib.sha256
        ).hexdigest()

    async def post(self, url_path: str, body: dict[str, Any], *, retries: int = 4) -> Any:
        last_err: Exception | None = None
        for attempt in range(retries):
            token = await self.get_token()
            ts = int(time.time() * 1000)
            nonce = random.randint(1, 99999)
            query = {
                "access_token": token,
                "client_id": self.client_id,
                "timestamp": ts,
                "nonce": nonce,
                "sign": self._sign(url_path, token, ts, nonce),
            }
            try:
                await self._throttle()
                r = await self._http.post(
                    f"{self.base_url}{url_path}",
                    params=query,
                    json=body,
                    headers={"Content-Type": "application/json"},
                )
                r.raise_for_status()
                resp = r.json()
            except (httpx.HTTPError, ValueError) as e:
                last_err = e
                log.warning("sellfox %s net err attempt=%s: %s", url_path, attempt + 1, e)
                import asyncio

                await asyncio.sleep(min(30, 2**attempt))
                continue

            code = resp.get("code")
            if code == 0:
                return resp.get("data")
            msg = str(resp.get("msg") or "")
            # 频控
            if code == 40019 or "超过限制" in msg:
                import asyncio

                await asyncio.sleep(min(60, 3 * (attempt + 1)))
                last_err = SellfoxError(code, msg, resp.get("requestId"))
                continue
            if "token" in msg.lower() and attempt < retries - 1:
                self._token = None
                continue
            raise SellfoxError(code, msg, resp.get("requestId"))
        raise SellfoxError(-1, f"重试{retries}次仍失败: {last_err}")

    # ---- TK 商品 ----

    async def tiktok_shop_parent_page(
        self,
        *,
        page_no: int = 1,
        page_size: int = 100,
        shop_ids: list[str] | None = None,
        date_type: str = "updateDate",
        start_date: str,
        end_date: str,
    ) -> Any:
        body: dict[str, Any] = {
            "pageNo": str(page_no),
            "pageSize": str(page_size),
            "dateType": date_type,
            "startDate": start_date,
            "endDate": end_date,
        }
        if shop_ids:
            body["shopIdList"] = [str(s) for s in shop_ids]
        return await self.post(
            "/api/multiplatform/tiktok/shop/product/getParentPageList.json", body
        )

    async def tiktok_shop_child_info(self, parent_id: str) -> Any:
        return await self.post(
            "/api/multiplatform/tiktok/shop/product/getChildInfo.json",
            {"parentId": str(parent_id)},
        )

    # ---- TK 利润 ----

    async def tiktok_report_shop(
        self,
        *,
        start_date: str,
        end_date: str,
        page_num: int = 1,
        page_size: int = 50,
        currency: str = "",
        shop_ids: list[Any] | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "pageNum": str(page_num),
            "pageSize": str(page_size),
            "currency": currency,
        }
        if shop_ids:
            body["shopIds"] = shop_ids
        return await self.post("/api/financial/tkReport/queryPageShop.json", body)

    async def tiktok_report_sku(
        self,
        *,
        start_date: str,
        end_date: str,
        page_num: int = 1,
        page_size: int = 50,
        currency: str = "",
        shop_ids: list[Any] | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "pageNum": str(page_num),
            "pageSize": str(page_size),
            "currency": currency,
        }
        if shop_ids:
            body["shopIds"] = shop_ids
        return await self.post("/api/financial/tkReport/queryPageSku.json", body)

    async def tiktok_report_msku(
        self,
        *,
        start_date: str,
        end_date: str,
        page_num: int = 1,
        page_size: int = 50,
        currency: str = "",
        shop_ids: list[Any] | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "pageNum": str(page_num),
            "pageSize": str(page_size),
            "currency": currency,
        }
        if shop_ids:
            body["shopIds"] = shop_ids
        return await self.post("/api/financial/tkReport/queryPageMsku.json", body)

    async def tiktok_report_statement_detail(
        self,
        *,
        start_date: str,
        end_date: str,
        page_no: int = 1,
        page_size: int = 50,
        currency: str = "",
        time_search_field: str = "statementTime",
        shop_ids: list[Any] | None = None,
    ) -> Any:
        body: dict[str, Any] = {
            "startDate": start_date,
            "endDate": end_date,
            "pageNo": int(page_no),
            "pageSize": int(page_size),
            "currency": currency,
            "timeSearchField": time_search_field,
        }
        if shop_ids:
            body["shopIds"] = shop_ids
        return await self.post("/api/financial/tkReport/queryStatementDetail.json", body)


def rows_of(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for k in ("rows", "list", "records"):
            v = data.get(k)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


def total_size(data: Any) -> int | None:
    if isinstance(data, dict):
        t = data.get("totalSize")
        if t is None:
            t = data.get("total")
        try:
            return int(t) if t is not None else None
        except (TypeError, ValueError):
            return None
    return None
