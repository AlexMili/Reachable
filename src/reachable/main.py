import random
import time
from urllib.parse import urlparse, urlunparse
from typing import List, Union

import httpx
import tldextract
from tqdm import tqdm

from reachable.client import Client


def is_reachable(
    url: Union[List[str], str],
    headers: dict = None,
    include_host: bool = True,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
):
    return_as_list = True
    if isinstance(url, str) is True:
        url = [url]
        return_as_list = False

    client = Client(headers=headers, include_host=include_host)

    results = []
    iterator = url
    if return_as_list is True:
        iterator = tqdm(url)

    for elt in iterator:
        resp = None
        to_return: dict = {
            "url": elt,
            "response": None,
            "status_code": -1,
            "success": False,
            "error_name": None,
            "cloudflare_protection": False,
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
                to_return["url"] = to_return["redirect"]["final_url"]

        if resp is not None:
            # Success
            if 300 > resp.status_code >= 200:
                to_return["success"] = True

            to_return["status_code"] = resp.status_code

            if b"cloudflareinsights.com" in resp.content:
                to_return["cloudflare_protection"] = True

        results.append(to_return)

    client.close()

    if return_as_list is False:
        return results[0]
    else:
        return results


def do_request(
    client, url: str, head_optim: bool = True, sleep_between_requests: bool = True
):
    error_name = None
    resp = None

    # We first use HEAD to optimize requests
    try:
        if sleep_between_requests is True:
            time.sleep(random.SystemRandom().uniform(1, 2))
        resp = client.head(url)
    except httpx.ConnectError:
        error_name = "ConnexionError"
    except httpx.ConnectTimeout:
        error_name = "ConnectTimeout"
    except httpx.ReadTimeout:
        error_name = "ReadTimeout"
    except httpx.RemoteProtocolError:
        error_name = "RemoteProtocolError"
    except Exception as e:
        error_name = type(e).__name__

    # Sometimes, the 40X and 50X errors are generated because of the use of HEAD request
    if head_optim is True and resp is not None and resp.status_code >= 400:
        # Reset error & response
        error_name = None
        resp = None

        try:
            if sleep_between_requests is True:
                time.sleep(random.SystemRandom().uniform(1, 2))
            resp = client.get(url)
        except httpx.ConnectError:
            error_name = "ConnexionError"
        except httpx.ConnectTimeout:
            error_name = "ConnectTimeout"
        except httpx.ReadTimeout:
            error_name = "ReadTimeout"
        except httpx.RemoteProtocolError:
            error_name = "RemoteProtocolError"
        except Exception as e:
            error_name = type(e).__name__

    return resp, error_name


def is_tlds_matching(url1: str, url2: str, strict_suffix: bool = True) -> bool:
    is_matching: bool = False
    tld_orig = tldextract.extract(url1)
    # In some cases they add the HTTPS port
    tld_redi = tldextract.extract(url2)

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


def _get_new_url(response):
    url_origin: str = str(response.url)
    redirect_url: str = response.headers.get("location", "unknown")

    # If it is a local redirection
    tld_redirect = tldextract.extract(redirect_url)
    if tld_redirect.domain == "":
        parsed_url = urlparse(url_origin)
        url_replaced = parsed_url._replace(path=redirect_url)
        new_url = urlunparse(url_replaced)
    else:
        new_url = redirect_url

    return new_url


def handle_redirect(client, resp, sleep_between_requests: bool = True):
    error_name = None
    data = {
        "chain": [],
        "final_url": None,
        "tld_match": False,
    }

    new_url = _get_new_url(resp)

    resp, error_name, chain = follow_redirect(client, new_url)

    data["chain"] = chain
    if resp is not None:
        data["final_url"] = str(resp.url)
        data["tld_match"] = is_tlds_matching(
            str(resp.url), data["final_url"], strict_suffix=False
        )

    return data, resp, error_name


def follow_redirect(
    client,
    url: str,
    depth: int = 5,
    sleep_between_requests: bool = True,
    head_optim: bool = True,
):
    if depth <= 0:
        return None, "Max depth reached", []

    chain = [url]
    resp, error_name = do_request(
        client,
        url,
        head_optim=head_optim,
        sleep_between_requests=sleep_between_requests,
    )

    # Has redirect
    if resp is not None and 400 > resp.status_code >= 300:
        new_url = _get_new_url(str(resp.url), resp.headers.get("location", "unknown"))
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
