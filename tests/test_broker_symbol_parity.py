"""AEGIS Phase 3 — broker/symbol parity machinery.

Pins the FIELD MAP (every mandated broker fact has a named owner-export
field, a Python SymbolSpec side or an explicit runtime-authority marker, and
a tolerance), the strict fail-fast export schema, the never-invent rule (no
owner export ⇒ PENDING, no fabricated numbers anywhere), the derived
tick-value P/L identity, and behavioural sizer parity against exported
grids.
"""

import json
import re
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "tools"))
sys.path.insert(0, str(REPO / "python"))

from broker_symbol_parity import (
    FIELD_MAP,
    REQUIRED_ASSET_CLASSES,
    compare_symbol,
    derived_pl_check,
    load_owner_export,
    render_markdown,
    sizer_behaviour_parity,
)

MQL5_EXPORT_SCRIPT = REPO / "mql5/Scripts/Mql5Bot/Mql5BotExportSymbolSpec.mq5"


def _synthetic_export(tmp_path, **over):
    sym = {
        "name": "EURUSD", "digits": 5, "point": 1e-05, "tick_size": 1e-05,
        "tick_value_profit": 1.0, "tick_value_loss": 1.0,
        "contract_size": 100000.0, "volume_min": 0.01, "volume_max": 100.0,
        "volume_step": 0.01, "volume_limit": 0.0, "stops_level_points": 0,
        "freeze_level_points": 0, "currency_profit": "USD",
        "trade_mode": 4, "filling_mode_mask": 1, "order_mode": 0,
        "expiration_mode_mask": 15, "margin_initial": 0.0,
        "margin_maintenance": 0.0,
    }
    sym.update(over)
    doc = {"schema": "mql5bot.broker_export/1", "symbol": sym}
    p = tmp_path / "EURUSD.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    return doc


# ---------------------------------------------------------------------------
# field map completeness (the mandated parity surface)
# ---------------------------------------------------------------------------


def test_field_map_covers_every_mandated_broker_fact():
    mandated = {
        "tick_size", "tick_value_profit", "tick_value_loss", "contract_size",
        "volume_min", "volume_max", "volume_step", "volume_limit",
        "margin_initial", "margin_maintenance", "trade_mode",
        "filling_mode_mask", "order_mode", "stops_level_points",
        "freeze_level_points", "digits", "point", "currency_profit",
    }
    assert mandated <= set(FIELD_MAP)
    # every mapped field declares a tolerance and at least one consumer
    for _py, _mq, consumers, tag in FIELD_MAP.values():
        assert consumers, "field without consumer annotation"
        assert tag in ("exact", "rel1e-12", "rel1e-9")


def test_python_side_fields_exist_on_symbolspec():
    from mql5bot.symbolspec import SymbolSpec
    for py_attr, _mq, _c, _t in FIELD_MAP.values():
        if py_attr is not None:
            assert py_attr in SymbolSpec.__dataclass_fields__


def test_mql5_ssymbolspec_has_every_mapped_member():
    src = (REPO / "mql5/Include/Mql5Bot/SymbolSpec.mqh").read_text(encoding="utf-8")
    for field, (_py, mq_member, _c, _t) in FIELD_MAP.items():
        if mq_member is not None:
            assert mq_member in src, f"SSymbolSpec missing {mq_member} ({field})"


def test_export_script_dumps_every_mandated_field():
    src = MQL5_EXPORT_SCRIPT.read_text(encoding="utf-8")
    for field in FIELD_MAP:
        assert f'JsonQuote("{field}")' in src, f"export script misses {field}"
    # and an OrderCalcMargin probe so margin parity has runtime authority
    assert "OrderCalcMargin" in src


def test_required_asset_classes_pinned():
    assert REQUIRED_ASSET_CLASSES == ("FX", "METAL", "INDEX_CFD", "CRYPTO")


# ---------------------------------------------------------------------------
# strict schema — fail fast, never repair
# ---------------------------------------------------------------------------


