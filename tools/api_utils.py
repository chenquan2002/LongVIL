import json
import os
from typing import Any, Dict, Optional

import requests


DEFAULT_API_BASE_URL = "https://your_baseurl/v1/chat/completions"


def get_api_base_url(args: Optional[Any] = None) -> str:
    if args is not None and getattr(args, "base_url", None):
        return args.base_url
    return os.getenv("LONGVIL_API_BASE_URL", DEFAULT_API_BASE_URL)


def build_headers(api_key: str) -> Dict[str, str]:
    if not api_key:
        raise ValueError("API key is not set. Pass --api_key or set LONGVIL_API_KEY.")
    authorization = api_key if api_key.lower().startswith("bearer ") else f"Bearer {api_key}"
    return {
        "Authorization": authorization,
        "Content-Type": "application/json",
    }


def request_chat_completion(base_url: str, headers: Dict[str, str], payload: Dict[str, Any]) -> Dict[str, Any]:
    response = requests.post(base_url, headers=headers, json=payload, timeout=120)
    response.raise_for_status()
    return response.json()


def log_token_usage(key: str, response_data: Dict[str, Any]) -> None:
    usage = response_data.get("usage") or {}
    total = usage.get("total_tokens")
    if total is None:
        total = (usage.get("prompt_tokens", 0) or 0) + (usage.get("completion_tokens", 0) or 0)

    token_path = os.getenv("TOKEN_PATH", "token_usage.jsonl")
    with open(token_path, "a", encoding="utf-8") as f:
        f.write(json.dumps({"key": key, "tokens": int(total or 0)}, ensure_ascii=False) + "\n")
