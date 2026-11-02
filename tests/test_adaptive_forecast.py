import random
import unittest
from fractions import Fraction
from adaptive_forecast import EXPERTS, evaluate, _predict

class AdaptiveForecastTests(unittest.TestCase):
    def test_stationary_fibonacci(self):
        seq=[0,1]
        for _ in range(55):seq.append(seq[-1]+seq[-2])
        result=evaluate(seq)
        self.assertEqual(result.selected_mae,0)
        self.assertEqual(dict(result.candidate_mae)["bm_short"],0)
        self.assertGreater(dict(result.candidate_mae)["persistence"],0)

    def test_future_mutation_cannot_change_prior_predictions(self):
        rng=random.Random(317)
        seq=[rng.randint(-4,5) for _ in range(55)]
        altered=seq.copy()
        altered[39:]=[1000000+n for n in range(39,len(seq))]
        a,b=evaluate(seq),evaluate(altered)
        for x,y in zip(a.records,b.records):
            if x.index<=39:
                self.assertEqual((x.index,x.selected,x.predicted,x.candidates,x.scores),
                                 (y.index,y.selected,y.predicted,y.candidates,y.scores))
        for record in a.records:
            scores=dict(record.scores)
            self.assertEqual(scores[record.selected],min(scores.values()))

    def test_independent_expert_oracles(self):
        seq=[n*n+n for n in range(48)]
        for record in evaluate(seq).records:
            predicted=dict(record.candidates)
            n=record.index
            self.assertEqual(predicted["linear"],2*seq[n-1]-seq[n-2])
            self.assertEqual(predicted["persistence"],seq[n-1])
            self.assertEqual(predicted["bm_short"],seq[n])
            self.assertEqual(predicted["bm_long"],seq[n])
            self.assertEqual(record.predicted,predicted[record.selected])

    def test_calibration_not_counted_in_metrics(self):
        seq=[n*n+(1 if n%9==0 else 0) for n in range(48)]
        result=evaluate(seq)
        for name, measured in result.candidate_relative_mae:
            direct=sum((abs(dict(r.candidates)[name]-r.observed)/(1+abs(r.observed))
                        for r in result.records),Fraction(0))/len(result.records)
            self.assertEqual(measured,direct)

    def test_rational_reproducibility(self):
        seq=[Fraction(1,2**n) for n in range(48)]
        a,b=evaluate(seq),evaluate(seq)
        self.assertEqual(a,b)
        self.assertEqual(a.selected_mae,0)

    def test_shifts_and_noise_not_automatically_solved(self):
        seq=[2**n+(5 if n%7==0 else 0) for n in range(64)]
        seq[40:]=[3**n+(5 if n%7==0 else 0) for n in range(40,64)]
        result=evaluate(seq)
        self.assertEqual(len(result.records),32)
        self.assertGreater(result.selected_mae,0)
        self.assertGreaterEqual(result.switches,1)
        self.assertEqual(set(dict(result.candidate_mae)),set(EXPERTS))

    def test_guarded_bit_budget(self):
        seq=[2**n for n in range(506,526)]
        self.assertEqual(_predict(seq,"bm_short",8,20),seq[-1])

    def test_calibration_leakage_guard(self):
        seq=[2**n for n in range(48)]
        altered=seq.copy()
        altered[32]+=100
        a,b=evaluate(seq),evaluate(altered)
        self.assertEqual(a.records[0].scores,b.records[0].scores)
        self.assertEqual(a.records[0].predicted,b.records[0].predicted)
        self.assertNotEqual(a.records[1].scores,b.records[1].scores)

    def test_invalid_inputs(self):
        seq=list(range(32))
        for kw in ({"warmup":5},{"short":2},{"short":23},{"long":7},
                   {"lookback":0},{"warmup":32},{"calibration":0}):
            with self.assertRaises(ValueError):evaluate(seq,**kw)
        with self.assertRaises(TypeError):evaluate([True]*40)
        with self.assertRaises(TypeError):evaluate(list(range(40)),lookback=1.0)
