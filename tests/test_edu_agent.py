"""Structure tests for the edu-agent capability (P2.2) — skill-only, no MCP server.

Validates the SKILL.md frontmatter (name follows the qwen-mm-plugins-<folder> convention
from CLAUDE.md) and the three harness plugin manifests. Deliberately does NOT pin the
body's section layout or first heading — the skill prose is actively edited (e.g. a
Troubleshooting index may be prepended) and that must not break these checks.
"""

import json
import os
import re

import pytest
from conftest import REPO_ROOT

CAP_DIR = os.path.join(REPO_ROOT, "src", "capabilities", "edu-agent")
SKILL_MD = os.path.join(CAP_DIR, "skill", "SKILL.md")
EXPECTED_NAME = "qwen-mm-plugins-edu-agent"

MANIFESTS = [".claude-plugin/plugin.json", ".codex-plugin/plugin.json", ".qoder-plugin/plugin.json"]


def _split_frontmatter(text: str) -> tuple[str, str]:
    """Split '---\\n<yaml>\\n---\\n<body>' without requiring a YAML parser."""
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n(.*)\Z", text, re.DOTALL)
    assert m, "SKILL.md must start with a --- frontmatter block"
    return m.group(1), m.group(2)


@pytest.fixture(scope="module")
def skill_parts() -> tuple[str, str]:
    assert os.path.isfile(SKILL_MD), f"missing {SKILL_MD}"
    with open(SKILL_MD, encoding="utf-8") as f:
        return _split_frontmatter(f.read())


def test_skill_name_matches_naming_convention(skill_parts):
    frontmatter, _ = skill_parts
    m = re.search(r"^name:\s*(\S+)\s*$", frontmatter, re.MULTILINE)
    assert m, "frontmatter must declare a name:"
    assert m.group(1) == EXPECTED_NAME, "SKILL.md name must equal the install/plugin name (CLAUDE.md convention)"


def test_skill_description_present(skill_parts):
    frontmatter, _ = skill_parts
    assert re.search(r"^description:", frontmatter, re.MULTILINE), "frontmatter must declare a description:"
    # description carries real trigger guidance, not a stub
    assert len(frontmatter) > 200


def test_skill_body_nonempty(skill_parts):
    _, body = skill_parts
    assert len(body.strip()) > 500, "SKILL.md body must hold real instructions"
    # at least one markdown heading somewhere — but no assumption about WHICH comes first
    assert re.search(r"^#{1,3} ", body, re.MULTILINE)


@pytest.mark.parametrize("rel", MANIFESTS)
def test_manifest_valid_json_with_key_fields(rel):
    path = os.path.join(CAP_DIR, rel)
    assert os.path.isfile(path), f"missing manifest {rel}"
    with open(path, encoding="utf-8") as f:
        manifest = json.load(f)  # raises on invalid JSON
    assert manifest["name"] == EXPECTED_NAME
    assert re.match(r"^\d+\.\d+", manifest["version"]), "version must look like a semver"
    assert manifest.get("description", "").strip()


@pytest.mark.parametrize("rel", MANIFESTS)
def test_manifest_skills_path_resolves(rel):
    with open(os.path.join(CAP_DIR, rel), encoding="utf-8") as f:
        manifest = json.load(f)
    skills = manifest.get("skills")
    assert skills, f"{rel} must reference the skill dir"
    # claude uses a list, codex/qoder a single string — accept both shapes
    entries = skills if isinstance(skills, list) else [skills]
    for entry in entries:
        target = os.path.normpath(os.path.join(CAP_DIR, entry))
        assert os.path.isdir(target), f"{rel} skills path {entry!r} must exist"
        assert os.path.isfile(os.path.join(target, "SKILL.md"))
