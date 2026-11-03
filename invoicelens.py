"""InvoiceLens: synthetic duplicate-invoice triage. Python 3.10+, standard library.

Run python invoicelens.py to retrain, evaluate and rebuild the offline reviewer.
No APIs, network calls, credentials, payment actions or third-party packages.
"""
from pathlib import Path
from datetime import date
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
import csv
import hashlib
import json
import math
import random
import re

ROOT = Path(__file__).resolve().parent
FEATURES = ['vendor_similarity', 'invoice_similarity', 'description_similarity',
            'same_amount', 'date_proximity', 'same_service_period', 'different_service_period']
THRESHOLD = 0.60

def norm(value):
    return re.sub(r'[^a-z0-9]', '', str(value).lower())

def similarity(a, b):
    return SequenceMatcher(None, norm(a), norm(b)).ratio() if a and b else 0.0

def money(value):
    try:
        result = Decimal(str(value))
        if not result.is_finite() or result.as_tuple().exponent < -2:
            return None
        return result
    except (InvalidOperation, ValueError):
        return None

def gap(a, b):
    try:
        return abs((date.fromisoformat(a) - date.fromisoformat(b)).days)
    except (ValueError, TypeError):
        return None

def features(a, b):
    days = gap(a['date'], b['date'])
    periods = bool(a.get('period') and b.get('period'))
    return [similarity(a['vendor'], b['vendor']), similarity(a['number'], b['number']),
            similarity(a['description'], b['description']),
            float(money(a['amount']) is not None and money(a['amount']) == money(b['amount'])),
            max(0, 1 - days / 90) if days is not None else 0,
            float(periods and a['period'] == b['period']),
            float(periods and a['period'] != b['period'])]

def sigmoid(z):
    return 1 / (1 + math.exp(-max(-35, min(35, z))))

def fit(rows):
    """Full-batch gradient descent, fixed initialization, L2=0.01, 1500 steps."""
    xy = [(features(r['a'], r['b']), r['label']) for r in rows]
    weights, bias = [0.0] * len(FEATURES), 0.0
    for _ in range(1500):
        dw, db = [0.0] * len(weights), 0.0
        for x, y in xy:
            error = sigmoid(bias + sum(w * v for w, v in zip(weights, x))) - y
            db += error
            for j, v in enumerate(x):
                dw[j] += error * v
        bias -= 0.25 * db / len(xy)
        weights = [w - 0.25 * (g / len(xy) + 0.01 * w) for w, g in zip(weights, dw)]
    # Canonical precision suppresses platform math-library noise (~1e-15),
    # keeping serialized model hashes stable without changing reported scores.
    weights, bias = [round(w, 12) for w in weights], round(bias, 12)
    return {'type': 'logistic regression', 'features': FEATURES, 'weights': weights,
            'bias': bias, 'coefficient_decimal_places': 12,
            'threshold': THRESHOLD, 'training_rows': len(rows),
            'training_sha256': digest(rows), 'version': 'synthetic-lr-v1',
            'warning': 'Uncalibrated ranking score; not a probability of duplicate payment.'}

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, ensure_ascii=True).encode()).hexdigest()

def assess(a, b, model):
    x = features(a, b)
    score = sigmoid(model['bias'] + sum(w * v for w, v in zip(model['weights'], x)))
    reasons = []
    invalid = any(not r.get(k) for r in (a, b) for k in ('vendor', 'number', 'currency', 'date'))
    invalid |= money(a['amount']) is None or money(b['amount']) is None or gap(a['date'], b['date']) is None
    if invalid:
        status, reasons = 'DATA REVIEW', ['A required field is missing or invalid; scoring cannot settle this pair.']
    elif a.get('kind') != 'invoice' or b.get('kind') != 'invoice' or money(a['amount']) <= 0 or money(b['amount']) <= 0:
        status, reasons = 'SPECIALIST REVIEW', ['Credit notes and non-positive amounts need a separate reconciliation workflow.']
    elif a['currency'] != 'USD' or b['currency'] != 'USD':
        status, reasons = 'OUT OF SCOPE', ['Only USD invoice pairs are supported; no exchange-rate conversion is performed.']
    elif money(a['amount']) != money(b['amount']):
        status, reasons = 'NO FLAG', ['Amounts differ exactly. Partial/revised duplicates can be missed by this narrow scope.']
    else:
        status = 'REVIEW' if score >= model['threshold'] else 'NO FLAG'
        reasons = ['Equal USD face amounts; this is not evidence of settlement.',
                   'Compare invoice identity, service period and supporting receipt before deciding.']
    reasons.append('NO FLAG never means approved for payment.')
    contributions = [{'feature': name, 'value': round(value, 4), 'logit_contribution': round(value * weight, 4)}
                     for name, value, weight in zip(FEATURES, x, model['weights'])]
    return {'status': status, 'score': round(score, 6), 'reasons': reasons,
            'contributions': contributions, 'a_sha256': digest(a), 'b_sha256': digest(b),
            'model_sha256': digest(model), 'policy_version': 'usd-equal-face-amount-v1'}

