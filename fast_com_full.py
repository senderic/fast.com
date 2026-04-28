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

    url = f"{base_url}netflix/speedtest?https=true&token={token}&urlCount=5"
    req = urllib.request.Request(url, headers=headers)

    with urllib.request.urlopen(req, timeout=5) as response:
        return json.loads(response.read().decode('utf-8'))

def download_worker(url, result, index):
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

def upload_worker(url, result, index):
    try:
        CHUNK = 100 * 1024
        data = b'0' * CHUNK
        i = 1
        while True:
            req = urllib.request.Request(url, data=data, method='POST')
            with urllib.request.urlopen(req) as response:
                if response.status == 200:
                    result[index] = i * CHUNK
                    i += 1
                else:
                    break
    except:
        pass

def application_bytes_to_networkbits(bytes_val):
    return bytes_val * 8 * 1.0415

def run_speed_test(urls, mode='download', maxtime=15, verbose=True):
    amount = len(urls)
    threads = [None] * amount
    results = [0] * amount

    worker_func = download_worker if mode == 'download' else upload_worker

    if verbose: print(f"Testing {mode} speed", end="", flush=True)

    for i in range(amount):
        threads[i] = Thread(target=worker_func, args=(urls[i], results, i))
        threads[i].daemon = True
        threads[i].start()

    time.sleep(1)
    sleepseconds = 3
    lasttotal = 0
    highestspeedkBps = 0
    nrloops = int(maxtime / sleepseconds)

    for loop in range(nrloops):
        if verbose: print(".", end="", flush=True)
        total = sum(results)
        delta = total - lasttotal
        speedkBps = (delta / sleepseconds) / 1024

        lasttotal = total
        if speedkBps > highestspeedkBps:
            highestspeedkBps = speedkBps
        time.sleep(sleepseconds)

    if verbose: print()
    Mbps = (application_bytes_to_networkbits(highestspeedkBps) / 1024)
    return float(f"{Mbps:.1f}")

def fast_com(verbose=True, maxtime=15):
    token = get_token()
    if not token:
        if verbose: print("Could not find token")
        return 0, 0

    parsedjson = None
    try:
        parsedjson = get_api_urls(token, force_ipv4=True)
    except:
        try:
            parsedjson = get_api_urls(token, force_ipv6=True)
        except:
            try:
                parsedjson = get_api_urls(token)
            except:
                if verbose: print("Could not get API URLs")
                return 0, 0

    if not parsedjson:
        return 0, 0

    urls = [jsonelement['url'] for jsonelement in parsedjson]

    download_speed = run_speed_test(urls, mode='download', maxtime=maxtime, verbose=verbose)
    upload_speed = run_speed_test(urls, mode='upload', maxtime=maxtime, verbose=verbose)

    return download_speed, upload_speed

if __name__ == "__main__":
    try:
        # Get local IP and ISP if possible
        try:
            with urllib.request.urlopen('https://api.fast.com/netflix/speedtest?https=true&token=YXNkZmFzZGxmbnNkYWZoYXNkZmhrYWxm') as r:
                # This is just to get a hint, but actually fast.com doesn't easily give ISP in a simple API
                pass
        except:
            pass

        print("Starting Speed test against fast.com")
        download, upload = fast_com(verbose=True)

        print(f"\nDownload: {download} Mbit/s")
        print(f"Upload: {upload} Mbit/s")
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
