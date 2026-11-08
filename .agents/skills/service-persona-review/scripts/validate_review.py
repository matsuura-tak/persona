#!/usr/bin/env python3
"""Validate review v1.0 structure and evidence invariants; no external packages."""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

AXES = ('value', 'discovery', 'comprehension', 'efficiency', 'recovery', 'trust', 'inclusion')
DYNAMIC_AXES = {'efficiency', 'recovery', 'inclusion'}
OBSERVED_OUTCOMES = {'success', 'partial', 'failure', 'abandoned'}


class ValidationError(ValueError):
    pass


def require(condition, path, message):
    if not condition:
        raise ValidationError(f'{path}: {message}')


def obj(value, path):
    require(isinstance(value, dict), path, 'must be an object')
    return value


def string(value, path):
    require(isinstance(value, str) and bool(value.strip()), path, 'must be a nonempty string')
    return value


def fields(value, names, path):
    obj(value, path)
    for name in names.split():
        string(value.get(name), f'{path}.{name}')


def array(value, path, minimum=0):
    require(isinstance(value, list), path, 'must be an array')
    require(len(value) >= minimum, path, f'must have at least {minimum} item(s)')
    return value


def strings(value, path, minimum=0):
    for item in array(value, path, minimum):
        string(item, path)
    return value


def choice(value, allowed, path):
    require(value in allowed, path, f'must be one of {sorted(allowed)}')


def timestamp(value, path):
    string(value, path)
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        raise ValidationError(f'{path}: must be an ISO 8601 timestamp') from None
    require(parsed.tzinfo is not None, path, 'timezone is required')


def refs(value, index, path, minimum=0):
    values = strings(value, path, minimum)
    require(len(values) == len(set(values)), path, 'duplicate references')
    for item in values:
        require(item in index, path, f'unknown or out-of-scope reference {item}')
    return set(values)


