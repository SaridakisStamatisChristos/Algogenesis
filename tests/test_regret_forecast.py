import itertools
import unittest
from fractions import Fraction
from regret_forecast import BoundedExperts, evaluate, EXPERTS, causal_candidates, tuned_eta


class RegretTests(unittest.TestCase):
    def test_exact_machine_and_state(self):
        model=BoundedExperts(('a','b'),lower=0,upper=1,eta=Fraction(1,2),prediction_resolution=512)
        self.assertEqual(model.predict({'a':0,'b':1}),Fraction(1,2))
        with self.assertRaises(RuntimeError):model.predict({'a':0,'b':1})
        with self.assertRaises(ValueError):model.observe(2)
        self.assertEqual(model.observe(0).learner_loss,Fraction(1,2))
        self.assertEqual(model.weights['a'],1)
        self.assertEqual(model.weights['b'],Fraction(1,2))
        with self.assertRaises(RuntimeError):model.observe(1)
        self.assertEqual(model.predict({'a':0,'b':1}),Fraction(171,512))
        with self.assertRaises(RuntimeError):model.certificate()
        model.observe(1)
        self.assertTrue(model.certificate().valid)

    def test_exhaustive_binary_adversaries(self):
        # Exhaust every 2^7 outcome sequence with opposite experts.
        for values in itertools.product((0,1),repeat=7):
            model=BoundedExperts(('zero','one'),lower=0,upper=1,eta=Fraction(1,4))
            for y in values:
                model.predict({'zero':0,'one':1})
                model.observe(y)
            certificate=model.certificate()
            self.assertTrue(certificate.valid)
            self.assertEqual(certificate.rounds,7)
            self.assertLessEqual(certificate.regret,certificate.bound)

    def test_future_mutation_cannot_affect_current_forecast(self):
        xs=[(n*n+n)%27 for n in range(53)]
        ys=xs[:];ys[37:]=[15]*(len(xs)-37)
        a=evaluate(xs,lower=0,upper=30)
        b=evaluate(ys,lower=0,upper=30)
        for x,y in zip(a.records,b.records):
            if x.index+32<=37:
                self.assertEqual((x.prediction,x.candidates,x.weights_before),
                                 (y.prediction,y.candidates,y.weights_before))
        self.assertTrue(a.certificate().valid)
        self.assertTrue(b.certificate().valid)

    def test_forecasting_competes_with_best_expert(self):
        xs=[n%7 for n in range(80)]
        model=evaluate(xs,lower=0,upper=10)
        self.assertEqual(len(model.records),48)
        self.assertTrue(model.certificate().valid)
        seasonal=dict((name,sum((dict(r.expert_losses)[name] for r in model.records),Fraction(0))) for name in EXPERTS)
        self.assertGreaterEqual(seasonal['seasonal'],0)
        self.assertEqual(model.certificate().best_expert_loss,min(seasonal.values()))

    def test_horizon_tuned_guarantee_and_scaling(self):
        for horizon in (1, 4, 16, 100, 1000, 10000):
            rate=tuned_eta(horizon)
            self.assertGreater(rate,0)
            self.assertLessEqual(rate,Fraction(1,2))
            model=BoundedExperts(('a','b','c','d'),lower=0,upper=1,eta=rate)
            for t in range(min(horizon,80)):
                model.predict({'a':t%2,'b':1,'c':0,'d':Fraction(1,2)})
                model.observe((t//7)%2)
            self.assertTrue(model.certificate().valid)
        self.assertLess(tuned_eta(10000),tuned_eta(100))
        with self.assertRaises(ValueError):tuned_eta(0)
        with self.assertRaises(ValueError):tuned_eta(10, experts=())

    def test_quantization_and_certificate_components(self):
        model=BoundedExperts(('near','far'),lower=0,upper=1,
                             eta=Fraction(1,4),resolution=4,prediction_resolution=4)
        self.assertEqual(model.predict({'near':Fraction(3,10),'far':Fraction(9,10)}),Fraction(3,4))
        rec=model.observe(Fraction(1,10))
        self.assertEqual(dict(rec.candidates),{'near':Fraction(1,4),'far':1})
        self.assertEqual(dict(rec.expert_losses),{'near':Fraction(3,20),'far':Fraction(9,10)})
        self.assertEqual(dict(rec.update_losses),{'near':Fraction(1,4),'far':1})
        self.assertTrue(model.certificate().valid)

    def test_certificate_under_seeded_adversarial_streams(self):
        import random
        gen=random.Random(208)
        for trial in range(24):
            model=BoundedExperts(('a','b','c'),lower=-10,upper=10,
                                 eta=tuned_eta(120,('a','b','c')),resolution=128)
            for t in range(120):
                guess={'a':gen.randint(-100,100),'b':gen.randint(-20,20),'c':Fraction(gen.randint(-100,100),7)}
                model.predict(guess)
                y=gen.randint(-10,10)
                model.observe(y)
            certificate=model.certificate()
            self.assertTrue(certificate.valid)
            self.assertLessEqual(certificate.regret,certificate.bound)

    def test_degenerate_and_invalid(self):
        for kwargs in ({'lower':0,'upper':0},{'lower':1,'upper':0},
                       {'lower':0,'upper':1,'eta':0},{'lower':0,'upper':1,'eta':1}):
            with self.assertRaises(ValueError):BoundedExperts(('x',),**kwargs)
        with self.assertRaises(ValueError):BoundedExperts(('x','x'),lower=0,upper=1)
        with self.assertRaises(ValueError):BoundedExperts(('x',),lower=0,upper=1,resolution=1)
        with self.assertRaises(ValueError):BoundedExperts(('x',),lower=0,upper=1,resolution=True)
        model=BoundedExperts(('x','y'),lower=0,upper=1)
        with self.assertRaises(ValueError):model.predict({'x':0})
        with self.assertRaises(TypeError):model.predict({'x':0,'y':0.1})
        with self.assertRaises(TypeError):model.predict({'x':0,'y':True})
        with self.assertRaises(TypeError):evaluate([0.1]*40,lower=0,upper=1)
        with self.assertRaises(ValueError):evaluate([2]*40,lower=0,upper=1)
        with self.assertRaises(ValueError):evaluate([0]*20,lower=0,upper=1)
