from __future__ import annotations

import base64
import hashlib
import json
import re
from html import unescape
from typing import Any
from urllib.parse import unquote

from bs4 import BeautifulSoup

from .exceptions import DuckDuckGoSearchException

try:
    HAS_ORJSON = True
    import orjson
except ImportError:
    HAS_ORJSON = False
    import json

REGEX_STRIP_TAGS = re.compile("<.*?>")


def json_dumps(obj: Any) -> str:
    try:
        return (
            orjson.dumps(obj, option=orjson.OPT_INDENT_2).decode()
            if HAS_ORJSON
            else json.dumps(obj, ensure_ascii=False, indent=2)
        )
    except Exception as ex:
        raise DuckDuckGoSearchException(f"{type(ex).__name__}: {ex}") from ex


def json_loads(obj: str | bytes) -> Any:
    try:
        return orjson.loads(obj) if HAS_ORJSON else json.loads(obj)
    except Exception as ex:
        raise DuckDuckGoSearchException(f"{type(ex).__name__}: {ex}") from ex


def _extract_vqd(html_bytes: bytes, keywords: str) -> str:
    """Extract vqd from html bytes."""
    for c1, c1_len, c2 in (
        (b'vqd="', 5, b'"'),
        (b"vqd=", 4, b"&"),
        (b"vqd='", 5, b"'"),
    ):
        try:
            start = html_bytes.index(c1) + c1_len
            end = html_bytes.index(c2, start)
            return html_bytes[start:end].decode()
        except ValueError:
            pass
    raise DuckDuckGoSearchException(f"_extract_vqd() {keywords=} Could not extract vqd.")


def _normalize(raw_html: str) -> str:
    """Strip HTML tags from the raw_html string."""
    return unescape(REGEX_STRIP_TAGS.sub("", raw_html)) if raw_html else ""


def _normalize_url(url: str) -> str:
    """Unquote URL and replace spaces with '+'."""
    return unquote(url).replace(" ", "+") if url else ""


def _expand_proxy_tb_alias(proxy: str | None) -> str | None:
    """Expand "tb" to a full proxy URL if applicable."""
    return "socks5://127.0.0.1:9150" if proxy == "tb" else proxy


# chat utils


def sha256_base64(text: str) -> str:
    """Return the base64 encoding of the SHA256 digest of the text."""
    sha256_hash = hashlib.sha256(text.encode("utf-8")).digest()
    return base64.b64encode(sha256_hash).decode()


def parse_dom_fingerprint(js_text: str) -> str:
    html_snippet = js_text.split("e.innerHTML = '")[1].split("';")[0]
    offset_value = js_text.split("return String(")[1].split(" ")[0]
    soup = BeautifulSoup(html_snippet, "html5lib")
    corrected_inner_html = soup.body.decode_contents()  # type: ignore
    inner_html_length = len(corrected_inner_html)
    fingerprint = int(offset_value) + inner_html_length
    return str(fingerprint)


def parse_server_hashes(js_text: str) -> list[Any]:
    return js_text.split('server_hashes: ["', maxsplit=1)[1].split('"]', maxsplit=1)[0].split('","')


def build_x_vqd_hash_1(vqd_hash_1: str, headers: dict[str, str]) -> str:
    decoded = base64.b64decode(vqd_hash_1).decode()
    server_hashes = parse_server_hashes(decoded)
    dom_fingerprint = parse_dom_fingerprint(decoded)

    ua_fingerprint = headers.get("user-agent", "") + headers.get("sec-ch-ua", "")
    ua_hash = sha256_base64(ua_fingerprint)
    dom_hash = sha256_base64(dom_fingerprint)

    final_result = {
        "server_hashes": server_hashes,
        "client_hashes": [ua_hash, dom_hash],
        "signals": {},
    }
    base64_final_result = base64.b64encode(json.dumps(final_result).encode()).decode()
    return base64_final_result
