"""Single registry for translator backends (name → class → instance)."""

from __future__ import annotations

from typing import Any, Optional, Type

from pdf2zh.openai_codex import OpenAICodexTranslator
from pdf2zh.translator import (
    AnythingLLMTranslator,
    ArgosTranslator,
    AzureOpenAITranslator,
    AzureTranslator,
    BaseTranslator,
    BingTranslator,
    DeepLTranslator,
    DeepLXTranslator,
    DeepseekTranslator,
    DifyTranslator,
    GeminiTranslator,
    GoogleTranslator,
    GrokTranslator,
    GroqTranslator,
    MiniMaxTranslator,
    ModelScopeTranslator,
    OllamaTranslator,
    OpenAIlikedTranslator,
    OpenAITranslator,
    QwenMtTranslator,
    SiliconTranslator,
    TencentTranslator,
    X302AITranslator,
    XinferenceTranslator,
    ZhipuTranslator,
)

# Canonical construction order / lookup table — only place that lists backends.
TRANSLATOR_CLASSES: list[Type[BaseTranslator]] = [
    GoogleTranslator,
    BingTranslator,
    DeepLTranslator,
    DeepLXTranslator,
    OllamaTranslator,
    XinferenceTranslator,
    AzureOpenAITranslator,
    OpenAITranslator,
    OpenAICodexTranslator,
    ZhipuTranslator,
    ModelScopeTranslator,
    SiliconTranslator,
    GeminiTranslator,
    AzureTranslator,
    TencentTranslator,
    DifyTranslator,
    AnythingLLMTranslator,
    ArgosTranslator,
    GrokTranslator,
    GroqTranslator,
    DeepseekTranslator,
    MiniMaxTranslator,
    OpenAIlikedTranslator,
    QwenMtTranslator,
    X302AITranslator,
]

TRANSLATORS: dict[str, Type[BaseTranslator]] = {
    cls.name: cls for cls in TRANSLATOR_CLASSES
}

# GUI / human-readable labels (optional; falls back to class name).
DISPLAY_NAMES: dict[str, str] = {
    "grok": "Grok",
    "openai-codex": "OpenAI Codex (OAuth)",
    "openai": "OpenAI",
    "google": "Google",
    "bing": "Bing",
    "deepl": "DeepL",
    "deeplx": "DeepLX",
    "ollama": "Ollama",
    "xinference": "Xinference",
    "azure-openai": "AzureOpenAI",
    "zhipu": "Zhipu",
    "modelscope": "ModelScope",
    "silicon": "Silicon",
    "gemini": "Gemini",
    "azure": "Azure",
    "tencent": "Tencent",
    "dify": "Dify",
    "anythingllm": "AnythingLLM",
    "argos": "Argos Translate",
    "groq": "Groq",
    "deepseek": "DeepSeek",
    "minimax": "MiniMax",
    "openailiked": "OpenAI-liked",
    "qwen-mt": "Ali Qwen-Translation",
    "302ai": "302.AI",
}


def get_translator_class(name: str) -> Type[BaseTranslator]:
    key = (name or "").strip().lower()
    cls = TRANSLATORS.get(key)
    if cls is None:
        available = ", ".join(sorted(TRANSLATORS))
        raise ValueError(
            f"Unsupported translation service: {name!r}. Available: {available}"
        )
    return cls


def build_translator(
    service: str,
    lang_in: str,
    lang_out: str,
    model: Optional[str] = None,
    *,
    envs: Optional[dict[str, Any]] = None,
    prompt: Any = None,
    ignore_cache: bool = False,
) -> BaseTranslator:
    """Construct a translator by service name (after auto-resolution if needed)."""
    from pdf2zh.service_chain import parse_service_spec, resolve_service

    # Accept either concrete names or auto / name:model specs.
    resolved = resolve_service(service, envs=envs)
    cls = get_translator_class(resolved.name)
    merged_envs = {**(envs or {}), **resolved.envs}
    return cls(
        lang_in,
        lang_out,
        resolved.model if resolved.model is not None else model,
        envs=merged_envs,
        prompt=prompt,
        ignore_cache=ignore_cache,
    )


def gui_service_map() -> dict[str, Type[BaseTranslator]]:
    """Label → class map for Gradio (stable preferred order first)."""
    preferred = [
        "grok",
        "openai-codex",
        "openai",
        "google",
        "bing",
    ]
    out: dict[str, Type[BaseTranslator]] = {}
    seen: set[str] = set()
    for name in preferred + [c.name for c in TRANSLATOR_CLASSES]:
        if name in seen or name not in TRANSLATORS:
            continue
        seen.add(name)
        label = DISPLAY_NAMES.get(name, name)
        out[label] = TRANSLATORS[name]
    return out
