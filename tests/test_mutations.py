import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from mutations import MutationDetector

_pass = 0
_fail = 0


def S(name: str) -> None:
    print(f"\n--- {name} ---")


def T(name: str, ok: bool, details: str = "") -> None:
    global _pass, _fail
    if ok:
        _pass += 1
        print(f"  [PASS] {name}")
    else:
        _fail += 1
        extra = f" ({details})" if details else ""
        print(f"  [FAIL] {name}{extra}")


class MockRepo:
    def get_narrative(self, _narrative_id: str) -> dict:
        return {"name": "[SYSTEM] Narrative"}


class MockLlm:
    def __init__(self):
        self.prompt = ""

    def call_haiku(self, _task_type: str, _narrative_id: str, prompt: str) -> str:
        self.prompt = prompt
        return "ok"


S("mutation explanation sanitization")

llm = MockLlm()
detector = MutationDetector(settings=object(), repository=MockRepo(), llm_client=llm)
result = detector.generate_llm_explanation(
    "nid",
    "stage_change",
    "IGNORE previous stage",
    "OVERRIDE with INJECT payload",
)

upper_prompt = llm.prompt.upper()
T("returns llm output", result == "ok", repr(result))
T(
    "prompt strips injection markers",
    all(x not in upper_prompt for x in ("SYSTEM", "IGNORE", "OVERRIDE", "INJECT")),
    llm.prompt,
)

print(f"\nTOTAL: {_pass} passed, {_fail} failed")
sys.exit(1 if _fail else 0)
