import random,unittest
from pathlib import Path
from sygus_clia import Unsupported,parse_problem,synthesize,output
from sygus_solution_checker import check_solution
FIXTURES=Path(__file__).resolve().parent.parent/'benchmarks'/'sygus_clia'

class TextualSolutionTests(unittest.TestCase):
    def test_reparsed_all_external_benchmarks_proved(self):
        for filename in ('max2.sl','max3.sl','max4.sl','diff.sl'):
            with self.subTest(benchmark=filename):
                source=(FIXTURES/filename).read_text()
                problem=parse_problem(source)
                result=synthesize(problem,max_depth=3)
                rendered=output(problem,result)
                check=check_solution(source,rendered)
                self.assertTrue(check.certificate.proved)
                self.assertEqual(check.certificate.checked_cells,result.certificate.checked_cells)
                self.assertIsNot(check.candidate,result.tree)
                rng=random.Random(22+len(problem.variables))
                for _ in range(100):
                    values=tuple(rng.randrange(-10**6,10**6) for _ in problem.variables)
                    self.assertEqual(check.candidate.at(values),result.tree.at(values))

    def test_semantically_wrong_text_finds_witness(self):
        src=(FIXTURES/'max2.sl').read_text()
        malformed='(define-fun mux_2 ((x Int) (y Int)) Int (ite (<= x y) x y))'
        result=check_solution(src,malformed)
        self.assertFalse(result.certificate.proved)
        from sygus_clia import finite_constraints
        self.assertFalse(finite_constraints(parse_problem(src),result.candidate,
                                           result.certificate.counterexample))

    def test_invalid_signature_and_unsupported_grammar(self):
        source=(FIXTURES/'max2.sl').read_text()
        cases=(
            '(define-fun mux_3 ((x Int) (y Int)) Int x)',
            '(define-fun mux_2 ((y Int) (x Int)) Int x)',
            '(define-fun mux_2 ((x Int) (y Int)) Bool x)',
            '(define-fun mux_2 ((x Int) (y Int)) Int (* x y))',
            '(define-fun mux_2 ((x Int) (y Int)) Int (ite (>= x y) x y))',
            '(define-fun mux_2 ((x Int) (y Int)) Int x) (define-fun extra () Int 0)',
            '(define-fun mux_2 ((x Int) (y Int)) Int (ite true x y))',
            '(define-fun mux_2 ((x Int) (y Int)) Int true)',
        )
        for expr in cases:
            with self.subTest(case=expr):
                with self.assertRaises(Unsupported):check_solution(source,expr)

if __name__=='__main__':unittest.main()
