#!/usr/bin/env python3
import urllib.request
import json
import socket
import re
import time
import sys
from threading import Thread

def get_token():
    url = 'https://fast.com/'
    try:
        with urllib.request.urlopen(url) as response:
            html = response.read().decode('utf-8')

        js_match = re.search(r'<script src="(/app-[^"]+\.js)"', html)
        if not js_match:
            return None

        js_url = 'https://fast.com' + js_match.group(1)
        with urllib.request.urlopen(js_url) as response:
            js_content = response.read().decode('utf-8')

        token_match = re.search(r'token:"([^"]+)"', js_content)
        if token_match:
            return token_match.group(1)
    except:
        pass
    return None

def get_api_urls(token, force_ipv4=False, force_ipv6=False):
    base_url = 'https://api.fast.com/'
    headers = {}

    if force_ipv4:
        try:
            ipv4 = socket.getaddrinfo('api.fast.com', 80, socket.AF_INET)[0][4][0]
            base_url = f'http://{ipv4}/'
            headers = {'Host': 'api.fast.com'}
        except:
            raise Exception("IPv4 resolution failed")
    elif force_ipv6:
        try:
            ipv6 = socket.getaddrinfo('api.fast.com', 80, socket.AF_INET6)[0][4][0]
            base_url = f'http://[{ipv6}]/'
            headers = {'Host': 'api.fast.com'}
        except:
            raise Exception("IPv6 resolution failed")

    url = f"{base_url}netflix/speedtest?https=true&token={token}&urlCount=3"
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode('utf-8'))

def get_html_result(url, result, index):
    try:
        req = urllib.request.urlopen(url)
        CHUNK = 100 * 1024
        i = 1
        while True:
            chunk = req.read(CHUNK)
            if not chunk:
                break
            result[index] = i * CHUNK
            i += 1
    except:
        pass

def application_bytes_to_networkbits(bytes_val):
    # convert bytes (at application layer) to bits (at network layer)
    return bytes_val * 8 * 1.0415

def fast_com(verbose=True, maxtime=15):
    token = get_token()
    if not token:
        if verbose: print("Could not find token")
        return 0
    if verbose: print(f"Token found: {token}")

    parsedjson = None
    # Try IPv4 first
    try:
        if verbose: print("Fetching API URLs via IPv4...")
        parsedjson = get_api_urls(token, force_ipv4=True)
    except:
        # Fallback to IPv6
        try:
            if verbose: print("IPv4 failed, trying IPv6...")
            parsedjson = get_api_urls(token, force_ipv6=True)
        except:
            # Final fallback to default
            try:
                if verbose: print("IPv6 failed, trying default...")
                parsedjson = get_api_urls(token)
            except:
                if verbose: print("Could not get API URLs")
                return 0

    if not parsedjson:
        return 0

    amount = len(parsedjson)
    if verbose: print(f"Number of URLs: {amount}")
    threads = [None] * amount
    results = [0] * amount
    urls = [jsonelement['url'] for jsonelement in parsedjson]

    for i in range(amount):
        if verbose: print(f"Starting thread for {urls[i]}")
        threads[i] = Thread(target=get_html_result, args=(urls[i], results, i))
        threads[i].daemon = True
        threads[i].start()

    time.sleep(1)
    sleepseconds = 3
    lasttotal = 0
    highestspeedkBps = 0
    nrloops = int(maxtime / sleepseconds)

    for loop in range(nrloops):
        total = sum(results)
        delta = total - lasttotal
        speedkBps = (delta / sleepseconds) / 1024

        if verbose:
            Mbps = (application_bytes_to_networkbits(speedkBps) / 1024)
            print(f"Loop {loop} Total MB {total/(1024*1024):.1f} Delta MB {delta/(1024*1024):.1f} Speed kB/s: {speedkBps:.1f} aka Mbps {Mbps:.1f}")

        lasttotal = total
        if speedkBps > highestspeedkBps:
            highestspeedkBps = speedkBps
        time.sleep(sleepseconds)

    Mbps = (application_bytes_to_networkbits(highestspeedkBps) / 1024)
    result_float = float(f"{Mbps:.1f}")
    if verbose: print(f"Highest Speed (kB/s): {highestspeedkBps:.1f} aka Mbps {result_float}")
    return result_float

if __name__ == "__main__":
    try:
        # Running with verbose=True by default as requested
        result = fast_com(verbose=True)
        print(f"\nResult: {result} Mbps")
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
