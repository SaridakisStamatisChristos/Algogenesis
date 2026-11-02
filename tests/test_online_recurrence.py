import unittest
from fractions import Fraction
from online_recurrence import monitor,metrics

class OnlineRecurrenceTests(unittest.TestCase):
    def test_stationary_fibonacci(self):
        seq=[0,1]
        for _ in range(55):seq.append(seq[-1]+seq[-2])
        result=monitor(seq,warmup=12,window=16)
        self.assertEqual(result.alarms,())
        self.assertEqual(result.covered,len(seq)-12)
        self.assertEqual(result.exact,result.covered)
        self.assertEqual(metrics(result)["mae_covered"],0)
    def test_unannounced_shift_is_detected_not_predicted(self):
        seq=[2**n for n in range(50)]
        seq[30:]=[3**n for n in range(30,50)]
        result=monitor(seq,warmup=12,window=16,method="bm")
        self.assertIn(30,result.alarms)
        first=next(e for e in result.events if e.index==30)
        self.assertEqual(first.prediction,2**30)
        self.assertEqual(first.actual,3**30)
        self.assertTrue(first.mismatch)
        self.assertGreater(result.covered,result.exact)
        # After reset, a fresh window eventually learns the new exponential.
        self.assertEqual(result.events[-1].prediction,seq[-1])
    def test_no_leakage_under_future_mutation(self):
        seq=[3**n for n in range(45)]
        changed=seq[:]
        changed[32:]=[123456+n for n in range(32,45)]
        a=monitor(seq,warmup=12)
        b=monitor(changed,warmup=12)
        for x,y in zip(a.events,b.events):
            if x.index<=32:
                self.assertEqual(x.prediction,y.prediction)
    def test_hankel_and_abstention(self):
        seq=[2**n for n in range(40)]
        result=monitor(seq,warmup=12,window=16,method="hankel")
        self.assertEqual(result.alarms,())
        self.assertEqual(result.exact,result.covered)
        self.assertEqual(result.covered,28)
    def test_invalid(self):
        seq=[2**n for n in range(20)]
        with self.assertRaises(ValueError):monitor(seq,warmup=2)
        with self.assertRaises(ValueError):monitor(seq,warmup=20)
        with self.assertRaises(ValueError):monitor(seq,method="none")
        with self.assertRaises(ValueError):monitor(seq,alarm_threshold=-1)
        with self.assertRaises(TypeError):monitor(seq,reset_on_alarm=1)
        with self.assertRaises(TypeError):monitor([1.0]*20)

if __name__=="__main__":unittest.main()
