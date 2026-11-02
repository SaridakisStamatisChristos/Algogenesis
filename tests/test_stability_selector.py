import unittest
from fractions import Fraction
from stability_selector import evaluate


class StabilitySelectorTests(unittest.TestCase):
    def test_exact_recurrence_and_causal_decisions(self):
        seq=[n*n for n in range(58)]
        run=evaluate(seq)
        self.assertEqual(run.selected_mae,0)
        self.assertEqual(run.records[0].index,32)
        self.assertTrue(any(r.selected in ('bm_short','bm_long') for r in run.records))

    def test_mutation_future_does_not_affect_prior_selection(self):
        seq=[n%7 for n in range(62)]
        bad=seq[:]
        bad[44:]=[n**2+4 for n in range(44,62)]
        a,b=evaluate(seq),evaluate(bad)
        for x,y in zip(a.records,b.records):
            if x.index<=44:
                self.assertEqual((x.selected,x.predicted,x.scores,x.candidates),
                                 (y.selected,y.predicted,y.scores,y.candidates))

    def test_adversarial_noise_safety(self):
        seq=[3**n+(17 if n%13==0 else 0) for n in range(64)]
        run=evaluate(seq)
        self.assertEqual(len(run.records),32)
        self.assertGreater(run.selected_mae,0)
        for x in run.records:
            self.assertEqual(x.predicted,dict(x.candidates)[x.selected])

    def test_invalid(self):
        seq=list(range(42))
        with self.assertRaises(ValueError):evaluate(seq,warmup=42)
        with self.assertRaises(ValueError):evaluate(seq,stability=100)
        with self.assertRaises(ValueError):evaluate(seq,lookback=0)
        with self.assertRaises(TypeError):evaluate([1.0]*50)
