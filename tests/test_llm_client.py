import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import llm_client as llm_module
from llm_client import LlmClient

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


def _make_repo(ns_score: float = 0.9) -> MagicMock:
    repo = MagicMock()
    repo.get_narrative.return_value = {
        "narrative_id": "n-test",
        "ns_score": ns_score,
        "created_at": (datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
    }
    repo.get_sonnet_calls_last_24h.return_value = []
    repo.get_sonnet_daily_spend.return_value = {"total_tokens_used": 0}
    return repo


def _make_settings() -> MagicMock:
    settings = MagicMock()
    settings.ANTHROPIC_API_KEY = "test-key"
    settings.CONFIDENCE_ESCALATION_THRESHOLD = 0.6
    settings.SONNET_DAILY_TOKEN_BUDGET = 200000
    settings.SONNET_MAX_TOKENS = 2048
    settings.SONNET_MODEL = "claude-sonnet-4-6"
    settings.HAIKU_MODEL = "claude-haiku-4-5-20251001"
    settings.HAIKU_MAX_TOKENS = 512
    settings.LLM_DAILY_BUDGET_USD = 999.0
    return settings


def _make_llm(repo: MagicMock, settings: MagicMock, client: MagicMock) -> LlmClient:
    llm = LlmClient.__new__(LlmClient)
    llm._settings = settings
    llm._repository = repo
    llm._client = client
    llm._consecutive_transport_errors = 0
    return llm


S("sonnet gate bypass")

repo1 = _make_repo(ns_score=0.2)
settings1 = _make_settings()
client1 = MagicMock()
sonnet_resp = MagicMock()
sonnet_resp.content = [MagicMock(text="Mutation analysis generated")]
sonnet_resp.usage = MagicMock(input_tokens=100, output_tokens=60)
client1.messages.create.return_value = sonnet_resp
llm1 = _make_llm(repo1, settings1, client1)

with patch("signals.get_narrative_age_days", return_value=10):
    no_bypass = llm1.call_sonnet("n-test", "Analyze this narrative")
    with_bypass = llm1.call_sonnet(
        "n-test",
        "Analyze this narrative",
        skip_ns_gate=True,
    )

T("without skip_ns_gate, low ns_score returns None", no_bypass is None, repr(no_bypass))
T("with skip_ns_gate, sonnet result is returned", with_bypass == "Mutation analysis generated", repr(with_bypass))
logged_calls = [args[0] for args, _kwargs in repo1.log_llm_call.call_args_list]
T(
    "skip_ns_gate audit event logged",
    any(record.get("task_type") == "mutation_gate_1_bypass" for record in logged_calls),
)


S("sonnet retries rate limits")

repo2 = _make_repo(ns_score=0.95)
settings2 = _make_settings()
client2 = MagicMock()
llm2 = _make_llm(repo2, settings2, client2)

class FakeRateLimit(Exception):
    pass

retry_success = MagicMock()
retry_success.content = [MagicMock(text="Recovered after retry")]
retry_success.usage = MagicMock(input_tokens=90, output_tokens=55)
client2.messages.create.side_effect = [
    FakeRateLimit("429-1"),
    FakeRateLimit("429-2"),
    retry_success,
]

with patch("signals.get_narrative_age_days", return_value=10), patch.object(
    llm_module, "_RATE_LIMIT_ERROR", FakeRateLimit
), patch("time.sleep") as sleep_mock, patch("random.uniform", return_value=0.0):
    retry_result = llm2.call_sonnet("n-test", "Analyze this narrative")

T("rate-limit retries eventually succeed", retry_result == "Recovered after retry", repr(retry_result))
T("rate-limit retries call sleep twice", sleep_mock.call_count == 2, f"count={sleep_mock.call_count}")
retry_audit = [args[0] for args, _kwargs in repo2.log_llm_call.call_args_list]
T(
    "rate-limit retries logged to llm_audit_log",
    any(row.get("task_type") == "mutation_analysis_retry_rate_limit" for row in retry_audit),
)


S("client recreation after consecutive transport failures")

repo3 = _make_repo(ns_score=0.95)
settings3 = _make_settings()
client3 = MagicMock()
llm3 = _make_llm(repo3, settings3, client3)
llm3.call_haiku = MagicMock(return_value="fallback")

class FakeTransport(Exception):
    pass

client3.messages.create.side_effect = FakeTransport("network down")

with patch("signals.get_narrative_age_days", return_value=10), patch.object(
    llm_module, "_API_CONNECTION_ERROR", FakeTransport
), patch("time.sleep"), patch("random.uniform", return_value=0.0), patch(
    "llm_client.anthropic.Anthropic", return_value=MagicMock()
) as anthropic_ctor:
    _first = llm3.call_sonnet("n-test", "Analyze this narrative")
    _second = llm3.call_sonnet("n-test", "Analyze this narrative")

T("first transport failure falls back", _first == "fallback", repr(_first))
T("second transport failure falls back", _second == "fallback", repr(_second))
T("client recreated after two consecutive transport failures", anthropic_ctor.call_count == 1, f"count={anthropic_ctor.call_count}")
T("transport error counter reset after recreation", llm3._consecutive_transport_errors == 0, str(llm3._consecutive_transport_errors))

print(f"\nTOTAL: {_pass} passed, {_fail} failed")
sys.exit(1 if _fail else 0)
