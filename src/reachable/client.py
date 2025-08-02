import ssl
from typing import Any, AsyncContextManager, ContextManager, Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
import tldextract
from fake_useragent import UserAgent
from typing_extensions import Self


ua: Any = UserAgent(browsers=["chrome"], os="windows", platforms="pc", min_version=120)


class BaseClient:
    def __init__(
        self,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
        ensure_protocol_url: bool = False,
    ) -> None:
        self.timeout: int = 10
        self.headers = {
            "User-Agent": ua.random,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US;q=0.7,en;q=0.3",
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "DNT": "1",
            "Connection": "keep-alive",
            "TE": "trailers",
        }
        if headers is not None:
            self.headers = {**self.headers, **headers}

        self.include_host: bool = include_host
        self.ssl_fallback_to_http: bool = ssl_fallback_to_http
        self.ensure_protocol_url: bool = ensure_protocol_url

    def _prepare_request(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
    ) -> Tuple[str, Optional[Dict[str, str]], bool]:
        include_host = include_host or self.include_host
        ssl_fallback_to_http = ssl_fallback_to_http or self.ssl_fallback_to_http

        if include_host is True and headers is None:
            # TLDExtract has better subdomain/domain separation
            # compared to urllib's urlparse
            headers = {"Host": tldextract.extract(url).fqdn}
        elif include_host is True and headers is not None and "Host" not in headers:
            headers["Host"] = tldextract.extract(url).fqdn

        if self.ensure_protocol_url is True:
            parsed_url = urlparse(url)

            if parsed_url.scheme != "http" or parsed_url.scheme != "https":
                url_replaced = parsed_url._replace(scheme="https")
                # Replace "///" by "//" in case URL is parsed as path and not netloc
                url = urlunparse(url_replaced).replace("https:///", "https://")

        return url, headers, ssl_fallback_to_http


