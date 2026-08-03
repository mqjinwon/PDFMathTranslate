"""OpenAI Codex (ChatGPT OAuth) translator via Responses API."""

from __future__ import annotations

import json
import logging
from pathlib import Path

import requests

from pdf2zh.translator import BaseTranslator

logger = logging.getLogger(__name__)

CODEX_RESPONSES_URL = "https://chatgpt.com/backend-api/codex/responses"


class OpenAICodexTranslator(BaseTranslator):
    """ChatGPT subscription via Codex CLI OAuth (~/.codex/auth.json).

    Uses the Codex Responses API (not api.openai.com Chat Completions).
    """

    name = "openai-codex"
    envs = {
        "OPENAI_CODEX_MODEL": "gpt-5.4",
        "OPENAI_CODEX_AUTH_PATH": "",  # empty → ~/.codex/auth.json
    }
    CustomPrompt = True

    def __init__(
        self,
        lang_in,
        lang_out,
        model,
        envs=None,
        prompt=None,
        ignore_cache=False,
    ):
        self.set_envs(envs)
        if not model:
            model = self.envs.get("OPENAI_CODEX_MODEL") or "gpt-5.4"
        super().__init__(lang_in, lang_out, model, ignore_cache)
        self.prompttext = prompt
        self.add_cache_impact_parameters("prompt", self.prompt("", self.prompttext))
        self.add_cache_impact_parameters("transport", "codex-responses")
        auth_path = (self.envs.get("OPENAI_CODEX_AUTH_PATH") or "").strip()
        self._auth_path = Path(auth_path) if auth_path else None

    def _auth_headers(self) -> dict[str, str]:
        from pdf2zh.auth.codex_oauth import get_codex_access_token

        creds = get_codex_access_token(auth_path=self._auth_path)
        headers = {
            "Authorization": f"Bearer {creds.access_token}",
            "OpenAI-Beta": "responses=experimental",
            "originator": "pdf2zh",
            "User-Agent": "pdf2zh",
            "accept": "text/event-stream",
            "content-type": "application/json",
        }
        if creds.account_id:
            headers["chatgpt-account-id"] = creds.account_id
        return headers

    def do_translate(self, text) -> str:
        messages = self.prompt(text, self.prompttext)
        instructions = (
            "You are a professional machine translation engine. "
            "Output only the translation. Never repeat the source text. "
            "Never add labels or explanations. Keep {v*} placeholders unchanged."
        )
        input_items = []
        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            if role == "system":
                instructions = content
                continue
            input_items.append(
                {
                    "role": role if role in ("user", "assistant") else "user",
                    "content": [{"type": "input_text", "text": content}],
                }
            )
        if not input_items:
            input_items = [
                {
                    "role": "user",
                    "content": [{"type": "input_text", "text": text}],
                }
            ]

        body = {
            "model": self.model,
            "store": False,
            "stream": True,
            "instructions": instructions,
            "input": input_items,
            "text": {"verbosity": "low"},
        }
        headers = self._auth_headers()
        with requests.post(
            CODEX_RESPONSES_URL,
            headers=headers,
            json=body,
            stream=True,
            timeout=120,
        ) as resp:
            if resp.status_code != 200:
                raise ValueError(
                    f"Codex Responses API error {resp.status_code}: "
                    f"{resp.text[:400]}"
                )
            content = self._consume_codex_sse(resp)
        return content.strip()

    @staticmethod
    def _consume_codex_sse(response) -> str:
        collected: list[str] = []
        for raw in response.iter_lines(decode_unicode=True):
            if not raw:
                continue
            line = raw if isinstance(raw, str) else raw.decode("utf-8", "ignore")
            if not line.startswith("data:"):
                continue
            data = line[5:].strip()
            if not data or data == "[DONE]":
                continue
            try:
                event = json.loads(data)
            except json.JSONDecodeError:
                continue
            etype = event.get("type")
            if etype == "response.output_text.delta":
                collected.append(event.get("delta") or "")
            elif etype == "response.output_text.done":
                text = event.get("text")
                if text:
                    return str(text).strip()
            elif etype == "response.failed":
                raise ValueError(f"Codex response failed: {event}")
        return "".join(collected).strip()
