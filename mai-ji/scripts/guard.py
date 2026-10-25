#!/usr/bin/env python3
"""Local-only guard. Never sends MCP requests or payments. Python 3.10+."""
import argparse
import hashlib
import json
import re
import secrets
import sqlite3
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path

VERSION = '1.2.0'
SKILL_ROOT = Path(__file__).resolve().parent.parent
MAX_INPUT = 200000

class GuardError(Exception):
    pass

def require(condition, code):
    if not condition:
        raise GuardError(code)

def fields(obj, allowed, required=()):
    require(isinstance(obj, dict), 'object_required')
    require(not (set(obj) - set(allowed)), 'unexpected_field')
    require(set(required) <= set(obj), 'missing_field')

def text(value, maximum=120):
    require(isinstance(value, str) and 0 < len(value) <= maximum, 'invalid_text')
    require(not re.search(r'[\x00-\x1f]', value), 'control_character')
    require(not re.search(r'[\ud800-\udfff]', value), 'invalid_unicode_text')
    return value

def private_text(value, maximum=120):
    value = text(value, maximum)
    require(not re.search(r'https?://|1[3-9]\d{9}|Bearer\s|sk-[A-Za-z0-9]', value, re.I), 'private_value_forbidden')
    return value

def integer(value, minimum=0, maximum=10**12):
    require(type(value) is int and minimum <= value <= maximum, 'invalid_integer')
    return value

def order_id(value):
    require(isinstance(value, str) and re.fullmatch(r'[0-9]{1,64}', value), 'invalid_order_id')
    return value

def fingerprint(value):
    require(isinstance(value, str) and re.fullmatch('[0-9a-f]{64}', value), 'invalid_fingerprint')
    return value

def canonical(value):
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)
    except RecursionError:
        raise GuardError('input_too_deep')

def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate_json_key')
        result[key] = value
    return result

def selection(data):
    fields(data, ['op', 'reply', 'current_card_id', 'require_card_id'],
           ['op', 'reply', 'current_card_id'])
    card_id = text(data['current_card_id'], 16).lower()
    require(re.fullmatch('[0-9a-f]{16}', card_id), 'invalid_card_id')
    reply = text(data['reply'], 100).strip()
    explicit = data.get('require_card_id', False)
    require(type(explicit) is bool, 'boolean_required')
    if re.fullmatch('[1-9][0-9]?', reply):
        require(not explicit, 'card_id_required')
        return {'card_id': card_id, 'choice': reply}
    match = re.fullmatch(r'(?:卡\s*)?([0-9a-f]{16})(?:\s*[:：]\s*|\s+)([1-9][0-9]?)', reply, re.I)
    require(match is not None, 'invalid_selection_reply')
    require(match.group(1).lower() == card_id, 'selection_targets_old_card')
    return {'card_id': card_id, 'choice': match.group(2)}

def instant(value):
    require(isinstance(value, str), 'invalid_time')
    try:
        result = datetime.fromisoformat(value.replace('Z', '+00:00'))
        require(result.tzinfo is not None and result.utcoffset() is not None, 'timezone_required')
        return result.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise GuardError('invalid_time')

def cents(value, unit):
    require(type(value) in (str, int), 'money_requires_string_or_integer')
    require(unit in ('yuan', 'cents'), 'invalid_money_unit')
    raw = str(value).strip().replace('¥', '').replace('￥', '').replace(' ', '')
    require(bool(re.fullmatch(r'[+-]?[0-9]+(?:\.[0-9]+)?', raw)), 'invalid_money')
    precision = len(raw.split('.', 1)[1]) if '.' in raw else 0
    require(precision <= (2 if unit == 'yuan' else 0), 'excess_money_precision')
    try:
        amount = Decimal(raw)
        scaled = amount * (100 if unit == 'yuan' else 1)
        require(amount.is_finite() and scaled == scaled.to_integral_value(), 'fractional_cent')
        require(abs(scaled) <= 10**12, 'money_out_of_range')
        return int(scaled)
    except InvalidOperation:
        raise GuardError('invalid_money')

