#!/usr/bin/env python3
"""Regression check for issue #100 CI trigger and version-transition policy."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import yaml

ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = ROOT / '.github' / 'workflows'
VERSION_SCRIPT = ROOT / '.github' / 'scripts' / 'version-transition.sh'


def run(*args, cwd, check=True):
    proc = subprocess.run(args, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if check and proc.returncode:
        raise AssertionError(f'{args}: status={proc.returncode}; stdout={proc.stdout}; stderr={proc.stderr}')
    return proc


class WorkflowPolicy(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.docker = yaml.load((WORKFLOWS / 'docker.yaml').read_text(), Loader=yaml.BaseLoader)
        cls.release = yaml.load((WORKFLOWS / 'release.yml').read_text(), Loader=yaml.BaseLoader)
        cls.pypi = yaml.load((WORKFLOWS / 'release-pypi.yml').read_text(), Loader=yaml.BaseLoader)

    def test_trigger_scopes(self):
        d = self.docker['on']
        self.assertIn('workflow_dispatch', d)
        self.assertEqual(d['push']['tags'], ['v*'])
        self.assertEqual(set(d['push']['branches']), {'main', 'dev'})
        self.assertIn('.github/**', d['push']['paths-ignore'])
        self.assertEqual(self.release['on']['push']['paths'], ['package.json'])
        self.assertIn('.github/**', self.pypi['on']['push']['paths-ignore'])
        self.assertIn('pypi-release', self.pypi['on']['push']['branches'])

    def test_gate_and_downstream_dependencies(self):
        jobs = self.docker['jobs']
        self.assertEqual(jobs['build']['needs'], ['version_gate'])
        self.assertIn("needs.version_gate.outputs.changed == 'false'", jobs['build']['if'])
        self.assertEqual(jobs['merge']['if'], "${{ needs.build.result == 'success' }}")
        self.assertIn('needs.merge.result', jobs['copy-to-dockerhub']['if'])
        jobs = self.pypi['jobs']
        self.assertEqual(jobs['release']['needs'], ['version_gate'])
        self.assertIn('needs.version_gate.outputs.publish', jobs['release']['if'])
        steps = self.release['jobs']['publish']['steps']
        guard = next(s for s in steps if s.get('id') == 'version_delta')
        self.assertIn('version-transition.sh', guard['run'])
        publisher = next(s for s in steps if s.get('id') == 'publication')
        self.assertIn('version_delta.outputs.changed', publisher['if'])
        dispatch = next(s for s in steps if s.get('name') == 'Trigger Docker build')
        self.assertIn('publication.outputs.created', dispatch['if'])
        self.assertIn("await github.rest.actions.createWorkflowDispatch({", dispatch['with']['script'])

    def test_existing_release_requires_explicit_dispatch_reconciliation(self):
        # Exercise the release shell step against an isolated fake gh executable.
        publisher = next(s for s in self.release['jobs']['publish']['steps'] if s.get('id') == 'publication')
        body = publisher['run'].replace('        v = yaml.load((WORKFLOWS / 'ci-release-policy-validation.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertIn('workflow_dispatch', v['on'])
        self.assertEqual(v['permissions'], {'contents': 'read'})
        self.assertEqual(list(v['jobs']), ['policy'])

    def test_script_real_git_history(self):
        run('bash', '-n', str(VERSION_SCRIPT), cwd=ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            run('git', 'init', '-q', cwd=repo)
            run('git', 'config', 'user.name', 'CI Test', cwd=repo)
            run('git', 'config', 'user.email', 'ci-test@example.invalid', cwd=repo)
            target = repo / 'package.json'
            target.write_text(json.dumps({'version': '1.2.3'}) + '\n')
            run('git', 'add', 'package.json', cwd=repo)
            run('git', 'commit', '-qm', 'baseline', cwd=repo)
            prev = run('git', 'rev-parse', 'HEAD', cwd=repo).stdout.strip()
            # unchanged package version is not a publishing event
            self.assertEqual(run('bash', str(VERSION_SCRIPT), prev, cwd=repo).stdout.strip(), 'changed=false')
            target.write_text(json.dumps({'version': '1.2.4'}) + '\n')
            self.assertEqual(run('bash', str(VERSION_SCRIPT), prev, cwd=repo).stdout.strip(), 'changed=true')
            for invalid in ['0' * 40, 'f' * 40, '', 'not-a-sha']:
                self.assertNotEqual(run('bash', str(VERSION_SCRIPT), invalid, cwd=repo, check=False).returncode, 0)
            target.write_text(json.dumps({'version': 123}) + '\n')
            self.assertNotEqual(run('bash', str(VERSION_SCRIPT), prev, cwd=repo, check=False).returncode, 0)
            target.write_text('{invalid-json\n')
            self.assertNotEqual(run('bash', str(VERSION_SCRIPT), prev, cwd=repo, check=False).returncode, 0)


if __name__ == '__main__':
    unittest.main()
 + '{{ steps.pkg.outputs.version }}', '9.8.7')
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            gh = work / 'gh'
            gh.write_text('''#!/bin/bash
if [[ "$1 $2" == "release view" ]]; then exit "$VIEW_STATUS"; fi
if [[ "$1 $2" == "release create" ]]; then exit 0; fi
exit 91
''')
            gh.chmod(0o755)
            output = work / 'output'
            for exists in [True, False]:
                output.write_text('')
                environment = dict(os.environ, PATH=str(work) + os.pathsep + os.environ.get('PATH', ''),
                                   VIEW_STATUS='0' if exists else '1', GITHUB_OUTPUT=str(output))
                proc = subprocess.run(['bash', '-e', '-c', body], cwd=work, env=environment,
                                      capture_output=True, text=True)
                if exists:
                    self.assertNotEqual(proc.returncode, 0, 'Existing release must not be accepted as Docker dispatch proof')
                    self.assertIn('Docker dispatch state is unresolved', proc.stderr)
                    self.assertNotIn('created=true', output.read_text())
                else:
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    self.assertEqual(output.read_text().strip(), 'created=true')

    def test_manual_validation_is_read_only(self):
        v = yaml.load((WORKFLOWS / 'ci-release-policy-validation.yml').read_text(), Loader=yaml.BaseLoader)
        self.assertIn('workflow_dispatch', v['on'])
        self.assertEqual(v['permissions'], {'contents': 'read'})
        self.assertEqual(list(v['jobs']), ['policy'])

    def test_script_real_git_history(self):
        run('bash', '-n', str(VERSION_SCRIPT), cwd=ROOT)
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            run('git', 'init', '-q', cwd=repo)
            run('git', 'config', 'user.name', 'CI Test', cwd=repo)
            run('git', 'config', 'user.email', 'ci-test@example.invalid', cwd=repo)
            target = repo / 'package.json'
            target.write_text(json.dumps({'version': '1.2.3'}) + '\n')
            run('git', 'add', 'package.json', cwd=repo)
            run('git', 'commit', '-qm', 'baseline', cwd=repo)
            prev = run('git', 'rev-parse', 'HEAD', cwd=repo).stdout.strip()
            # unchanged package version is not a publishing event
            self.assertEqual(run('bash', str(VERSION_SCRIPT), prev, cwd=repo).stdout.strip(), 'changed=false')
            target.write_text(json.dumps({'version': '1.2.4'}) + '\n')
            self.assertEqual(run('bash', str(VERSION_SCRIPT), prev, cwd=repo).stdout.strip(), 'changed=true')
            for invalid in ['0' * 40, 'f' * 40, '', 'not-a-sha']:
                self.assertNotEqual(run('bash', str(VERSION_SCRIPT), invalid, cwd=repo, check=False).returncode, 0)
            target.write_text(json.dumps({'version': 123}) + '\n')
            self.assertNotEqual(run('bash', str(VERSION_SCRIPT), prev, cwd=repo, check=False).returncode, 0)
            target.write_text('{invalid-json\n')
            self.assertNotEqual(run('bash', str(VERSION_SCRIPT), prev, cwd=repo, check=False).returncode, 0)


if __name__ == '__main__':
    unittest.main()
