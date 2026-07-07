"""pot.bff — the verified reference BFF interpreter.

BFF is a tiny self-modifying Brainfuck variant where *program == data*: the
tape being executed is also the tape being written to. Two tapes are
concatenated so that, during an interaction, either can read from or write
into the other. There is no separate data pointer register file — only two
heads (h0, h1) that roam a single shared byte array.

This module is the correctness *oracle*. The Rust port in ``rust/src/lib.rs``
must reproduce these semantics byte-for-byte; ``tests/test_bff.py`` pins the
primitives and cross-checks Rust against this file. When in doubt, this is
ground truth. Do not "optimize" the semantics here — port them.

Semantics (all wrapping / modular, matching a real byte machine):
  >  h0 = (h0 + 1) mod n        move read head right
  <  h0 = (h0 - 1) mod n        move read head left
  }  h1 = (h1 + 1) mod n        move write head right
  {  h1 = (h1 - 1) mod n        move write head left
  +  t[h0] = (t[h0] + 1) & 255  increment cell under read head
  -  t[h0] = (t[h0] - 1) & 255  decrement cell under read head
  .  t[h1] = t[h0]              copy read-head cell -> write-head cell
  ,  t[h0] = t[h1]              copy write-head cell -> read-head cell
  [  if t[h0] == 0: jump past matching ]   (dynamic scan, no precompile)
  ]  if t[h0] != 0: jump to matching [     (lands *after* the [, a BFF quirk)

Halting: unmatched bracket, ip running off either end, or the step budget.
"""

from __future__ import annotations

GT, LT = ord(">"), ord("<")
RB, LB = ord("}"), ord("{")
PLUS, MINUS = ord("+"), ord("-")
DOT, COMMA = ord("."), ord(",")
OPEN, CLOSE = ord("["), ord("]")

# The only bytes that mean anything. Everything else is an inert "data" byte
# (a no-op under the ip) — which is exactly what lets program and data share
# one address space.
INSTRUCTION_SET = bytes([GT, LT, RB, LB, PLUS, MINUS, DOT, COMMA, OPEN, CLOSE])


def run_tape(tape, max_steps: int = 1024) -> int:
    """Execute ``tape`` (a mutable bytearray) in place. Returns steps taken.

    The tape is modified in place; callers read the result out of ``tape``
    after the call. This is the reference semantics — see module docstring.
    """
    n = len(tape)
    ip = h0 = h1 = steps = 0
    t = tape
    while steps < max_steps and 0 <= ip < n:
        c = t[ip]
        if c == GT:
            h0 = (h0 + 1) % n
        elif c == LT:
            h0 = (h0 - 1) % n
        elif c == RB:
            h1 = (h1 + 1) % n
        elif c == LB:
            h1 = (h1 - 1) % n
        elif c == PLUS:
            t[h0] = (t[h0] + 1) & 255
        elif c == MINUS:
            t[h0] = (t[h0] - 1) & 255
        elif c == DOT:
            t[h1] = t[h0]
        elif c == COMMA:
            t[h0] = t[h1]
        elif c == OPEN:
            if t[h0] == 0:
                depth, j = 1, ip + 1
                while j < n and depth:
                    if t[j] == OPEN:
                        depth += 1
                    elif t[j] == CLOSE:
                        depth -= 1
                    j += 1
                if depth:
                    break
                ip = j - 1
        elif c == CLOSE:
            if t[h0] != 0:
                depth, j = 1, ip - 1
                while j >= 0 and depth:
                    if t[j] == CLOSE:
                        depth += 1
                    elif t[j] == OPEN:
                        depth -= 1
                    j -= 1
                if depth:
                    break
                ip = j + 1
        ip += 1
        steps += 1
    return steps


def run_batch_py(pairs, max_steps: int = 1024):
    """Pure-Python batched entry point mirroring the Rust signature.

    ``pairs`` is a sequence of bytes-like objects, each already the
    concatenation of two tapes. Each is run in place and the mutated bytes are
    returned as a list of ``bytearray``. This is the fallback path used when
    the compiled ``pot._rust`` extension is unavailable.
    """
    out = []
    for p in pairs:
        b = bytearray(p)
        run_tape(b, max_steps)
        out.append(b)
    return out
