"""Independent regression and falsification of exact CLIA claims."""
import itertools,random,unittest
from pathlib import Path
from sygus_clia import (parse_sexpressions,parse_problem,synthesize,certify,output,
                        Affine,Guard,Tree,Unsupported,_cells,_relation,finite_constraints)
FIXTURES=Path(__file__).resolve().parent.parent/'benchmarks'/'sygus_clia'

class SygusCLIAExternalTests(unittest.TestCase):
    def test_official_max_family_universal(self):
        for n,cell_count in ((2,13),(3,75),(4,541)):
            with self.subTest(arity=n):
                p=parse_problem((FIXTURES/f'max{n}.sl').read_text())
                r=synthesize(p,max_depth=n-1)
                self.assertEqual(r.status,'proved')
                self.assertEqual(r.certificate.checked_cells,cell_count)
                self.assertEqual(r.verified_grid,5**n)
                self.assertIn(f'(define-fun mux_{n}',output(p,r))
                rng=random.Random(20261102+n)
                for _ in range(400):
                    vec=tuple(rng.randint(-10000,10000) for _ in range(n))
                    self.assertEqual(r.tree.at(vec),max(vec))

    def test_official_difference_relational_symmetry(self):
        p=parse_problem((FIXTURES/'diff.sl').read_text())
        r=synthesize(p,max_depth=1)
        self.assertEqual(r.status,'proved')
        self.assertEqual(r.certificate.checked_cells,13)
        for x,y in itertools.product((-10000,-9,-1,0,2,8000),repeat=2):
            self.assertEqual(r.tree.at((x,y)),abs(x-y))
            self.assertEqual(r.tree.at((x,y)),r.tree.at((y,x)))

    def test_finite_sample_is_not_a_proof(self):
        p=parse_problem((FIXTURES/'max2.sl').read_text())
        r=synthesize(p,domain=range(0,1))
        self.assertEqual(r.status,'finite_only')
        self.assertFalse(r.certificate.proved)
        self.assertIsNotNone(r.certificate.counterexample)

    def test_mutation_yields_real_counterexample(self):
        p=parse_problem((FIXTURES/'max2.sl').read_text())
        bad=Tree(leaf=Affine((1,0)))
        cert=certify(p,bad)
        self.assertFalse(cert.proved)
        self.assertFalse(finite_constraints(p,bad,cert.counterexample))

    def test_order_cells_and_sign_extremes(self):
        self.assertEqual([len(_cells(n)) for n in (1,2,3,4)],[3,13,75,541])
        for n in (2,3,4):
            cells=set(_cells(n))
            for point in itertools.product(range(-3,4),repeat=n):
                values=sorted(set(point)|{0})
                cell=tuple(values.index(x) for x in point)+(values.index(0),)
                self.assertIn(cell,cells)
        cell=(0,2,1)
        x=Affine((1,0));y=Affine((0,1));z=Affine((0,0))
        self.assertTrue(_relation(y,x,'>',cell))
        self.assertFalse(_relation(x,y,'>=',cell))
        self.assertIsNone(_relation(Affine((1,1)),z,'>=',cell))

    def test_no_false_proof_for_random_candidates(self):
        rng=random.Random(83016)
        p=parse_problem((FIXTURES/'max2.sl').read_text())
        for _ in range(100):
            def make(depth):
                if depth==0 or rng.random()<0.45:
                    return Tree(leaf=Affine((rng.randint(-1,1),rng.randint(-1,1))))
                yes=make(depth-1);no=make(depth-1)
                return Tree(guard=Guard(rng.choice((0,1)),rng.choice((0,1,None)),rng.choice(('<','<='))),
                            yes=yes,no=no)
            tree=make(3)
            if certify(p,tree).proved:
                for x,y in itertools.product(range(-30,31),repeat=2):
                    self.assertEqual(tree.at((x,y)),max(x,y))

    def test_reject_unsupported_or_invalid_inputs(self):
        src=(FIXTURES/'max2.sl').read_text()
        with self.assertRaises(ValueError):parse_sexpressions(src+')')
        with self.assertRaises(ValueError):parse_sexpressions('('+src)
        for changed in (src.replace('(set-logic LIA)','(set-logic BV)'),
                        src.replace('(check-synth)','(check-synth)(check-synth)'),
                        src.replace('(synth-fun mux_2 ((x Int) (y Int)) Int)',
                                    '(synth-fun mux_2 ((x Int) (y Int)) Int ((Start Int)))')):
            with self.assertRaises(Unsupported):parse_problem(changed)
        p=parse_problem(src)
        with self.assertRaises(ValueError):certify(p,Tree(leaf=Affine((1,))))
        with self.assertRaises(ValueError):
            certify(p,Tree(guard=Guard(8,1,'<'),
                           yes=Tree(leaf=Affine((1,0))),no=Tree(leaf=Affine((0,1)))))
        with self.assertRaises(ValueError):synthesize(p,max_depth=5)
        with self.assertRaises(ValueError):synthesize(p,max_rounds=0)
        with self.assertRaises(ValueError):synthesize(p,domain=(False,True))
        q=src.replace('(constraint (>= (mux_2 x y) x))',
                      '(constraint (>= (mux_2 y x) x))')
        with self.assertRaises(Unsupported):synthesize(parse_problem(q))

if __name__=='__main__':unittest.main()
