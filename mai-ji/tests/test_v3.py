"""1.2.0 standard-food, explicit-note and legacy-template regressions."""
import copy
import json
import unittest
from pathlib import Path

import test_guard as base
from test_guard import food, g


def standard(code='TEST_FOOD', **kw):
    item = food(code, **kw)
    item.pop('modifications', None)
    return item


class StandardFoodTests(unittest.TestCase):
    compare = base.CompareTests.compare

    def test_standard_missing_modifications_is_complete(self):
        result = self.compare([standard()], [standard()])
        self.assertEqual(result['classification'], 'equivalent')
        self.assertTrue(result['cheaper'])

    def test_old_empty_and_new_standard_are_equivalent(self):
        self.assertEqual(self.compare([food()], [standard()])['classification'], 'equivalent')

    def test_normalized_standard_has_no_recipe_field(self):
        item = g.leaf(food())
        self.assertNotIn('modifications', item)
        self.assertNotIn('notes', item)

    def test_standard_empty_notes_and_omitted_notes_match(self):
        self.assertEqual(self.compare([standard(notes=[])], [standard()])['classification'], 'equivalent')

    def test_explicit_note_cannot_be_dropped(self):
        self.assertEqual(self.compare([standard(notes=['不要酱'])], [standard()])['classification'], 'different')

    def test_added_note_is_not_equivalent(self):
        self.assertEqual(self.compare([standard()], [standard(notes=['不要酱'])])['classification'], 'different')

    def test_explicit_notes_preserved_with_quantity(self):
        item = g.leaf(standard(quantity=2, notes=[' 不要酱 ']))
        self.assertEqual(item['notes'], ['不要酱'])
        self.assertEqual(item['quantity'], 2)

    def test_note_order_does_not_change_comparison(self):
        a = standard(notes=['不要酱', '不加盐'])
        b = standard(notes=['不加盐', '不要酱'])
        self.assertEqual(self.compare([a], [b])['classification'], 'equivalent')

    def test_note_per_food_cannot_move_to_another_item(self):
        left = [standard('MAIN', notes=['不要酱']), standard('FRIES')]
        right = [standard('MAIN'), standard('FRIES', notes=['不要酱'])]
        self.assertEqual(self.compare(left, right)['classification'], 'different')

    def test_synonym_notes_not_assumed_equal(self):
        self.assertEqual(self.compare([standard(notes=['不要酱'])],
                                      [standard(notes=['少酱'])])['classification'], 'different')

    def test_quantity_and_product_flavor_remain_hard(self):
        self.assertEqual(self.compare([standard(quantity=2)], [standard()])['classification'], 'different')
        self.assertEqual(self.compare([standard()], [standard(quantity=2)])['classification'], 'extra')
        for changed in [standard('ZERO_COLA'), standard(spec='大杯')]:
            with self.subTest(changed=changed):
                self.assertEqual(self.compare([standard()], [changed])['classification'], 'different')

    def test_extra_still_requires_all_explicit_notes(self):
        need = [standard(notes=['不要酱'])]
        missing = [standard(), standard('DRINK')]
        kept = [standard(notes=['不要酱']), standard('DRINK')]
        self.assertEqual(self.compare(need, missing)['classification'], 'different')
        self.assertEqual(self.compare(need, kept)['classification'], 'extra')

    def test_changed_whole_order_remark_is_different(self):
        f = base.fulfill()
        f['remark_digest'] = 'b' * 64
        self.assertEqual(self.compare([standard()], [standard()],
                                      candidate_fulfillment=f)['classification'], 'different')

    def test_nonempty_legacy_field_not_ignored_even_with_notes(self):
        a = food(modifications=[dict(code='OLD', key='NO', quantity=1)], notes=['不要酱'])
        result = self.compare([a], [standard(notes=['不要酱'])])
        self.assertEqual(result['classification'], 'unknown')
        self.assertEqual(result['reason'], 'legacy_modifications_require_review')

    def test_invalid_legacy_field_not_treated_as_standard(self):
        for value in [None, '', {}, 0]:
            with self.subTest(value=value):
                self.assertEqual(self.compare([food(modifications=value)],
                                              [standard()])['classification'], 'unknown')

    def test_invalid_private_or_duplicate_notes_rejected(self):
        for value in ['不要酱', None, [' '], ['不要酱', ' 不要酱 '], ['x'] * 11,
                      ['x' * 121], ['https://test.invalid/note'], ['Bearer SYNTHETIC'], ['a\nb']]:
            with self.subTest(value=value), self.assertRaises(g.GuardError):
                g.leaf(standard(notes=value))


