"""Map geometry: the minimap transform and the outline tracer, on synthetic inputs only."""
import numpy as np
import pytest

from opscope import geometry as G


@pytest.fixture
def fake_map(monkeypatch):
    """A made-up map whose transform looks like the real ones (x runs up the minimap, y across)."""
    tf = {"testmap": {"x_mult": 1e-4, "y_mult": -1e-4, "x_add": 0.5, "y_add": 0.5}}
    monkeypatch.setattr(G, "transforms", lambda: tf)
    return "testmap"


def test_transform_swaps_axes_like_the_official_minimap(fake_map):
    # +x (game) goes up the minimap, +y goes right: the opposite of a plain x/y scatter, which mirrors maps.
    u, v = G.to_minimap(fake_map, [0, 1000, 0], [0, 0, 1000])
    assert u.tolist() == pytest.approx([500, 500, 600])
    assert v.tolist() == pytest.approx([500, 400, 500])


def test_rotation_keeps_handedness_and_puts_attackers_at_the_bottom():
    u, v = G.rotate([500, 1000], [0, 500], 1)  # one quarter turn clockwise: top -> right, right -> bottom
    assert u.tolist() == pytest.approx([1000, 500])
    assert v.tolist() == pytest.approx([500, 1000])
    for attacker, turns in [((500, 950), 0), ((950, 500), 1), ((500, 50), 2), ((50, 500), 3)]:
        assert G.turns_for(attacker) == turns
        assert G.rotate(*attacker, turns)[1] == pytest.approx(950)


def test_clean_mask_drops_specks_and_fills_small_wall_holes():
    hits = np.zeros((60, 60))
    hits[10:50, 10:50] = 3          # a room
    hits[28:31, 28:31] = 0          # a tiny gap in the floor (a missing reading): filled
    hits[2, 2] = 5                  # a stray reading far away: dropped
    m = G.clean_mask(hits, blur=0)
    assert m[29, 29] and not m[2, 2]
    assert m[10:50, 10:50].all()


def test_trace_and_straighten_give_a_clean_l_shape():
    mask = np.zeros((40, 40), dtype=bool)
    mask[5:35, 5:15] = True
    mask[25:35, 5:35] = True
    rings = G.trace_rings(mask)
    assert len(rings) == 1
    ring = G.straighten(G.rdp(rings[0], 1.0))
    assert len(ring) == 6  # an L has six corners
    d = np.roll(ring, -1, 0) - ring
    assert np.all((np.abs(d[:, 0]) < 1e-6) | (np.abs(d[:, 1]) < 1e-6))  # every wall axis-aligned
    assert abs(G._area(ring)) == pytest.approx(30 * 10 + 10 * 20)


def test_floor_rings_wrap_the_positions(fake_map):
    rng = np.random.default_rng(0)
    # a 20 m x 8 m corridor of positions, in game units (cm)
    x = rng.uniform(0, 2000, 20000)
    y = rng.uniform(0, 800, 20000)
    rings = G.floor_rings(fake_map, x, y)
    assert len(rings) == 1
    r = np.array(rings[0])
    u, v = G.to_minimap(fake_map, [1000], [400])  # the corridor centre is inside the outline
    assert r[:, 0].min() < u[0] < r[:, 0].max() and r[:, 1].min() < v[0] < r[:, 1].max()
    # 20 m along game x becomes ~200 minimap units tall; 8 m along y ~80 wide
    assert (r[:, 1].max() - r[:, 1].min()) == pytest.approx(200, abs=12)
    assert (r[:, 0].max() - r[:, 0].min()) == pytest.approx(80, abs=12)


def test_trace_icon_reads_floor_walls_props_and_sites():
    """A synthetic minimap: transparent outside, grey floor with a wall hole, a lighter prop, an olive site."""
    img = np.zeros((100, 100, 4), dtype=np.uint8)
    img[10:90, 10:90] = (118, 118, 118, 255)      # floor
    img[40:60, 40:60] = (0, 0, 0, 0)              # a wall block (hole)
    img[15:25, 15:30] = (140, 140, 140, 255)      # a prop (box)
    img[70:88, 65:88] = (152, 152, 118, 255)      # a plant site (olive)
    layers = G.trace_icon(img)
    assert len(layers["rings"]) == 2               # the outline and the wall block
    outer = np.array(layers["rings"][0])
    assert outer[:, 0].min() == pytest.approx(100) and outer[:, 0].max() == pytest.approx(900)
    assert len(layers["props"]) == 1 and len(layers["site_areas"]) == 1
    site = np.array(layers["site_areas"][0])
    assert site[:, 0].min() == pytest.approx(650) and site[:, 1].max() == pytest.approx(880)


def test_markers_on_a_wall_snap_onto_the_floor():
    room = [[0, 0], [100, 0], [100, 100], [0, 100]]
    pillar = [[40, 40], [60, 40], [60, 60], [40, 60]]
    rings = [room, pillar]
    assert G.inside([10, 10], rings) and not G.inside([50, 50], rings) and not G.inside([150, 50], rings)
    for p in ([50, 45], [150, 50]):  # inside the pillar, and off the map to the right
        q = G.snap_to_floor(p, rings)
        assert G.inside(q, rings)
    assert G.snap_to_floor([10, 10], rings) == [10, 10]
