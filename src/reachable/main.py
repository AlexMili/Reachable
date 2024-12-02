import asyncio
import hashlib
import os
import random
import ssl
import time
from typing import Any, Dict, List, Optional, Tuple, Union
from urllib.parse import urlparse, urlunparse

import httpx
import tldextract
from tqdm import tqdm

from reachable.aio_client import AioAsyncClient
from reachable.client import AsyncClient, AsyncPlaywrightClient, Client


def is_reachable(
    url: Union[List[str], str],
    headers: Optional[Dict[str, str]] = None,
    include_host: bool = True,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
    include_response: bool = False,
    client: Optional[Client] = None,
    ssl_fallback_to_http: bool = False,
    check_parking_domain: bool = False,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    return_as_list: bool = True
    url_list: List[str] = []

    if isinstance(url, str):
        url_list = [url]
        return_as_list = False
    elif isinstance(url, list):
        url_list = url
    else:
        raise ValueError(f"URL(s) of type {type(url)} is not supported")

    close_client: bool = True
    if client is None:
        client = Client(
            headers=headers,
            include_host=include_host,
            ssl_fallback_to_http=ssl_fallback_to_http,
        )
    else:
        close_client = False

    # Only keep unique URLs to avoid requesting same URL multiple times
    url_list = list(set(url_list))

    results: List[Dict[str, Any]] = []
    iterator: Union[List[str], tqdm] = url_list
    if return_as_list is True:
        iterator = tqdm(url_list)

    for elt in iterator:
        resp: Optional[httpx.Response] = None
        to_return: Dict[str, Any] = {
            "original_url": elt,
            "status_code": -1,
            "success": False,
            "error_name": None,
            "cloudflare_protection": False,
            "has_js_redirect": False,
        }

        resp, to_return["error_name"] = do_request(
            client,
            elt,
            head_optim=head_optim,
            sleep_between_requests=sleep_between_requests,
        )

        # Then we handle redirects
        if resp is not None and 400 > resp.status_code >= 300:
            to_return["error_name"] = None
            to_return["redirect"], resp, to_return["error_name"] = handle_redirect(
                client, resp
            )

            if to_return["redirect"]["final_url"] is not None:
                to_return["final_url"] = to_return["redirect"]["final_url"]

        if resp is not None:
            # Success
            if 300 > resp.status_code >= 200:
                to_return["success"] = True

            to_return["status_code"] = resp.status_code

            if b"cloudflareinsights.com" in resp.content:
                to_return["cloudflare_protection"] = True
            elif "cf-ray" in resp.headers:
                to_return["cloudflare_protection"] = True

            # Since really detecting JS redirects is not doable, we only detect
            # some cases and flag it has JS redirect. Of course it needs more tests
            # with some frameworks like selenium.
            if b"DOMContentLoaded" in resp.content and b"location.href" in resp.content:
                to_return["has_js_redirect"] = True

            if check_parking_domain is True:
                to_return["is_parking_domain"] = is_parking_domain(
                    client,
                    str(resp.url),
                    head_optim=head_optim,
                    sleep=sleep_between_requests,
                )

        if include_response is True:
            to_return["response"] = resp

        results.append(to_return)

    if close_client is True:
        client.close()

    if return_as_list is False:
        return results[0]
    else:
        return results


async def is_reachable_async(
    url: Union[List[str], str],
    headers: Optional[Dict[str, str]] = None,
    include_host: bool = True,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
    include_response: bool = False,
    client: Optional[AsyncClient] = None,
    ssl_fallback_to_http: bool = False,
    check_parking_domain: bool = False,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    return_as_list: bool = True
    url_list: List[str] = []

    if isinstance(url, str):
        url_list = [url]
        return_as_list = False
    elif isinstance(url, list):
        url_list = url
    else:
        raise ValueError(f"URL(s) of type {type(url)} is not supported")

    close_client: bool = True
    if client is None:
        client = AsyncClient(
            headers=headers,
            include_host=include_host,
            ssl_fallback_to_http=ssl_fallback_to_http,
        )
        await client.open()
    else:
        close_client = False

    # Only keep unique URLs to avoid requesting same URL multiple times
    url_list = list(set(url_list))

    results: List[Dict[str, Any]] = []
    iterator: Union[List[str], tqdm] = url_list
    if return_as_list is True:
        iterator = tqdm(url_list)

    for elt in iterator:
        resp: Optional[httpx.Response] = None
        to_return: Dict[str, Any] = {
            "original_url": elt,
            "status_code": -1,
            "success": False,
            "error_name": None,
            "cloudflare_protection": False,
            "has_js_redirect": False,
        }

        # I don't know why but sometimes a TypeError is raised with the message
        # "an integer is required". This only happens when a httpx.ConnectError
        # has just been raised, tried different fixes without any success.
        # The problem appears to appear in the async process so the error
        # is not catchable here but where the async job has been called.
        # Looks like using `asyncio.create_task` fix the problem (thks ChatGPT).
        resp, to_return["error_name"] = await asyncio.create_task(
            do_request_async(
                client,
                elt,
                head_optim=head_optim,
                sleep_between_requests=sleep_between_requests,
            )
        )

        # If the request has been made by a browser client and the final URL doesn't
        # match the initial one, it has been redirected.
        # Redirects are handled transparently, so we need to populate `to_return`
        # with information that we have.
        if (
            client._type == "browser"
            and resp is not None
            and len(str(getattr(resp, "url", ""))) > 0
            and str(resp.url) != elt
            and 300 > resp.status_code >= 200
        ):
            to_return["redirect"] = {
                "chain": [str(resp.url)],
                "final_url": str(resp.url),
                "tld_match": is_tlds_matching(elt, str(resp.url), strict_suffix=False),
            }
            to_return["final_url"] = str(resp.url)

        # Then we handle redirects
        if resp is not None and 400 > resp.status_code >= 300:
            to_return["error_name"] = None
            (
                to_return["redirect"],
                resp,
                to_return["error_name"],
            ) = await handle_redirect_async(client, resp, head_optim=head_optim)

            if to_return["redirect"]["final_url"] is not None:
                to_return["final_url"] = to_return["redirect"]["final_url"]

        if resp is not None:
            # Success
            if 300 > resp.status_code >= 200:
                to_return["success"] = True

            to_return["status_code"] = resp.status_code

            if b"cloudflareinsights.com" in resp.content:
                to_return["cloudflare_protection"] = True
            elif "cf-ray" in resp.headers:
                to_return["cloudflare_protection"] = True

            # Since really detecting JS redirects is not doable, we only detect
            # some cases and flag it has JS redirect. Of course it needs more tests
            # with some frameworks like selenium.
            if b"DOMContentLoaded" in resp.content and b"location.href" in resp.content:
                to_return["has_js_redirect"] = True

            if check_parking_domain is True:
                to_return["is_parking_domain"] = await is_parking_domain_async(
                    client,
                    str(resp.url),
                    head_optim=head_optim,
                    sleep=sleep_between_requests,
                )

        if include_response is True:
            to_return["response"] = resp

        results.append(to_return)

    if close_client is True:
        await client.close()

    if return_as_list is False:
        return results[0]
    else:
        return results


async def is_reachable_aio_async(
    url: Union[List[str], str],
    headers: Optional[Dict[str, str]] = None,
    include_host: bool = True,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
    include_response: bool = False,
    client: Optional[AioAsyncClient] = None,
) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
    return_as_list: bool = True
    url_list: List[str] = []

    if isinstance(url, str):
        url_list = [url]
        return_as_list = False
    elif isinstance(url, list):
        url_list = url
    else:
        raise ValueError(f"URL(s) of type {type(url)} is not supported")

    close_client: bool = True
    if client is None:
        client = AioAsyncClient(headers=headers, include_host=include_host)
        await client.open()
    else:
        close_client = False

    # Only keep unique URLs to avoid requesting same URL multiple times
    url_list = list(set(url_list))

    results: List[Dict[str, Any]] = []
    iterator: Union[List[str], tqdm] = url
    if return_as_list is True:
        iterator = tqdm(url_list)

    for elt in iterator:
        resp = None
        to_return: Dict[str, Any] = {
            "original_url": elt,
            "status_code": -1,
            "success": False,
            "error_name": None,
            "cloudflare_protection": False,
        }

        resp, to_return["error_name"] = await do_request_async(
            client,
            elt,
            head_optim=head_optim,
            sleep_between_requests=sleep_between_requests,
        )

        # Then we handle redirects
        if resp is not None and 400 > resp.status >= 300:
            to_return["error_name"] = None
            (
                to_return["redirect"],
                resp,
                to_return["error_name"],
            ) = await handle_redirect_async(client, resp)

            if to_return["redirect"]["final_url"] is not None:
                to_return["final_url"] = to_return["redirect"]["final_url"]

        if resp is not None:
            # Success
            if 300 > resp.status >= 200:
                to_return["success"] = True

            to_return["status_code"] = resp.status

            if b"cloudflareinsights.com" in resp.content:
                to_return["cloudflare_protection"] = True

        if include_response is True:
            to_return["response"] = resp

        results.append(to_return)

    if close_client is True:
        await client.close()

    if return_as_list is False:
        return results[0]
    else:
        return results


def do_request(
    client: Client,
    url: str,
    head_optim: bool = True,
    sleep_between_requests: bool = True,
) -> Tuple[Optional[httpx.Response], Optional[str]]:
    error_name: Optional[str] = None
    resp: Optional[httpx.Response] = None

    # We first use HEAD to optimize requests
    try:
        if sleep_between_requests is True:
            time.sleep(random.SystemRandom().uniform(1, 2))

        # "Classic" client is httpx, AioHttp, etc.
        # Otherwise it is a "browser" like Playwright, etc
        if head_optim is True and client._type == "classic":
            resp = client.head(url)
        else:
            resp = client.get(url)
    except httpx.ConnectError:
        error_name = "ConnectionError"
    except httpx.ConnectTimeout:
        error_name = "ConnectTimeout"
    except httpx.ReadTimeout:
        error_name = "ReadTimeout"
    except httpx.RemoteProtocolError:
        error_name = "RemoteProtocolError"
    except ssl.SSLError:
        error_name = "SSLError"
    except httpx.ReadError:
        # Usually this is when the server block us
        error_name = "ReadError"
    except Exception as e:
        if getattr(e, "name", None) is not None:
            error_name = e.name
        else:
            error_name = type(e).__name__

    # Sometimes, the 40X and 50X errors are generated because of the use of HEAD request
    # If client's type is a browser, the error is definitive.
    if (
        head_optim is True
        and resp is not None
        and resp.status_code >= 400
        and client._type == "classic"
    ):
        # Reset error & response
        error_name = None
        resp = None

        try:
            if sleep_between_requests is True:
                time.sleep(random.SystemRandom().uniform(1, 2))
            resp = client.get(url)
        except httpx.ConnectError:
            error_name = "ConnectionError"
        except httpx.ConnectTimeout:
            error_name = "ConnectTimeout"
        except httpx.ReadTimeout:
            error_name = "ReadTimeout"
        except httpx.RemoteProtocolError:
            error_name = "RemoteProtocolError"
        except ssl.SSLError:
            error_name = "SSLError"
        except httpx.ReadError:
            # Usually this is when the server block us
            error_name = "ReadError"
        except Exception as e:
            if getattr(e, "name", None) is not None:
                error_name = e.name
            else:
                error_name = type(e).__name__

    return resp, error_name


async def do_request_async(
    client: Union[AsyncClient, AsyncPlaywrightClient],
    url: str,
    head_optim: bool = True,
    sleep_between_requests: bool = True,
    ssl_fallback_to_http: bool = False,
) -> Tuple[Optional[httpx.Response], Optional[str]]:
    error_name: Optional[str] = None
    resp: Optional[httpx.Response] = None

    # We first use HEAD to optimize requests
    try:
        if sleep_between_requests is True:
            await asyncio.sleep(random.SystemRandom().uniform(1, 2))

        # "Classic" client is httpx, AioHttp, etc.
        # Otherwise it is a "browser" like Playwright, etc
        if head_optim is True and client._type == "classic":
            resp = await client.head(url, ssl_fallback_to_http=ssl_fallback_to_http)
        else:
            resp = await client.get(url, ssl_fallback_to_http=ssl_fallback_to_http)
    except httpx.ConnectError:
        error_name = "ConnectionError"
    except httpx.ConnectTimeout:
        error_name = "ConnectTimeout"
    except httpx.ReadTimeout:
        error_name = "ReadTimeout"
    except httpx.WriteTimeout:
        error_name = "ReadTimeout"
    except httpx.RemoteProtocolError:
        error_name = "RemoteProtocolError"
    except ssl.SSLError:
        error_name = "SSLError"
    except httpx.ReadError:
        # Usually this is when the server block us
        error_name = "ReadError"
    except Exception as e:
        if getattr(e, "name", None) is not None:
            error_name = e.name
        else:
            error_name = type(e).__name__

    # Sometimes, the 40X and 50X errors are generated because of the use of HEAD request
    # If client's type is a browser, the error is definitive.
    if (
        head_optim is True
        and resp is not None
        and resp.status_code >= 400
        and client._type == "classic"
    ):
        # Reset error & response
        error_name = None
        resp = None

        try:
            if sleep_between_requests is True:
                await asyncio.sleep(random.SystemRandom().uniform(1, 2))
            resp = await client.get(url, ssl_fallback_to_http=ssl_fallback_to_http)
        except httpx.ConnectError:
            error_name = "ConnectionError"
        except httpx.ConnectTimeout:
            error_name = "ConnectTimeout"
        except httpx.WriteTimeout:
            error_name = "ReadTimeout"
        except httpx.ReadTimeout:
            error_name = "ReadTimeout"
        except httpx.RemoteProtocolError:
            error_name = "RemoteProtocolError"
        except httpx.HTTPStatusError as e:
            # For whatever reason HTTPStatusError is raised for non 20X status code
            # which is documented in HTTPX's documentation but this is not what happens
            # when using sync mode so we standardize behavior here.
            resp = e.response
        except ssl.SSLError:
            error_name = "SSLError"
        except httpx.ReadError:
            # Usually this is when the server block us
            error_name = "ReadError"
        except Exception as e:
            if getattr(e, "name", None) is not None:
                error_name = e.name
            else:
                error_name = type(e).__name__

    return resp, error_name


def is_tlds_matching(url1: str, url2: str, strict_suffix: bool = True) -> bool:
    is_matching: bool = False
    tld_orig: Any = tldextract.extract(url1)
    # In some cases they add the HTTPS port
    tld_redi: Any = tldextract.extract(url2)

    # If it's the same example.com
    if tld_orig.domain == tld_redi.domain and tld_orig.suffix == tld_redi.suffix:
        is_matching = True
    # If we have example.io and example.com
    elif tld_orig.domain == tld_redi.domain and strict_suffix is False:
        is_matching = True
    # Local redirection: /somepath
    elif tld_redi.domain == "":
        is_matching = True
    else:
        is_matching = False

    return is_matching


def _get_new_url(response: httpx.Response) -> str:
    url_origin: str = str(response.url)
    redirect_url: str = response.headers.get("location", "unknown")

    # If it is a local redirection
    new_url: str = ""
    tld_redirect: Any = tldextract.extract(redirect_url)
    if tld_redirect.domain == "":
        parsed_url = urlparse(url_origin)
        url_replaced = parsed_url._replace(path=redirect_url)
        new_url = urlunparse(url_replaced)
    else:
        new_url = redirect_url

    return new_url


def handle_redirect(
    client: Client,
    resp: httpx.Response,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
) -> Tuple[Dict[str, Any], Optional[httpx.Response], Optional[str]]:
    error_name: Optional[str] = None
    new_resp: Optional[httpx.Response] = None
    chain: List[str] = []
    data: Dict[str, Any] = {
        "chain": [],
        "final_url": None,
        "tld_match": False,
    }

    new_url: str = _get_new_url(resp)

    new_resp, error_name, chain = follow_redirect(
        client,
        new_url,
        sleep_between_requests=sleep_between_requests,
        head_optim=head_optim,
    )

    data["chain"] = chain
    if new_resp is not None:
        data["final_url"] = str(new_resp.url)
        data["tld_match"] = is_tlds_matching(
            str(new_resp.url), data["final_url"], strict_suffix=False
        )

    return data, new_resp, error_name


async def handle_redirect_async(
    client: AsyncClient,
    resp: httpx.Response,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
) -> Tuple[Dict[str, Any], Optional[httpx.Response], Optional[str]]:
    error_name: Optional[str] = None
    new_resp: Optional[httpx.Response] = None
    chain: List[str] = []
    data: Dict[str, Any] = {
        "chain": [],
        "final_url": None,
        "tld_match": False,
    }

    new_url: str = _get_new_url(resp)

    new_resp, error_name, chain = await follow_redirect_async(
        client,
        new_url,
        sleep_between_requests=sleep_between_requests,
        head_optim=head_optim,
    )

    data["chain"] = chain
    if new_resp is not None:
        data["final_url"] = str(new_resp.url)
        data["tld_match"] = is_tlds_matching(
            str(new_resp.url), data["final_url"], strict_suffix=False
        )

    return data, new_resp, error_name


def follow_redirect(
    client: Client,
    url: str,
    depth: int = 5,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
) -> Tuple[Optional[httpx.Response], Optional[str], List[str]]:
    if depth <= 0:
        return None, "Max depth reached", []

    chain: List[str] = [url]
    resp, error_name = do_request(
        client,
        url,
        head_optim=head_optim,
        sleep_between_requests=sleep_between_requests,
    )

    # Has redirect
    if resp is not None and 400 > resp.status_code >= 300:
        new_url: str = _get_new_url(resp)
        nresp, error_name, tchain = follow_redirect(
            client,
            new_url,
            depth=depth - 1,
            sleep_between_requests=sleep_between_requests,
            head_optim=head_optim,
        )
        chain += tchain
        return nresp, error_name, chain
    else:
        return resp, error_name, chain


async def follow_redirect_async(
    client: AsyncClient,
    url: str,
    depth: int = 5,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
) -> Tuple[Optional[httpx.Response], Optional[str], List[str]]:
    if depth <= 0:
        return None, "Max depth reached", []

    chain: List[str] = [url]
    resp, error_name = await do_request_async(
        client,
        url,
        head_optim=head_optim,
        sleep_between_requests=sleep_between_requests,
    )

    # Has redirect
    if resp is not None and 400 > resp.status_code >= 300:
        new_url: str = _get_new_url(resp)
        nresp, error_name, tchain = await follow_redirect_async(
            client,
            new_url,
            depth=depth - 1,
            sleep_between_requests=sleep_between_requests,
            head_optim=head_optim,
        )
        chain += tchain
        return nresp, error_name, chain
    else:
        return resp, error_name, chain


def _replace_url_path(url: str, path: str) -> str:
    parsed_url = urlparse(url)
    url_replaced = parsed_url._replace(query="", path=path)
    return urlunparse(url_replaced)


async def is_parking_domain_async(
    client: AsyncClient, url: str, head_optim: bool = True, sleep: bool = False
) -> bool:
    # Set random URL and if it returns 200, it is a parked domain since
    # they always answer with 200 or redirect
    rand = hashlib.sha512(os.urandom(128)).hexdigest()
    new_url = _replace_url_path(url, path=f"{rand[:64]}/{rand[65:]}")
    result, _ = await do_request_async(
        client, new_url, head_optim=head_optim, sleep_between_requests=sleep
    )
    return result.status_code < 400


def is_parking_domain(
    client: AsyncClient, url: str, head_optim: bool = True, sleep: bool = False
) -> bool:
    # Set random URL and if it returns 200, it is a parked domain since
    # they always answer with 200 or redirect
    rand = hashlib.sha512(os.urandom(128)).hexdigest()
    new_url = _replace_url_path(url, path=f"{rand[:64]}/{rand[65:]}")
    result, _ = do_request(
        client, new_url, head_optim=head_optim, sleep_between_requests=sleep
    )
    return result.status_code < 400