class LegacyTemplateTests(unittest.TestCase):
    setUp = base.TemplateTests.setUp
    tearDown = base.TemplateTests.tearDown
    call = base.TemplateTests.call
    save = base.TemplateTests.save
    consent = base.TemplateTests.consent

    def legacy(self, tid='legacy', mods=None):
        item = food(modifications=[] if mods is None else mods)
        data = dict(name='合成旧早餐', scene={'mode': 'pickup'}, items=[item], restrictions=[])
        self.guard.db.execute('INSERT INTO templates VALUES(?,?,?)',
                              ('account', tid, g.canonical(data)))
        return data

    def raw(self, tid='legacy'):
        return self.guard.db.execute('SELECT data FROM templates WHERE scope=? AND id=?',
                                     ('account', tid)).fetchone()['data']

    def test_new_standard_template_roundtrip_without_recipe_field(self):
        self.consent()
        data = dict(name='标准早餐', scene={'mode': 'pickup'}, items=[standard()], restrictions=[])
        self.save(data=data)
        loaded = self.call('template-load')
        self.assertEqual(loaded['review_required'], [])
        self.assertTrue(loaded['templates'][0]['auto_reuse_allowed'])
        self.assertNotIn('modifications', loaded['templates'][0]['data']['items'][0])

    def test_explicit_notes_roundtrip(self):
        self.consent()
        data = dict(name='明确备注早餐', scene={'mode': 'pickup'},
                    items=[standard(notes=['不要酱'])], restrictions=['不加饮料'])
        self.save(data=data)
        self.assertEqual(self.call('template-load')['templates'][0]['data'], data)

    def test_empty_legacy_normalized_read_without_db_overwrite(self):
        self.consent(); self.legacy()
        before = self.raw()
        result = self.call('template-load')
        self.assertEqual(len(result['templates']), 1)
        self.assertNotIn('modifications', result['templates'][0]['data']['items'][0])
        self.assertEqual(result['review_required'], [])
        self.assertEqual(before, self.raw())

    def test_nonempty_legacy_is_preserved_but_not_auto_reused(self):
        self.consent()
        data = self.legacy(mods=[dict(code='OLD', key='NO', quantity=1)])
        before = self.raw()
        result = self.call('template-load')
        self.assertEqual(result['templates'], [])
        self.assertFalse(result['review_required'][0]['auto_reuse_allowed'])
        self.assertEqual(result['review_required'][0]['data'], data)
        self.assertEqual(before, self.raw())
        listed = self.call('template-list')['templates'][0]
        self.assertFalse(listed['auto_reuse_allowed'])
        self.assertEqual(listed['data'], data)

    def test_one_legacy_does_not_block_other_standard_templates(self):
        self.consent(); self.save()
        self.legacy(mods=[dict(code='OLD', key='NO', quantity=1)])
        result = self.call('template-load')
        self.assertEqual([t['template_id'] for t in result['templates']], ['breakfast'])
        self.assertEqual([t['template_id'] for t in result['review_required']], ['legacy'])

    def test_nonempty_legacy_new_save_rejected_not_cleared(self):
        self.consent()
        data = self.legacy(mods=[dict(code='OLD', key='NO', quantity=1)])
        before = self.raw()
        with self.assertRaises(g.GuardError): self.save(template_id='legacy', data=data)
        self.assertEqual(before, self.raw())

    def test_explicit_update_preserves_notes_and_does_not_touch_consent(self):
        self.consent()
        data = self.legacy(mods=[dict(code='OLD', key='NO', quantity=1)])
        updated = copy.deepcopy(data)
        updated['items'] = [standard(notes=['不要酱'])]
        self.save(template_id='legacy', data=updated)
        result = self.call('template-load')
        self.assertEqual(result['review_required'], [])
        self.assertEqual(result['templates'][0]['data']['items'][0]['notes'], ['不要酱'])
        self.assertNotIn('modifications', json.loads(self.raw())['items'][0])

    def test_revocation_still_blocks_legacy_load_and_save(self):
        self.consent(); self.legacy(mods=[dict(code='OLD', key='NO', quantity=1)])
        self.call('consent', granted=False, notice_version='1')
        with self.assertRaises(g.GuardError): self.call('template-load')
        self.assertFalse(self.call('template-list')['reuse_allowed'])
        self.assertEqual(len(self.call('template-list')['templates']), 1)
        with self.assertRaises(g.GuardError): self.save()

    def test_review_survives_reopen(self):
        self.consent(); self.legacy(mods=[dict(code='OLD', key='NO', quantity=1)])
        before = self.raw()
        self.guard.close()
        self.guard = g.Guard(Path(self.tmp.name) / 'test.db')
        result = self.call('template-load')
        self.assertEqual(len(result['review_required']), 1)
        self.assertEqual(before, self.raw())

    def test_bad_legacy_note_kept_for_review_not_auto_reused(self):
        self.consent()
        data = self.legacy()
        data['items'][0]['notes'] = [' ']
        self.guard.db.execute('UPDATE templates SET data=? WHERE scope=? AND id=?',
                              (g.canonical(data), 'account', 'legacy'))
        result = self.call('template-load')
        self.assertEqual(result['templates'], [])
        self.assertEqual(result['review_required'][0]['review_reason'], 'empty_note')