def leaf(item, legacy_review=False):
    fields(item, ['identity', 'name', 'spec', 'notes', 'modifications', 'quantity', 'complete'],
           ['identity', 'name', 'spec', 'quantity', 'complete'])
    require(item['complete'] is True, 'incomplete_product')
    ident = text(item['identity'], 100)
    require(re.fullmatch(r'[A-Za-z0-9_.:-]+', ident), 'invalid_identity')
    name = private_text(item['name'], 100)
    require(isinstance(item['spec'], str) and len(item['spec']) <= 100, 'invalid_spec')
    if item['spec']:
        private_text(item['spec'], 100)
    qty = integer(item['quantity'], 1)
    require(qty <= 1000, 'quantity_out_of_range')
    # Nonempty legacy choices are viewable for review, never executable by default.
    legacy = []
    if 'modifications' in item:
        mods = item['modifications']
        require(isinstance(mods, list) and len(mods) <= 60, 'invalid_legacy_modifications')
        require(not mods or legacy_review, 'legacy_modifications_require_review')
        for mod in mods:
            fields(mod, ['code', 'key', 'quantity'], ['code', 'key', 'quantity'])
            legacy.append({'code': private_text(mod['code'], 64),
                           'key': private_text(mod['key'], 64),
                           'quantity': integer(mod['quantity'], maximum=1000)})
        legacy.sort(key=lambda m: (m['code'], m['key'], m['quantity']))
        require(len({(m['code'], m['key']) for m in legacy}) == len(legacy), 'duplicate_modification')
    notes = item.get('notes', [])
    require(isinstance(notes, list) and len(notes) <= 10, 'invalid_notes')
    normalized = sorted(private_text(n, 120).strip() for n in notes)
    require(all(normalized), 'empty_note')
    require(len(set(normalized)) == len(normalized), 'duplicate_note')
    result = {'identity': ident, 'name': name, 'spec': item['spec'],
              'quantity': qty, 'complete': True}
    if normalized:
        result['notes'] = normalized
    if legacy:
        result['modifications'] = legacy
    return result

def leaves(items, legacy_review=False):
    require(isinstance(items, list) and 0 < len(items) <= 200, 'invalid_items')
    return [leaf(i, legacy_review=legacy_review) for i in items]

def template_data(data, legacy_review=False):
    fields(data, ['name', 'scene', 'items', 'restrictions'], ['name', 'scene', 'items', 'restrictions'])
    name = private_text(data['name'], 80)
    scene = data['scene']
    fields(scene, ['daypart', 'mode', 'storeCode', 'address_label', 'takeway_label'])
    require(bool(scene), 'scene_required')
    scene = {k: private_text(v, 80) for k, v in scene.items()}
    require(isinstance(data['restrictions'], list) and len(data['restrictions']) <= 30, 'invalid_restrictions')
    return {'name': name, 'scene': scene, 'items': leaves(data['items'], legacy_review=legacy_review),
            'restrictions': [private_text(v, 120) for v in data['restrictions']]}

def stored_template(raw):
    require(isinstance(raw, str), 'invalid_stored_template')
    require(not re.search(r'[\ud800-\udfff]', raw), 'invalid_unicode_text')
    require(len(raw.encode('utf-8')) <= MAX_INPUT, 'stored_template_too_large')
    try:
        saved = json.loads(raw, object_pairs_hook=unique_object,
                           parse_constant=lambda _: (_ for _ in ()).throw(GuardError('invalid_json_number')))
        return template_data(saved, legacy_review=True)
    except RecursionError:
        raise GuardError('input_too_deep')
    except (ValueError, TypeError, KeyError):
        raise GuardError('invalid_stored_template')

def counts(items):
    result = Counter()
    for item in leaves(items):
        key = canonical({'identity': item['identity'], 'spec': item['spec'],
                         'notes': item.get('notes', [])})
        result[key] += item['quantity']
    return result

