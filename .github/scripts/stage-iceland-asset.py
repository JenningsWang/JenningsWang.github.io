"""Locally stage the expiring read link for a single verified GitHub release asset."""

import argparse
import http.client
import json
import re
import subprocess
import urllib.parse

REPOSITORY = "JenningsWang/JenningsWang.github.io"
SECRET = "ICELAND_PAGES_DOWNLOAD_URL"


def gh(*args):
    return subprocess.check_output(["gh", *args], text=True).strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("release_id", type=int)
    parser.add_argument("sha256")
    args = parser.parse_args()
    if not re.fullmatch("[0-9a-f]{64}", args.sha256):
        parser.error("Expected the lowercase SHA-256 of the release ZIP")
    release = json.loads(gh("api", f"repos/{REPOSITORY}/releases/{args.release_id}"))
    if not release["draft"] or not release["tag_name"].startswith("iceland-pages-"):
        raise SystemExit("Expected an unpublished Iceland Pages release")
    assets = [a for a in release["assets"] if a["name"] == "iceland-pages.zip"]
    if len(assets) != 1 or assets[0]["digest"] != "sha256:" + args.sha256:
        raise SystemExit("The release asset does not match the verified digest")

    # Request only the redirect. The account credential never follows the redirect.
    api = http.client.HTTPSConnection("api.github.com", timeout=30)
    try:
        api.request("GET", f"/repos/{REPOSITORY}/releases/assets/{assets[0]['id']}",
                    headers={"User-Agent": "iceland-pages-publisher",
                             "Accept": "application/octet-stream",
                             "Authorization": "Bearer " + gh("auth", "token", "--hostname", "github.com")})
        response = api.getresponse()
        url = response.getheader("Location", "")
        target = urllib.parse.urlsplit(url)
        if (response.status != 302 or target.scheme != "https" or
                target.netloc != "release-assets.githubusercontent.com" or
                not target.path.startswith("/github-production-release-asset/")):
            raise SystemExit(f"GitHub did not issue the expected asset link (HTTP {response.status})")
    finally:
        api.close()

    # Only the single-asset read URL is passed to Actions, by stdin.
    subprocess.run(["gh", "secret", "set", SECRET, "--repo", REPOSITORY],
                   input=url, text=True, check=True)
    print("Staged the expiring read link for the verified archive.")


if __name__ == "__main__":
    main()
