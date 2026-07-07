"""Primitive correctness for the BFF VM, and Rust-vs-oracle equivalence.

``pot.bff.run_tape`` is the oracle. Every hand-computed expectation below was
traced by hand from the module docstring's semantics. The Rust extension, when
built, must reproduce the oracle byte-for-byte on random tapes.
"""

import random

import pytest

import pot
from pot import bff
from pot.bff import (
    INSTRUCTION_SET, run_tape, GT, LT, RB, LB, PLUS, MINUS, DOT, COMMA, OPEN, CLOSE,
)


def _run(bytes_in, max_steps=1024):
    t = bytearray(bytes_in)
    steps = run_tape(t, max_steps)
    return bytes(t), steps


# --- single-primitive traces (hand-computed) --------------------------------

def test_gt_then_plus_increments_cell_one():
    # '>' moves read head to cell 1; '+' increments cell 1 ('+'=43 -> 44).
    out, steps = _run(b">+")
    assert out == bytes([GT, PLUS + 1])
    assert steps == 2


def test_minus_wraps_and_decrements():
    out, _ = _run(b">-")
    assert out == bytes([GT, MINUS - 1])  # '-'=45 -> 44


def test_plus_wraps_mod_256():
    # cell holding 255 ('+' path): put a 255 data byte under h0 and increment.
    # '>' -> h0=1; cell1 is 255; '+' -> 0.
    out, _ = _run(bytes([GT, 255]))
    assert out[1] == 255  # only two cells, second op is data(255), no '+' ran
    # now with an explicit '+': cells [>, 255, +]; h0=1 at the '+'
    out2, _ = _run(bytes([GT, 255, PLUS]))
    assert out2[1] == 0  # 255 + 1 wrapped to 0


def test_dot_copies_read_to_write_head():
    # '>' -> h0=1 (h1 stays 0); '.' writes t[h1=0] = t[h0=1].
    out, _ = _run(b">.")
    assert out[0] == DOT  # cell0 became a copy of cell1 ('.')
    assert out == bytes([DOT, DOT])


def test_comma_copies_write_to_read_head():
    # '}' -> h1=1 (h0 stays 0); ',' writes t[h0=0] = t[h1=1].
    out, _ = _run(b"},")
    assert out == bytes([COMMA, COMMA])


def test_head_movement_is_modular():
    # '<' from h0=0 wraps to the last cell; '+' then hits that last cell.
    # tape [<, +, data0]: '<' -> h0 = n-1 = 2; '+' -> t[2] = 0+1 = 1.
    out, _ = _run(bytes([LT, PLUS, 0]))
    assert out[2] == 1


def test_open_bracket_skips_when_zero():
    # [GT, 0, OPEN, PLUS, CLOSE]: '>' -> h0=1 (a zero cell); '[' sees 0 and
    # jumps past the matching ']', so the '+' is never executed.
    out, _ = _run(bytes([GT, 0, OPEN, PLUS, CLOSE]))
    assert out[1] == 0          # cell1 untouched -> the body was skipped
    assert out[3] == PLUS       # the '+' instruction itself unchanged


def test_self_modification_can_break_a_loop():
    # program == data: '[+]' looks like a loop but the '+' increments cell0,
    # which *is* the '[' byte (91 -> 92). When ']' scans back for its matching
    # '[', the byte is no longer '[', the match fails, and it halts. This quirk
    # is real and intended — pin it so a "fix" can't silently change semantics.
    _, steps = _run(b"[+]", max_steps=64)
    assert steps == 2


def test_close_bracket_loops_when_body_preserves_brackets():
    # '[><]' loops forever: the body only moves heads (never writes), so cell0
    # stays '[' (nonzero) and the brackets are never overwritten. With a tight
    # budget it must still be looping.
    _, steps = _run(b"[><]", max_steps=64)
    assert steps == 64


def test_unmatched_bracket_halts():
    # A lone '[' over a zero cell has no matching ']': must break, not spin.
    out, steps = _run(bytes([GT, 0, OPEN]), max_steps=1000)
    assert steps < 1000


def test_empty_and_tiny_tapes_are_safe():
    assert run_tape(bytearray(b""), 100) == 0
    assert run_tape(bytearray(b"+"), 100) >= 0


def test_step_budget_never_exceeded():
    rng = random.Random(1)
    for _ in range(200):
        L = rng.randint(1, 64)
        data = bytes(rng.randint(0, 255) for _ in range(L))
        _, steps = _run(data, max_steps=50)
        assert steps <= 50


# --- Rust <-> oracle equivalence --------------------------------------------

@pytest.mark.skipif(not pot.HAVE_RUST, reason="Rust extension not built")
def test_rust_matches_oracle_on_random_tapes():
    rng = random.Random(12345)
    IS = INSTRUCTION_SET
    mism = 0
    for _ in range(3000):
        L = rng.randint(2, 256)
        # bias toward instruction bytes so real programs (loops) get exercised
        data = bytes(
            rng.choice(IS) if rng.random() < 0.65 else rng.randint(0, 255)
            for _ in range(L)
        )
        max_steps = rng.choice([64, 256, 1024])
        a = bytearray(data)
        bff.run_tape(a, max_steps)
        b = pot.run_batch([data], max_steps)[0]
        if bytes(a) != bytes(b):
            mism += 1
    assert mism == 0, f"{mism} Rust/oracle mismatches"


@pytest.mark.skipif(not pot.HAVE_RUST, reason="Rust extension not built")
def test_rust_batch_preserves_order_and_length():
    rng = random.Random(7)
    pairs = [bytes(rng.randint(0, 255) for _ in range(rng.randint(4, 40)))
             for _ in range(50)]
    out = pot.run_batch(pairs, 256)
    assert len(out) == len(pairs)
    for p, o in zip(pairs, out):
        assert len(o) == len(p)