def test_load_owner_export_rejects_wrong_schema_and_missing_fields(tmp_path):
    doc = _synthetic_export(tmp_path)
    doc["schema"] = "some/other"
    p = tmp_path / "bad.json"
    p.write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError, match="wrong schema"):
        load_owner_export(p)

    doc2 = _synthetic_export(tmp_path)
    del doc2["symbol"]["tick_value_loss"]
    p2 = tmp_path / "bad2.json"
    p2.write_text(json.dumps(doc2), encoding="utf-8")
    with pytest.raises(ValueError, match="missing fields"):
        load_owner_export(p2)


def test_missing_export_reports_pending_and_fabricates_nothing(capsys):
    from broker_symbol_parity import build_report
    exports, rows, coverage = build_report(
        REPO / "data/broker_exports/definitely-missing-dir")
    assert exports == [] and rows == []
    assert all(v.startswith("PENDING") for v in coverage.values())
    md = render_markdown([], [], coverage)
    assert "NOT VERIFIED" in md and "PENDING" in md
    out = capsys.readouterr()  # no exception; no invented numbers in doc
    assert out.err == ""


# ---------------------------------------------------------------------------
# comparison semantics
# ---------------------------------------------------------------------------


def test_compare_flags_mismatch_within_tolerance(tmp_path):
    from mql5bot.symbolspec import SymbolSpec
    model = SymbolSpec()  # defaults == the synthetic EURUSD export
    doc = _synthetic_export(tmp_path, tick_value_loss=1.0000000001)
    rows = compare_symbol(doc, model)
    by = {r.field: r for r in rows}
    assert by["tick_value_loss"].status == "MATCH"      # inside rel 1e-9
    doc_off = _synthetic_export(tmp_path, tick_value_loss=1.1)
    by_off = {r.field: r for r in compare_symbol(doc_off, model)}
    assert by_off["tick_value_loss"].status == "MISMATCH"  # outside tolerance
    doc2 = _synthetic_export(tmp_path, volume_step=0.001)
    by2 = {r.field: r for r in compare_symbol(doc2, model)}
    assert by2["volume_step"].status == "MISMATCH"      # exact-tolerance field


def test_runtime_authority_fields_marked_n_a_not_matched(tmp_path):
    doc = _synthetic_export(tmp_path)
    rows = compare_symbol(doc, None)
    by = {r.field: r for r in rows}
    for runtime_field in ("trade_mode", "filling_mode_mask", "margin_initial"):
        assert by[runtime_field].status == "N_A"
        assert "runtime" in by[runtime_field].python or \
            "runtime" in by[runtime_field].detail


def test_derived_tick_value_identity(tmp_path):
    doc = _synthetic_export(tmp_path)  # 100000 × 1e-5 × 1.0 = 1.0
    assert derived_pl_check(doc, fx_profit_to_deposit=1.0).status == "MATCH"
    assert derived_pl_check(doc, fx_profit_to_deposit=0.9).status == "MISMATCH"
    r = derived_pl_check(doc, fx_profit_to_deposit=None)
    assert r.status == "PENDING" and "fx" in r.detail


def test_derived_identity_cross_currency(tmp_path):
    # XAU-like: contract 100 oz, tick 0.01 → structural 1.0 USD/tick; with
    # deposit EUR the owner-supplied fx must reconcile
    doc = _synthetic_export(tmp_path, name="XAUUSD", contract_size=100.0,
                            tick_size=0.01, tick_value_loss=1.0,
                            currency_profit="USD")
    assert derived_pl_check(doc, fx_profit_to_deposit=1.0).status == "MATCH"
    assert derived_pl_check(doc, fx_profit_to_deposit=1.08).status == "MISMATCH"


def test_sizer_behaviour_parity_on_exported_grid(tmp_path):
    doc = _synthetic_export(tmp_path, tick_size=0.25, point=0.01,
                            volume_step=0.1, volume_min=0.1)
    rows = sizer_behaviour_parity(doc)
    by = {r.field: r for r in rows}
    # floor semantics: 0.1 + 0.4×0.1 = 0.14 → floored to 0.1 (never up)
    assert by["sizer.normalize_volume(floor)"].owner == pytest.approx(0.14)
    assert by["sizer.normalize_volume(floor)"].python == pytest.approx(0.1)
    assert by["sizer.loss_per_lot"].status == "MATCH"