class FinalTemplateReviewTests(unittest.TestCase):
    setUp = base.TemplateTests.setUp
    tearDown = base.TemplateTests.tearDown
    call = base.TemplateTests.call
    save = base.TemplateTests.save
    consent = base.TemplateTests.consent

    def put(self, raw, tid='broken'):
        self.guard.db.execute('INSERT OR REPLACE INTO templates VALUES(?,?,?)', ('account', tid, raw))

    def check_isolated(self, raw):
        self.put(raw)
        for op in ['template-load', 'template-list']:
            result = self.call(op)
            bad = result['review_required'][0]
            self.assertEqual(bad['template_id'], 'broken')
            self.assertIsNone(bad['data'])
            self.assertFalse(bad['auto_reuse_allowed'])
            self.assertEqual(len([t for t in result['templates'] if t['auto_reuse_allowed']]), 1)
        stored = self.guard.db.execute('SELECT data FROM templates WHERE id=?', ('broken',)).fetchone()['data']
        self.assertEqual(stored, raw)

    def test_corrupt_json_isolated_without_overwrite(self):
        self.consent(); self.save()
        self.check_isolated('{broken-SYNTHETIC-PRIVATE')

    def test_nonobject_and_missing_fields_isolated(self):
        self.consent(); self.save()
        for value in [None, [], {}, {'name': '合成缺字段'}]:
            with self.subTest(value=value): self.check_isolated(g.canonical(value))

    def test_entire_schema_and_private_fields_revalidated(self):
        self.consent(); self.save()
        good = dict(name='合成', scene={'mode': 'pickup'}, items=[standard()], restrictions=[])
        candidates = []
        for key in ['name', 'scene', 'restrictions']:
            d = copy.deepcopy(good)
            d[key] = {'addressId': 'SYNTHETIC_PRIVATE'} if key == 'scene' else 'https://test.invalid/private'
            candidates.append(d)
        d = copy.deepcopy(good); d['paymentUrl'] = 'https://test.invalid/private'; candidates.append(d)
        d = copy.deepcopy(good); d['restrictions'] = ['Bearer SYNTHETIC']; candidates.append(d)
        for d in candidates:
            with self.subTest(data=d): self.check_isolated(g.canonical(d))

    def test_stored_duplicate_json_key_isolated(self):
        self.consent(); self.save()
        self.check_isolated('{"items":[],"items":[],"name":"合成","scene":{"mode":"pickup"},"restrictions":[]}')

    def test_stored_deep_json_isolated(self):
        self.consent(); self.save()
        self.check_isolated('[' * 5000 + '0' + ']' * 5000)

    def test_stored_oversize_isolated(self):
        self.consent(); self.save()
        self.check_isolated(' ' * (g.MAX_INPUT + 1))

    def test_stored_nonfinite_isolated(self):
        self.consent(); self.save()
        self.check_isolated('{"name":NaN,"scene":{"mode":"pickup"},"items":[],"restrictions":[]}')

    def test_private_legacy_code_is_not_echoed_for_review(self):
        self.consent(); self.save()
        d = dict(name='旧模板', scene={'mode': 'pickup'}, restrictions=[],
                 items=[food(modifications=[dict(code='Bearer SYNTHETIC', key='NO', quantity=1)])])
        self.check_isolated(g.canonical(d))

    def test_stored_surrogate_name_isolated_and_output_utf8_safe(self):
        self.consent(); self.save()
        d = dict(name='\ud800', scene={'mode': 'pickup'}, items=[standard()], restrictions=[])
        self.put(json.dumps(d, ensure_ascii=True))
        result = self.call('template-load')
        self.assertIsNone(result['review_required'][0]['data'])
        self.assertEqual(result['review_required'][0]['review_reason'], 'invalid_unicode_text')
        json.dumps(result, ensure_ascii=False).encode('utf-8')
        self.assertEqual(len(result['templates']), 1)

    def test_stored_unescaped_surrogate_isolated(self):
        self.consent(); self.save()
        with self.assertRaises(g.GuardError): g.stored_template('{"name":"\ud800"}')

    def test_bad_record_inspection_after_revocation_still_works(self):
        self.consent(); self.save(); self.put('{broken')
        self.call('consent', granted=False, notice_version='1')
        result = self.call('template-list')
        self.assertFalse(result['reuse_allowed'])
        self.assertEqual(len(result['templates']), 2)
        self.assertTrue(all(not t['auto_reuse_allowed'] for t in result['templates']))
        with self.assertRaises(g.GuardError): self.call('template-load')


