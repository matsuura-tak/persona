"""Behavioral invariants: prevent unsupported outcomes and misattributed evidence."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

SKILL = Path(__file__).resolve().parents[1] / '.agents/skills/service-persona-review'
SCRIPT = SKILL / 'scripts/validate_review.py'
spec = importlib.util.spec_from_file_location('validator', SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class ReviewValidationTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads((SKILL / 'assets/example-review.json').read_text(encoding='utf-8'))

    def invalid(self, message):
        with self.assertRaisesRegex(validator.ValidationError, message):
            validator.validate(self.data)

    def interactive(self):
        self.data['sessions'] = [self.data['sessions'][0]]
        self.data['findings'] = []
        self.data['human_checks'] = []
        self.data['run']['mode'] = 'interactive'
        self.data['evidence'][0]['kind'] = 'ui'
        end = copy.deepcopy(self.data['evidence'][0])
        end.update(id='E2', observation='TEST FIXTURE: confirmation state')
        self.data['evidence'].append(end)
        session = self.data['sessions'][0]
        session.update(mode='interactive', outcome='success', result_evidence_ids=['E2'])
        session['steps'][0].update(action_status='executed', result_evidence_ids=['E2'])
        return session

    def test_documented_example_is_valid(self):
        validator.validate(self.data)

    def test_interactive_completion_is_valid(self):
        self.interactive()
        validator.validate(self.data)

    def test_artifact_cannot_claim_success(self):
        self.data['sessions'][0]['outcome'] = 'success'
        self.invalid('artifact outcome')

    def test_artifact_cannot_execute(self):
        self.data['sessions'][0]['steps'][0]['action_status'] = 'executed'
        self.invalid('artifact sessions cannot execute')

    def test_artifact_cannot_score_keyboard_usability(self):
        self.data['sessions'][0]['scores']['inclusion'].update(score=3, evidence_ids=['E1'])
        self.invalid('dynamic score')

    def test_success_requires_final_ui_evidence(self):
        session = self.interactive()
        session['result_evidence_ids'] = []
        self.invalid('final UI evidence')

    def test_success_requires_executed_action(self):
        session = self.interactive()
        session['steps'] = []
        self.invalid('executed action')

    def test_start_screen_cannot_prove_completion(self):
        self.interactive()['result_evidence_ids'] = ['E1']
        self.invalid('final evidence must come from executed')

    def test_mixed_review_preserves_session_modes(self):
        artifact_session = copy.deepcopy(self.data['sessions'][1])
        session = self.interactive()
        artifact = copy.deepcopy(self.data['evidence'][0])
        artifact.update(id='E3', kind='artifact')
        self.data['evidence'].append(artifact)
        artifact_session['steps'][0]['observation_evidence_ids'] = ['E3']
        for score in artifact_session['scores'].values():
            if score['evidence_ids']:
                score['evidence_ids'] = ['E3']
        self.data['sessions'].append(artifact_session)
        self.data['run']['mode'] = 'mixed'
        validator.validate(self.data)

    def test_fully_blocked_review_does_not_need_fabricated_evidence(self):
        session = self.interactive()
        self.data['evidence'] = []
        session.update(outcome='blocked', outcome_reason='No authorized login', result_evidence_ids=[], steps=[])
        for score in session['scores'].values():
            score.update(score=None, evidence_ids=[])
        validator.validate(self.data)

    def test_tool_error_is_not_success_evidence(self):
        self.interactive()
        self.data['evidence'][1]['kind'] = 'tool'
        self.invalid('final UI evidence')

    def test_tool_error_can_block_a_session(self):
        session = self.interactive()
        self.data['evidence'][1]['kind'] = 'tool'
        session.update(outcome='blocked', outcome_reason='TEST FIXTURE: tool cannot navigate')
        validator.validate(self.data)

    def test_not_run_cannot_have_executed_action(self):
        self.interactive()['outcome'] = 'not_run'
        self.invalid('not_run cannot contain executed')

    def test_proposed_action_cannot_claim_result(self):
        self.data['sessions'][0]['steps'][0]['result_evidence_ids'] = ['E1']
        self.invalid('proposed actions')

    def test_unobserved_scores_remain_null(self):
        for session in self.data['sessions']:
            for score in session['scores'].values():
                score.update(score=None, evidence_ids=[])
        validator.validate(self.data)

    def test_numeric_score_needs_evidence(self):
        self.data['sessions'][0]['scores']['trust']['evidence_ids'] = []
        self.invalid('numeric score needs')

    def test_boolean_is_not_a_score(self):
        self.data['sessions'][0]['scores']['trust']['score'] = True
        self.invalid('integer 1..5')

    def test_score_out_of_range(self):
        self.data['sessions'][0]['scores']['trust']['score'] = 6
        self.invalid('integer 1..5')

    def test_all_seven_axes_are_required(self):
        del self.data['sessions'][0]['scores']['recovery']
        self.invalid('seven axes')

    def test_unknown_evidence_reference(self):
        self.data['findings'][0]['evidence_ids'] = ['missing']
        self.invalid('unknown or out-of-scope')

    def test_score_cannot_borrow_unobserved_evidence(self):
        other = copy.deepcopy(self.data['evidence'][0])
        other['id'] = 'E-other'
        self.data['evidence'].append(other)
        self.data['sessions'][0]['scores']['trust']['evidence_ids'] = ['E-other']
        self.invalid('out-of-scope')

    def test_finding_cannot_borrow_another_sessions_evidence(self):
        other = copy.deepcopy(self.data['evidence'][0])
        other['id'] = 'E-other'
        self.data['evidence'].append(other)
        self.data['sessions'][1]['steps'][0]['observation_evidence_ids'].append('E-other')
        self.data['findings'][0]['evidence_ids'] = ['E-other']
        self.invalid('out-of-scope')

    def test_duplicate_ids_rejected(self):
        self.data['personas'][1]['id'] = 'P1'
        self.invalid('duplicate id')

    def test_research_informed_persona_needs_source(self):
        self.data['personas'][0]['basis'] = 'research_informed'
        self.invalid('at least 1')

    def test_hypothesis_cannot_be_high_confidence(self):
        self.data['findings'][1]['confidence'] = 'high'
        self.invalid('hypotheses require low')

    def test_hypothesis_requires_a_human_check(self):
        self.data['human_checks'] = []
        self.invalid('needs a human check')

    def test_unsupported_issue_cannot_be_fix_now(self):
        self.data['findings'][0]['priority'] = 'fix_now'
        self.invalid('fix_now requires')

    def test_strength_is_not_a_defect(self):
        self.data['findings'][2]['severity'] = 'S2'
        self.invalid('strengths require')

    def test_mode_must_match_sessions(self):
        self.data['run']['mode'] = 'interactive'
        self.invalid('must be artifact')

    def test_timezone_required(self):
        self.data['run']['recorded_at'] = '2026-11-08T15:00:00'
        self.invalid('timezone')

    def test_malformed_structures_produce_validation_errors(self):
        original = copy.deepcopy(self.data)
        for key in ('run', 'personas', 'tasks', 'evidence', 'sessions', 'findings', 'human_checks'):
            with self.subTest(key=key):
                self.data = copy.deepcopy(original)
                self.data[key] = None
                self.invalid('must be')

    def test_command_line_rejects_invalid_json_and_missing_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.json'
            for content in ('{"x": NaN}', '{"x": 1, "x": 2}', 'null', '{broken'):
                with self.subTest(content=content):
                    path.write_text(content, encoding='utf-8')
                    result = subprocess.run([sys.executable, str(SCRIPT), str(path)], capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1)
                    self.assertIn('INVALID:', result.stderr)
                    self.assertNotIn('Traceback', result.stderr)
            result = subprocess.run([sys.executable, str(SCRIPT), str(path) + '.missing'], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)


if __name__ == '__main__':
    unittest.main()