def validate(data):
    obj(data, 'review')
    require(data.get('schema_version') == '1.0', 'schema_version', 'must be 1.0')
    run = obj(data.get('run'), 'run')
    fields(run, 'id target target_version recorded_at mode nature environment permissions limits', 'run')
    timestamp(run['recorded_at'], 'run.recorded_at')
    choice(run['mode'], {'interactive', 'artifact', 'mixed'}, 'run.mode')
    choice(run['nature'], {'review', 'example'}, 'run.nature')
    strings(run.get('limitations'), 'run.limitations')

    indexes = {}
    seen = {run['id']}
    for collection in ('personas', 'tasks', 'evidence', 'sessions', 'findings', 'human_checks'):
        entries = array(data.get(collection), collection, int(collection in {'personas', 'tasks', 'sessions'}))
        indexes[collection] = {}
        for i, entry in enumerate(entries):
            path = f'{collection}[{i}]'
            obj(entry, path)
            key = string(entry.get('id'), path + '.id')
            require(key not in seen, path, f'duplicate id {key}')
            seen.add(key)
            indexes[collection][key] = entry

    for key, persona in indexes['personas'].items():
        fields(persona, 'label basis goal context prior_knowledge constraints decision_rule stop_rule', key)
        choice(persona['basis'], {'hypothesis', 'research_informed'}, key + '.basis')
        strings(persona.get('source_refs'), key + '.source_refs', int(persona['basis'] == 'research_informed'))

    for key, task in indexes['tasks'].items():
        fields(task, 'goal start_state success_criteria allowed_actions', key)

    evidence = indexes['evidence']
    for key, item in evidence.items():
        fields(item, 'kind ref locator captured_at observation', key)
        choice(item['kind'], {'ui', 'artifact', 'tool'}, key + '.kind')
        timestamp(item['captured_at'], key + '.captured_at')

    def has_kind(ids, kinds):
        return any(evidence[eid]['kind'] in kinds for eid in ids)

    session_evidence = {}
    modes = set()
    for key, session in indexes['sessions'].items():
        fields(session, 'persona_id task_id mode outcome outcome_reason state_reset review', key)
        refs([session['persona_id']], indexes['personas'], key + '.persona_id')
        refs([session['task_id']], indexes['tasks'], key + '.task_id')
        choice(session['mode'], {'interactive', 'artifact'}, key + '.mode')
        choice(session['outcome'], OBSERVED_OUTCOMES | {'blocked', 'not_run'}, key + '.outcome')
        modes.add(session['mode'])
        result_ids = refs(session.get('result_evidence_ids'), evidence, key + '.result_evidence_ids')
        all_ids = set(result_ids)
        executed = False
        executed_results = set()
        for i, step in enumerate(array(session.get('steps'), key + '.steps')):
            path = f'{key}.steps[{i}]'
            fields(step, 'action action_status expected actual', path)
            choice(step['action_status'], {'executed', 'proposed'}, path + '.action_status')
            before = refs(step.get('observation_evidence_ids'), evidence, path + '.observation_evidence_ids', 1)
            after = refs(step.get('result_evidence_ids'), evidence, path + '.result_evidence_ids')
            all_ids.update(before | after)
            if step['action_status'] == 'executed':
                require(session['mode'] == 'interactive', path, 'artifact sessions cannot execute actions')
                require(has_kind(before, {'ui'}), path, 'executed actions need UI observation evidence')
                require(has_kind(after, {'ui', 'tool'}), path, 'executed actions need result evidence')
                executed = True
                executed_results.update(after)
            else:
                require(not after, path, 'proposed actions cannot have execution result evidence')
        if session['mode'] == 'artifact':
            require(session['outcome'] == 'not_run', key, 'artifact outcome must be not_run')
            require(not has_kind(all_ids, {'ui'}), key, 'artifact session cannot claim live UI evidence')
        if session['outcome'] in OBSERVED_OUTCOMES:
            require(executed, key, 'observed outcome requires an executed action')
            require(has_kind(result_ids, {'ui'}), key, 'observed outcome requires final UI evidence')
            require(result_ids <= executed_results, key, 'final evidence must come from executed action results')
        if session['outcome'] == 'not_run':
            require(not executed, key, 'not_run cannot contain executed actions')
        session_evidence[key] = all_ids
        scores = obj(session.get('scores'), key + '.scores')
        require(set(scores) == set(AXES), key + '.scores', 'must include exactly the seven axes')
        for axis, score in scores.items():
            path = f'{key}.scores.{axis}'
            fields(score, 'reason', path)
            require('score' in score, path, 'score is required (use null when unknown)')
            value = score['score']
            require(value is None or (type(value) is int and 1 <= value <= 5), path, 'score must be null or integer 1..5')
            score_ids = refs(score.get('evidence_ids'), all_ids, path + '.evidence_ids')
            if value is not None:
                require(has_kind(score_ids, {'ui', 'artifact'}), path, 'numeric score needs UI or artifact evidence')
                if axis in DYNAMIC_AXES:
                    require(executed and has_kind(score_ids, {'ui'}), path, 'dynamic score needs executed UI evidence')

    expected_mode = next(iter(modes)) if len(modes) == 1 else 'mixed'
    require(run['mode'] == expected_mode, 'run.mode', f'must be {expected_mode} for these sessions')
    for key, finding in indexes['findings'].items():
        fields(finding, 'kind title fact interpretation impact severity confidence priority recommendation acceptance_check alternative_explanation', key)
        kind, severity, confidence, priority = (finding[n] for n in ('kind', 'severity', 'confidence', 'priority'))
        choice(kind, {'observed_issue', 'hypothesis', 'strength'}, key + '.kind')
        choice(severity, {'S0', 'S1', 'S2', 'S3'}, key + '.severity')
        choice(confidence, {'low', 'medium', 'high'}, key + '.confidence')
        choice(priority, {'fix_now', 'fix_next', 'consider', 'validate_first', 'preserve'}, key + '.priority')
        sessions = refs(finding.get('session_ids'), indexes['sessions'], key + '.session_ids', 1)
        available = set().union(*(session_evidence[sid] for sid in sessions))
        ids = refs(finding.get('evidence_ids'), available, key + '.evidence_ids')
        if kind != 'hypothesis':
            require(has_kind(ids, {'ui', 'artifact'}), key, 'observed finding requires UI or artifact evidence')
        if kind == 'hypothesis':
            require(confidence == 'low' and priority == 'validate_first', key, 'hypotheses require low / validate_first')
        if kind == 'strength':
            require(severity == 'S0' and priority == 'preserve', key, 'strengths require S0 / preserve')
        else:
            require(severity != 'S0' and priority != 'preserve', key, 'issues/hypotheses require S1..S3 and cannot use preserve')
        if kind == 'observed_issue' and confidence == 'low':
            require(priority == 'validate_first', key, 'low-confidence issues require validate_first')
        if priority == 'fix_now':
            require(kind == 'observed_issue' and severity == 'S3' and confidence == 'high', key, 'fix_now requires observed_issue / S3 / high')
        if priority == 'fix_next':
            require(kind == 'observed_issue' and severity in {'S2', 'S3'} and confidence in {'medium', 'high'}, key, 'fix_next requires a supported major issue')

    checked = set()
    for key, check in indexes['human_checks'].items():
        fields(check, 'prompt supports refutes', key)
        checked.update(refs(check.get('finding_ids'), indexes['findings'], key + '.finding_ids', 1))
    for key, finding in indexes['findings'].items():
        if finding['kind'] == 'hypothesis':
            require(key in checked, key, 'hypothesis needs a human check')


def reject_constant(value):
    raise ValidationError(f'non-standard JSON number: {value}')


def unique_keys(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, key, 'duplicate JSON object key')
        result[key] = value
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('review', type=Path)
    args = parser.parse_args()
    try:
        data = json.loads(args.review.read_text(encoding='utf-8'), parse_constant=reject_constant, object_pairs_hook=unique_keys)
        validate(data)
    except (OSError, UnicodeError, ValueError) as error:
        print(f'INVALID: {error}', file=sys.stderr)
        return 1
    print('VALID: structure and evidence references checked; factual accuracy not verified.')
    return 0


if __name__ == '__main__':
    sys.exit(main())
