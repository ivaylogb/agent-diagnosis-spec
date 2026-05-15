"""pytest bootstrap: make the src-layout package importable without install."""

import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

FIXTURES = ROOT / "tests" / "fixtures"
# The three canonical reference outputs (sibling repos, read-only).
CANONICAL = {
    "agent-researcher": ROOT.parent / "agent_researcher" / "examples" / "issue_107" / "report.md",
    "funnel-researcher": ROOT.parent / "funnel-researcher" / "examples" / "api_activation" / "diagnosis.md",
    "integration-watcher": ROOT.parent / "integration-watcher" / "examples" / "agent_platform" / "findings.md",
}