class FinalStateReviewTests(unittest.TestCase):
    setUp = base.StateTests.setUp
    tearDown = base.StateTests.tearDown
    call = base.StateTests.call
    offer = base.StateTests.offer
    claim = base.StateTests.claim
    created = base.StateTests.created
    fail = base.StateTests.fail

    def cancelled_reconcile(self):
        r = self.created('replace')
        self.call('begin', receipt=r, stage='cancel', old_pending=True)
        self.call('record', receipt=r, stage='cancel', outcome='unknown')
        self.call('reconcile', receipt=r, stage='cancel', outcome='success', confirmed_terminal='cancelled')
        return r

    def test_reconciled_cancel_terminal_persists_across_reopen(self):
        r = self.cancelled_reconcile()
        self.guard.close(); self.guard = g.Guard(self.path, clock=lambda: self.now)
        self.assertEqual(self.call('status')['cards'][0]['old_terminal'], 'cancelled')
        self.assertTrue(self.call('finish', receipt=r, final_new_pending=True,
                                  final_old_terminal='cancelled')['completed'])

    def test_reconciled_terminal_cannot_be_changed_by_finish(self):
        r = self.cancelled_reconcile()
        self.fail('finish', receipt=r, final_new_pending=True, final_old_terminal='expired')
        row = self.call('status')['cards'][0]
        self.assertEqual(row['status'], 'claimed')
        self.assertEqual(row['old_terminal'], 'cancelled')

    def test_conflicting_reconcile_and_observe_both_rollback(self):
        r = self.cancelled_reconcile()
        self.fail('reconcile', receipt=r, stage='cancel', outcome='success', confirmed_terminal='expired')
        self.fail('observe', receipt=r, target='old', order_id='1001', terminal='expired',
                  evidence='detail_and_list_confirmed')
        self.assertEqual(self.call('status')['cards'][0]['old_terminal'], 'cancelled')

    def test_finish_persists_final_old_terminal(self):
        r = self.created('replace')
        self.call('begin', receipt=r, stage='cancel', old_pending=True)
        self.call('record', receipt=r, stage='cancel', outcome='success')
        self.call('finish', receipt=r, final_new_pending=True, final_old_terminal='cancelled')
        self.assertEqual(self.call('status')['cards'][0]['old_terminal'], 'cancelled')

    def test_closed_failed_creation_cannot_reconcile_or_dispatch(self):
        r = self.claim()
        self.call('begin', receipt=r, stage='create')
        self.call('record', receipt=r, stage='create', outcome='failed')
        self.fail('reconcile', receipt=r, stage='create', outcome='success', new_order_id='1002')
        self.fail('reconcile', receipt=r, stage='create', outcome='unknown')
        self.fail('begin', receipt=r, stage='create')
        row = self.call('status')['cards'][0]
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['create_state'], 'failed')
        self.assertIsNone(row['new_order_id'])


if __name__ == '__main__':
    unittest.main()