def baselines(a, b):
    valid = all(r.get('currency') == 'USD' and r.get('kind') == 'invoice' and money(r['amount']) is not None and money(r['amount']) > 0 for r in (a,b))
    equal = valid and money(a['amount']) == money(b['amount'])
    exact = bool(equal and a['vendor_id'] == b['vendor_id'] and a['number'] == b['number'])
    normalized = bool(equal and a['vendor_id'] == b['vendor_id'] and norm(a['number']) == norm(b['number']))
    days = gap(a['date'], b['date'])
    fuzzy = bool(equal and similarity(a['vendor'], b['vendor']) >= 0.55 and days is not None and days <= 45)
    return {'exact': exact, 'normalized': normalized, 'broad_fuzzy': fuzzy}

def metrics(rows, key):
    labeled = [r for r in rows if r['label'] in (0, 1)]
    tp = sum(r['label'] == 1 and r[key] for r in labeled)
    fp = sum(r['label'] == 0 and r[key] for r in labeled)
    fn = sum(r['label'] == 1 and not r[key] for r in labeled)
    tn = sum(r['label'] == 0 and not r[key] for r in labeled)
    return {'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
            'precision': round(tp/(tp+fp), 4) if tp+fp else None,
            'recall': round(tp/(tp+fn), 4) if tp+fn else None,
            'flagged': tp+fp, 'labeled_pairs': len(labeled)}

def main():
    training = json.loads((ROOT / 'data/train.json').read_text(encoding='utf-8'))
    cases = json.loads((ROOT / 'data/test.json').read_text(encoding='utf-8'))
    assert not ({digest(r['a']) for r in training} & {digest(r['a']) for r in cases})
    model = fit(training)
    results = []
    for case in cases:
        assessment = assess(case['a'], case['b'], model)
        result = {**case, **assessment, **baselines(case['a'], case['b'])}
        result['hybrid'] = assessment['status'] == 'REVIEW'
        results.append(result)
    report = {'model': model, 'test_sha256': digest(cases), 'cases': results,
              'metrics': {k: metrics(results, k) for k in ['exact', 'normalized', 'broad_fuzzy', 'hybrid']},
              'routing_checks': {r['id']: r['status'] == r['expected_route'] for r in results if 'expected_route' in r},
              'limitations': 'AI-authored synthetic data and labels. Test templates overlap with training motifs. No independent field validation, OCR, production calibration, or timing study.'}
    for filename, obj in [('model.json', model), ('results.json', report)]:
        (ROOT / filename).write_text(json.dumps(obj, indent=2), encoding='utf-8')
    with (ROOT / 'results.csv').open('w', newline='', encoding='utf-8') as f:
        fields = ['id','scenario','label','status','score','exact','normalized','broad_fuzzy','hybrid','rationale']
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore', lineterminator='\n')
        writer.writeheader(); writer.writerows(results)
    payload = json.dumps(report, ensure_ascii=True).replace('<', '\\u003c')
    (ROOT / 'index.html').write_text((ROOT / 'reviewer.template.html').read_text(encoding='utf-8').replace('__REPORT_JSON__', payload), encoding='utf-8')
    print(json.dumps({'metrics': report['metrics'], 'routing_checks': report['routing_checks']}, indent=2))

if __name__ == '__main__':
    main()
