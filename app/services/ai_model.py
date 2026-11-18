"""One place to pick the Claude model every feature uses, and to shape each request for it.

    FAMILYHUB_AI_MODEL   default claude-opus-5-5 (the current Opus: sharpest of the everyday models)
                         claude-sonnet-5-5  about half the price, nearly as good
                         claude-haiku-5-5   about 40x cheaper; great for voice trivia, quick-add and
                                            email parsing; a little weaker on tricky homework help
    FAMILYHUB_VOICE_MODEL  optional: a different model just for spoken requests on the wall
                           (services/voice_agent.voice_model). Unset = same as FAMILYHUB_AI_MODEL.
    FAMILYHUB_PACKAGE_MODEL  the porch package check (services/porch.py), default claude-haiku-5-5.
Change it in .env, restart familyhub, done.

Why the helpers below exist (Nov 2026 move from claude-opus-4-8):
- The current models always think before they answer, and that thinking counts against max_tokens. A small cap
  (the old 120 / 400 / 1024) can be used up before any answer is written, so callers ask for plenty of room and
  set how hard to think with `effort` instead.
- If a safety filter declines a request, `create()` lets the API hand it to another model in the same call
  (server-side fallback) on the models that offer it.
"""
import os
import re

DEFAULT = "claude-opus-5-5"

_EFFORT_OK = re.compile(r"opus-4-[5678]|opus-5|sonnet-4-6|sonnet-5|haiku-5|fable|mythos")
_NEW_SEARCH = re.compile(r"opus-4-[678]|opus-5|sonnet-4-6|sonnet-5|fable|mythos")
_FALLBACK_OK = re.compile(r"fable-5-[12]|opus-5|sonnet-5-5")


def model() -> str:
    return (os.environ.get("FAMILYHUB_AI_MODEL") or DEFAULT).strip() or DEFAULT


def effort(mdl: str, level: str = "low") -> dict:
    """{'output_config': {'effort': level}} for models that take it, else {} (spread into the request)."""
    return {"output_config": {"effort": level}} if _EFFORT_OK.search(mdl or "") else {}


def web_search_tool(mdl: str, **opts) -> dict:
    """The web search tool this model supports (the newer one filters results itself; small models keep the basic one)."""
    return {"type": "web_search_20260209" if _NEW_SEARCH.search(mdl or "") else "web_search_20250305", "name": "web_search", **opts}


def create(client, **kw):
    """client.messages.create, plus server-side fallback where the model offers it. Falls back to the plain call if
    this SDK or account doesn't take the fallback option."""
    if _FALLBACK_OK.search(str(kw.get("model") or "")):
        try:
            return client.beta.messages.create(betas=["server-side-fallback-2026-07-01"], fallbacks="default", **kw)
        except TypeError:
            pass                                   # an SDK from before the option existed
        except Exception as e:
            if getattr(e, "status_code", None) != 400:
                raise
    return client.messages.create(**kw)
