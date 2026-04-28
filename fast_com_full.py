#!/usr/bin/env python3
"""
Fast.com Speed Test CLI
A self-contained Python 3 script to measure internet download and upload speed
using Netflix's Fast.com infrastructure.
"""

import urllib.request
import json
import socket
import re
import time
import sys
from threading import Thread

def get_token():
    """
    Retrieves the authentication token from Fast.com.

    The process involves:
    1. Fetching the main fast.com HTML.
    2. Finding the script URL for the application logic.
    3. Fetching that script and extracting the 'token' string using regex.

    Returns:
        str: The authentication token if found, None otherwise.
    """
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
    """
    Fetches the speed test server URLs from the Fast.com API.

    Args:
        token (str): The authentication token.
        force_ipv4 (bool): Whether to force the API request over IPv4.
        force_ipv6 (bool): Whether to force the API request over IPv6.

    Returns:
        list: A list of dictionaries, each containing a 'url' for testing.

    Raises:
        Exception: If IP resolution fails when forcing a specific protocol.
    """
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
    """
    Worker thread function for measuring download speed.

    Continually reads data from the provided URL in chunks and updates
    the result list with the total bytes received.

    Args:
        url (str): The test server URL.
        result (list): Shared list to store progress.
        index (int): This worker's index in the result list.
    """
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
    """
    Worker thread function for measuring upload speed.

    Continually sends POST requests with data chunks to the test server
    and updates the result list with the total bytes sent.

    Args:
        url (str): The test server URL.
        result (list): Shared list to store progress.
        index (int): This worker's index in the result list.
    """
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
    """
    Converts application-layer bytes to network-layer bits.

    Includes an overhead factor (1.0415) to account for TCP/IP headers.

    Args:
        bytes_val (float): Data in bytes.

    Returns:
        float: Data in bits.
    """
    return bytes_val * 8 * 1.0415

def run_speed_test(urls, mode='download', maxtime=15, verbose=True):
    """
    Orchestrates a speed test (either download or upload).

    Spawns multiple worker threads and monitors their progress over a
    set period of time to calculate the highest achieved speed.

    Args:
        urls (list): List of test server URLs.
        mode (str): Either 'download' or 'upload'.
        maxtime (int): Maximum duration for the test in seconds.
        verbose (bool): Whether to print progress information.

    Returns:
        float: The highest recorded speed in Mbit/s.
    """
    amount = len(urls)
    threads = [None] * amount
    results = [0] * amount

    worker_func = download_worker if mode == 'download' else upload_worker

    print(f"Testing {mode} speed", end="", flush=True)

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
        total = sum(results)
        delta = total - lasttotal
        speedkBps = (delta / sleepseconds) / 1024

        Mbps = (application_bytes_to_networkbits(speedkBps) / 1024)
        if verbose:
            print(f"\nLoop {loop} Total MB {total/(1024*1024):.1f} Delta MB {delta/(1024*1024):.1f} Speed kB/s: {speedkBps:.1f} aka Mbps {Mbps:.1f}", end="", flush=True)
        else:
            print(".", end="", flush=True)

        lasttotal = total
        if speedkBps > highestspeedkBps:
            highestspeedkBps = speedkBps
        time.sleep(sleepseconds)

    print()
    Mbps = (application_bytes_to_networkbits(highestspeedkBps) / 1024)
    return float(f"{Mbps:.1f}")

def fast_com(verbose=True, maxtime=15):
    """
    Executes the full Fast.com speed test suite.

    Handles token retrieval, API URL discovery with protocol fallback,
    and runs both download and upload tests.

    Args:
        verbose (bool): Whether to print detailed logs.
        maxtime (int): Maximum duration for each test phase.

    Returns:
        tuple: (download_speed, upload_speed) in Mbit/s.
    """
    token = get_token()
    if not token:
        print("Could not find token")
        return 0, 0
    if verbose: print(f"Token found: {token}")

    parsedjson = None
    try:
        if verbose: print("Fetching API URLs via IPv4...")
        parsedjson = get_api_urls(token, force_ipv4=True)
    except:
        try:
            if verbose: print("IPv4 failed, trying IPv6...")
            parsedjson = get_api_urls(token, force_ipv6=True)
        except:
            try:
                if verbose: print("IPv6 failed, trying default...")
                parsedjson = get_api_urls(token)
            except:
                print("Could not get API URLs")
                return 0, 0

    if not parsedjson:
        return 0, 0

    urls = [jsonelement['url'] for jsonelement in parsedjson]
    if verbose: print(f"Number of URLs: {len(urls)}")

    download_speed = run_speed_test(urls, mode='download', maxtime=maxtime, verbose=verbose)
    upload_speed = run_speed_test(urls, mode='upload', maxtime=maxtime, verbose=verbose)

    return download_speed, upload_speed

if __name__ == "__main__":
    try:
        print("Starting Speed test against fast.com")
        download, upload = fast_com(verbose=True)

        print(f"\nDownload: {download} Mbit/s")
        print(f"Upload: {upload} Mbit/s")
    except KeyboardInterrupt:
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)
