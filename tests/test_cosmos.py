"""The real-world physics layer: always-on local sources work offline, the seed
is well-formed, and reproducibility is preserved (a cosmic seed is still just a
logged integer the run reproduces from)."""

from pot import cosmos
from pot.soup import SoupConfig, run_soup, summarize


def test_local_sources_work_without_network():
    # hardware entropy + timing jitter + machine state must harvest with no net.
    digest, prov = cosmos.harvest(network=False)
    assert len(digest) == 64
    live = [p for p in prov if p["available"]]
    assert any(p["source"] == "hardware_entropy" for p in live)
    assert any(p["source"] == "timing_jitter" for p in live)


def test_cosmic_seed_is_well_formed_and_varies():
    s1, meta1 = cosmos.cosmic_seed(bits=64, network=False)
    s2, _ = cosmos.cosmic_seed(bits=64, network=False)
    assert 0 <= s1 < 2 ** 64
    assert meta1["sources_live"] >= 2          # at least the two always-on sources
    assert s1 != s2                            # physical entropy -> not repeatable


def test_resolve_seed_passthrough_when_not_cosmic():
    seed, origin = cosmos.resolve_seed(1234, cosmic=False)
    assert seed == 1234 and origin is None


def test_cosmic_run_is_reproducible_from_its_logged_seed():
    # The whole honesty claim: a cosmic origin still reproduces, because the seed
    # it produced is logged and the run is deterministic in that seed.
    seed, origin = cosmos.resolve_seed(0, cosmic=True, network=False)
    assert origin is not None
    cfg = dict(soup_size=64, tape_len=32, max_steps=128, epochs=300,
               checkpoint_every=100, seed=seed)
    a = summarize(run_soup(SoupConfig(**cfg)))
    b = summarize(run_soup(SoupConfig(**cfg)))
    assert a == b


def test_physical_sample_shape():
    v = cosmos.physical_sample(32)
    assert v.shape == (32,)
    assert v.dtype.kind == "u"
