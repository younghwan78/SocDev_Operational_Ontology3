import hashlib
from pathlib import Path

import yaml

PROMPT_BUNDLE_VERSION = "prompts.v2"
_BUNDLE_DIR = Path(__file__).parent / PROMPT_BUNDLE_VERSION
_MANIFEST_PATH = _BUNDLE_DIR / "manifest.yaml"


def _read_verified_bundle() -> tuple[dict[str, str], str]:
    manifest_value: object = yaml.safe_load(_MANIFEST_PATH.read_text(encoding="utf-8"))
    if not isinstance(manifest_value, dict):
        raise RuntimeError("PROMPT_MANIFEST_INVALID")
    files_value = manifest_value.get("files")
    if manifest_value.get("bundle_version") != PROMPT_BUNDLE_VERSION or not isinstance(
        files_value, dict
    ):
        raise RuntimeError("PROMPT_MANIFEST_INVALID")
    contents: dict[str, str] = {}
    aggregate = hashlib.sha256()
    for name in ("role.md", "challenger.md", "chair.md"):
        expected = files_value.get(name)
        if not isinstance(expected, str):
            raise RuntimeError("PROMPT_MANIFEST_INVALID")
        content = (_BUNDLE_DIR / name).read_text(encoding="utf-8").strip()
        actual = hashlib.sha256(content.encode()).hexdigest()
        if actual != expected:
            raise RuntimeError(f"PROMPT_HASH_MISMATCH:{name}")
        contents[name] = content
        aggregate.update(name.encode())
        aggregate.update(actual.encode())
    return contents, aggregate.hexdigest()


_CONTENTS, PROMPT_BUNDLE_HASH = _read_verified_bundle()
ROLE_REVIEW_INSTRUCTIONS = _CONTENTS["role.md"]
CHALLENGER_INSTRUCTIONS = _CONTENTS["challenger.md"]
CHAIR_INSTRUCTIONS = _CONTENTS["chair.md"]