def fulfillment(value):
    keys = ['storeCode', 'orderType', 'beType', 'beCode', 'address_binding',
            'takeWayCode', 'reservationDate', 'needTableware', 'remark_digest']
    fields(value, keys, keys)
    text(value['storeCode'], 64)
    require(type(value['orderType']) is int and value['orderType'] in (1, 2), 'invalid_order_type')
    require(type(value['beType']) is int and value['beType'] in (1, 2), 'unsupported_first_version_channel')
    require(value['orderType'] == value['beType'], 'channel_mismatch')
    require(type(value['needTableware']) is bool, 'tableware_required')
    fingerprint(value['remark_digest'])
    require(value['reservationDate'] == '', 'reservation_not_validated')
    if value['orderType'] == 1:
        require(value['beCode'] == '' and value['address_binding'] == '', 'invalid_pickup_context')
        text(value['takeWayCode'], 100)
    else:
        text(value['beCode'], 100)
        fingerprint(value['address_binding'])
        require(value['takeWayCode'] == '', 'invalid_delivery_takeway')
    return value

def compare(data):
    fields(data, ['op', 'required', 'candidate', 'required_fulfillment', 'candidate_fulfillment',
                  'baseline_cents', 'candidate_cents'], ['op', 'required', 'candidate'])
    try:
        left, right = counts(data['required']), counts(data['candidate'])
        a, b = data.get('required_fulfillment'), data.get('candidate_fulfillment')
        fulfillment(a)
        fulfillment(b)
        if canonical(a) != canonical(b):
            return {'classification': 'different', 'reason': 'fulfillment_changed'}
    except GuardError as exc:
        return {'classification': 'unknown', 'reason': str(exc)}
    if left == right:
        result = {'classification': 'equivalent'}
    elif not (left - right):
        result = {'classification': 'extra', 'extra_quantity': sum((right - left).values())}
    else:
        result = {'classification': 'different', 'reason': 'required_product_changed'}
    if result['classification'] != 'different' and 'baseline_cents' in data and 'candidate_cents' in data:
        base = integer(data['baseline_cents'])
        cost = integer(data['candidate_cents'])
        result['savings_cents'] = base - cost
        result['cheaper'] = cost < base
        result['optional_gain'] = result['classification'] == 'extra' and cost <= base
    return result

