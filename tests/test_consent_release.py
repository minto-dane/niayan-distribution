# SPDX-License-Identifier: MIT
"""Product gate completeness: structural checks, not a qualification claim."""
import json
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'distribution/tools'))
from nia_policy import GATES,readiness
from nia_common import Invalid

class ConsentRelease(unittest.TestCase):
    def test_registered_gate_set_matches_product_contract(self):
        c=json.loads((ROOT/'distribution/contracts/release-gates.json').read_text())
        self.assertEqual(c['required_gates'],list(GATES))
        self.assertFalse(c['production_qualified'])
    def test_consent_cannot_disappear_from_missing_evidence(self):
        r=readiness('a'*64,[])
        ids={g['gate'] for g in r['gates']}
        self.assertTrue({'consent-peer-and-backend-identity','consent-exact-scope-ui-response',
          'portal-intent-before-effect','grant-revocation-observed',
          'consent-anchor-and-reservation','real-desktop-session-switch-tests'}<=ids)
        self.assertFalse(r['execution_permit'])
        self.assertTrue(all(x['state']=='missing' for x in r['gates']))
    def test_self_asserted_ui_pass_is_not_qualification(self):
        row=dict(gate='consent-exact-scope-ui-response',state='PASS',scope_sha256='a'*64,evidence_ref='self')
        with self.assertRaises(Invalid):readiness('a'*64,[row])
    def test_duplicate_and_stale_gates_rejected(self):
        row=dict(gate='grant-revocation-observed',state='planned',scope_sha256='a'*64,evidence_ref='plan')
        with self.assertRaises(Invalid):readiness('a'*64,[row,row])
        with self.assertRaises(Invalid):readiness('b'*64,[row])

if __name__=='__main__':unittest.main()
