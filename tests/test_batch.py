"""Batch/matrix path resolution."""

from pathlib import Path

import yaml

from harness.batch import _path_relative_to_matrix

REPO = Path(__file__).resolve().parents[1]


def test_matrix_scenario_dir_resolves_next_to_matrix_file_not_cwd():
    """Regression: ../scenarios/... in YAML must not escape the repo via cwd."""
    matrix_file = REPO / "experiments" / "coaching_ab_matrix.yaml"
    raw = yaml.safe_load(matrix_file.read_text(encoding="utf-8"))
    scenario_dir = _path_relative_to_matrix(matrix_file, str(raw["scenario_dir"]))
    assert scenario_dir is not None
    expected = (REPO / "scenarios" / "two-teams-shared-staging").resolve()
    assert scenario_dir == expected
