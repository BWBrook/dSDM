"""Failure and provenance boundaries for the approved numerical recovery."""
import json
from pathlib import Path

import pytest

from dsdm_phase1 import goal051_seawfb_conventional as science
from dsdm_phase1 import goal051_nectar_execution as nectar
from dsdm_phase1.seawfb_modeling import SeawfbModelingError

ROOT = Path(__file__).resolve().parents[1]


def test_failed_surface_is_recorded_before_exception_leaves_worker(tmp_path, monkeypatch, capsys):
    config = science._config(ROOT)
    monkeypatch.setattr(science, '_identity', lambda root: {'version': 'v4'})
    error = SeawfbModelingError('tertiary_failed')
    error.attempts = [{'attempt': 'tertiary', 'n_iter': 20000}]

    def fail(*args, **kwargs):
        raise error

    monkeypatch.setattr(science, 'fit_q_linear', fail)
    with pytest.raises(SeawfbModelingError, match='tertiary_failed'):
        science.prepare_q_surface(tmp_path, object(), config, 1, 0, 'full')
    model, receipt = science._q_paths(tmp_path, config, 1, 0, 'full')
    failure = json.loads(receipt.with_suffix('.failure.json').read_text())
    assert failure['attempts'] == error.attempts
    assert (failure['held_block'], failure['held_fold'], failure['auxiliary_size']) == (1, 0, 'full')
    assert failure['identity'] == {'version': 'v4'}
    assert not model.exists() and not receipt.exists()
    assert 'tertiary_failed' in capsys.readouterr().out


def test_target_cli_requires_complete_q_before_scheduling(tmp_path, monkeypatch):
    monkeypatch.setattr(science, '_config', lambda root: science_config)
    science_config = {'execution': {'default_workers': 16}}
    monkeypatch.setattr(science, 'validate_inputs', lambda root: {})

    def incomplete(root, config, require_complete):
        assert require_complete is True
        raise SeawfbModelingError('q_surface_completion_failed')

    monkeypatch.setattr(science, 'q_provenance', incomplete)
    monkeypatch.setattr(science, '_run_parallel', lambda *args: pytest.fail('target scheduled before q gate'))
    with pytest.raises(SeawfbModelingError, match='q_surface_completion_failed'):
        science.main(['run', '--root', str(tmp_path)])


def test_stress_requires_valid_current_checkpoint(tmp_path, monkeypatch):
    monkeypatch.setattr(science, '_identity', lambda root: {'version': 'v4'})
    monkeypatch.setattr(science, '_config', lambda root: {'execution': {'private_root': 'v4'}})
    monkeypatch.setattr(science, '_load_q', lambda *args: None)
    with pytest.raises(SeawfbModelingError, match='stress_missing'):
        nectar.stress_evidence(tmp_path)


def test_stress_checkpoint_is_separate_from_production():
    normal = science._config(ROOT)
    stress = nectar._stress_config(ROOT)
    assert science._q_paths(ROOT, normal, 1, 0, 'full') != science._q_paths(ROOT, stress, 1, 0, 'full')
    assert normal['community_control'] == stress['community_control']
