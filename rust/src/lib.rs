//! Fast BFF interpreter for the-pot.
//!
//! This is a byte-for-byte port of `pot/bff.py::run_tape`. The Python file is
//! the correctness oracle; `tests/test_bff.py` cross-checks this against it on
//! random tapes. Do not change the semantics here without changing the oracle
//! and the tests together.
//!
//! The only public entry point is [`run_batch`], which crosses the Python↔Rust
//! boundary once per epoch (not once per pair) and runs the whole batch in
//! parallel with rayon while the GIL is released.

use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList};
use rayon::prelude::*;

const GT: u8 = b'>';
const LT: u8 = b'<';
const RB: u8 = b'}';
const LB: u8 = b'{';
const PLUS: u8 = b'+';
const MINUS: u8 = b'-';
const DOT: u8 = b'.';
const COMMA: u8 = b',';
const OPEN: u8 = b'[';
const CLOSE: u8 = b']';

/// Execute `t` in place. Mirrors `pot.bff.run_tape` exactly. Returns steps.
fn run_tape(t: &mut [u8], max_steps: usize) -> usize {
    let n = t.len();
    if n == 0 {
        return 0;
    }
    // ip is signed-ish: it can transiently go to -1 or n via `ip += 1` after a
    // jump, so we track it as i64 and bounds-check like `0 <= ip < n`.
    let mut ip: i64 = 0;
    let mut h0: usize = 0;
    let mut h1: usize = 0;
    let mut steps: usize = 0;

    while steps < max_steps && ip >= 0 && (ip as usize) < n {
        let ipu = ip as usize;
        let c = t[ipu];
        match c {
            GT => h0 = (h0 + 1) % n,
            LT => h0 = (h0 + n - 1) % n,
            RB => h1 = (h1 + 1) % n,
            LB => h1 = (h1 + n - 1) % n,
            PLUS => t[h0] = t[h0].wrapping_add(1),
            MINUS => t[h0] = t[h0].wrapping_sub(1),
            DOT => t[h1] = t[h0],
            COMMA => t[h0] = t[h1],
            OPEN => {
                if t[h0] == 0 {
                    let mut depth: i64 = 1;
                    let mut j = ipu + 1;
                    while j < n && depth != 0 {
                        if t[j] == OPEN {
                            depth += 1;
                        } else if t[j] == CLOSE {
                            depth -= 1;
                        }
                        j += 1;
                    }
                    if depth != 0 {
                        break;
                    }
                    ip = j as i64 - 1;
                }
            }
            CLOSE => {
                if t[h0] != 0 {
                    let mut depth: i64 = 1;
                    // j starts at ip-1; may fall to -1, matching the Python
                    // `while j >= 0` guard. Track as i64.
                    let mut j: i64 = ip - 1;
                    while j >= 0 && depth != 0 {
                        let bj = t[j as usize];
                        if bj == CLOSE {
                            depth += 1;
                        } else if bj == OPEN {
                            depth -= 1;
                        }
                        j -= 1;
                    }
                    if depth != 0 {
                        break;
                    }
                    ip = j + 1;
                }
            }
            _ => {} // inert data byte
        }
        ip += 1;
        steps += 1;
    }
    steps
}

/// Run a batch of concatenated tape-pairs in place, in parallel.
///
/// `pairs`: each inner list is the concatenation of two tapes (already joined
/// by the caller). Each is executed with identical semantics to
/// `pot.bff.run_tape` and the mutated bytes are returned in the same order.
#[pyfunction]
fn run_batch(py: Python<'_>, pairs: Vec<Vec<u8>>, max_steps: usize) -> PyResult<Py<PyList>> {
    // Release the GIL for the compute-heavy part so multiple soup workers can
    // truly run in parallel, and fan the batch across cores with rayon.
    let mut bufs = pairs;
    py.allow_threads(|| {
        bufs.par_iter_mut().for_each(|buf| {
            run_tape(buf.as_mut_slice(), max_steps);
        });
    });

    let out = PyList::empty(py);
    for buf in &bufs {
        out.append(PyBytes::new(py, buf))?;
    }
    Ok(out.into())
}

#[pymodule]
fn _rust(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(run_batch, m)?)?;
    m.add("__doc__", "Fast batched BFF interpreter (rayon-parallel).")?;
    Ok(())
}
