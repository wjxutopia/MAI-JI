import json
import sqlite3
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from pathlib import Path

import test_guard as base
from test_guard import FP, ROOT, food, g

class V2StateTests(unittest.TestCase):
    setUp = base.StateTests.setUp
    tearDown = base.StateTests.tearDown
    call = base.StateTests.call
    offer = base.StateTests.offer
    claim = base.StateTests.claim
    created = base.StateTests.created
    fail = base.StateTests.fail
    def observe(self, r, target='old', terminal='expired', **kw):
        d=dict(receipt=r,target=target,order_id='1001' if target=='old' else '1002',
               terminal=terminal,evidence='detail_and_list_confirmed'); d.update(kw)
        return self.call('observe',**d)
    def test_v2_expired_old_without_cancel_dispatch(self):
        r=self.created('replace'); self.observe(r)
        self.fail('begin',receipt=r,stage='cancel',old_pending=True)
        done=self.call('finish',receipt=r,final_new_pending=True,final_old_terminal='expired')
        self.assertTrue(done['completed'])
        self.assertIsNone(self.call('status')['cards'][0]['cancel_state'])
    def test_v2_old_terminal_requires_bound_id_evidence(self):
        r=self.created('replace')
        for kw in [dict(order_id='9999'),dict(evidence='list_only'),dict(terminal='paid'),dict(terminal='unknown')]:
            with self.subTest(kw=kw), self.assertRaises(g.GuardError): self.observe(r,**kw)
    def test_v2_expired_old_still_needs_verified_new(self):
        r=self.created('replace'); self.call('verify',receipt=r,new_order_id='1002',matched=False,pending=True)
        self.observe(r); self.fail('finish',receipt=r,final_new_pending=True,final_old_terminal='expired')
    def test_v2_terminal_cannot_be_rewritten(self):
        r=self.created('replace'); self.observe(r)
        with self.assertRaises(g.GuardError): self.observe(r,terminal='cancelled')
    def test_v2_status_has_bound_action_and_old_order(self):
        r=self.created('replace'); self.guard.close(); self.guard=g.Guard(self.path,clock=lambda:self.now)
        row=self.call('status')['cards'][0]
        self.assertEqual(row['selected']['action'],'replace')
        self.assertEqual(row['selected']['old_order_id'],'1001')
        self.assertEqual(row['selected']['fingerprint'],FP)
        self.assertEqual(row['selected']['total_cents'],1500)
        self.assertNotIn('options',row)
    def test_v2_recovery_cannot_dispatch_from_other_session(self):
        r=self.created('replace')
        self.call('recover',session='new-session',receipt=r,target='old',order_id='1001',
                  terminal='expired',evidence='detail_and_list_confirmed')
        self.fail('begin',session='new-session',receipt=r,stage='cancel',old_pending=True)
        self.fail('finish',session='new-session',receipt=r,final_new_pending=True,final_old_terminal='expired')
    def test_v2_both_terminal_stop_releases_scope(self):
        r=self.created('replace'); self.observe(r)
        out=self.observe(r,target='new',close=True)
        self.assertTrue(out['stopped']); self.assertFalse(out['completed']); self.assertFalse(out['allow_dispatch'])
        self.assertTrue(self.offer())
        self.fail('begin',receipt=r,stage='cancel',old_pending=True)
    def test_v2_unknown_new_cannot_stop(self):
        r=self.claim('replace'); self.call('begin',receipt=r,stage='create')
        self.call('record',receipt=r,stage='create',outcome='unknown')
        self.observe(r)
        with self.assertRaises(g.GuardError): self.observe(r,target='new',close=True)
        self.fail('abort',receipt=r)
    def test_v2_one_terminal_not_enough_to_close_replace(self):
        r=self.created('replace')
        with self.assertRaises(g.GuardError): self.observe(r,close=True)
        self.assertIsNone(self.call('status')['cards'][0]['old_terminal'])
    def test_v2_cross_session_recovery_stops_both_terminal_only(self):
        r=self.created('replace')
        self.call('recover',session='new-session',receipt=r,target='old',order_id='1001',
                  terminal='cancelled',evidence='detail_and_list_confirmed')
        self.assertTrue(self.call('recover',session='new-session',receipt=r,target='new',order_id='1002',
                  terminal='expired',evidence='detail_and_list_confirmed',close=True)['stopped'])
    def test_v2_recovery_wrong_scope(self):
        r=self.created('replace')
        self.fail('recover',scope='other',session='new-session',receipt=r,target='old',order_id='1001',
                  terminal='expired',evidence='detail_and_list_confirmed')
    def test_v2_terminal_new_cannot_verify_or_finish(self):
        r=self.created(); self.observe(r,target='new')
        self.fail('verify',receipt=r,new_order_id='1002',matched=True,pending=True)
        self.fail('finish',receipt=r,final_new_pending=True)
    def test_v2_observe_completes_without_cancel_dispatch(self):
        r=self.created('replace')
        out=self.observe(r,complete=True,final_new_pending=True)
        self.assertTrue(out['completed']); self.assertEqual(out['order_id'],'1002')
        self.assertFalse(out['allow_dispatch']); self.assertFalse(out['payment_performed'])
        row=self.call('status')['cards'][0]
        self.assertEqual(row['status'],'completed'); self.assertIsNone(row['cancel_state'])
        self.fail('begin',receipt=r,stage='cancel',old_pending=True)
        self.assertTrue(self.offer())
    def test_v2_recover_completes_from_new_session_without_dispatch(self):
        r=self.created('replace'); self.guard.close(); self.guard=g.Guard(self.path,clock=lambda:self.now)
        out=self.call('recover',session='new-session',receipt=r,target='old',order_id='1001',
                      terminal='cancelled',evidence='detail_and_list_confirmed',complete=True,final_new_pending=True)
        self.assertTrue(out['completed']); self.assertFalse(out['allow_dispatch'])
        self.fail('begin',session='new-session',receipt=r,stage='create')
        self.fail('begin',session='new-session',receipt=r,stage='cancel',old_pending=True)
        self.assertTrue(self.offer(session='new-session'))
    def test_v2_complete_requires_current_pending_true(self):
        r=self.created('replace')
        for kw in [{},dict(final_new_pending=False),dict(final_new_pending='true')]:
            with self.subTest(kw=kw), self.assertRaises(g.GuardError): self.observe(r,complete=True,**kw)
        row=self.call('status')['cards'][0]
        self.assertEqual(row['status'],'claimed'); self.assertIsNone(row['old_terminal'])
    def test_v2_complete_rejects_unverified_new(self):
        r=self.created('replace'); self.call('verify',receipt=r,new_order_id='1002',matched=False,pending=True)
        with self.assertRaises(g.GuardError): self.observe(r,complete=True,final_new_pending=True)
        self.assertEqual(self.call('status')['cards'][0]['verified'],0)
    def test_v2_complete_rejects_ended_new(self):
        r=self.created('replace'); self.observe(r,target='new')
        with self.assertRaises(g.GuardError): self.observe(r,complete=True,final_new_pending=True)
    def test_v2_complete_rejects_unknown_creation(self):
        r=self.claim('replace'); self.call('begin',receipt=r,stage='create')
        self.call('record',receipt=r,stage='create',outcome='unknown')
        with self.assertRaises(g.GuardError): self.observe(r,complete=True,final_new_pending=True)
        with self.assertRaises(g.GuardError): self.offer()
    def test_v2_complete_only_replacement_old_target(self):
        r=self.created()
        with self.assertRaises(g.GuardError): self.observe(r,target='new',complete=True,final_new_pending=True)
    def test_v2_resolution_flags_are_unambiguous(self):
        r=self.created('replace')
        for kw in [dict(close=True,complete=True,final_new_pending=True),dict(close='true'),
                   dict(complete=1),dict(final_new_pending=True)]:
            with self.subTest(kw=kw), self.assertRaises(g.GuardError): self.observe(r,**kw)
        self.assertIsNone(self.call('status')['cards'][0]['old_terminal'])
    def test_v2_single_created_terminal_stop(self):
        r=self.created(); self.assertTrue(self.observe(r,target='new',close=True)['stopped'])
        self.fail('finish',receipt=r,final_new_pending=True); self.assertTrue(self.offer())
    def test_v2_keep_terminal_stop(self):
        r=self.claim('keep'); self.assertTrue(self.observe(r,close=True)['stopped'])
        self.fail('finish',receipt=r,old_pending=True); self.assertTrue(self.offer())
    def test_v2_cancel_unknown_terminal_observation_completes(self):
        r=self.created('replace'); self.call('begin',receipt=r,stage='cancel',old_pending=True)
        self.call('record',receipt=r,stage='cancel',outcome='unknown')
        out=self.observe(r,terminal='cancelled',complete=True,final_new_pending=True)
        self.assertTrue(out['completed']); self.assertFalse(out['allow_dispatch'])
        self.assertEqual(self.call('status')['cards'][0]['cancel_state'],'unknown')
    def test_v2_huge_total_rejected(self):
        o=dict(number='1',action='create',label='合成',total_cents=10**30,fingerprint=FP)
        self.fail('offer',expires_at=(self.now+timedelta(minutes=1)).isoformat(),options=[o])
    def test_v2_concurrent_begin_one_dispatch(self):
        r=self.claim(); barrier=threading.Barrier(2)
        def worker(_):
            guard=g.Guard(self.path,clock=lambda:self.now)
            try:
                barrier.wait()
                try:
                    guard.apply(dict(op='begin',scope='test-account',session='test-session',receipt=r,stage='create'))
                    return True
                except g.GuardError: return False
            finally: guard.close()
        with ThreadPoolExecutor(max_workers=2) as pool: self.assertEqual(sum(pool.map(worker,range(2))),1)
    def test_v2_success_never_downgraded(self):
        r=self.created()
        for outcome in ['unknown','confirmed_absent']:
            self.fail('reconcile',receipt=r,stage='create',outcome=outcome,evidence='authoritative_absence')
        self.fail('record',receipt=r,stage='create',outcome='failed')
    def test_v2_migrate_legacy_db_preserves_dispatch(self):
        r=self.claim(); self.call('begin',receipt=r,stage='create')
        self.guard.close()
        conn=sqlite3.connect(str(self.path))
        conn.execute('ALTER TABLE cards DROP COLUMN old_terminal')
        conn.execute('ALTER TABLE cards DROP COLUMN new_terminal')
        conn.commit(); conn.close()
        self.guard=g.Guard(self.path,clock=lambda:self.now)
        self.assertEqual(self.call('status')['cards'][0]['create_state'],'dispatching')
        self.fail('begin',receipt=r,stage='create')

