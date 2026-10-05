from pathlib import Path
import importlib.util, json, time
ROOT = Path('/Users/bwbrook/papers/dSDM')
HOST = 'utas-ubuntu'
RUNREL = 'data/processed/dsdm/goal052-seawfb-dsdm-experiment/outer-assessment-20261003-r2'
REMOTE = '/data/codex/repos/dSDM-outer-20261003-r2'
rr = REMOTE + '/' + RUNREL
run = ROOT / RUNREL
control = run / 'postproduction-control-005'
rc = REMOTE + '/postproduction-control-005'
spec = importlib.util.spec_from_file_location('outer_complete', ROOT / 'scripts/goal052_outer_complete.py')
c = importlib.util.module_from_spec(spec)
spec.loader.exec_module(c)
t = c.SubprocessTransport()
deadline = time.monotonic() + 3 * 3600
def require(condition, message):
    if not condition:
        raise c.ControllerError(message)

manifest = json.loads((control / 'manifest.json').read_bytes())
digest = manifest['plan_digest']
closure_sha = manifest['closure_sha256']
FAILED_SHA = 'bb2e4c50c07e86476edd747fc0999ce455e0ac98a65450645576b371d8433f77'
MANIFEST_SHA = 'a5bfa5d9ff02b96d6430828844751dd8519c7c9715c3e6d17580c8bf1b84ab1a'
REASON = 'report exited without a completion receipt'
require(c.sha256_file(control / 'complete.json') == FAILED_SHA, 'prior failure changed')
require(c.sha256_file(control / 'manifest.json') == MANIFEST_SHA, 'attempt005 manifest changed')
failed = json.loads((control / 'complete.json').read_bytes())
require(failed['status'] == 'failed' and failed['success'] is False and failed['reason'] == REASON, 'wrong prior failure')
require(not (control / 'return-complete-006.json').exists() and not (run / 'returned-files.json').exists(), 'return already completed')

def completed_stage(name, expected_pid, expected_sha):
    marker = json.loads((control / (name + '-process.json')).read_bytes())
    require(marker['pid'] == expected_pid, 'stage launch PID drift')
    receipt, raw = c._ssh_json(t, HOST, rc + '/' + name + '/stage.json', deadline, time.monotonic)
    require(receipt == {'status': 'complete', 'stage': name, 'pid': expected_pid, 'return_code': 0}, 'stage not successfully complete')
    require(c.sha256_bytes(raw) == expected_sha, 'completed stage receipt changed')
    local_stage = control / 'remote-postproduction' / name / 'stage.json'
    if local_stage.exists():
        require(local_stage.read_bytes() == raw, 'returned stage receipt differs')
    else:
        c._immutable_bytes(local_stage, raw)
    return dict(receipt, remote_status_sha256=expected_sha)