def test_crypto_style_grid_non_point_tick_size(tmp_path):
    # index/crypto CFDs where tick_size is a multiple of point — the sizer
    # must use tick_size (not digits/point) for rounding
    doc = _synthetic_export(tmp_path, name="BTCUSD", digits=2, point=0.01,
                            tick_size=0.5, contract_size=1.0,
                            tick_value_loss=0.5)
    rows = sizer_behaviour_parity(doc)
    by = {r.field: r for r in rows}
    assert by["sizer.loss_per_lot"].status == "MATCH"
    # structural: contract 1.0 × tick 0.5 = 0.5 = exported tick value
    assert derived_pl_check(doc, fx_profit_to_deposit=1.0).status == "MATCH"


# ---------------------------------------------------------------------------
# exporter JSON escaping — 2026-09-09 owner-export defect
#
# The owner's real MT5 run produced `"path": "Forex\EURUSD"` — a raw
# backslash inside a JSON string — so tools/broker_symbol_parity.py skipped
# the export with "Invalid \escape" and the owner evidence was lost.
#
# Three layers, cheapest and most independent first:
#
# 1. the JSON contract itself, asserted WITHOUT reading any MQL5 source text:
#    the canonical RFC 8259 string encoding, a json.loads round-trip, and the
#    counter-example showing that the pre-fix output was not JSON at all;
# 2. the exporter source contract: the rules declared in the .mq5 helper must
#    produce that same encoding.  Extraction is layout-agnostic — indentation,
#    line breaks, parameter/variable names and quoting style are irrelevant,
#    and both a StringReplace() table and a per-character switch are read —
#    because the tests pin SEMANTICS, never formatting.  The rules are then
#    REPLAYED the way MQL5 applies them and re-validated as JSON;
# 3. the harness behaviour: an escaped export is parsed and counted, a
#    malformed one is skipped and never repaired.
#
# MetaEditor cannot run in this sandbox (same constraint as
# tests/test_mql5_sources.py).  If the helper is ever rewritten in a style the
# extractor cannot read, the failure message says so explicitly — layer 1
# keeps the contract pinned either way.
# ---------------------------------------------------------------------------

#: every character class JSON forbids raw inside a string literal, plus the
#: values that must survive untouched.  U+0000 is not exercised: a NUL cannot
#: occur in broker text, so its MQL5 round-trip is not part of this contract.
JSON_STRING_SAMPLES = [
    "EURUSD",            # ordinary text must not be corrupted
    "Forex\\EURUSD",   # <-- the observed defect (SYMBOL_PATH)
    "Forex\\Sub\\EURUSD",
    "C:\\Users\\mt5",
    'say "hello"',
    "line1\nline2",
    "carriage\rreturn",
    "tab\there",
    "back\bspace",
    "form\ffeed",
    "vertical\x0btab",
    "control\x01char",
    'mixed "quote" and \\backslash\\ and\nnewline',
    "US30",
    "Ørsta",             # non-ASCII passes through untouched
    "DAX40.GI",
    "",
]

#: characters RFC 8259 requires a JSON writer to escape with a NAMED sequence
NAMED_ESCAPE_CHARS = ["\\", '"', "\n", "\r", "\t", "\b", "\f"]


def _json_string_literal(value: str) -> str:
    """The canonical encoding of a string value — what the exporter must emit.
    Derived from the JSON encoder itself (never a hand-copied table): named
    escapes, ``\\u00xx`` for the rest of the control range, and every other
    character copied through, because MQL5 writes the document as-is
    (``ensure_ascii=False``).  Canonical also means minimal: a writer that
    over-escapes (``\\/`` for a slash) is rejected, so the exported bytes stay
    comparable with every other JSON producer."""
    return json.dumps(value, ensure_ascii=False)


# --- layer 1: the JSON contract, independent of the MQL5 source ------------


@pytest.mark.parametrize("value", JSON_STRING_SAMPLES)
def test_json_string_literal_contract_round_trips(value):
    document = '{"symbol": {"path": ' + _json_string_literal(value) + "}}"
    assert json.loads(document)["symbol"]["path"] == value


