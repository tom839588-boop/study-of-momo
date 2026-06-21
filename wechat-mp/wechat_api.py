"""WeChat Official Account API integration — draft box management."""

import json
import os
import sys
import urllib.request
import urllib.error
from typing import Optional

from config import WECHAT_APP_ID, WECHAT_APP_SECRET

TOKEN_URL = "https://api.weixin.qq.com/cgi-bin/token"
DRAFT_ADD_URL = "https://api.weixin.qq.com/cgi-bin/draft/add"
DRAFT_LIST_URL = "https://api.weixin.qq.com/cgi-bin/draft/batchget"
DRAFT_DELETE_URL = "https://api.weixin.qq.com/cgi-bin/draft/delete"

_DEFAULT_THUMB_PATH = os.path.join(os.path.dirname(__file__), "default_thumb.png")
_THUMB_CACHE_PATH = os.path.join(os.path.dirname(__file__), ".thumb_cache")


def _request(url: str, method: str = "GET", data: Optional[dict] = None) -> dict:
    """Make an HTTP request and return parsed JSON."""
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        req = urllib.request.Request(url, data=body, method=method)
        req.add_header("Content-Type", "application/json; charset=utf-8")
    else:
        req = urllib.request.Request(url, method=method)

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"errcode": e.code, "errmsg": str(e)}
    except Exception as e:
        return {"errcode": -1, "errmsg": str(e)}


def get_access_token() -> Optional[str]:
    """Get WeChat API access token using appid and secret.

    Returns the token string, or None on failure.
    """
    url = f"{TOKEN_URL}?grant_type=client_credential&appid={WECHAT_APP_ID}&secret={WECHAT_APP_SECRET}"
    result = _request(url)

    if "access_token" in result:
        return result["access_token"]

    print(
        f"[ERROR] Failed to get access_token: {result.get('errcode')} {result.get('errmsg')}",
        file=sys.stderr,
    )
    return None


def upload_image(image_path: str) -> Optional[str]:
    """Upload an image as permanent material to WeChat.

    Args:
        image_path: Local path to the image file.

    Returns:
        media_id string, or None on failure.
    """
    token = get_access_token()
    if not token:
        return None

    url = f"https://api.weixin.qq.com/cgi-bin/material/add_material?access_token={token}&type=image"

    boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
    filename = os.path.basename(image_path)

    with open(image_path, "rb") as f:
        file_data = f.read()

    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="media"; filename="{filename}"\r\n'
        f"Content-Type: image/png\r\n\r\n"
    ).encode("utf-8") + file_data + f"\r\n--{boundary}--\r\n".encode("utf-8")

    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", f"multipart/form-data; boundary={boundary}")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read().decode("utf-8"))
        if "media_id" in result:
            print(f"[OK] Image uploaded! media_id: {result['media_id']}")
            return result["media_id"]
        else:
            print(
                f"[ERROR] Failed to upload image: {result.get('errcode')} {result.get('errmsg')}",
                file=sys.stderr,
            )
            return None
    except Exception as e:
        print(f"[ERROR] Upload image exception: {e}", file=sys.stderr)
        return None


def _get_or_create_thumb() -> Optional[str]:
    """Get cached thumbnail media_id, or create and cache a default one."""
    # Check cache
    if os.path.exists(_THUMB_CACHE_PATH):
        with open(_THUMB_CACHE_PATH) as f:
            cached = f.read().strip()
            if cached:
                return cached

    # Create default thumbnail if it doesn't exist
    if not os.path.exists(_DEFAULT_THUMB_PATH):
        _create_default_thumb()

    # Upload
    thumb_id = upload_image(_DEFAULT_THUMB_PATH)
    if thumb_id:
        with open(_THUMB_CACHE_PATH, "w") as f:
            f.write(thumb_id)
    return thumb_id


def _create_default_thumb():
    """Create a minimal solid-gray 300x300 PNG as default thumbnail."""
    import struct, zlib

    def chunk(chunk_type, data):
        c = chunk_type + data
        crc = struct.pack(">I", zlib.crc32(c) & 0xFFFFFFFF)
        return struct.pack(">I", len(data)) + c + crc

    sig = b"\x89PNG\r\n\x1a\n"
    ihdr = chunk(b"IHDR", struct.pack(">IIBBBBB", 300, 300, 8, 2, 0, 0, 0))
    raw = b"\x00" + b"\x50\x50\x50" * 300  # filter byte + one row of gray pixels
    raw = raw * 300  # 300 rows
    idat = chunk(b"IDAT", zlib.compress(raw))
    iend = chunk(b"IEND", b"")

    with open(_DEFAULT_THUMB_PATH, "wb") as f:
        f.write(sig + ihdr + idat + iend)


def create_draft(
    title: str,
    content: str,
    author: str = "",
    thumb_media_id: Optional[str] = None,
) -> dict:
    """Create a new draft in the WeChat Official Account draft box.

    Args:
        title: Article title.
        content: HTML content for the article body.
        author: Optional author name.
        thumb_media_id: Optional thumbnail media_id. Auto-fetched if not provided.

    Returns:
        Response dict from the WeChat API.
    """
    token = get_access_token()
    if not token:
        return {"errcode": -1, "errmsg": "Failed to get access token"}

    # Auto-handle thumbnail
    if not thumb_media_id:
        thumb_media_id = _get_or_create_thumb()

    url = f"{DRAFT_ADD_URL}?access_token={token}"

    article = {
        "title": title,
        "author": author or "职场漫谈",
        "content": content,
        "need_open_comment": 1,
        "only_fans_can_comment": 0,
    }
    if thumb_media_id:
        article["thumb_media_id"] = thumb_media_id

    body = {"articles": [article]}

    result = _request(url, method="POST", data=body)

    if "media_id" in result:
        print(f"[OK] Draft created successfully! media_id: {result['media_id']}")
    else:
        print(
            f"[ERROR] Failed to create draft: {result.get('errcode')} {result.get('errmsg')}",
            file=sys.stderr,
        )

    return result


def list_drafts(offset: int = 0, count: int = 10) -> dict:
    """List drafts in the WeChat draft box.

    Args:
        offset: Start offset for pagination.
        count: Number of drafts to return (max 20).

    Returns:
        Response dict from the WeChat API.
    """
    token = get_access_token()
    if not token:
        return {"errcode": -1, "errmsg": "Failed to get access token"}

    url = f"{DRAFT_LIST_URL}?access_token={token}"
    body = {"offset": offset, "count": count, "no_content": 1}
    result = _request(url, method="POST", data=body)

    return result


if __name__ == "__main__":
    """CLI entry point: python wechat_api.py <title> <content_file> [author]"""
    if len(sys.argv) < 3:
        print("Usage: python wechat_api.py <title> <content_file> [author]")
        print("  Reads HTML content from content_file, '-'' means stdin")
        sys.exit(1)

    title = sys.argv[1]
    content_path = sys.argv[2]
    author = sys.argv[3] if len(sys.argv) > 3 else ""

    if content_path == "-":
        content = sys.stdin.read()
    else:
        with open(content_path, "r", encoding="utf-8") as f:
            content = f.read()

    result = create_draft(title, content, author)
    if result.get("errcode"):
        sys.exit(1)
