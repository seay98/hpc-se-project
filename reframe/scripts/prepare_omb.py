#!/usr/bin/env python3
"""Verify/cache the official OMB 7.5 source archive and extract it safely.

The cache is shared across ReFrame runs; the extracted build tree is per-run.
Requires Python 3.8+ and a POSIX filesystem (fcntl.lockf/flock).
"""

import argparse
import fcntl
import hashlib
import os
from pathlib import Path
import shutil
import sys
import tarfile
import tempfile
from urllib.request import urlopen

VERSION = '7.5'
ARCHIVE = f'osu-micro-benchmarks-{VERSION}.tar.gz'
SOURCE_DIR = f'osu-micro-benchmarks-{VERSION}'
URL = f'https://mvapich.cse.ohio-state.edu/download/mvapich/{ARCHIVE}'
SHA256 = '1cf84ac5419456202757a757c5f9a4f5c6ecd05c65783c7976421cfd6020b3b3'


def verified(path):
    if not path.is_file():
        return False
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest() == SHA256


def download_verified(cache, url):
    cache.parent.mkdir(parents=True, exist_ok=True)
    # Persistent lock file prevents concurrent ReFrame builds from racing.
    with (cache.parent / (cache.name + '.lock')).open('a+b') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if verified(cache):
            print(f'[OMB source] Verified cached archive: {cache}', flush=True)
            return
        if cache.exists():
            print(f'[OMB source] Invalid checksum; replacing {cache}', flush=True)
        else:
            print(f'[OMB source] Cache missing: {cache}', flush=True)

        fd, tmpname = tempfile.mkstemp(prefix='.omb-7.5-', suffix='.tar.gz', dir=cache.parent)
        os.close(fd)
        tmp = Path(tmpname)
        try:
            print(f'[OMB source] Downloading: {url}', flush=True)
            with urlopen(url, timeout=60) as response, tmp.open('wb') as target:
                shutil.copyfileobj(response, target)
            if not verified(tmp):
                raise RuntimeError('Downloaded archive SHA-256 does not match OMB 7.5')
            os.replace(tmp, cache)
            print('[OMB source] Downloaded and SHA-256 verified', flush=True)
        finally:
            tmp.unlink(missing_ok=True)


def extract_verified(cache, destination):
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / SOURCE_DIR
    if target.exists():
        raise RuntimeError(f'Extraction destination already exists: {target}')

    with tarfile.open(cache, 'r:gz') as archive:
        members = archive.getmembers()
        for member in members:
            # Only files/directories are expected in this source release.
            name = Path(member.name)
            if (name.is_absolute() or '..' in name.parts or
                    not member.name.startswith(SOURCE_DIR + '/') and
                    member.name.rstrip('/') != SOURCE_DIR or
                    not (member.isfile() or member.isdir())):
                raise RuntimeError(f'Unexpected archive entry: {member.name}')
        archive.extractall(destination, members=members)

    if not (target / 'configure').is_file():
        raise RuntimeError('Verified archive has no configure script')
    print(f'[OMB source] Extracted source into {target}', flush=True)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--cache', type=Path, required=True, help='Path to local tar.gz cache')
    p.add_argument('--dest', type=Path, required=True, help='ReFrame staging directory')
    p.add_argument('--url', default=URL, help='Fallback download URL (SHA-256 is always enforced)')
    args = p.parse_args()
    try:
        download_verified(args.cache.expanduser().resolve(), args.url)
        extract_verified(args.cache.expanduser().resolve(), args.dest.resolve())
    except Exception as exc:
        print(f'[OMB source] ERROR: {exc}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main())
