import itertools,random,unittest
from fractions import Fraction
from regret_forecast import BoundedExperts
from switching_experts import FixedShareExperts,_ceil_log2_ratio,tuned_tracking_parameters

class SwitchingExpertsTests(unittest.TestCase):
    def test_log2_exact_boundary(self):
        for i in range(1,201):
            for j in range(1,80):
                v=_ceil_log2_ratio(i,j)
                self.assertGreaterEqual(j*(1<<v),i)
                if v>0:self.assertLess(j*(1<<(v-1)),i)

    def test_exhaustive_binary_outcomes_all_paths(self):
        for ys in itertools.product((0,1),repeat=6):
            m=FixedShareExperts(("zero","one"),lower=0,upper=1,
                                share=Fraction(1,8),eta=Fraction(1,4),
                                resolution=32,prediction_resolution=128)
            for y in ys:
                m.predict({"zero":0,"one":1});m.observe(y)
            for path in itertools.product(m.names,repeat=6):
                cert=m.switching_certificate(path)
                self.assertTrue(cert.valid,(ys,path,cert))
                self.assertEqual(cert.rounds,6)
            for budget in (0,1,2,5):
                best=m.best_switching_path(budget)
                self.assertLessEqual(sum(a!=b for a,b in zip(best,best[1:])),budget)
                brute=min(m.switching_certificate(path).comparator_loss
                          for path in itertools.product(m.names,repeat=6)
                          if sum(a!=b for a,b in zip(path,path[1:]))<=budget)
                self.assertEqual(m.switching_certificate(best).comparator_loss,brute)

    def test_protocol_and_weights(self):
        m=FixedShareExperts(("a","b"),lower=0,upper=1,share=Fraction(1,4))
        old=BoundedExperts(("a","b"),lower=0,upper=1)
        for machine in (m,old):
            self.assertEqual(machine.predict({"a":0,"b":1}),Fraction(1,2))
            machine.observe(0)
        self.assertEqual(m.weights["a"],Fraction(63,64))
        self.assertEqual(m.weights["b"],Fraction(57,64))
        self.assertEqual(sum(m.weights.values()),sum(old.weights.values()))
        self.assertEqual(m.best_switching_path(10),("a",))
        with self.assertRaises(NotImplementedError):m.certificate()
        with self.assertRaises(ValueError):m.switching_certificate(())
        with self.assertRaises(ValueError):m.switching_certificate(("z",))
        with self.assertRaises(ValueError):m.best_switching_path(True)
        with self.assertRaises(ValueError):m.best_switching_path(-1)

    def test_random_adversarial_streams(self):
        rng=random.Random(12029)
        for _ in range(12):
            m=FixedShareExperts(("left","right","middle"),lower=-10,upper=10,
                                share=Fraction(1,7),eta=Fraction(1,5),
                                resolution=128,prediction_resolution=128)
            for _ in range(45):
                p={"left":rng.randint(-12,12),"right":rng.randint(-12,12),
                   "middle":rng.randint(-12,12)}
                m.predict(p);m.observe(rng.randint(-10,10))
            for budget in (0,1,3,10):
                self.assertTrue(m.switching_certificate(m.best_switching_path(budget)).valid)

    def test_invalid_empty_and_pending(self):
        for share in (0,1,-1):
            with self.assertRaises(ValueError):
                FixedShareExperts(("x",),lower=0,upper=1,share=share)
        m=FixedShareExperts(("a","b"),lower=0,upper=1)
        self.assertTrue(m.switching_certificate(()).valid)
        m.predict({"a":0,"b":1})
        with self.assertRaises(RuntimeError):m.switching_certificate(())
        with self.assertRaises(ValueError):m.observe(3)

    def test_tuned_nonvacuous(self):
        eta,share=tuned_tracking_parameters(1000,8,2)
        self.assertTrue(Fraction(0)<eta<=Fraction(1,2))
        self.assertLess(share,Fraction(1,2))
        m=FixedShareExperts(tuple(str(i) for i in range(8)),lower=0,upper=1,eta=eta,share=share)
        for t in range(1000):
            m.predict({str(i):int(i%2==(t>=500)) for i in range(8)})
            m.observe(int(t>=500))
        c=m.switching_certificate(m.best_switching_path(2))
        self.assertTrue(c.valid)
        self.assertLess(c.bound,1000)

    def test_tuned_parameter_validation(self):
        for a in ((0,2,0),(10,0,0),(10,2,10),(10,2,-1)):
            with self.assertRaises(ValueError):tuned_tracking_parameters(*a)
        with self.assertRaises(TypeError):tuned_tracking_parameters(10,2,True)
