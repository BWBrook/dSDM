"""Measure 28-worker portability against the existing frozen Linux canary.

Run on an allocated PBS compute node, in an isolated qualification checkout.
A passing receipt is evidence for review, not permission to start production.
The reference hash must be supplied from the accepted transfer manifest.
"""
from __future__ import annotations

import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
import multiprocessing
from pathlib import Path
import platform
import time

from dsdm_phase1 import goal052_seawfb_dsdm as runner
import goal052_canary24 as reference_checks


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--reference', type=Path, required=True)
    parser.add_argument('--reference-sha256', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    runner.require(not args.output.exists(), 'qualification_output_exists')
    runner.require(runner.sha256_file(args.reference) == args.reference_sha256,
                   'reference_canary_hash_drift')
    prior = runner.read_json(args.reference)
    identity = runner.validate_inputs(root)['identity']
    config = runner.config_at(root)
    runtime = runner.host_runtime('cpu')
    runner.require(prior['identity'] == identity and prior['status'] == 'goal052_canary_valid',
                   'reference_canary_identity_invalid')
    runner.require(prior['runtime']['device'] == 'cpu', 'cpu_reference_required')
    # The reference retains its original host/runtime; it is never rebound.
    block, fold, target = prior['block'], prior['fold'], prior['target']
    reference = reference_checks._scientific_fields(prior['results'][0])
    for result in prior['results']:
        reference_checks._verify_result(result, config, block, fold, target)
        runner.require(reference_checks._scientific_fields(result) == reference,
                       'reference_results_differ')
    drivers = {str(p.relative_to(root)): runner.sha256_file(p) for p in
               (Path(__file__).resolve(), Path(reference_checks.__file__).resolve())}
    started = time.monotonic()
    context = multiprocessing.get_context('spawn')
    with ProcessPoolExecutor(max_workers=28, mp_context=context,
                             initializer=reference_checks._initialize,
                             initargs=(context.Barrier(28),)) as pool:
        futures = [pool.submit(reference_checks._synchronized_worker,
                               str(root), 'cpu', identity, block, fold, target)
                   for _ in range(56)]
        results = [future.result() for future in futures]
    counts = Counter(result['pid'] for result in results)
    runner.require(len(counts) == 28 and set(counts.values()) == {2},
                   'canary_concurrency_not_exercised')
    for result in results:
        reference_checks._verify_result(result, config, block, fold, target)
        runner.require(reference_checks._scientific_fields(result) == reference,
                       'cross_host_numerical_agreement_failed')
    runner.require(runner.identity_at(root) == identity and
                   runner.host_runtime('cpu') == runtime and
                   runner.sha256_file(args.reference) == args.reference_sha256 and
                   all(runner.sha256_file(root / p) == sha for p, sha in drivers.items()),
                   'qualification_binding_changed')
    runner.atomic_json(args.output, {
        'status': 'goal052_canary_valid', 'identity': identity, 'runtime': runtime,
        'qualified_workers': 28, 'block': block, 'fold': fold, 'target': target,
        'architecture': 'seawfb_scale', 'scope': 'full_auxiliary_memory_bounded_one_epoch_optimization',
        'results': results, 'jobs_per_worker': dict(sorted(counts.items())),
        'synchronized_waves': 2, 'all_nonruntime_fields_match_prior': True,
        'comparison_excluded_runtime_fields': sorted(reference_checks._RUNTIME_FIELDS),
        'prior_canary_sha256': args.reference_sha256, 'driver_sha256': drivers,
        'platform': platform.platform(), 'duration_seconds': time.monotonic() - started,
        'peak_worker_rss_bytes': max(r['peak_rss_bytes'] for r in results),
        'resource_sampling': 'external_PBS_job_and_group_samples_required_for_review',
        'ecological_metrics_computed': False, 'outer_response_rows_read': 0,
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'production_authorized': False,
    })
    print(f'QUALIFICATION_CANARY_PASSED {args.output}', flush=True)


if __name__ == '__main__':
    main()