class Guard:
    def __init__(self, db_path, clock=None):
        path = Path(db_path).expanduser()
        require(path.is_absolute(), 'absolute_db_path_required')
        path = path.resolve()
        require(not path.is_relative_to(SKILL_ROOT), 'db_inside_skill_forbidden')
        require(path.suffix in ('.sqlite3', '.db'), 'invalid_db_extension')
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), timeout=10, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA busy_timeout=10000')
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.execute('PRAGMA synchronous=FULL')
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS cards(
          id TEXT PRIMARY KEY, scope TEXT NOT NULL, session TEXT NOT NULL,
          expires TEXT NOT NULL, status TEXT NOT NULL, options TEXT NOT NULL,
          receipt TEXT UNIQUE, choice TEXT, create_state TEXT, cancel_state TEXT,
          new_order_id TEXT, verified INTEGER NOT NULL DEFAULT 0);
        CREATE INDEX IF NOT EXISTS card_scope ON cards(scope,status);
        CREATE TABLE IF NOT EXISTS consents(scope TEXT PRIMARY KEY, granted INTEGER NOT NULL, notice TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS templates(scope TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL,
          PRIMARY KEY(scope,id));
        ''')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            columns = {r['name'] for r in self.db.execute('PRAGMA table_info(cards)')}
            for column in ('old_terminal', 'new_terminal'):
                if column not in columns:
                    self.db.execute('ALTER TABLE cards ADD COLUMN ' + column + ' TEXT')
            self.db.execute('COMMIT')
        except Exception:
            self.db.execute('ROLLBACK')
            self.db.close()
            raise

    def close(self):
        self.db.close()

    def now(self):
        now = self.clock()
        require(now.tzinfo is not None, 'clock_timezone_required')
        return now.astimezone(timezone.utc)

    def apply(self, data):
        require(isinstance(data, dict), 'object_required')
        op = text(data.get('op'), 40)
        scope = text(data.get('scope'), 100)
        require(re.fullmatch('[A-Za-z0-9_.-]+', scope), 'invalid_scope')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            result = self._apply(op, scope, data)
            self.db.execute('COMMIT')
            return result
        except Exception:
            self.db.execute('ROLLBACK')
            raise

    def card(self, data, scope, receipt=False):
        session = text(data.get('session'), 120)
        key = text(data.get('receipt' if receipt else 'card_id'), 100)
        column = 'receipt' if receipt else 'id'
        row = self.db.execute('SELECT * FROM cards WHERE ' + column + '=? AND scope=? AND session=?',
                              (key, scope, session)).fetchone()
        require(row is not None, 'card_not_found_or_wrong_context')
        return dict(row)

    def chosen(self, card):
        return next(o for o in json.loads(card['options']) if o['number'] == card['choice'])

    def update(self, card, **values):
        keys = list(values)
        self.db.execute('UPDATE cards SET ' + ','.join(k + '=?' for k in keys) + ' WHERE id=?',
                        [values[k] for k in keys] + [card['id']])

    def _apply(self, op, scope, d):
        common = ['op', 'scope']
        context = common + ['session', 'card_id']
        rc = common + ['session', 'receipt']
        if op == 'offer':
            fields(d, common + ['session', 'expires_at', 'options'], common + ['session', 'expires_at', 'options'])
            session = text(d['session'], 120)
            expiry = instant(d['expires_at'])
            seconds = (expiry - self.now()).total_seconds()
            require(0 < seconds <= 300, 'card_ttl_must_be_1_to_300_seconds')
            require(not self.db.execute(
                "SELECT 1 FROM cards WHERE scope=? AND status='claimed'", (scope,)).fetchone(), 'unresolved_execution')
            options = d['options']
            require(isinstance(options, list) and 1 <= len(options) <= 3, 'invalid_options')
            normalized = []
            for o in options:
                fields(o, ['number', 'action', 'label', 'total_cents', 'fingerprint', 'old_order_id'],
                       ['number', 'action', 'label', 'total_cents', 'fingerprint'])
                require(isinstance(o['number'], str) and re.fullmatch('[1-9][0-9]?', o['number']), 'invalid_choice')
                require(o['action'] in ('keep', 'create', 'replace'), 'invalid_action')
                p = dict(o)
                p['label'] = private_text(o['label'], 200)
                integer(o['total_cents'])
                fingerprint(o['fingerprint'])
                if o['action'] in ('keep', 'replace'):
                    order_id(o.get('old_order_id'))
                else:
                    require('old_order_id' not in o, 'create_has_old_order')
                normalized.append(p)
            require(len({o['number'] for o in normalized}) == len(normalized), 'duplicate_choice')
            self.db.execute("UPDATE cards SET status='invalid' WHERE scope=? AND session=? AND status='offered'", (scope, session))
            card_id = secrets.token_hex(8)
            self.db.execute('INSERT INTO cards(id,scope,session,expires,status,options) VALUES(?,?,?,?,?,?)',
                            (card_id, scope, session, expiry.isoformat(), 'offered', canonical(normalized)))
            return {'card_id': card_id, 'expires_at': expiry.isoformat(), 'options': normalized}
        if op == 'claim':
            fields(d, context + ['choice', 'fingerprint'], context + ['choice', 'fingerprint'])
            c = self.card(d, scope)
            require(c['status'] == 'offered', 'card_already_used_or_invalid')
            require(self.now() < instant(c['expires']), 'card_expired')
            require(isinstance(d['choice'], str) and re.fullmatch('[1-9][0-9]?', d['choice']), 'pure_number_required')
            o = next((o for o in json.loads(c['options']) if o['number'] == d['choice']), None)
            require(o is not None, 'choice_not_found')
            require(fingerprint(d['fingerprint']) == o['fingerprint'], 'revalidation_changed')
            require(not self.db.execute("SELECT 1 FROM cards WHERE scope=? AND status='claimed'", (scope,)).fetchone(),
                    'unresolved_execution')
            receipt = secrets.token_hex(16)
            self.update(c, status='claimed', receipt=receipt, choice=d['choice'])
            self.db.execute("UPDATE cards SET status='invalid' WHERE scope=? AND id<>? AND status='offered'",
                            (scope, c['id']))
            return {'receipt': receipt, 'action': o['action'], 'old_order_id': o.get('old_order_id')}
        if op == 'invalidate':
            fields(d, context, context)
            c = self.card(d, scope)
            require(c['status'] == 'offered', 'cannot_invalidate_execution')
            self.update(c, status='invalid')
            return {'invalidated': True}
        if op == 'abort':
            fields(d, rc, rc)
            c = self.card(d, scope, receipt=True)
            require(c['status'] == 'claimed', 'execution_not_active')
            require(c['create_state'] is None and c['cancel_state'] is None, 'cannot_abort_dispatched_execution')
            self.update(c, status='aborted')
            return {'aborted': True, 'no_dispatch_recorded': True}
        if op in ('observe', 'recover'):
            allowed = rc + ['target', 'order_id', 'terminal', 'evidence', 'close', 'complete', 'final_new_pending']
            fields(d, allowed, rc + ['target', 'order_id', 'terminal', 'evidence'])
            if op == 'observe':
                c = self.card(d, scope, receipt=True)
            else:
                text(d['session'], 120)
                receipt = text(d['receipt'], 100)
                row = self.db.execute('SELECT * FROM cards WHERE receipt=? AND scope=?', (receipt, scope)).fetchone()
                require(row is not None, 'card_not_found_or_wrong_context')
                c = dict(row)
            require(c['status'] == 'claimed', 'execution_not_active')
            require(d['evidence'] == 'detail_and_list_confirmed', 'terminal_evidence_required')
            require(d['target'] in ('old', 'new'), 'invalid_target')
            require(d['terminal'] in ('cancelled', 'expired'), 'safe_terminal_required')
            require('close' not in d or type(d['close']) is bool, 'boolean_required')
            require('complete' not in d or type(d['complete']) is bool, 'boolean_required')
            require(not (d.get('close') and d.get('complete')), 'ambiguous_resolution')
            o = self.chosen(c)
            target = d['target']
            expected = o.get('old_order_id') if target == 'old' else c['new_order_id']
            require(expected is not None and order_id(d['order_id']) == expected, 'wrong_bound_order')
            if target == 'new':
                require(c['create_state'] == 'success', 'create_not_successful')
            require(c[target + '_terminal'] in (None, d['terminal']), 'conflicting_terminal')
            self.update(c, **{target + '_terminal': d['terminal']})
            c[target + '_terminal'] = d['terminal']
            if d.get('complete'):
                require(o['action'] == 'replace' and target == 'old', 'replacement_completion_only')
                require(c['create_state'] == 'success' and c['verified'] == 1 and
                        c['new_terminal'] is None and d.get('final_new_pending') is True, 'new_order_not_verified_pending')
                self.update(c, status='completed')
                return {'completed': True, 'order_id': c['new_order_id'], 'allow_dispatch': False,
                        'payment_performed': False}
            require('final_new_pending' not in d, 'unexpected_final_pending')
            if d.get('close'):
                if o['action'] == 'keep':
                    require(c['old_terminal'] in ('cancelled', 'expired'), 'old_terminal_not_confirmed')
                elif o['action'] == 'create':
                    require(c['new_terminal'] in ('cancelled', 'expired'), 'new_terminal_not_confirmed')
                else:
                    require(c['old_terminal'] in ('cancelled', 'expired') and
                            c['new_terminal'] in ('cancelled', 'expired'), 'both_terminals_required')
                self.update(c, status='stopped')
                return {'stopped': True, 'completed': False, 'allow_dispatch': False, 'payment_performed': False}
            return {'observed': True, 'target': target, 'terminal': d['terminal'], 'allow_dispatch': False}
        if op in ('begin', 'record', 'verify', 'reconcile', 'finish'):
            c = self.card(d, scope, receipt=True)
            require(c['status'] == 'claimed', 'execution_not_active')
            o = self.chosen(c)
            if op == 'begin':
                fields(d, rc + ['stage', 'old_pending'], rc + ['stage'])
                stage = d['stage']
                require(stage in ('create', 'cancel'), 'invalid_stage')
                require(c[stage + '_state'] is None, 'stage_already_dispatched')
                require(c['old_terminal'] is None and c['new_terminal'] is None, 'order_already_terminal')
                if stage == 'create':
                    require(o['action'] in ('create', 'replace'), 'create_not_authorized')
                else:
                    require(o['action'] == 'replace', 'cancel_not_authorized')
                    require(c['create_state'] == 'success' and c['verified'] == 1, 'new_order_not_verified')
                    require(d.get('old_pending') is True, 'old_order_not_pending')
                    require(c['new_order_id'] != o['old_order_id'], 'same_order_forbidden')
                self.update(c, **{stage + '_state': 'dispatching'})
                return {'allow_dispatch': True, 'stage': stage, 'old_order_id': o.get('old_order_id')}
            if op == 'record':
                fields(d, rc + ['stage', 'outcome', 'new_order_id'], rc + ['stage', 'outcome'])
                stage, outcome = d['stage'], d['outcome']
                require(stage in ('create', 'cancel'), 'invalid_stage')
                require(outcome in ('success', 'failed', 'unknown'), 'invalid_outcome')
                require(c[stage + '_state'] == 'dispatching', 'record_requires_dispatched_stage')
                values = {stage + '_state': outcome}
                if stage == 'create' and outcome == 'success':
                    new_id = order_id(d.get('new_order_id'))
                    require(new_id != o.get('old_order_id'), 'same_order_forbidden')
                    values['new_order_id'] = new_id
                else:
                    require('new_order_id' not in d, 'unexpected_new_order_id')
                if stage == 'create' and outcome == 'failed':
                    values['status'] = 'failed'
                self.update(c, **values)
                return {'recorded': True, 'stage': stage, 'outcome': outcome}
            if op == 'verify':
                fields(d, rc + ['new_order_id', 'matched', 'pending'], rc + ['new_order_id', 'matched', 'pending'])
                require(c['create_state'] == 'success', 'create_not_successful')
                require(order_id(d['new_order_id']) == c['new_order_id'], 'wrong_new_order')
                require(type(d['matched']) is bool and type(d['pending']) is bool, 'boolean_required')
                require(c['new_terminal'] is None, 'new_order_already_terminal')
                self.update(c, verified=1 if d['matched'] and d['pending'] else 0)
                return {'verified': d['matched'] and d['pending']}
            if op == 'reconcile':
                fields(d, rc + ['stage', 'outcome', 'new_order_id', 'evidence', 'confirmed_terminal'], rc + ['stage', 'outcome'])
                stage, outcome = d['stage'], d['outcome']
                require(stage in ('create', 'cancel'), 'invalid_stage')
                require(c[stage + '_state'] in ('dispatching', 'unknown', 'failed', 'success'), 'nothing_to_reconcile')
                require(outcome in ('success', 'confirmed_absent', 'unknown'), 'invalid_reconcile_outcome')
                require(c[stage + '_state'] != 'success' or outcome == 'success', 'cannot_downgrade_success')
                if outcome == 'unknown':
                    self.update(c, **{stage + '_state': 'unknown'})
                    return {'resolved': False}
                if stage == 'create' and outcome == 'confirmed_absent':
                    require(d.get('evidence') == 'authoritative_absence', 'absence_not_proven')
                    self.update(c, create_state='absent', status='failed')
                    return {'resolved': True, 'retry_requires_new_card': True}
                require(outcome == 'success', 'invalid_stage_outcome')
                if stage == 'create':
                    new_id = order_id(d.get('new_order_id'))
                    require(new_id != o.get('old_order_id'), 'same_order_forbidden')
                    require(c['new_order_id'] in (None, new_id), 'conflicting_order_id')
                    self.update(c, create_state='success', new_order_id=new_id)
                else:
                    terminal = d.get('confirmed_terminal')
                    require(terminal in ('cancelled', 'expired'), 'old_terminal_not_confirmed')
                    require(c['old_terminal'] in (None, terminal), 'conflicting_old_terminal')
                    self.update(c, cancel_state='success', old_terminal=terminal)
                return {'resolved': True}
            if op == 'finish':
                fields(d, rc + ['old_pending', 'final_new_pending', 'final_old_terminal'], rc)
                if o['action'] == 'keep':
                    require(c['old_terminal'] is None and d.get('old_pending') is True, 'old_order_not_pending')
                else:
                    require(c['new_terminal'] is None, 'new_order_already_terminal')
                    require(c['create_state'] == 'success' and c['verified'] == 1, 'new_order_not_verified')
                    require(d.get('final_new_pending') is True, 'new_order_not_pending')
                    if o['action'] == 'replace':
                        require(c['cancel_state'] == 'success' or c['old_terminal'] in ('cancelled', 'expired'),
                                'old_cancel_not_successful')
                        require(d.get('final_old_terminal') in ('cancelled', 'expired'), 'old_terminal_not_confirmed')
                        require(c['old_terminal'] is None or c['old_terminal'] == d['final_old_terminal'],
                                'conflicting_old_terminal')
                final = {'status': 'completed'}
                if o['action'] == 'replace':
                    final['old_terminal'] = d['final_old_terminal']
                self.update(c, **final)
                return {'completed': True, 'order_id': c['new_order_id'] or o.get('old_order_id'),
                        'payment_performed': False}
        if op == 'status':
            fields(d, common + ['session'], common)
            params = [scope]
            where = 'scope=?'
            if 'session' in d:
                where += ' AND session=?'
                params.append(text(d['session'], 120))
            rows = self.db.execute('SELECT * FROM cards WHERE ' + where +
                                   " ORDER BY CASE WHEN status='claimed' THEN 0 ELSE 1 END, rowid DESC LIMIT 30", params).fetchall()
            cards = []
            keys = ('id', 'session', 'status', 'receipt', 'choice', 'expires', 'create_state',
                    'cancel_state', 'new_order_id', 'verified', 'old_terminal', 'new_terminal')
            for row in rows:
                card = dict(row)
                view = {key: card[key] for key in keys}
                if card['choice'] is not None:
                    option = self.chosen(card)
                    view['selected'] = {key: option[key] for key in
                                        ('number', 'action', 'label', 'total_cents', 'fingerprint')}
                    view['selected']['old_order_id'] = option.get('old_order_id')
                cards.append(view)
            return {'cards': cards}
        if op == 'consent':
            fields(d, common + ['granted', 'notice_version', 'purge'], common + ['granted', 'notice_version'])
            require(type(d['granted']) is bool and d['notice_version'] == '1', 'invalid_consent')
            require('purge' not in d or type(d['purge']) is bool, 'boolean_required')
            require(not d.get('purge') or d['granted'] is False, 'purge_requires_revocation')
            self.db.execute('INSERT INTO consents VALUES(?,?,?) ON CONFLICT(scope) DO UPDATE SET granted=excluded.granted,notice=excluded.notice',
                            (scope, int(d['granted']), '1'))
            if d.get('purge'):
                self.db.execute('DELETE FROM templates WHERE scope=?', (scope,))
            return {'granted': d['granted'], 'reuse_allowed': d['granted'],
                    'templates_purged': d.get('purge', False)}
        if op == 'template-save':
            fields(d, common + ['template_id', 'data', 'explicit_intent', 'source'],
                   common + ['template_id', 'data', 'explicit_intent', 'source'])
            require(d['explicit_intent'] is True and d['source'] == 'user_confirmed_request', 'explicit_request_required')
            consent = self.db.execute('SELECT granted FROM consents WHERE scope=?', (scope,)).fetchone()
            require(consent is not None and consent['granted'] == 1, 'consent_required')
            tid = text(d['template_id'], 80)
            clean = template_data(d['data'])
            self.db.execute('INSERT INTO templates VALUES(?,?,?) ON CONFLICT(scope,id) DO UPDATE SET data=excluded.data',
                            (scope, tid, canonical(clean)))
            return {'saved': True, 'template_id': tid}
        if op in ('template-list', 'template-load'):
            fields(d, common, common)
            consent = self.db.execute('SELECT granted FROM consents WHERE scope=?', (scope,)).fetchone()
            reuse_allowed = consent is not None and consent['granted'] == 1
            if op == 'template-load':
                require(reuse_allowed, 'template_reuse_consent_required')
            rows = self.db.execute('SELECT id,data FROM templates WHERE scope=? ORDER BY id', (scope,)).fetchall()
            templates, review_required = [], []
            for row in rows:
                entry = {'template_id': row['id'], 'data': None, 'auto_reuse_allowed': False}
                try:
                    entry['data'] = stored_template(row['data'])
                except GuardError as exc:
                    entry['review_reason'] = str(exc)
                else:
                    if any(item.get('modifications') for item in entry['data']['items']):
                        entry['review_reason'] = 'legacy_modifications_require_review'
                    else:
                        entry['auto_reuse_allowed'] = reuse_allowed
                if 'review_reason' in entry:
                    review_required.append(entry)
                    if op == 'template-list':
                        templates.append(entry)
                else:
                    templates.append(entry)
            return {'reuse_allowed': reuse_allowed, 'templates': templates,
                    'review_required': review_required}
        if op == 'template-delete':
            fields(d, common + ['template_id', 'explicit_all'], common)
            if d.get('explicit_all') is True:
                require('template_id' not in d, 'ambiguous_delete')
                cur = self.db.execute('DELETE FROM templates WHERE scope=?', (scope,))
            else:
                require('explicit_all' not in d, 'invalid_delete')
                cur = self.db.execute('DELETE FROM templates WHERE scope=? AND id=?', (scope, text(d.get('template_id'), 80)))
            return {'deleted_count': cur.rowcount}
        raise GuardError('unsupported_operation')

def dispatch(data, db_path=None):
    require(isinstance(data, dict), 'object_required')
    if data.get('op') == 'money':
        fields(data, ['op', 'value', 'unit'], ['op', 'value', 'unit'])
        amount = cents(data['value'], data['unit'])
        return {'cents': amount, 'yuan': format(Decimal(amount) / 100, '.2f')}
    if data.get('op') == 'digest':
        fields(data, ['op', 'value'], ['op', 'value'])
        return {'fingerprint': hashlib.sha256(canonical(data['value']).encode('utf-8')).hexdigest()}
    if data.get('op') == 'compare':
        return compare(data)
    if data.get('op') == 'selection':
        return selection(data)
    require(db_path is not None, 'db_required')
    guard = Guard(db_path)
    try:
        return guard.apply(data)
    finally:
        guard.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', help='Absolute SQLite path outside the skill directory')
    args = parser.parse_args()
    try:
        raw = sys.stdin.buffer.read(MAX_INPUT + 1)
        require(len(raw) <= MAX_INPUT, 'input_too_large')
        data = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_object,
                          parse_constant=lambda _: (_ for _ in ()).throw(GuardError('invalid_json_number')))
        result = dispatch(data, args.db)
        print(json.dumps({'ok': True, 'result': result}, ensure_ascii=False, allow_nan=False))
        return 0
    except RecursionError:
        print(json.dumps({'ok': False, 'error': 'input_too_deep'}))
        return 2
    except (GuardError, ValueError, TypeError, KeyError, OverflowError, sqlite3.Error, OSError):
        error = sys.exc_info()[1]
        code = str(error) if isinstance(error, GuardError) else 'invalid_input_or_storage_error'
        print(json.dumps({'ok': False, 'error': code}, ensure_ascii=False))
        return 2

if __name__ == '__main__':
    sys.exit(main())
