"""Pinned external SyGuS CLIA smoke-suite; not a competition benchmark."""
from pathlib import Path
from time import perf_counter_ns
from dataclasses import dataclass,asdict
from sygus_clia import Unsupported,parse_problem,synthesize,output
import json
FIXTURES=Path(__file__).resolve().parent/'benchmarks'/'sygus_clia'
INPUTS=('max2.sl','max3.sl','max4.sl','diff.sl')

@dataclass(frozen=True)
class BenchmarkRecord:
    benchmark:str
    status:str
    function:str|None
    verified_grid:int
    certificate_cells:int
    rounds_examples:int
    partitions:int
    ast_nodes:int|None
    elapsed_ns:int
    solution:str|None
    reason:str|None

def run_suite(*,names=INPUTS,depth_limit=3):
    if type(depth_limit) is not int or not 0<=depth_limit<=4:raise ValueError('invalid depth budget')
    if any(name not in INPUTS for name in names):raise ValueError('only pinned benchmarks permitted')
    results=[]
    for name in names:
        start=perf_counter_ns()
        problem=None
        candidate=None
        reason=None
        try:
            problem=parse_problem((FIXTURES/name).read_text(encoding='utf-8'))
            candidate=synthesize(problem,max_depth=depth_limit)
            status=candidate.status
            if candidate.certificate and not candidate.certificate.proved:
                reason=candidate.certificate.reason
        except (Unsupported,ValueError) as error:
            status='unsupported'
            reason=str(error)
        results.append(BenchmarkRecord(
            name,status,problem.name if problem else None,
            candidate.verified_grid if candidate else 0,
            candidate.certificate.checked_cells if candidate and candidate.certificate else 0,
            candidate.examples if candidate else 0,
            candidate.candidate_count if candidate else 0,
            candidate.tree.nodes() if candidate and candidate.tree else None,
            perf_counter_ns()-start,
            output(problem,candidate) if candidate and candidate.tree else None,
            reason))
    return tuple(results)

def summarize(results):
    records=tuple(results)
    return {'benchmarks':len(records),
            'proved':sum(r.status=='proved' for r in records),
            'unsupported':sum(r.status=='unsupported' for r in records),
            'finite_only':sum(r.status=='finite_only' for r in records),
            'not_found':sum(r.status not in ('proved','unsupported','finite_only') for r in records),
            'results':[asdict(r) for r in records]}
if __name__=='__main__':
    print(json.dumps(summarize(run_suite()),indent=2))