def test_unescaped_broker_value_is_not_json_at_all():
    """The pre-fix behaviour (quote without escaping) as a counter-example:
    this is what made the owner export unparsable, and it is what a regression
    to ``return "\\"" + s + "\\"";`` would produce again."""
    broken = '{"symbol": {"path": "Forex' + chr(92) + 'EURUSD"}}'
    assert chr(92) + "EURUSD" in broken          # raw backslash in the document
    with pytest.raises(json.JSONDecodeError, match=r"Invalid \\escape"):
        json.loads(broken)
    fixed = ('{"symbol": {"path": '
             + _json_string_literal("Forex\\EURUSD") + "}}")
    assert json.loads(fixed)["symbol"]["path"] == "Forex\\EURUSD"


# --- layer 2: the exporter source contract (semantics, not layout) ---------

_MQL5_LITERAL_RE = re.compile(r'"((?:[^"\\]|\\.)*)"')
_MQL5_SIMPLE_ESCAPES = {
    "n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'",
}

# StringReplace(target, "<find>" | ShortToString(<code>), "<replacement>")
_REPLACE_RULE_RE = re.compile(
    r"StringReplace\s*\(\s*\w+\s*,\s*"
    r'(?:"((?:[^"\\]|\\.)*)"'
    r"|ShortToString\s*\(\s*(?:\(\s*ushort\s*\)\s*)?(0x[0-9A-Fa-f]+|\d+)\s*\))"
    r'\s*,\s*"((?:[^"\\]|\\.)*)"\s*\)')

# case <char|code>: out += "<replacement>";
_CASE_RULE_RE = re.compile(
    r"case\s+(?:\"((?:[^\"\\]|\\.)*)\"|'((?:[^'\\]|\\.)*)'"
    r"|(0x[0-9A-Fa-f]+|\d+))\s*:\s*\w+\s*(?:\+=|=)\s*\"((?:[^\"\\]|\\.)*)\"\s*;")


def _mql5_constant(text: str) -> str:
    """Decode an MQL5 string/character constant (the escape forms the
    exporter's serialization can legitimately use)."""
    out, i = [], 0
    while i < len(text):
        ch = text[i]
        if ch != "\\":
            out.append(ch)
            i += 1
            continue
        i += 1
        assert i < len(text), f"truncated MQL5 escape in {text!r}"
        nxt = text[i]
        if nxt in _MQL5_SIMPLE_ESCAPES:
            out.append(_MQL5_SIMPLE_ESCAPES[nxt])
            i += 1
        elif nxt in "xX":
            j = i + 1
            while (j < len(text) and j - i <= 4
                   and text[j] in "0123456789abcdefABCDEF"):
                j += 1
            digits = text[i + 1:j]
            assert digits, f"empty hex escape in {text!r}"
            out.append(chr(int(digits, 16)))
            i = j
        else:
            raise AssertionError(
                f"unsupported MQL5 escape \\{nxt} in {text!r}: the extractor"
                " knows \\n \\r \\t \\\\ \\\" \\' and \\x<hex> (the forms"
                " MQL5 documents for string constants)")
    return "".join(out)


def _exporter_source() -> str:
    return MQL5_EXPORT_SCRIPT.read_text(encoding="utf-8")


def _mql5_function(name_pattern: str, src: str | None = None) -> tuple[str, str]:
    """Return (name, body) of the first `string <name>(...) { ... }` helper
    whose name matches, located by brace matching: indentation, line breaks,
    brace placement and parameter naming are all irrelevant."""
    src = _exporter_source() if src is None else src
    m = re.search(r"^[ \t]*string[ \t]+(\w*" + name_pattern + r"\w*)[ \t]*\("
                  r"[^)]*\)\s*\{", src, re.MULTILINE)
    assert m, (
        f"no `string *{name_pattern}*()` helper found in the exporter: with no"
        " escaping every string value would be written raw again (the "
        "2026-09-09 defect)")
    depth, i = 0, m.end() - 1
    while i < len(src):
        ch = src[i]
        if ch in "\"'":                     # step over constants
            quote, i = ch, i + 1
            while i < len(src) and src[i] != quote:
                i += 2 if src[i] == "\\" else 1
            i += 1
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return m.group(1), src[m.end():i]
        i += 1
    raise AssertionError("unbalanced braces in the exporter helper")


