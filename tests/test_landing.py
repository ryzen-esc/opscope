"""Tests for the landing-spot model (synthetic throws only)."""
import numpy as np
import pandas as pd

from opscope.analytics.landing import fit, predict, validate


def throws(n=400, seed=0, ability="snake-bite"):
    """Synthetic casts: steeper upward aim throws farther (1000 cm + 40 cm per degree), plus noise."""
    rng = np.random.default_rng(seed)
    pitch = rng.uniform(-20, 20, n)
    yaw = rng.uniform(0, 2 * np.pi, n)
    vz = np.sin(np.radians(pitch))
    h = np.cos(np.radians(pitch))
    vx, vy = np.cos(yaw) * h, np.sin(yaw) * h
    x, y = rng.uniform(-5000, 5000, n), rng.uniform(-5000, 5000, n)
    dist = 1000 + 40 * pitch
    tx = x + np.cos(yaw) * dist + rng.normal(0, 150, n)
    ty = y + np.sin(yaw) * dist + rng.normal(0, 150, n)
    df = pd.DataFrame({"x": x, "y": y, "view_x": vx, "view_y": vy, "view_z": vz, "tx": tx, "ty": ty,
                       "ability": ability, "series_id": [f"s{i % 50}" for i in range(n)], "pitch": pitch})
    df["along"] = (df["tx"] - df["x"]) * np.cos(yaw) + (df["ty"] - df["y"]) * np.sin(yaw)
    return df


def test_prediction_lies_along_the_aim_at_the_learned_distance():
    model = fit(throws())
    one = pd.DataFrame({"x": [0.0], "y": [0.0], "view_x": [0.0], "view_y": [1.0], "view_z": [0.0], "ability": ["snake-bite"]})
    px, py = predict(model, one)
    assert abs(px[0]) < 1                          # straight along +y, no sideways drift
    assert 900 < py[0] < 1150                      # ~1000 cm at a flat aim


def test_steeper_aim_goes_farther():
    model = fit(throws())
    aim = lambda deg: pd.DataFrame({"x": [0.0], "y": [0.0], "view_x": [np.cos(np.radians(deg))], "view_y": [0.0],
                                    "view_z": [np.sin(np.radians(deg))], "ability": ["snake-bite"]})
    assert predict(model, aim(15))[0][0] > predict(model, aim(-15))[0][0] + 600


def test_unknown_abilities_get_no_estimate():
    model = fit(throws())
    other = pd.DataFrame({"x": [0.0], "y": [0.0], "view_x": [1.0], "view_y": [0.0], "view_z": [0.0], "ability": ["dark-cover"]})
    assert np.isnan(predict(model, other)[0][0])


def test_validation_beats_the_cast_spot_on_held_out_series():
    report = validate(throws(n=1000))
    assert report["median_model_m"] < report["median_fixed_m"] < report["median_cast_m"]
    assert report["median_model_m"] < 3            # noise is 1.5 m per axis
