import unittest
from sygus_benchmark import run_suite,summarize

class SygusBenchmarkTests(unittest.TestCase):
    def test_official_results(self):
        records=run_suite()
        self.assertEqual([r.benchmark for r in records],['max2.sl','max3.sl','max4.sl','diff.sl'])
        self.assertEqual([r.status for r in records],['proved']*4)
        self.assertEqual([r.certificate_cells for r in records],[13,75,541,13])
        result=summarize(records)
        self.assertEqual((result['benchmarks'],result['proved'],result['unsupported']),(4,4,0))
        self.assertTrue(all(r.elapsed_ns>=0 and r.solution for r in records))
    def test_budget_restrictions(self):
        self.assertEqual(run_suite(names=('max3.sl',),depth_limit=1)[0].status,'not_found_in_grammar')
        with self.assertRaises(ValueError):run_suite(names=('madeup.sl',))
        with self.assertRaises(ValueError):run_suite(depth_limit=5)

if __name__=='__main__':unittest.main()