class V2BudgetFixtureTests(unittest.TestCase):
    """Synthetic constraints exercise the comparator, not a menu search engine."""
    def quote(self, candidate, price, required=None, **kw):
        d=dict(op='compare',required=required or [food('MAIN',quantity=8),food('FRIES',quantity=4)],
               candidate=candidate,required_fulfillment=base.fulfill(),candidate_fulfillment=base.fulfill(),
               baseline_cents=32000,candidate_cents=price)
        d.update(kw)
        return g.compare(d)
    def test_budget_feasible_exact_foods(self):
        r=self.quote([food('MAIN',quantity=8),food('FRIES',quantity=4)],28000)
        self.assertEqual(r['classification'],'equivalent'); self.assertEqual(r['savings_cents'],4000)
        self.assertLessEqual(28000,30000)
    def test_budget_infeasible_keeps_all_required_foods(self):
        r=self.quote([food('MAIN',quantity=8),food('FRIES',quantity=4)],31500)
        self.assertEqual(r['classification'],'equivalent'); self.assertGreater(31500,30000)
        self.assertEqual(31500-30000,1500)
    def test_under_budget_with_missing_portion_is_different(self):
        r=self.quote([food('MAIN',quantity=7),food('FRIES',quantity=4)],27000)
        self.assertEqual(r['classification'],'different')
    def test_unaccepted_drink_never_equivalent(self):
        r=self.quote([food('MAIN',quantity=8),food('FRIES',quantity=4),food('DRINK')],28000)
        self.assertEqual(r['classification'],'extra'); self.assertTrue(r['optional_gain'])
        self.assertNotEqual(r['classification'],'equivalent')
    def test_changed_delivery_not_feasible_equivalence(self):
        f=base.fulfill(); f['storeCode']='OTHER_STORE'
        r=self.quote([food('MAIN',quantity=8),food('FRIES',quantity=4)],27000,candidate_fulfillment=f)
        self.assertEqual(r['classification'],'different')

