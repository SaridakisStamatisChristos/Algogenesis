import unittest
from fractions import Fraction
from forecast_evaluation import evaluate,report

class ForecastEvaluationTests(unittest.TestCase):
    def test_fibonacci_unseen_forecast(self):
        seq=[0,1]
        for _ in range(35):seq.append(seq[-1]+seq[-2])
        result=evaluate(seq,min_train=10,horizon=4,stride=3)
        self.assertEqual(result.recurrence_mae,0)
        self.assertEqual(result.coverage,1)
        self.assertGreater(result.persistence_mae,0)
        self.assertGreater(result.linear_mae,0)
        for fold in result.folds:
            self.assertEqual(fold.recurrence,fold.actual)
            self.assertEqual(fold.order,2)

    def test_cubic_unseen_forecast(self):
        seq=[n**3 for n in range(45)]
        result=evaluate(seq,min_train=12,horizon=5,stride=4,window=15)
        self.assertEqual(result.recurrence_mae,0)
        self.assertEqual(result.coverage,1)
        self.assertTrue(all(f.order==4 for f in result.folds))

    def test_abstention_does_not_count_as_zero_error(self):
        seq=[n*n for n in range(25)]
        result=evaluate(seq,min_train=8,horizon=3,max_order=1)
        self.assertEqual(result.coverage,0)
        self.assertIsNone(result.recurrence_mae)
        self.assertGreater(result.persistence_mae,0)
        self.assertIsNone(report(result)['recurrence_mae'])

    def test_future_changes_are_not_seen_in_past_folds(self):
        seq=[3*2**n for n in range(28)]
        altered=seq.copy()
        altered[20:]=[100000+n for n in range(20,28)]
        first=evaluate(seq,min_train=8,horizon=2,stride=2)
        second=evaluate(altered,min_train=8,horizon=2,stride=2)
        for a,b in zip(first.folds,second.folds):
            if a.origin+2<=20:
                self.assertEqual(a,b)

    def test_rational_and_validation(self):
        seq=[Fraction(1,2**n) for n in range(30)]
        result=evaluate(seq,min_train=8,horizon=3)
        self.assertEqual(result.recurrence_mae,0)
        self.assertEqual(result.coverage,1)
        with self.assertRaises(ValueError):evaluate(seq,min_train=2)
        with self.assertRaises(ValueError):evaluate(seq,horizon=0)
        with self.assertRaises(ValueError):evaluate(seq,window=3)
        with self.assertRaises(ValueError):evaluate(seq[:9],min_train=8,horizon=3)
        with self.assertRaises(TypeError):evaluate([1,2.0]*10)

if __name__=='__main__':unittest.main()
