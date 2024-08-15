from reachable import is_reachable

def test_serp():
    result = is_reachable("https://google.com")
    result2 = is_reachable(["https://google.com", "https://bing.com"])
    print("Done")
