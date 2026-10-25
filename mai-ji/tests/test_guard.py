import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sp = importlib.util.spec_from_file_location('guard', ROOT / 'scripts' / 'guard.py')
g = importlib.util.module_from_spec(sp)
sp.loader.exec_module(g)
FP = 'a' * 64

def food(code='TEST_FOOD', quantity=1, **kw):
    v = dict(identity=code, name='合成食品', spec='标准', modifications=[], quantity=quantity, complete=True)
    v.update(kw)
    return v

def fulfill():
    return dict(storeCode='TEST_STORE', orderType=1, beType=1, beCode='', address_binding='',
                takeWayCode='TEST_PICKUP', reservationDate='', needTableware=False, remark_digest=FP)

class MoneyTests(unittest.TestCase):
    def test_exact(self):
        for raw, expected in [('7.50',750), ('- ¥1',-100), ('+ ¥2.5',250), ('0',0)]:
            with self.subTest(raw=raw): self.assertEqual(g.cents(raw,'yuan'), expected)
    def test_cents(self):
        self.assertEqual(g.cents(750,'cents'),750)
    def test_reject(self):
        for v in [7.5, True, 'NaN', 'Infinity', '0.001', '1,000', '1e2']:
            with self.subTest(v=v), self.assertRaises(g.GuardError): g.cents(v,'yuan')
    def test_fractional_cent(self):
        with self.assertRaises(g.GuardError): g.cents('1.5','cents')
    def test_reject_excess_precision_even_zero(self):
        with self.assertRaises(g.GuardError): g.cents('1.000','yuan')
        with self.assertRaises(g.GuardError): g.cents('100.0','cents')

class CompareTests(unittest.TestCase):
    def compare(self, left, right, **kw):
        d = dict(op='compare', required=left, candidate=right, required_fulfillment=fulfill(),
                 candidate_fulfillment=fulfill(), baseline_cents=2000, candidate_cents=1500)
        d.update(kw)
        return g.compare(d)
    def test_equal(self):
        self.assertEqual(self.compare([food()],[food()])['classification'],'equivalent')
    def test_duplicate_aggregation(self):
        self.assertEqual(self.compare([food(),food()],[food(quantity=2)])['classification'],'equivalent')
    def test_extra(self):
        r = self.compare([food()],[food(),food('TEST_DRINK')])
        self.assertEqual(r['classification'],'extra')
        self.assertTrue(r['optional_gain'])
        self.assertEqual(r['savings_cents'],500)
    def test_extra_expensive(self):
        self.assertFalse(self.compare([food()],[food(),food('TEST_DRINK')],candidate_cents=2500)['optional_gain'])
    def test_missing_item(self):
        self.assertEqual(self.compare([food(quantity=2)],[food()])['classification'],'different')
    def test_spec(self):
        self.assertEqual(self.compare([food()],[food(spec='小份')])['classification'],'different')
    def test_legacy_nonempty_modifications_require_review(self):
        m = [dict(code='MOD',key='NO',quantity=1)]
        result = self.compare([food(modifications=m)],[food()])
        self.assertEqual(result['classification'],'unknown')
        self.assertEqual(result['reason'],'legacy_modifications_require_review')
    def test_unknown_complete(self):
        f = food(); del f['complete']
        self.assertEqual(self.compare([f],[food()])['classification'],'unknown')
    def test_unknown_spec(self):
        f = food(); del f['spec']
        self.assertEqual(self.compare([f],[food()])['classification'],'unknown')
    def test_fulfillment_missing(self):
        self.assertEqual(self.compare([food()],[food()],candidate_fulfillment={'storeCode':'TEST_STORE'})['classification'],'unknown')
    def test_fulfillment_changed(self):
        f = fulfill(); f['storeCode'] = 'OTHER'
        self.assertEqual(self.compare([food()],[food()],candidate_fulfillment=f)['classification'],'different')
    def test_unsupported_channel(self):
        f = fulfill(); f['beType'] = 5
        self.assertEqual(self.compare([food()],[food()],candidate_fulfillment=f)['classification'],'unknown')

class StateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.path = Path(self.tmp.name) / 'guard.sqlite3'
        self.now = datetime(2030,1,1,tzinfo=timezone.utc)
        self.guard = g.Guard(self.path, clock=lambda:self.now)
    def tearDown(self):
        self.guard.close(); self.tmp.cleanup()
    def call(self, op, **kw):
        d = dict(op=op,scope='test-account',session='test-session'); d.update(kw)
        return self.guard.apply(d)
    def offer(self, action='create', **kw):
        o = dict(number='1',action=action,label='合成测试方案',total_cents=1500,fingerprint=FP)
        if action != 'create': o['old_order_id'] = '1001'
        d = dict(expires_at=(self.now+timedelta(minutes=3)).isoformat(),options=[o]); d.update(kw)
        return self.call('offer',**d)['card_id']
    def claim(self, action='create'):
        c = self.offer(action)
        return self.call('claim',card_id=c,choice='1',fingerprint=FP)['receipt']
    def created(self, action='create'):
        r = self.claim(action)
        self.call('begin',receipt=r,stage='create')
        self.call('record',receipt=r,stage='create',outcome='success',new_order_id='1002')
        self.call('verify',receipt=r,new_order_id='1002',matched=True,pending=True)
        return r
    def fail(self, op, **kw):
        with self.assertRaises(g.GuardError): self.call(op,**kw)
    def test_duplicate_claim(self):
        c = self.offer(); self.call('claim',card_id=c,choice='1',fingerprint=FP)
        self.fail('claim',card_id=c,choice='1',fingerprint=FP)
    def test_old_card(self):
        c = self.offer(); self.offer()
        self.fail('claim',card_id=c,choice='1',fingerprint=FP)
    def test_expiry(self):
        c = self.offer(); self.now += timedelta(minutes=4)
        self.fail('claim',card_id=c,choice='1',fingerprint=FP)
    def test_price_change(self):
        c = self.offer(); self.fail('claim',card_id=c,choice='1',fingerprint='b'*64)
    def test_natural_language_not_number(self):
        c = self.offer(); self.fail('claim',card_id=c,choice='好的',fingerprint=FP)
    def test_cross_session(self):
        c = self.offer(); self.fail('claim',card_id=c,choice='1',fingerprint=FP,session='other')
    def test_cross_scope(self):
        c = self.offer(); self.fail('claim',card_id=c,choice='1',fingerprint=FP,scope='other')
    def test_ttl_max(self):
        self.fail('offer',expires_at=(self.now+timedelta(minutes=6)).isoformat(),options=[])
    def test_unexpected_private_field(self):
        o = dict(number='1',action='create',label='合成',total_cents=1,fingerprint=FP,addressId='secret')
        self.fail('offer',expires_at=(self.now+timedelta(minutes=1)).isoformat(),options=[o])
    def test_one_dispatch(self):
        r=self.claim(); self.call('begin',receipt=r,stage='create')
        self.fail('begin',receipt=r,stage='create')
    def test_unknown_blocks_scope(self):
        r=self.claim(); self.call('begin',receipt=r,stage='create')
        self.call('record',receipt=r,stage='create',outcome='unknown')
        with self.assertRaises(g.GuardError): self.offer(session='other')
        self.fail('abort',receipt=r)
    def test_crash_after_begin_blocks(self):
        r=self.claim(); self.call('begin',receipt=r,stage='create')
        self.fail('finish',receipt=r,final_new_pending=True)
        self.fail('begin',receipt=r,stage='create')
    def test_absence_requires_evidence(self):
        r=self.claim(); self.call('begin',receipt=r,stage='create')
        self.fail('reconcile',receipt=r,stage='create',outcome='confirmed_absent')
        self.call('reconcile',receipt=r,stage='create',outcome='confirmed_absent',evidence='authoritative_absence')
        self.fail('begin',receipt=r,stage='create')
        self.assertTrue(self.offer())
    def test_unknown_recovery(self):
        r=self.claim(); self.call('begin',receipt=r,stage='create')
        self.call('record',receipt=r,stage='create',outcome='unknown')
        self.call('reconcile',receipt=r,stage='create',outcome='success',new_order_id='1002')
        self.call('verify',receipt=r,new_order_id='1002',matched=True,pending=True)
        self.assertTrue(self.call('finish',receipt=r,final_new_pending=True)['completed'])
    def test_cancel_before_create_forbidden(self):
        r=self.claim('replace'); self.fail('begin',receipt=r,stage='cancel',old_pending=True)
    def test_failed_verification_stops_cancel(self):
        r=self.created('replace')
        self.call('verify',receipt=r,new_order_id='1002',matched=False,pending=True)
        self.fail('begin',receipt=r,stage='cancel',old_pending=True)
    def test_old_not_pending_stops_cancel(self):
        r=self.created('replace'); self.fail('begin',receipt=r,stage='cancel',old_pending=False)
    def test_replace_complete(self):
        r=self.created('replace')
        self.call('begin',receipt=r,stage='cancel',old_pending=True)
        self.call('record',receipt=r,stage='cancel',outcome='success')
        self.fail('finish',receipt=r,final_new_pending=True,final_old_terminal='paid')
        self.assertEqual(self.call('finish',receipt=r,final_new_pending=True,final_old_terminal='cancelled')['order_id'],'1002')
    def test_cancel_failure_stops_finish(self):
        for outcome in ['failed','unknown']:
            with self.subTest(outcome=outcome):
                r=self.created('replace')
                self.call('begin',receipt=r,stage='cancel',old_pending=True)
                self.call('record',receipt=r,stage='cancel',outcome=outcome)
                self.fail('finish',receipt=r,final_new_pending=True,final_old_terminal='cancelled')
                self.fail('begin',receipt=r,stage='cancel',old_pending=True)
                self.call('reconcile',receipt=r,stage='cancel',outcome='success',confirmed_terminal='cancelled')
                self.call('finish',receipt=r,final_new_pending=True,final_old_terminal='cancelled')
    def test_keep_no_create(self):
        r=self.claim('keep'); self.fail('begin',receipt=r,stage='create')
        self.assertTrue(self.call('finish',receipt=r,old_pending=True)['completed'])
    def test_abort_before_dispatch(self):
        r=self.claim(); self.assertTrue(self.call('abort',receipt=r)['aborted'])
        self.assertTrue(self.offer())
    def test_record_without_begin(self):
        r=self.claim(); self.fail('record',receipt=r,stage='create',outcome='success',new_order_id='1002')
    def test_same_order_forbidden(self):
        r=self.claim('replace'); self.call('begin',receipt=r,stage='create')
        self.fail('record',receipt=r,stage='create',outcome='success',new_order_id='1001')
    def test_conflicting_recovery_forbidden(self):
        r=self.created(); self.fail('reconcile',receipt=r,stage='create',outcome='success',new_order_id='1003')
    def test_concurrent_claim(self):
        c=self.offer(); barrier=threading.Barrier(2)
        def worker(_):
            guard=g.Guard(self.path,clock=lambda:self.now)
            try:
                barrier.wait()
                try:
                    guard.apply(dict(op='claim',scope='test-account',session='test-session',card_id=c,choice='1',fingerprint=FP))
                    return True
                except g.GuardError: return False
            finally: guard.close()
        with ThreadPoolExecutor(max_workers=2) as pool:
            self.assertEqual(sum(pool.map(worker,range(2))),1)
    def test_cross_session_card_invalidated(self):
        c=self.offer(session='other'); r=self.claim()
        self.call('abort',receipt=r)
        self.fail('claim',session='other',card_id=c,choice='1',fingerprint=FP)
    def test_package_db_forbidden(self):
        with self.assertRaises(g.GuardError): g.Guard(ROOT/'bad.sqlite3')
    def test_status_reopen_persists_unknown(self):
        r=self.claim(); self.call('begin',receipt=r,stage='create')
        self.guard.close(); self.guard=g.Guard(self.path,clock=lambda:self.now)
        self.assertEqual(self.call('status')['cards'][0]['create_state'],'dispatching')
        self.fail('begin',receipt=r,stage='create')
    def test_cancel_reconcile_rejects_paid(self):
        r=self.created('replace'); self.call('begin',receipt=r,stage='cancel',old_pending=True)
        self.call('record',receipt=r,stage='cancel',outcome='unknown')
        self.fail('reconcile',receipt=r,stage='cancel',outcome='success',confirmed_terminal='paid')
    def test_failed_create_requires_new_authorization(self):
        r=self.claim(); self.call('begin',receipt=r,stage='create')
        self.call('record',receipt=r,stage='create',outcome='failed')
        self.fail('begin',receipt=r,stage='create')
        self.assertTrue(self.offer())

class TemplateTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.guard=g.Guard(Path(self.tmp.name)/'test.db')
    def tearDown(self): self.guard.close(); self.tmp.cleanup()
    def call(self,op,**kw): return self.guard.apply(dict(op=op,scope='account',**kw))
    def save(self,**kw):
        d=dict(template_id='breakfast',explicit_intent=True,source='user_confirmed_request',
               data=dict(name='合成早餐',scene={'mode':'pickup'},items=[food()],restrictions=[])); d.update(kw)
        return self.call('template-save',**d)
    def consent(self): self.call('consent',granted=True,notice_version='1')
    def test_consent_required(self):
        with self.assertRaises(g.GuardError): self.save()
    def test_explicit_required(self):
        self.consent()
        for kw in [dict(explicit_intent=False),dict(source='cancelled_order'),dict(source='pending_order')]:
            with self.subTest(kw=kw), self.assertRaises(g.GuardError): self.save(**kw)
    def test_save_list_delete(self):
        self.consent(); self.save()
        self.assertEqual(len(self.call('template-list')['templates']),1)
        self.assertEqual(self.call('template-delete',template_id='breakfast')['deleted_count'],1)
    def test_revocation_preserves_until_purge(self):
        self.consent(); self.save(); self.call('consent',granted=False,notice_version='1')
        with self.assertRaises(g.GuardError): self.save()
        self.assertEqual(len(self.call('template-list')['templates']),1)
        self.call('consent',granted=False,notice_version='1',purge=True)
        self.assertEqual(self.call('template-list')['templates'],[])
    def test_private_fields_forbidden(self):
        self.consent()
        d=dict(name='合成',scene={'mode':'pickup','addressId':'secret'},items=[food()],restrictions=[])
        with self.assertRaises(g.GuardError): self.save(data=d)
    def test_reopen_template_persists(self):
        self.consent(); self.save(); self.guard.close()
        self.guard=g.Guard(Path(self.tmp.name)/'test.db')
        self.assertEqual(self.call('template-list')['templates'][0]['template_id'],'breakfast')
    def test_payment_url_forbidden(self):
        self.consent()
        d=dict(name='https://test.invalid/pay',scene={'mode':'pickup'},items=[food()],restrictions=[])
        with self.assertRaises(g.GuardError): self.save(data=d)