def _control_bound(body: str) -> int:
    """Exclusive upper bound of a generic ``\\u00xx`` control-character rule in
    the helper body, or 0 when the helper has none (then it must list every
    control character explicitly)."""
    for literal in _MQL5_LITERAL_RE.findall(body):
        decoded = _mql5_constant(literal)
        if decoded.startswith("\\u") and "%04x" in decoded.lower():
            m = re.search(r"<\s*(0x[0-9A-Fa-f]+|\d+)", body)
            return int(m.group(1), 0) if m else 0
    return 0


def _escape_rules(body: str) -> tuple[list[tuple[str, str]], int]:
    """(ordered rules, control bound) of an escaping helper body.  A rule is a
    (find, replacement) pair, read from either implementation style."""
    found: list[tuple[int, tuple[str, str]]] = []
    for m in _REPLACE_RULE_RE.finditer(body):
        find_lit, code, repl_lit = m.group(1), m.group(2), m.group(3)
        find = _mql5_constant(find_lit) if find_lit is not None else chr(int(code, 0))
        found.append((m.start(), (find, _mql5_constant(repl_lit))))
    for m in _CASE_RULE_RE.finditer(body):
        lit, char, code, repl_lit = m.groups()
        if lit is not None:
            find = _mql5_constant(lit)
        elif char is not None:
            find = _mql5_constant(char)
        else:
            find = chr(int(code, 0))
        found.append((m.start(), (find, _mql5_constant(repl_lit))))
    found.sort(key=lambda item: item[0])
    return [rule for _, rule in found], _control_bound(body)


def _exporter_escaped(value: str) -> str:
    """Apply the exporter's own escape rules to a string the way the MQL5 code
    would: a StringReplace() table is applied sequentially in source order
    (that order is part of the algorithm), a per-character helper maps each
    code unit independently (so the order of its cases is irrelevant)."""
    body = _mql5_function("[Ee]scape")[1]
    rules, bound = _escape_rules(body)
    table = dict(rules)
    if re.search(r"\bStringReplace\s*\(", body):
        out = value
        for find, repl in rules:
            out = out.replace(find, repl)
        for code in range(1, bound):
            out = out.replace(chr(code), f"\\u{code:04x}")
        return out
    return "".join(
        table[ch] if ch in table
        else (f"\\u{ord(ch):04x}" if 1 <= ord(ch) < bound else ch)
        for ch in value)


def _render_like_exporter(doc, escape) -> str:
    """Serialize a document the way the exporter does: keys and string VALUES
    go through the escaper, at the string-value level only, and the finished
    document is never post-processed."""
    if isinstance(doc, str):
        return '"' + escape(doc) + '"'
    if isinstance(doc, bool):
        return "true" if doc else "false"
    if isinstance(doc, (int, float)):
        return json.dumps(doc)
    if isinstance(doc, dict):
        return "{" + ", ".join(
            '"' + escape(k) + '": ' + _render_like_exporter(v, escape)
            for k, v in doc.items()) + "}"
    if isinstance(doc, list):
        return "[" + ", ".join(_render_like_exporter(v, escape) for v in doc) + "]"
    raise AssertionError(f"unserializable value {doc!r}")


def test_exporter_declares_a_rule_for_every_character_json_forbids():
    name, body = _mql5_function("[Ee]scape")
    rules, bound = _escape_rules(body)
    table = dict(rules)
    assert table or bound, (
        f"{name}() exposes no escape rule the extractor can read — if the "
        f"implementation style changed, teach _escape_rules() about it "
        "(layer 1 pins the JSON semantics independently)")
    # the named escapes must be exactly the canonical JSON forms
    for ch in NAMED_ESCAPE_CHARS:
        expected = _json_string_literal(ch)[1:-1]
        assert table.get(ch) == expected, (
            f"{name}() must turn {ch!r} into {expected!r}, "
            f"got {table.get(ch)!r}")
    # a backslash introduced later would corrupt the escapes added before it
    if re.search(r"\bStringReplace\s*\(", body):
        assert rules[0][0] == "\\", (
            f"{name}() must escape the backslash BEFORE introducing any "
            "other escape sequence")
    # nothing in the control range may survive raw, whether it is listed
    # one-by-one or covered by a generic rule
    raw = [code for code in range(1, 0x20)
           if chr(code) not in table and not (bound and code < bound)]
    assert not raw, (
        f"{name}() leaves {len(raw)} control character(s) raw "
        f"(first: U+{raw[0]:04X}) — JSON forbids them")


