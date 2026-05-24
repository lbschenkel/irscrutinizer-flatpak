#!/usr/bin/env python3
import hashlib
import html
import json
import os
import re
import sys
import urllib.request

RELEASES_API_URL = "https://api.github.com/repos/bengtmartensson/IrScrutinizer/releases"
MANIFEST = "org.harctoolbox.irscrutinizer.yml"
METAINFO = "org.harctoolbox.irscrutinizer.metainfo.xml"
ASSET_RE = re.compile(r"IrScrutinizer-.*-bin\.zip$")
URL_PATTERN = r"https://github\.com/bengtmartensson/IrScrutinizer/releases/download/[^\s\"]+/IrScrutinizer-[^\s\"]+-bin\.zip"


def fetch_releases():
    req = urllib.request.Request(
        RELEASES_API_URL,
        headers={"User-Agent": "flatpak-sync-script"},
    )
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read().decode("utf-8"))


def normalize_version(tag_name):
    if tag_name.startswith("Version-"):
        return tag_name[len("Version-") :]
    return tag_name


BOILERPLATE_PATTERNS = (
    "Windows",
    "Mac",
    "AppImage",
    "generic binary",
    "checksums",
)


def contains_boilerplate(text):
    lower_text = text.lower()
    return any(pattern.lower() in lower_text for pattern in BOILERPLATE_PATTERNS)


