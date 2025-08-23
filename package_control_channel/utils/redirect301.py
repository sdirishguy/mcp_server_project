#!/usr/bin/env python3
# Python 3.4+

import datetime
import json
import logging
import sys
from pathlib import Path
from time import sleep

import requests

base_dir = Path(__file__).parent.parent
log_path = base_dir / f"redirect301_{datetime.datetime.now():%Y-%M-%d_%H-%m-%S}.log"

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

formatter = logging.Formatter("%(message)s")
stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setLevel(level=logging.DEBUG)
stream_handler.setFormatter(formatter)
logger.addHandler(stream_handler)

file_handler = logging.FileHandler(log_path)
file_handler.setLevel(level=logging.INFO)
file_handler.setFormatter(formatter)
logger.addHandler(file_handler)

for path in sorted(Path(base_dir, "repository").glob("*.json")):
    if path.name == "dependencies.json":
        continue
    logger.debug(f"Processing '{path!s}'")

    with path.open("r", encoding="utf-8") as f:
        packages_text = f.read()
        packages = json.loads(packages_text)["packages"]

    for package in packages:
        link = package["details"]
        try:
            r = requests.head(link, allow_redirects=False)
            if r.status_code == 301:
                new_link = requests.head(link, allow_redirects=True).url
                if link == new_link:
                    logger.warning(f"Redirected to same URL: {link}")
                else:
                    logger.info(f'Found 301: "{link}" -> "{new_link}"')
                    packages_text = packages_text.replace(link, new_link)
            else:
                logger.debug(f'No change for "{link}"')

        except Exception:
            logger.exception(f"Exception on {link!r}")

        sleep(0.1)

    with path.open("w", encoding="utf-8") as f:
        f.write(packages_text)
