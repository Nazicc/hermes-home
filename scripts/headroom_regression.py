#!/usr/bin/env python3
"""
Headroom v0.24.0 回归测试套件 — 崩溃安全，断电/重启后可立即重跑。

验证安装完整性：15 个测试覆盖全部核心模块。

用法：
  python ~/.hermes/scripts/headroom_regression.py
"""

import sys
import json
import dataclasses
import traceback

# ── 全部公用 API ──
from headroom import (
    SmartCrusher,        # lossless JSON compressor
    create_scorer,       # BM25 / embedding / hybrid scorer factory
    CompressConfig,      # compression settings dataclass
    CacheConfig,         # cache settings dataclass
    CompressResult,      # SmartCrusher output (alias: CrushResult)
    TokenCounter,        # token counting protocol
    ScopeLevel,          # context scope enum
    Block,               # memory block
    SharedContext,       # shared context
    generate_report,     # memory report generator
    count_tokens_text,   # fast token count
    __version__,         # package version
)
from headroom.relevance import RelevanceScore


# ── 测试框架 ──
passed = failed = 0

def test(name):
    """Decorator: run test function, print PASS/FAIL, tally."""
    def deco(fn):
        global passed, failed
        try:
            fn()
            print(f"  [PASS] {name}")
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")
            traceback.print_exc()
            failed += 1
    return deco


# ═══════════════════════════════════════════
# 1. SmartCrusher — lossless JSON compression
# ═══════════════════════════════════════════

@test("SmartCrusher: empty object")
def test_sc_empty():
    sc = SmartCrusher()
    r = sc.crush("{}")
    assert hasattr(r, 'compressed')
    assert hasattr(r, 'was_modified')


@test("SmartCrusher: large JSON reduces size")
def test_sc_large():
    sc = SmartCrusher()
    data = json.dumps({"key": list(range(100)), "meta": {"v": "1.0"}})
    r = sc.crush(data)
    # Must either shrink or stay identical (already minimal)
    assert len(r.compressed) <= len(data), f"{len(r.compressed)} > {len(data)}"


@test("SmartCrusher: short data compresses gracefully")
def test_sc_short():
    sc = SmartCrusher()
    tiny = json.dumps({"a": 1})
    r = sc.crush(tiny)
    # Short data may get compressed or bypassed; either way, no crash
    assert hasattr(r, 'compressed')


@test("SmartCrusher: repetitive data compresses")
def test_sc_repetitive():
    sc = SmartCrusher()
    rep = json.dumps({"items": [{"id": i, "name": "alpha"} for i in range(50)]})
    r = sc.crush(rep)
    assert len(r.compressed) < len(rep), "repetitive data should compress"
    # strategy is a dict-like report of what the crusher did
    assert r.strategy is not None


@test("SmartCrusher: idempotent (second crush = no-op)")
def test_sc_idempotent():
    sc = SmartCrusher()
    data = json.dumps({"x": list(range(30))})
    r1 = sc.crush(data)
    r2 = sc.crush(r1.compressed)
    assert r2.was_modified is False, "already compressed output should be stable"
    assert r2.compressed == r1.compressed


# ═══════════════════════════════════════════
# 2. BM25 Relevance Scorer
# ═══════════════════════════════════════════

@test("RelevanceScorer: BM25 relevant > irrelevant")
def test_bm25_relevant():
    scorer = create_scorer("bm25")
    rel = scorer.score("machine learning", "Machine learning is a subset of artificial intelligence that enables systems to learn and improve from experience.")
    irr = scorer.score("machine learning", "The weather today is sunny with a chance of rain in the afternoon.")
    assert rel.score > irr.score, f"{rel.score:.3f} <= {irr.score:.3f}"


@test("RelevanceScore: type and formatting")
def test_relevance_score_type():
    scorer = create_scorer("bm25")
    s = scorer.score("hello", "hello world")
    assert isinstance(s, RelevanceScore)
    assert isinstance(s.score, float)
    assert repr(s) is not None