class Client(BaseClient):
    _type: str = "classic"

    def __init__(
        self,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
        ensure_protocol_url: bool = False,
        proxy_url: Optional[str] = None,
    ) -> None:
        super().__init__(
            headers, include_host, ssl_fallback_to_http, ensure_protocol_url
        )
        transport: httpx.HTTPTransport = httpx.HTTPTransport(retries=2, proxy=proxy_url)

        self.client: httpx.Client = httpx.Client(
            transport=transport,
            timeout=self.timeout,
            headers=self.headers,
            http2=True,
        )

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        content: Any = None,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        resp: Optional[httpx.Response] = None

        url, headers, ssl_fallback_to_http = self._prepare_request(
            url, headers, include_host, ssl_fallback_to_http
        )

        try:
            resp = self.client.request(method, url, headers=headers, content=content)
        except ssl.SSLError as e:
            if ssl_fallback_to_http is True:
                resp = self.client.request(
                    method,
                    url.lower().replace("https://", "http://"),
                    headers=headers,
                    content=content,
                )
            else:
                raise e
        except ssl.SSLWantReadError:
            # From https://github.com/encode/httpx/discussions/2941#discussioncomment-7574569
            # SSLWantReadError does itself not cause any problems. All it indicates is
            # that there isn't enough data in the local buffer for decrypting more
            # incoming data, so more needs to be read from the socket. And that's where
            # the timeout is coming from.
            # So we just retry
            pass
        return resp

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        return self.request(
            "get", url, headers, include_host, ssl_fallback_to_http=ssl_fallback_to_http
        )

    def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        content: Any = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        return self.request(
            "post",
            url,
            headers,
            include_host,
            content,
            ssl_fallback_to_http=ssl_fallback_to_http,
        )

    def head(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        return self.request(
            "head",
            url,
            headers,
            include_host,
            ssl_fallback_to_http=ssl_fallback_to_http,
        )

    def stream(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        content: Any = None,
        ssl_fallback_to_http: bool = False,
    ) -> ContextManager[httpx.Response]:
        url, headers, ssl_fallback_to_http = self._prepare_request(
            url, headers, include_host, ssl_fallback_to_http
        )

        try:
            return self.client.stream(method, url, headers=headers, content=content)
        except ssl.SSLError as e:
            if ssl_fallback_to_http is True:
                return self.client.stream(
                    method,
                    url.lower().replace("https://", "http://"),
                    headers=headers,
                    content=content,
                )
            else:
                raise e
        except ssl.SSLWantReadError:
            # From https://github.com/encode/httpx/discussions/2941#discussioncomment-7574569
            # SSLWantReadError does itself not cause any problems. All it indicates is
            # that there isn't enough data in the local buffer for decrypting more
            # incoming data, so more needs to be read from the socket. And that's where
            # the timeout is coming from.
            # So we just retry
            pass

    def close(self) -> None:
        self.client.close()


class AsyncClient(BaseClient):
    _type: str = "classic"

    def __init__(
        self,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
        ensure_protocol_url: bool = False,
        proxy_url: Optional[str] = None,
    ) -> None:
        super().__init__(
            headers, include_host, ssl_fallback_to_http, ensure_protocol_url
        )
        self.transport: httpx.AsyncHTTPTransport = httpx.AsyncHTTPTransport(
            retries=2, proxy=proxy_url
        )

    async def open(self) -> None:
        self.client: httpx.AsyncClient = httpx.AsyncClient(
            transport=self.transport,
            timeout=self.timeout,
            headers=self.headers,
            http2=True,
        )

    async def close(self) -> None:
        await self.client.aclose()

    async def __aenter__(self) -> Self:
        await self.open()
        return self

    # See link below for why more parameters than expected
    # https://docs.python.org/3/reference/datamodel.html#asynchronous-context-managers
    async def __aexit__(self, *args: Any) -> Self:
        await self.close()
        return self

    async def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        content: Any = None,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        resp: Optional[httpx.Response] = None

        url, headers, ssl_fallback_to_http = self._prepare_request(
            url, headers, include_host, ssl_fallback_to_http
        )

        try:
            resp = await self.client.request(
                method, url, headers=headers, content=content
            )
        except ssl.SSLError as e:
            if ssl_fallback_to_http is True:
                resp = await self.client.request(
                    method,
                    url.lower().replace("https://", "http://"),
                    headers=headers,
                    content=content,
                )
            else:
                raise e
        except ssl.SSLWantReadError:
            # From https://github.com/encode/httpx/discussions/2941#discussioncomment-7574569
            # SSLWantReadError does itself not cause any problems. All it indicates is
            # that there isn't enough data in the local buffer for decrypting more
            # incoming data, so more needs to be read from the socket. And that's where
            # the timeout is coming from.
            # So we just retry
            pass
        except httpx.RequestError as exc:
            if (
                exc.__cause__
                and isinstance(exc.__cause__, ssl.SSLError)
                and ssl_fallback_to_http is True
            ):
                resp = await self.client.request(
                    method,
                    url.lower().replace("https://", "http://"),
                    headers=headers,
                    content=content,
                )

        return resp

    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        return await self.request(
            "get", url, headers, include_host, ssl_fallback_to_http=ssl_fallback_to_http
        )

    async def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        content: Any = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        return await self.request(
            "post",
            url,
            headers,
            include_host,
            content,
            ssl_fallback_to_http=ssl_fallback_to_http,
        )

    async def head(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        return await self.request(
            "head",
            url,
            headers,
            include_host,
            ssl_fallback_to_http=ssl_fallback_to_http,
        )

    def stream(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        content: Any = None,
        ssl_fallback_to_http: bool = False,
    ) -> AsyncContextManager[httpx.Response]:
        url, headers, ssl_fallback_to_http = self._prepare_request(
            url, headers, include_host, ssl_fallback_to_http
        )

        try:
            return self.client.stream(method, url, headers=headers, content=content)
        except ssl.SSLError as e:
            if ssl_fallback_to_http is True:
                return self.client.stream(
                    method,
                    url.lower().replace("https://", "http://"),
                    headers=headers,
                    content=content,
                )
            else:
                raise e
        except ssl.SSLWantReadError:
            # From https://github.com/encode/httpx/discussions/2941#discussioncomment-7574569
            # SSLWantReadError does itself not cause any problems. All it indicates is
            # that there isn't enough data in the local buffer for decrypting more
            # incoming data, so more needs to be read from the socket. And that's where
            # the timeout is coming from.
            # So we just retry
            pass
