import asyncio
import logging
import re
import ssl
from typing import Any, AsyncContextManager, ContextManager, Dict, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import httpx
import tldextract
from fake_useragent import UserAgent
from playwright.async_api import Error, TimeoutError, async_playwright
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
            verify=False,
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


class AsyncPlaywrightClient:
    _type: str = "browser"

    def __init__(
        self,
        headless: bool = False,
        ssl_fallback_to_http: bool = False,
        ensure_protocol_url: bool = False,
        executable_path: Optional[str] = None,
        proxy_url: Optional[str] = None,
    ):
        self.playwright = None
        self.playwright_manager = async_playwright()

        self.browser = None

        self.ssl_fallback_to_http: bool = ssl_fallback_to_http
        self.ensure_protocol_url: bool = ensure_protocol_url
        self.headless: bool = headless
        self.executable_path: Optional[str] = executable_path
        self.proxy = proxy_url

    async def open(self) -> None:
        self.playwright = await self.playwright_manager.__aenter__()

        if self.proxy is not None:
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless,
                executable_path=self.executable_path,
                proxy={"server": self.proxy},
            )
        else:
            self.browser = await self.playwright.chromium.launch(
                headless=self.headless, executable_path=self.executable_path
            )

    async def close(self) -> None:
        await self.browser.close()
        await self.playwright.stop()
        await self.playwright_manager.__aexit__()

    async def __aenter__(self) -> Self:
        await self.open()
        return self

    async def __aexit__(self, *args: Any) -> Self:
        await self.close()

    @staticmethod
    async def block_resources(route, request):
        # Manifest is the document for installing app on home screen on
        #   mobile defined by <link rel="manifest" href=""/>
        # TextTrack is for resources with videos
        if request.resource_type in [
            "image",
            "media",
            "stylesheet",
            "font",
            "manifest",
            "texttrack",
        ]:
            # Block the request
            await route.abort()
        else:
            # Continue with the request
            await route.continue_()

    @staticmethod
    async def _get_page_content(page, retries=3, delay=1):
        for i in range(retries):
            try:
                return await page.content()
            # Playwright is triggering `Error` exception or `UnboundLocalError`
            # which are not specific errors, so we catch them all
            except Exception:
                await asyncio.sleep(delay)

        raise Exception("Failed to get page content after multiple retries.")

    async def request(
        self,
        url: str,
        ssl_fallback_to_http: bool = False,
    ) -> Optional[httpx.Response]:
        ssl_fallback_to_http = ssl_fallback_to_http or self.ssl_fallback_to_http

        if self.ensure_protocol_url is True:
            parsed_url = urlparse(url)

            if parsed_url.scheme != "http" or parsed_url.scheme != "https":
                url_replaced = parsed_url._replace(scheme="https")
                # Replace "///" by "//" in case URL is parsed as path and not netloc
                url = urlunparse(url_replaced).replace("https:///", "https://")

        # We need a mutable data structure like a list or dictionary to hold the
        # response, as mutable structures can be modified inside nested functions.
        resp_obj = {"response": None, "final_url": url}

        page = await self.browser.new_page()

        # Register the route to block specific resources
        await page.route("**/*", AsyncPlaywrightClient.block_resources)

        async def response_handler(response):
            # If URL is "about:blank" it means this is the initial load,
            # so the first request must be the URL we are looking for
            # to handle correctly redirects.
            if page.url == "about:blank":
                resp_obj["response"] = response

        page.on("response", response_handler)

        content: str = ""
        try:
            await page.goto(url, timeout=60000)
            # Wait for all network requests in order to have the response object
            # and the HTML generated by an eventual React or Vue framework.
            await page.wait_for_load_state("networkidle")
            content = await AsyncPlaywrightClient._get_page_content(page, delay=2)
        except TimeoutError:
            raise httpx.ConnectTimeout("Connection timeout")
        except Error as e:
            # All Chronium errors are listed here:
            # https://source.chromium.org/chromium/chromium/src/+/main:net/base/net_error_list.h
            # DNS error, the domain has not been resolved
            if "NAME_NOT_RESOLVED" in str(e) or "CONNECTION_REFUSED" in str(e):
                raise httpx.ConnectError(
                    "[Errno 8] nodename nor servname provided, or not known"
                )
            elif "TIMED_OUT" in str(e):
                raise httpx.ConnectTimeout("Connection timeout")
            elif ("_SSL_" in str(e)) or ("_CERT_" in str(e)) and ssl_fallback_to_http:
                await page.close()
                await page.goto(url.replace("https://", "http://"), timeout=60000)
                # Wait for all network requests in order to have the response object
                # and the HTML generated by an eventual React or Vue framework.
                await page.wait_for_load_state("networkidle")
                content = await AsyncPlaywrightClient._get_page_content(page, delay=2)
            else:
                result = re.findall(r"net::([A-Z_0-9]*)", e.message)
                if len(result) > 0:
                    error = Error(result[0])
                    error.name = result[0]
                    raise error
                else:
                    raise e
        except Exception as e:
            raise e
        finally:
            await page.close()

        # Building the response
        resp: Optional[httpx.Response] = None
        if resp_obj["response"] is not None:
            headers = httpx.Headers(resp_obj["response"].headers)
            # When we build the Response, httpx will try to decompress the content
            # given the content-encoding value in the headers. Since it already
            # has been decompressed, we mark it as "identity" which
            # mean no compression
            headers["content-encoding"] = "identity"
            req = httpx.Request(method="get", url=resp_obj["response"].url)
            resp = httpx.Response(
                request=req,
                status_code=resp_obj["response"].status,
                headers=headers,
                content=content.encode(),
            )

        return resp

    async def get(
        self, url: str, ssl_fallback_to_http: bool = False
    ) -> Optional[httpx.Response]:
        return await self.request(url, ssl_fallback_to_http=ssl_fallback_to_http)

    async def post(
        self, url: str, ssl_fallback_to_http: bool = False
    ) -> Optional[httpx.Response]:
        logging.warning(
            "Using Playwright client, all requests are GET requests through the browser"
        )
        return await self.request(url, ssl_fallback_to_http=ssl_fallback_to_http)

    async def head(
        self, url: str, ssl_fallback_to_http: bool = False
    ) -> Optional[httpx.Response]:
        logging.warning(
            "Using Playwright client, all requests are GET requests through the browser"
        )
        return await self.request(url, ssl_fallback_to_http=ssl_fallback_to_http)
