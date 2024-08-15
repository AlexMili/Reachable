**Reachable** checks if a URL exists and is reachable.

# Features
- Use `HEAD`request instead of `GET` to save some bandwidth
- Follow redirects
- Handle local redirects (without full URL in `location` header)
- Record all the URLs of the redirection chain
- Check if redirected URL match the TLD of source URL
- Detect Cloudflare protection
- Avoid basic bot detectors
    - Use randome Chrome user agent
    - Wait between consecutive requests to the same host
    - Include `Host` header
- Use of HTTP/2

# Installation
You can install it with pip :
```bash
pip install reachable
```
Or clone this repository and simply run :
```bash
cd reachable/
pip install -e .
```

# Usage

## Simple URL
```python
result = is_reachable("https://google.com")
```

The output will look like this:
```json
{
    "url": "https://www.google.com/",
    "response": null, 
    "status_code": 200,
    "success": true,
    "error_name": null,
    "cloudflare_protection": false,
    "redirect": {
        "chain": ["https://www.google.com/"],
        "final_url": "https://www.google.com/",
        "tld_match": true
    }
}
```

## Multiple URLs
```python
result = is_reachable(["https://google.com", "http://bing.com"])
```

The output will look like this:
```json
[
    {
        "url": "https://www.google.com/",
        "response": null, 
        "status_code": 200,
        "success": true,
        "error_name": null,
        "cloudflare_protection": false,
        "redirect": {
            "chain": ["https://www.google.com/"],
            "final_url": "https://www.google.com/",
            "tld_match": true
        }
    },
    {
        "url": "https://www.bing.com/?toWww=1&redig=16A78C94",
        "response": null,
        "status_code": 200,
        "success": true,
        "error_name": null,
        "cloudflare_protection": false,
        "redirect": {"chain": ["https://www.bing.com:443/?toWww=1&redig=16A78C94"],
        "final_url": "https://www.bing.com/?toWww=1&redig=16A78C94",
        "tld_match": true
    }
]
```