require(c.sha256_file(ROOT / 'scripts/goal052_outer_complete.py') == manifest['completion_helper_sha256'], "c.sha256_file(ROOT / 'scripts/goal052_outer_complete.py') == manifest['completion_helper_sha256']")
c._immutable_bytes(control / 'return-source-006.py', Path(__file__).read_bytes())
try:
    score_stage = completed_stage('score', 597547, '65ee80a967cf805a0bfae8d62cf61679333008f243408e21c50f8c2cd9e50f3e')
    report_stage = completed_stage('report', 609488, '892f7dab94e10e02d130c06b5db501934e8492022eeedc23df78e9567018f134')
    optional = c._return_optional_receipts(t, HOST, rr, run, ('response-access.json', 'response-access-success.json', 'scoring-failure.json'), deadline, time.monotonic, time.sleep)
    require('scoring-failure.json' not in optional, "'scoring-failure.json' not in optional")
    require(set(optional) == {'response-access.json', 'response-access-success.json'}, "set(optional) == {'response-access.json', 'response-access-success.json'}")
    require(c.sha256_file(run / 'response-access.json') == manifest['prior_access_sha256'], 'original response-access receipt changed')
    recovery_dir = control / 'remote-postproduction/recovery'
    recovery_dir.mkdir(parents=True, exist_ok=True)
    c._rsync(t, HOST + ':' + rc + '/recovery/', str(recovery_dir) + '/', deadline, time.monotonic, time.sleep)
    for path in sorted(recovery_dir.rglob('*')):
        if path.is_file():
            relative = str(path.relative_to(recovery_dir))
            require(c._remote_sha256(t, HOST, rc + '/recovery/' + relative, deadline, time.monotonic, time.sleep) == c.sha256_file(path), 'recovery receipt transfer drift')
    recovery_success = json.loads((recovery_dir / 'response-access-recovery-success.json').read_bytes())
    require(recovery_success['status'] == 'scoring_complete', 'recovery did not finish')
    require(recovery_success['native_access_success_sha256'] == c.sha256_file(run / 'response-access-success.json'), 'recovery success binding drift')
    rp = recovery_success['recovery_provenance']
    require(rp['recovery_helper_sha256'] == manifest['recovery_helper_sha256'] and rp['inventory_certificate_sha256'] == manifest['inventory_certificate_sha256'] and rp['inventory_proof_sha256'] == manifest['inventory_proof_sha256'] and rp['prior_access_sha256'] == manifest['prior_access_sha256'], 'recovery provenance drift')
    print(json.dumps({'status': 'scoring_completed', 'receipt_sha256': score_stage['remote_status_sha256']}), flush=True)
    old = json.loads((run / 'continuation-control-002/manifest.json').read_bytes())
    reporter_sha = old['source_hashes'][c.REPORT_RELATIVE]
    require(c.sha256_file(ROOT / c.REPORT_RELATIVE) == reporter_sha, 'c.sha256_file(ROOT / c.REPORT_RELATIVE) == reporter_sha')
    require(c._remote_sha256(t, HOST, REMOTE + '/' + c.REPORT_RELATIVE, deadline, time.monotonic, time.sleep) == reporter_sha, "c._remote_sha256(t, HOST, REMOTE + '/' + c.REPORT_RELATIVE, deadline, time.monotonic, time.sleep) == reporter_sha")
    require(c._remote_sha256(t, HOST, rr + '/scores.json', deadline, time.monotonic, time.sleep) == recovery_success['scores_sha256'], 'remote score receipt drift')
    require(c._remote_sha256(t, HOST, rr + '/closure.json', deadline, time.monotonic, time.sleep) == closure_sha, "c._remote_sha256(t, HOST, rr + '/closure.json', deadline, time.monotonic, time.sleep) == closure_sha")
    closure = json.loads((run / 'closure.json').read_bytes())
    require(c.sha256_file(run / 'closure.json') == closure_sha, "c.sha256_file(run / 'closure.json') == closure_sha")
    print(json.dumps({'status': 'returning_verified_artifacts'}), flush=True)
    returned = c._return_artifacts(t, HOST, REMOTE, rr, rc, run, control, closure, deadline, time.monotonic, time.sleep, attempt='002')
    require(c.sha256_file(run / 'closure.json') == closure_sha, "c.sha256_file(run / 'closure.json') == closure_sha")
    require(c.sha256_file(control / 'response-transfer.json') == c.sha256_file(control / 'remote-postproduction/response-transfer.json'), "c.sha256_file(control / 'response-transfer.json') == c.sha256_file(control / 'remote-postproduction/response-transfer.json')")
    require(c.sha256_file(control / 'independent-audit.json') == c.sha256_file(control / 'remote-postproduction/audit/independent-audit.json'), "c.sha256_file(control / 'independent-audit.json') == c.sha256_file(control / 'remote-postproduction/audit/independent-audit.json')")
    scores = json.loads((run / 'scores.json').read_bytes())
    require(c.sha256_file(run / 'scores.json') == recovery_success['scores_sha256'], 'scores differ from recovery receipt')
    require(scores['recovery_provenance'] == recovery_success['recovery_provenance'], 'score recovery provenance differs')
    prov = scores['response_provenance']
    require(prov['registered_active_species_count'] == 505 and prov['registered_effort_donor_count'] == 505 and prov['serialized_nonempty_species_count'] == 449 and prov['canonical_membership_rows'] == 5048061, 'response inventory semantics drift')
    require(scores['schema_version'] == 'goal052-outer-scores-v1' and scores['plan_digest'] == digest and (scores['closure_sha256'] == closure_sha), "scores['schema_version'] == 'goal052-outer-scores-v1' and scores['plan_digest'] == digest and (scores['closure_sha256'] == closure_sha)")
    require(prov['schema_version'] == 'goal052-outer-response-provenance-v1' and prov['plan_digest'] == digest and (prov['closure_file_sha256'] == closure_sha), "prov['schema_version'] == 'goal052-outer-response-provenance-v1' and prov['plan_digest'] == digest and (prov['closure_file_sha256'] == closure_sha)")
    require(prov['canonical_species_cells_sha256'] == manifest['response_metadata']['response_sha256'] and prov['closure_digest'] == closure['closure_digest'], "prov['canonical_species_cells_sha256'] == manifest['response_metadata']['response_sha256'] and prov['closure_digest'] == closure['closure_digest']")
    start = json.loads((run / 'response-access.json').read_bytes())
    success = json.loads((run / 'response-access-success.json').read_bytes())
    require(start['status'] == 'response_access_started' and success['status'] == 'response_access_complete', "start['status'] == 'response_access_started' and success['status'] == 'response_access_complete'")
    require(success['access_started_sha256'] == c.sha256_file(run / 'response-access.json'), "success['access_started_sha256'] == c.sha256_file(run / 'response-access.json')")
    for x in (start, success):
        require(x['immutable'] is True and x['closure_file_sha256'] == closure_sha and (x['closure_digest'] == closure['closure_digest']) and (x['plan_digest'] == digest), "x['immutable'] is True and x['closure_file_sha256'] == closure_sha and (x['closure_digest'] == closure['closure_digest']) and (x['plan_digest'] == digest)")
        require(x['canonical_species_cells_sha256'] == manifest['response_metadata']['response_sha256'] and x['domain_rows'] == 144860, "x['canonical_species_cells_sha256'] == manifest['response_metadata']['response_sha256'] and x['domain_rows'] == 144860")
    require(start['target_inventory_sha256'] == success['target_inventory_sha256'] and success['target_count'] == 157, "start['target_inventory_sha256'] == success['target_inventory_sha256'] and success['target_count'] == 157")
    result = {'schema_version': 'goal052-outer-postproduction-completion-v1', 'status': 'complete', 'success': True, 'completed_utc': c.utc_now(), 'plan_digest': digest, 'plan_sha256': manifest['plan_sha256'], 'closure_sha256': closure_sha, 'production_complete_sha256': manifest['production_complete_sha256'], 'auditor_sha256': manifest['auditor_sha256'], 'independent_audit_sha256': c.sha256_file(control / 'independent-audit.json'), 'response_transfer_sha256': c.sha256_file(control / 'response-transfer.json'), 'native_access_started_sha256': c.sha256_file(run / 'response-access.json'), 'native_access_success_sha256': c.sha256_file(run / 'response-access-success.json'), 'scores_sha256': c.sha256_file(run / 'scores.json'), 'report_sha256': c.sha256_file(run / 'outer-report.md'), 'score_stage': score_stage, 'report_stage': report_stage, 'returned_manifest_sha256': c.sha256_file(run / 'returned-files.json'), 'returned_artifact_count': len(returned['files']), 'models_retained_on_deep': rr + '/fits'}
    result.update({'recovery_helper_sha256': manifest['recovery_helper_sha256'], 'inventory_certificate_sha256': manifest['inventory_certificate_sha256'], 'inventory_proof_sha256': manifest['inventory_proof_sha256'], 'recovery_success_sha256': c.sha256_file(recovery_dir / 'response-access-recovery-success.json'), 'original_response_access_preserved': True, 'audit_is_preserved_preopening_reference': True})
    require(c.sha256_file(control / 'complete.json') == FAILED_SHA, 'prior failure modified during return')
    result.update({'reconciled_failure_sha256': FAILED_SHA, 'reconciled_failure_reason': REASON, 'reconciliation_mode': 'return_only', 'original_attempt005_manifest_sha256': MANIFEST_SHA, 'return_source_sha256': c.sha256_file(Path(__file__)), 'scientific_recomputation': False, 'report_regenerated': False})
    c._immutable_json(control / 'return-complete-006.json', result)
    print(json.dumps(result), flush=True)
except Exception as exc:
    c._immutable_json(control / 'return-failure-006.json', {'status': 'failed', 'success': False, 'ended_utc': c.utc_now(), 'error_type': type(exc).__name__, 'reason': str(exc), 'reconciled_failure_sha256': FAILED_SHA, 'scientific_recomputation': False})
    raise
