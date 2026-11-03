"""Safety and reproducibility checks. Run: python -m unittest -v"""
import json
import unittest
from decimal import Decimal
from invoicelens import ROOT, assess, digest, fit, money, metrics

class Checks(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.model=json.loads((ROOT/'model.json').read_text())
        cls.cases=json.loads((ROOT/'data/test.json').read_text())
        cls.a=cls.cases[0]['a']
    def test_decimal_exactness(self):
        self.assertEqual(money('0.10')+money('0.20'),Decimal('0.30'))
    def test_invalid_money(self):
        for v in ['', 'NaN', 'Infinity', '-Infinity', '1.001', 'USD 10']:
            self.assertIsNone(money(v))
    def test_abstention_routes(self):
        for c in self.cases:
            if 'expected_route' in c:
                self.assertEqual(assess(c['a'],c['b'],self.model)['status'],c['expected_route'])
    def test_zero_amount_requires_review(self):
        self.assertEqual(assess(self.a,dict(self.a,amount='0.00'),self.model)['status'],'SPECIALIST REVIEW')
    def test_both_non_usd_out_of_scope(self):
        a=dict(self.a,currency='EUR')
        self.assertEqual(assess(a,a,self.model)['status'],'OUT OF SCOPE')
    def test_missing_vendor_requires_review(self):
        self.assertEqual(assess(self.a,dict(self.a,vendor=''),self.model)['status'],'DATA REVIEW')
    def test_no_payment_action(self):
        result=assess(self.a,self.a,self.model)
        self.assertNotIn('approved',result)
        self.assertIn('NO FLAG never means approved for payment.',result['reasons'])
    def test_source_hash_changes(self):
        self.assertNotEqual(digest(self.a),digest(dict(self.a,amount='1250.01')))
    def test_training_reproducible(self):
        rows=json.loads((ROOT/'data/train.json').read_text())
        self.assertEqual(fit(rows),self.model)
    def test_metrics_match_rows(self):
        r=json.loads((ROOT/'results.json').read_text())
        for name,value in r['metrics'].items():
            self.assertEqual(metrics(r['cases'],name),value)

if __name__=='__main__': unittest.main()
