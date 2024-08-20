from typing import Union

import httpx
import tldextract
from fake_useragent import UserAgent


ua = UserAgent(browsers=["chrome"], os="windows", platforms="pc", min_version=120)


class Client:
    def __init__(self, headers: Union[dict, None] = None, include_host: bool = False):
        transport = httpx.HTTPTransport(retries=3)
        timeout = httpx.Timeout(10.0, connect=60.0, read=10.0)
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

        self.client = httpx.Client(
            transport=transport,
            timeout=timeout,
            headers=headers,
            http2=True,
        )
        self.include_host = include_host

    def request(
        self,
        method: str,
        url: str,
        retries: int = 3,
        headers: Union[dict, None] = None,
        include_host: bool = False,
        content=None,
    ):
        include_host = include_host | self.include_host
        data = None
        tried: int = 0

        if include_host is True and headers is None:
            headers = {"Host": tldextract.extract(url).fqdn}
        elif include_host is True and "Host" not in headers:
            headers["Host"] = tldextract.extract(url).fqdn

        while data is None and tried < retries:
            try:
                data = self.client.request(
                    method, url, headers=headers, content=content
                )
            except httpx.ReadTimeout:
                tried += 1

        return data

    def get(
        self, url, retries: int = 3, headers: dict = None, include_host: bool = False
    ):
        return self.request("get", url, retries, headers, include_host)

    def post(
        self,
        url,
        retries: int = 3,
        headers: dict = None,
        content=None,
        include_host: bool = False,
    ):
        return self.request("post", url, retries, headers, include_host, content)

    def head(
        self, url, retries: int = 3, headers: dict = None, include_host: bool = False
    ):
        return self.request("head", url, retries, headers, include_host)

    def close(self):
        self.client.close()


class AsyncClient:
    def __init__(self, headers: Union[dict, None] = None, include_host: bool = False):
        self.transport = httpx.AsyncHTTPTransport(retries=3)
        self.timeout = httpx.Timeout(10.0, connect=60.0, read=10.0)
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

        self.include_host = include_host

    async def open(self):
        self.client = httpx.AsyncClient(
            transport=self.transport,
            timeout=self.timeout,
            headers=self.headers,
            http2=True,
        )

    async def close(self):
        await self.client.aclose()

    async def __aenter__(self):
        await self.open()
        return self

    # See link below for why more parameters than expected
    # https://docs.python.org/3/reference/datamodel.html#asynchronous-context-managers
    async def __aexit__(self, exc_type, exc, tb):
        await self.close()
        return self

    async def request(
        self,
        method: str,
        url: str,
        retries: int = 3,
        headers: Union[dict, None] = None,
        include_host: bool = False,
        content=None,
    ):
        include_host = include_host | self.include_host

        data = None
        tried: int = 0

        if include_host is True and headers is None:
            headers = {"Host": tldextract.extract(url).fqdn}
        elif include_host is True and "Host" not in headers:
            headers["Host"] = tldextract.extract(url).fqdn

        while data is None and tried < retries:
            try:
                resp = await self.client.request(
                    method, url, headers=headers, content=content
                )
                resp.raise_for_status()
                data = resp
            except httpx.ReadTimeout:
                tried += 1
                data = None

        return data

    async def get(
        self, url, retries: int = 3, headers: dict = None, include_host: bool = False
    ):
        return await self.request("get", url, retries, headers, include_host)

    async def post(
        self,
        url,
        retries: int = 3,
        headers: dict = None,
        content=None,
        include_host: bool = False,
    ):
        return await self.request("post", url, retries, headers, include_host, content)

    async def head(
        self, url, retries: int = 3, headers: dict = None, include_host: bool = False
    ):
        return await self.request("head", url, retries, headers, include_host)