class V2TemplateTests(unittest.TestCase):
    setUp = base.TemplateTests.setUp
    tearDown = base.TemplateTests.tearDown
    call = base.TemplateTests.call
    save = base.TemplateTests.save
    consent = base.TemplateTests.consent
    def test_v2_revoke_stops_reuse_but_allows_inspect(self):
        self.consent(); self.save(); self.call('consent',granted=False,notice_version='1')
        self.assertFalse(self.call('template-list')['reuse_allowed'])
        with self.assertRaises(g.GuardError): self.call('template-load')
        self.consent(); self.assertEqual(len(self.call('template-load')['templates']),1)
    def test_v2_nonempty_legacy_private_field_rejected(self):
        self.consent()
        for value in ['https://test.invalid/payment','Bearer SYNTHETIC']:
            f=food(modifications=[dict(code=value,key='0-1',quantity=1)])
            data=dict(name='合成',scene={'mode':'pickup'},items=[f],restrictions=[])
            with self.subTest(value=value), self.assertRaises(g.GuardError): self.save(data=data)
    def test_v2_nonempty_legacy_quantity_cannot_bypass_review(self):
        f=food(modifications=[dict(code='M',key='K',quantity=10**30)])
        with self.assertRaises(g.GuardError) as exc: g.leaf(f)
        self.assertEqual(str(exc.exception),'legacy_modifications_require_review')

