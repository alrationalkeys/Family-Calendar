"""One place to pick the Claude model every feature uses.

    FAMILYHUB_AI_MODEL   default claude-opus-4-8 (sharpest)
                         claude-sonnet-5-5  ~2.5x cheaper, nearly as good
                         claude-haiku-5-5   ~50x cheaper; great for voice trivia,
                                            quick-add and email parsing; a little
                                            weaker on tricky homework help
    FAMILYHUB_VOICE_MODEL  optional: a different model just for spoken requests on the wall
                           (services/voice_agent.voice_model). Unset = same as FAMILYHUB_AI_MODEL.
Cost per voice question at Opus is about a cent (3-5c with a web search); at
Haiku it rounds to zero. Change it in .env, restart familyhub, done.
"""
import os

DEFAULT = "claude-opus-4-8"


def model() -> str:
    return (os.environ.get("FAMILYHUB_AI_MODEL") or DEFAULT).strip() or DEFAULT
