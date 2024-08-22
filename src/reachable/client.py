from typing import Any, Dict, Optional

import httpx
import tldextract
from fake_useragent import UserAgent
from typing_extensions import Self


ua: Any = UserAgent(browsers=["chrome"], os="windows", platforms="pc", min_version=120)


class Client:
    def __init__(
        self, headers: Optional[Dict[str, str]] = None, include_host: bool = False
    ) -> None:
        transport: httpx.HTTPTransport = httpx.HTTPTransport(retries=2)
        timeout: int = 10
        if headers is None:
            headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US;q=0.7,en;q=0.3",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "DNT": "1",
                "Connection": "keep-alive",
                "TE": "trailers",
            }

        self.client: httpx.Client = httpx.Client(
            transport=transport,
            timeout=timeout,
            headers=headers,
            http2=True,
        )
        self.include_host: bool = include_host

    def request(
        self,
        method: str,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
        content: Any = None,
    ) -> Optional[httpx.Response]:
        include_host = include_host | self.include_host
        resp: Optional[httpx.Response] = None

        if include_host is True and headers is None:
            headers = {"Host": tldextract.extract(url).fqdn}
        elif include_host is True and headers is not None and "Host" not in headers:
            headers["Host"] = tldextract.extract(url).fqdn

        resp = self.client.request(method, url, headers=headers, content=content)

        return resp

    def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
    ) -> Optional[httpx.Response]:
        return self.request("get", url, headers, include_host)

    def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        content: Any = None,
        include_host: bool = False,
    ) -> Optional[httpx.Response]:
        return self.request("post", url, headers, include_host, content)

    def head(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
    ) -> Optional[httpx.Response]:
        return self.request("head", url, headers, include_host)

    def close(self) -> None:
        self.client.close()


class AsyncClient:
    def __init__(
        self, headers: Optional[Dict[str, str]] = None, include_host: bool = False
    ) -> None:
        self.transport: httpx.AsyncHTTPTransport = httpx.AsyncHTTPTransport(retries=2)
        self.timeout: int = 10
        if headers is None:
            self.headers = {
                "User-Agent": ua.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "Accept-Language": "en-US;q=0.7,en;q=0.3",
                "Accept-Encoding": "gzip, deflate, br, zstd",
                "DNT": "1",
                "Connection": "keep-alive",
                "TE": "trailers",
            }
        else:
            self.headers = headers

        self.include_host: bool = include_host

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
    ) -> Optional[httpx.Response]:
        include_host = include_host | self.include_host

        if include_host is True and headers is None:
            headers = {"Host": tldextract.extract(url).fqdn}
        elif include_host is True and headers is not None and "Host" not in headers:
            headers["Host"] = tldextract.extract(url).fqdn

        resp = await self.client.request(method, url, headers=headers, content=content)

        return resp

    async def get(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
    ) -> Optional[httpx.Response]:
        return await self.request("get", url, headers, include_host)

    async def post(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        content: Any = None,
        include_host: bool = False,
    ) -> Optional[httpx.Response]:
        return await self.request("post", url, headers, include_host, content)

    async def head(
        self,
        url: str,
        headers: Optional[Dict[str, str]] = None,
        include_host: bool = False,
    ) -> Optional[httpx.Response]:
        return await self.request("head", url, headers, include_host)