class V2ParserTests(unittest.TestCase):
    def cli(self, raw, db=None):
        cmd=[sys.executable,'-B',str(ROOT/'scripts/guard.py')]
        if db: cmd += ['--db',str(db)]
        return subprocess.run(cmd,input=raw,capture_output=True,text=True)
    def error(self, raw, expected, db=None):
        p=self.cli(raw,db); self.assertEqual(p.returncode,2,p.stderr)
        self.assertEqual(json.loads(p.stdout)['error'],expected); self.assertEqual(p.stderr,'')
    def test_duplicate_money_key(self):
        self.error('{"op":"money","value":"1","value":"9","unit":"yuan"}','duplicate_json_key')
    def test_duplicate_consent_no_write(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=Path(tmp)/'test.db'
            self.error('{"op":"consent","scope":"synthetic","granted":false,"granted":true,"notice_version":"1"}',
                       'duplicate_json_key',db)
            self.assertFalse(db.exists())
    def test_duplicate_nested_digest(self):
        self.error('{"op":"digest","value":{"x":1,"x":2}}','duplicate_json_key')
    def test_duplicate_op(self):
        self.error('{"op":"money","op":"digest","value":1}','duplicate_json_key')
    def test_deep_json(self):
        self.error('{"op":"digest","value":'+'['*5000+'0'+']'*5000+'}','input_too_deep')
    def test_extreme_time(self):
        with self.assertRaises(g.GuardError) as exc: g.instant('9999-12-31T23:59:59-23:59')
        self.assertEqual(str(exc.exception),'invalid_time')
    def test_oversize_input(self): self.error(' '*200001,'input_too_large')
    def test_selection_normal_number(self):
        r=g.dispatch(dict(op='selection',reply='2',current_card_id='a'*16))
        self.assertEqual(r['choice'],'2')
    def test_selection_current_explicit(self):
        r=g.dispatch(dict(op='selection',reply='卡 '+ 'a'*16+' 2',current_card_id='a'*16,require_card_id=True))
        self.assertEqual(r['choice'],'2')
    def test_selection_old_card_rejected(self):
        with self.assertRaises(g.GuardError):
            g.dispatch(dict(op='selection',reply='卡 '+ 'b'*16+' 2',current_card_id='a'*16))
    def test_selection_ambiguous_number_requires_id(self):
        with self.assertRaises(g.GuardError):
            g.dispatch(dict(op='selection',reply='2',current_card_id='a'*16,require_card_id=True))
    def test_selection_natural_consent_rejected(self):
        for reply in ['好','可以','要这个','2 然后支付']:
            with self.subTest(reply=reply), self.assertRaises(g.GuardError):
                g.dispatch(dict(op='selection',reply=reply,current_card_id='a'*16))

if __name__=='__main__': unittest.main()