def extract_bullets(body):
    if not body:
        return [("p", "No release notes provided.")]

    body = body.replace("\r\n", "\n").replace("\r", "\n")
    blocks = []
    paragraph_lines = []
    list_kind = None
    list_items = []
    current_item_lines = []

    def flush_paragraph():
        nonlocal paragraph_lines
        if paragraph_lines:
            blocks.append(("p", paragraph_lines[:]))
            paragraph_lines = []

    def flush_list_item():
        nonlocal current_item_lines, list_items
        if current_item_lines:
            list_items.append(" ".join(current_item_lines).strip())
            current_item_lines = []

    def flush_list():
        nonlocal list_kind, list_items
        flush_list_item()
        if list_kind and list_items:
            blocks.append((list_kind, list_items))
        list_kind = None
        list_items = []

    for line in body.splitlines():
        stripped = line.strip()
        bullet_match = re.match(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$", line)

        if not stripped:
            flush_paragraph()
            flush_list_item()
            continue

        if bullet_match:
            flush_paragraph()
            marker = bullet_match.group(2)
            item_text = bullet_match.group(3).strip()
            if list_kind is None:
                list_kind = "ol" if re.match(r"^\d+[.)]$", marker) else "ul"
            flush_list_item()
            current_item_lines = [item_text]
            continue

        if current_item_lines:
            current_item_lines.append(stripped)
            continue

        if list_kind is not None:
            flush_list()

        paragraph_lines.append(stripped)

    flush_paragraph()
    flush_list()

    if not blocks:
        return [("p", "No release notes provided.")]

    filtered_blocks = []
    for kind, value in blocks:
        if kind == "p":
            kept_lines = [line for line in value if not contains_boilerplate(line)]
            if kept_lines:
                filtered_blocks.append(("p", " ".join(kept_lines).strip()))
        elif kind in ("ul", "ol"):
            kept_items = [item for item in value if not contains_boilerplate(item)]
            if kept_items:
                filtered_blocks.append((kind, kept_items))
        else:
            filtered_blocks.append((kind, value))

    return filtered_blocks


def pick_bin_asset(release):
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if ASSET_RE.search(name):
            return asset
    return None


def official_releases_with_bin(releases):
    out = []
    for rel in releases:
        if rel.get("draft") or rel.get("prerelease"):
            continue
        asset = pick_bin_asset(rel)
        if asset is None:
            continue
        out.append((rel, asset))
    if not out:
        raise RuntimeError("No suitable non-prerelease release with -bin.zip asset found")
    return out


def select_target_release(releases_with_assets, requested_version):
    if requested_version is None:
        return releases_with_assets[0]

    requested = requested_version.strip()
    for rel, asset in releases_with_assets:
        tag = rel["tag_name"]
        ver = normalize_version(tag)
        if requested in (tag, ver):
            return rel, asset

    raise RuntimeError(
        f"Release '{requested_version}' not found among official releases with -bin.zip asset"
    )


def releases_up_to_target(releases_with_assets, target_release):
    tags = [rel["tag_name"] for rel, _ in releases_with_assets]
    if target_release["tag_name"] not in tags:
        raise RuntimeError("Selected release not present in release list")
    target_i = tags.index(target_release["tag_name"])
    return releases_with_assets[target_i:]


def sha256_of_url(url):
    import shutil
    import tempfile

    cache_dir = os.path.join(".flatpak-builder", "downloads")
    os.makedirs(cache_dir, exist_ok=True)
    source_name = os.path.basename(url.rstrip("/")) or "download"

    print(f"Downloading {url} ...")
    with urllib.request.urlopen(url) as r, tempfile.NamedTemporaryFile(
        dir=cache_dir, delete=False
    ) as tmp:
        h = hashlib.sha256()
        while True:
            chunk = r.read(65536)
            if not chunk:
                break
            h.update(chunk)
            tmp.write(chunk)
        tmp_path = tmp.name

    digest = h.hexdigest()
    cache_path = os.path.join(cache_dir, digest)
    if not os.path.exists(cache_path):
        os.makedirs(cache_path, exist_ok=True)
        cached_file = os.path.join(cache_path, source_name)
        shutil.move(tmp_path, cached_file)
        print(f"Cached to {cached_file}")
    else:
        os.unlink(tmp_path)
        print(f"Already cached at {cache_path}")

    return digest


def update_manifest(download_url, sha256):
    with open(MANIFEST, encoding="utf-8") as f:
        old_content = f.read()

    def replace_url(match):
        return f"{match.group(1)}{download_url}"

    def replace_sha(match):
        return f"{match.group(1)}{sha256}"

    content, url_count = re.subn(
        rf"(url:\s*){URL_PATTERN}",
        replace_url,
        old_content,
    )
    content, sha_count = re.subn(
        r"(sha256:\s*)[0-9a-f]{64}",
        replace_sha,
        content,
        count=1,
    )

    if url_count == 0:
        raise RuntimeError("Could not find IrScrutinizer bin.zip url in manifest")
    if sha_count == 0:
        raise RuntimeError("Could not find sha256 in manifest")

    if content == old_content:
        print(f"No changes needed in {MANIFEST}")
        return

    with open(MANIFEST, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Updated {MANIFEST}: {download_url}, sha256 {sha256}")


def release_block(version, date, blocks, url):
    description_lines = []
    for kind, value in blocks:
        if kind == "p":
            description_lines.append(f"        <p>{html.escape(value, quote=False)}</p>")
        elif kind in ("ul", "ol"):
            li_lines = "\n".join(
                f"          <li>{html.escape(item, quote=False)}</li>" for item in value
            )
            description_lines.append(f"        <{kind}>")
            description_lines.append(li_lines)
            description_lines.append(f"        </{kind}>")
        else:
            raise RuntimeError(f"Unknown release body block type: {kind}")

    description = "\n".join(description_lines)
    return (
        f"    <release version=\"{version}\" date=\"{date}\">\n"
        f"      <description>\n"
        f"{description}\n"
        f"      </description>\n"
        f"      <url>{html.escape(url, quote=False)}</url>\n"
        f"    </release>"
    )


def update_metainfo(releases_with_assets):
    releases = []
    for rel, _asset in releases_with_assets:
        tag = rel["tag_name"]
        version = normalize_version(tag)
        published = rel.get("published_at", "")
        date = (published[:10] if published else "1970-01-01")
        blocks = extract_bullets(rel.get("body", ""))
        url = rel.get("html_url", "https://github.com/bengtmartensson/IrScrutinizer/releases")
        releases.append(
            {
                "tag": tag,
                "version": version,
                "date": date,
                "blocks": blocks,
                "url": url,
            }
        )

    with open(METAINFO, encoding="utf-8") as f:
        content = f.read()

    if re.search(r"<releases>\s*</releases>", content, flags=re.DOTALL):
        content = re.sub(
            r"<releases>\s*</releases>",
            "<releases>\n  </releases>",
            content,
            count=1,
        )
    if "<releases>" not in content or "</releases>" not in content:
        content = content.replace("</component>", "  <releases>\n  </releases>\n</component>", 1)

    for r in releases:
        version = re.escape(r["version"])
        content = re.sub(
            rf"\n\s*<release\s+version=\"{version}\"[\s\S]*?</release>",
            "",
            content,
            count=1,
        )

    for r in reversed(releases):
        block = release_block(r["version"], r["date"], r["blocks"], r["url"])
        content = content.replace("  <releases>\n", f"  <releases>\n{block}\n", 1)

    with open(METAINFO, "w", encoding="utf-8") as f:
        f.write(content)

    print(f"Updated {METAINFO}: latest release {releases[0]['version']}")


def main():
    all_releases = fetch_releases()
    candidates = official_releases_with_bin(all_releases)

    requested_version = sys.argv[1] if len(sys.argv) > 1 else None
    target_release, target_asset = select_target_release(candidates, requested_version)

    target_download_url = target_asset["browser_download_url"]
    target_sha256 = sha256_of_url(target_download_url)
    update_manifest(target_download_url, target_sha256)

    selected_releases = releases_up_to_target(candidates, target_release)
    update_metainfo(selected_releases)


if __name__ == "__main__":
    main()