def test_exporter_escaped_values_decode_back_to_the_broker_value():
    problems = []
    for value in JSON_STRING_SAMPLES:
        literal = '"' + _exporter_escaped(value) + '"'
        if literal != _json_string_literal(value):
            problems.append(f"{value!r}: emits {literal}, canonical is "
                            f"{_json_string_literal(value)}")
            continue
        document = '{"symbol": {"path": ' + literal + "}}"
        try:
            if json.loads(document)["symbol"]["path"] != value:
                problems.append(f"{value!r}: round-trip changed the value")
        except json.JSONDecodeError as exc:
            problems.append(f"{value!r}: produces invalid JSON ({exc})")
    assert not problems, (
        "exporter escaping differs from JSON semantics:\n"
        + "\n".join(problems))


def test_every_broker_string_reaches_the_document_through_the_quoting_helper():
    """Statements (not physical lines) are scanned, so wrapped or reindented
    code is judged exactly like a single long line."""
    src = _exporter_source()
    quote_name, quote_body = _mql5_function("[Qq]uote")
    escape_name = _mql5_function("[Ee]scape")[0]
    # the quoting helper escapes; it does not merely wrap
    assert re.search(r"\b" + escape_name + r"\s*\(", quote_body), (
        f"{quote_name}() must delegate to {escape_name}() — quoting without "
        "escaping is the 2026-09-09 defect")
    main = src[src.index("void Main"):]
    offenders = []
    for statement in re.findall(r"j\s*\+=\s*(.*?);", main, re.DOTALL):
        code = "\n".join(line.split("//")[0] for line in statement.splitlines())
        reads_broker_text = ("SymbolInfoString(" in code
                             or "AccountInfoString(" in code
                             or "TimeToString(" in code)
        if reads_broker_text and not re.search(r"\b" + quote_name + r"\s*\(", code):
            offenders.append(" ".join(code.split()))
    assert not offenders, (
        f"string value(s) written without {quote_name}(): {offenders}")


# --- layer 3: harness behaviour on escaped vs malformed exports ------------


def test_exporter_output_is_accepted_by_the_parity_harness(tmp_path, capsys):
    """End-to-end for the fix: the document the fixed exporter builds is
    accepted by load_owner_export()/build_report() — no 'skipping malformed
    export' warning — and counts as the FX portion of the gate only."""
    from broker_symbol_parity import build_report
    doc = _synthetic_export(tmp_path, path="Forex\\EURUSD")
    p = tmp_path / "EURUSD.json"
    p.write_text(_render_like_exporter(doc, _exporter_escaped), encoding="utf-8")
    # the bytes on disk carry the escaped form, not the raw one
    assert '"path": ' + _json_string_literal("Forex\\EURUSD") \
        in p.read_text(encoding="utf-8")
    assert load_owner_export(p) == doc
    exports, rows, coverage = build_report(tmp_path)
    assert capsys.readouterr().err == "", "a valid export must not be skipped"
    assert len(exports) == 1 and rows
    assert coverage["FX"] == "exported: EURUSD"
    # one FX export does not complete the gate: the rest stays pending
    assert all(coverage[cls].startswith("PENDING")
               for cls in ("METAL", "INDEX_CFD", "CRYPTO"))


def test_malformed_export_is_skipped_and_never_repaired(tmp_path, capsys):
    """The pre-fix bytes, and the fail-closed rule that must keep applying:
    malformed JSON is reported and skipped, never silently repaired."""
    from broker_symbol_parity import build_report
    doc = _synthetic_export(tmp_path, path="Forex\\EURUSD")
    p = tmp_path / "EURUSD.json"
    raw = _render_like_exporter(doc, lambda value: value)   # old JsonQuote
    with pytest.raises(json.JSONDecodeError, match=r"Invalid \\escape"):
        json.loads(raw)
    p.write_text(raw, encoding="utf-8")
    exports, rows, coverage = build_report(tmp_path)
    err = capsys.readouterr().err
    assert "skipping malformed export" in err and "Invalid \\escape" in err
    assert exports == [] and rows == []
    assert all(v.startswith("PENDING") for v in coverage.values())