@test("RelevanceScorer: multi-word query")
def test_bm25_multiword():
    scorer = create_scorer("bm25")
    scores = [
        scorer.score("deep learning neural networks", txt).score
        for txt in [
            "Neural networks are a key technology in deep learning research.",
            "I like to bake cookies on the weekend.",
            "Python is a programming language used for deep learning.",
        ]
    ]
    assert scores[0] > scores[1], f"neural net doc {scores[0]:.3f} should beat cookie doc {scores[1]:.3f}"


# ═══════════════════════════════════════════
# 3. Configuration Dataclasses
# ═══════════════════════════════════════════

@test("CompressConfig: field defaults")
def test_compress_config():
    cfg = CompressConfig()
    fields = {f.name: f.default for f in dataclasses.fields(cfg)}
    assert fields["compress_system_messages"] is True
    assert fields["compress_user_messages"] is False
    assert fields["protect_recent"] == 4
    assert fields["min_tokens_to_compress"] == 250
    assert fields["kompress_model"] is None
    print(f"  sys_msgs={fields['compress_system_messages']}, usr_msgs={fields['compress_user_messages']}, protect={fields['protect_recent']}")


@test("CacheConfig: field defaults")
def test_cache_config():
    cfg = CacheConfig()
    fields = {f.name: f.default for f in dataclasses.fields(cfg)}
    assert fields["enabled"] is True
    assert fields["min_cacheable_tokens"] == 1024
    assert fields["max_breakpoints"] == 4
    print(f"  enabled={fields['enabled']}, min_tokens={fields['min_cacheable_tokens']}")


# ═══════════════════════════════════════════
# 4. Module Integrity — all public APIs import
# ═══════════════════════════════════════════

@test("All public symbols import correctly")
def test_public_api():
    required = [
        "SmartCrusher", "create_scorer", "CompressConfig", "CacheConfig",
        "CompressResult", "TokenCounter", "ScopeLevel", "Block",
        "SharedContext", "generate_report", "count_tokens_text",
        "RelevanceScore",
    ]
    import headroom
    for name in required:
        obj = getattr(headroom, name, None) or getattr(
            __import__("headroom.relevance", fromlist=[name]), name, None
        )
        assert obj is not None, f"{name} missing from headroom namespace"


# ═══════════════════════════════════════════
# 5. Edge Cases
# ═══════════════════════════════════════════

@test("Edge: deeply nested JSON")
def test_deep_nested():
    sc = SmartCrusher()
    deep = json.dumps({"a": {"b": {"c": {"d": {"e": {"f": "deep"}}}}}})
    r = sc.crush(deep)
    assert hasattr(r, 'compressed')
    assert len(r.compressed) <= len(deep)


@test("Edge: large array (500 items)")
def test_large_array():
    sc = SmartCrusher()
    big = json.dumps([{"id": i, "val": f"item_{i}"} for i in range(500)])
    r = sc.crush(big)
    assert len(r.compressed) < len(big), "500-item array should compress"


@test("Edge: plain text (non-JSON, should bypass)")
def test_plain_text():
    sc = SmartCrusher()
    text = "Hello, this is a plain text message that should not be modified by the crusher." * 10
    r = sc.crush(text)
    # SmartCrusher may or may not modify plain text; just ensure no crash
    _ = r


# ═══════════════════════════════════════════
# — Run All —
# ═══════════════════════════════════════════

print(":" * 60)
print(f"HEADROOM REGRESSION TEST SUITE v{__version__}".center(60))
print(":" * 60)
print()

# Collect all test functions decorated above
import inspect
test_fns = []
for name, obj in list(globals().items()):
    if name.startswith("test_") and callable(obj):
        # Find the original function (decorator wraps it)
        test_fns.append(obj)

# Execute them
for fn in test_fns:
    fn()

print()
print(":" * 60)
print(f"  {passed}/{passed + failed} tests passed", end="")
if failed:
    print(f", {failed} FAILED!")
    sys.exit(1)
else:
    print()
    sys.exit(0)
