"""Puts the Gradle distributions that the workspace's wrappers name into the Gradle user home.

Usage: gradle-wrappers.py <workspace> <gradle user home>

The wrapper downloads its distribution before Gradle starts, so the init script cannot send that
download through the cache. This fetches each services.gradle.org distribution named by a
gradle/wrapper/gradle-wrapper.properties through the cache's /gradle-dist route and stores it where
the wrapper looks for it: <home>/wrapper/dists/<name>/<hash of distributionUrl>/<file>. The wrapper
then finds the zip, checks distributionSha256Sum, unpacks it and never goes to services.gradle.org.
The checkout is not changed and the token never goes to disk. Environment: PACKAGE_CACHE_URL,
PACKAGE_CACHE_TOKEN.
"""

import hashlib
import os
import sys
import time
import urllib.error
import urllib.request

UPSTREAM = 'https://services.gradle.org/distributions/'
SKIP_DIRS = {'.git', 'node_modules', 'build', '.gradle', 'target'}
# Waits before each retry of a 5xx, 429 or network failure, as the token requests do.
RETRY_WAITS = [1, 2, 4, 8, 16, 32]


def properties(path):
    """Reads a Java properties file of simple key=value lines (as Gradle writes them)."""
    values = {}
    with open(path, encoding='iso-8859-1') as file:
        for line in file:
            line = line.strip()
            if not line or line[0] in '#!' or '=' not in line:
                continue
            key, value = line.split('=', 1)
            values[key.strip()] = value.strip().replace('\\:', ':').replace('\\=', '=')
    return values


def wrapper_hash(url):
    """The wrapper's directory name for a distribution URL: base 36 of the URL's MD5."""
    number = int.from_bytes(hashlib.md5(url.encode('utf-8')).digest(), 'big')
    digits = '0123456789abcdefghijklmnopqrstuvwxyz'
    text = ''
    while number:
        number, digit = divmod(number, 36)
        text = digits[digit] + text
    return text or '0'


def download(url, token, target):
    request = urllib.request.Request(url, headers={'Authorization': f'Bearer {token}'})
    for attempt, wait in enumerate(RETRY_WAITS + [None]):
        try:
            with urllib.request.urlopen(request, timeout=60) as response, open(target, 'wb') as out:
                while chunk := response.read(1 << 20):
                    out.write(chunk)
            return
        except urllib.error.HTTPError as error:
            transient = error.code in (408, 429) or error.code >= 500
            failure = f'{error.code} {error.reason}'
        except (urllib.error.URLError, TimeoutError, ConnectionError) as error:
            transient = True
            failure = str(error)
        if not transient or wait is None:
            sys.exit(f'package-cache: {url} failed: {failure}')
        print(f'::warning::package-cache: {url} failed ({failure}); retrying in {wait} s', flush=True)
        time.sleep(wait)


def main(workspace, home):
    cache = os.environ['PACKAGE_CACHE_URL']
    token = os.environ['PACKAGE_CACHE_TOKEN']
    urls = {}
    for root, dirs, files in os.walk(workspace):
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
        if 'gradle-wrapper.properties' in files and root.endswith(os.path.join('gradle', 'wrapper')):
            path = os.path.join(root, 'gradle-wrapper.properties')
            values = properties(path)
            url = values.get('distributionUrl', '')
            if not url.startswith(UPSTREAM):
                print(f'package-cache: {path}: {url or "no distributionUrl"} is not a services.gradle.org distribution; left alone')
                continue
            for key in ('distributionBase', 'zipStoreBase'):
                if values.get(key, 'GRADLE_USER_HOME') != 'GRADLE_USER_HOME':
                    sys.exit(f'package-cache: {path}: {key}={values[key]} is not supported')
            if values.get('zipStorePath', 'wrapper/dists') != 'wrapper/dists':
                sys.exit(f'package-cache: {path}: zipStorePath={values["zipStorePath"]} is not supported')
            urls.setdefault(url, path)
    for url, path in sorted(urls.items()):
        file = url[len(UPSTREAM):]
        name = file[:-len('.zip')] if file.endswith('.zip') else file
        directory = os.path.join(home, 'wrapper', 'dists', name, wrapper_hash(url))
        zip_path = os.path.join(directory, file)
        if os.path.isfile(zip_path + '.ok') or os.path.isfile(zip_path):
            print(f'package-cache: {file} is already in {directory}')
            continue
        os.makedirs(directory, exist_ok=True)
        part = zip_path + '.package-cache.part'
        download(f'{cache}/gradle-dist/{file}', token, part)
        os.replace(part, zip_path)
        print(f'package-cache: {file} (for {path}) stored in {directory}')


if __name__ == '__main__':
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