class CliTests(unittest.TestCase):
    def full_cli(self, action):
        with tempfile.TemporaryDirectory() as tmp:
            db=str(Path(tmp)/'cli.db')
            def invoke(op, **kw):
                data=dict(op=op,scope='cli-account',session='cli-session'); data.update(kw)
                p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/guard.py'),'--db',db],
                                 input=json.dumps(data),capture_output=True,text=True)
                self.assertEqual(p.returncode,0,p.stdout+p.stderr)
                return json.loads(p.stdout)['result']
            option=dict(number='1',action=action,label='合成命令行流程',total_cents=1500,fingerprint=FP)
            if action!='create': option['old_order_id']='2001'
            card=invoke('offer',expires_at=(datetime.now(timezone.utc)+timedelta(minutes=3)).isoformat(),options=[option])
            r=invoke('claim',card_id=card['card_id'],choice='1',fingerprint=FP)['receipt']
            if action=='keep':
                self.assertTrue(invoke('finish',receipt=r,old_pending=True)['completed']); return
            self.assertTrue(invoke('begin',receipt=r,stage='create')['allow_dispatch'])
            invoke('record',receipt=r,stage='create',outcome='success',new_order_id='2002')
            invoke('verify',receipt=r,new_order_id='2002',matched=True,pending=True)
            final=dict(final_new_pending=True)
            if action=='replace':
                invoke('begin',receipt=r,stage='cancel',old_pending=True)
                invoke('record',receipt=r,stage='cancel',outcome='success')
                final['final_old_terminal']='cancelled'
            self.assertTrue(invoke('finish',receipt=r,**final)['completed'])
    def test_cli_keep(self): self.full_cli('keep')
    def test_cli_create(self): self.full_cli('create')
    def test_cli_replace(self): self.full_cli('replace')
    def test_json_cli(self):
        p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/guard.py')],
                         input=json.dumps(dict(op='money',value='7.5',unit='yuan')),capture_output=True,text=True)
        self.assertEqual(p.returncode,0); self.assertEqual(json.loads(p.stdout)['result']['cents'],750)
    def test_bad_json_no_echo(self):
        p=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/guard.py')],input='secret-not-json',capture_output=True,text=True)
        self.assertNotEqual(p.returncode,0); self.assertNotIn('secret-not-json',p.stdout+p.stderr)

if __name__=='__main__': unittest.main()
