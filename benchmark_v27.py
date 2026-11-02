"""Reproducible exploratory SyGuS comparative harness (11 frozen tasks).

Run both engines in distinct subprocesses, with the same wall-clock timeout.
Measure end-to-end wall time separately from a common independent Z3 validity
check. Neither success percentage nor one-shot latency is a SOTA claim.

Original, byte-preserved SyGuS-Org fixtures are checked against pinned Git
blob SHAs before any measurement.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
from time import perf_counter_ns

ROOT = Path(__file__).resolve().parent
DEFAULT_MANIFEST = ROOT/'benchmarks'/'sygus_manifest_v27.json'
MAX_OUTPUT_CHARS = 250_000


def _blob_sha(data: bytes) -> str:
    return hashlib.sha1(f'blob {len(data)}\0'.encode('ascii') + data).hexdigest()


def _record_status(status: str, elapsed_ns: int, reason: str = '',
                   proof: str = '', candidate: str = '') -> dict:
    return {'status': status, 'elapsed_ns': elapsed_ns, 'reason': reason[:400],
            'external_z3': proof, 'solution': candidate[:4000]}


def _version(program: str, flag: str = '--version') -> str:
    if not shutil.which(program):
        return 'UNAVAILABLE'
    try:
        r = subprocess.run([program, flag], capture_output=True, text=True,
                           timeout=6, check=False)
        return (r.stdout or r.stderr).strip().splitlines()[0][:160]
    except (OSError, subprocess.TimeoutExpired, IndexError):
        return 'UNAVAILABLE'


def _git_revision() -> str:
    try:
        r=subprocess.run(['git','rev-parse','HEAD'],cwd=ROOT,timeout=2,
                         capture_output=True,text=True,check=False)
        return r.stdout.strip() if r.returncode == 0 else 'UNKNOWN'
    except (OSError, subprocess.TimeoutExpired):
        return 'UNKNOWN'


def _candidate_from_output(text: str) -> str | None:
    """Accept a single define-fun, including the optional one-element wrapper.

    Non-parseable outputs cannot be counted as verified; multi-function
    output is supported only if every top-level form is a define-fun.
    """
    from sygus_clia import parse_sexpressions
    try:
        roots = parse_sexpressions(text)
    except ValueError:
        return None
    if len(roots)==1 and isinstance(roots[0],list) and roots[0] and isinstance(roots[0][0],list):
        roots = roots[0]
    if not roots or any(not isinstance(item,list) or not item or
                        item[0]!='define-fun' for item in roots):
        return None
    def sexpr(node):
        return '('+' '.join(sexpr(v) for v in node)+')' if isinstance(node,list) else str(node)
    return '\n'.join(sexpr(item) for item in roots)


def _run_subprocess(argv: list[str], timeout: float, *, source: str | None = None) -> dict:
    begin=perf_counter_ns()
    try:
        r=subprocess.run(argv,capture_output=True,text=True,input=source,
                         timeout=timeout,check=False,cwd=ROOT)
    except subprocess.TimeoutExpired:
        return _record_status('timeout',perf_counter_ns()-begin,'wall-clock timeout')
    except OSError as exc:
        return _record_status('unavailable',perf_counter_ns()-begin,type(exc).__name__)
    elapsed=perf_counter_ns()-begin
    if r.returncode != 0:
        return _record_status('error',elapsed,'subprocess exit '+str(r.returncode)+': '+r.stderr[:180])
    if len(r.stdout)>MAX_OUTPUT_CHARS:
        return _record_status('error',elapsed,'excessive subprocess output')
    return {'status':'candidate','elapsed_ns':elapsed,'stdout':r.stdout}


def _verify(source: str, candidate: str, z3_timeout: float) -> tuple[str,str]:
    from sygus_smt_bridge import check_with_smt
    from sygus_clia import Unsupported
    try:
        result=check_with_smt(source,candidate,solver='z3',timeout_seconds=z3_timeout)
        return result.status,result.detail
    except (ValueError,TypeError,Unsupported,RecursionError) as exc:
        return 'unverified_grammar',str(exc)[:300]


def _verify_external(source: str, candidate: str, z3_timeout: float) -> tuple[str,str]:
    """Use the broader verification-only reader for cvc5, not the synthesis grammar."""
    from sygus_general_checker import check_external_solution
    from sygus_clia import Unsupported
    try:
        result=check_external_solution(source,candidate,timeout_seconds=z3_timeout)
        return result.status,result.detail
    except (ValueError,TypeError,Unsupported,RecursionError) as exc:
        return 'unverified_grammar',str(exc)[:300]


def _own_worker(path: Path) -> int:
    from sygus_clia import Result, parse_problem, synthesize, output, Unsupported
    from structural_max import synthesize_structural_max, synthesize_linear_max
    try:
        problem=parse_problem(path.read_text(encoding='utf-8'))
        structural=synthesize_structural_max(problem)
        folded=synthesize_linear_max(problem) if structural is None else None
        if folded is not None:
            report={'status':'candidate','method':folded.rule,
                    'solution':folded.solution,'checker':'general',
                    'comparisons':folded.comparisons}
        else:
            if structural is not None:
                candidate=Result(structural.tree,0,0,0,None,'candidate')
                method=structural.rule
            else:
                candidate=synthesize(problem,max_depth=3)
                method='bounded-cegis'
            if candidate.tree is None:
                report={'status':candidate.status,'method':method}
            else:
                report={'status':'candidate','method':method,
                        'solution':output(problem,candidate),'checker':'restricted',
                        'internal_certificate':(
                            bool(candidate.certificate and candidate.certificate.proved))}
    except (Unsupported,ValueError,RuntimeError,RecursionError) as exc:
        report={'status':'unsupported','reason':str(exc)[:200]}
    print(json.dumps(report,sort_keys=True))
    return 0


def _algogenesis(path: Path, timeout: float, source: str,
                 z3_timeout: float) -> dict:
    result=_run_subprocess([sys.executable,str(Path(__file__).resolve()),
                            '--worker',str(path)],timeout)
    if result['status']!='candidate':
        return result
    try:
        payload=json.loads(result['stdout'])
    except (ValueError,TypeError):
        return _record_status('error',result['elapsed_ns'],'malformed worker JSON')
    if payload['status']!='candidate':
        return _record_status(payload['status'],result['elapsed_ns'],
                              payload.get('reason',''))
    checker=payload.get('checker')
    if checker=='general':
        proof,reason=_verify_external(source,payload['solution'],z3_timeout)
    elif checker=='restricted':
        proof,reason=_verify(source,payload['solution'],z3_timeout)
    else:
        return _record_status('error',result['elapsed_ns'],'invalid checker selector')
    return _record_status('proved' if proof=='proved' else 'unverified',
                          result['elapsed_ns'],reason,proof,payload['solution']) | {
                          'method':payload['method']}


def _cvc5(path: Path, timeout: float, source: str,
          z3_timeout: float) -> dict:
    if not shutil.which('cvc5'):
        return _record_status('unavailable',0,'cvc5 executable not installed')
    result=_run_subprocess(['cvc5','--lang=sygus2',str(path)],timeout)
    if result['status']!='candidate':
        return result
    candidate=_candidate_from_output(result['stdout'].strip())
    if candidate is None:
        return _record_status('unverified',result['elapsed_ns'],
                              'cvc5 output was not one recognized define-fun')
    proof,reason=_verify_external(source,candidate,z3_timeout)
    return _record_status('proved' if proof=='proved' else 'unverified',
                          result['elapsed_ns'],reason,proof,candidate)


def run(*,manifest: Path=DEFAULT_MANIFEST,timeout: float=5.0,
        z3_timeout: float=10.0, repeats: int=1) -> dict:
    if not (0<timeout<=120 and 0<z3_timeout<=120 and 1<=repeats<=7):
        raise ValueError('invalid timeout/repetition budget')
    manifest=Path(manifest).resolve()
    if manifest!=DEFAULT_MANIFEST.resolve():
        raise ValueError('only the pinned repository manifest is accepted')
    suite=json.loads(manifest.read_text(encoding='utf-8'))
    results=[]
    for item in suite['benchmarks']:
        path=(ROOT/item['file']).resolve()
        if not path.is_relative_to(ROOT) or path.suffix!='.sl':
            raise ValueError('unsafe fixture path')
        data=path.read_bytes()
        if _blob_sha(data)!=item['git_blob_sha']:
            raise ValueError('upstream provenance mismatch: '+item['name'])
        source=data.decode('utf-8')
        runs=[]
        for iteration in range(repeats):
            # Alternating order reduces systematic first-run bias.
            if iteration%2:
                base=_cvc5(path,timeout,source,z3_timeout)
                own=_algogenesis(path,timeout,source,z3_timeout)
            else:
                own=_algogenesis(path,timeout,source,z3_timeout)
                base=_cvc5(path,timeout,source,z3_timeout)
            runs.append({'algogenesis':own,'cvc5':base})
        results.append({'benchmark':item['name'],'upstream_blob':item['git_blob_sha'],
                        'runs':runs})
    return {
        'protocol':'AlgoGenesis SyGuS comparison v2.7',
        'selection':suite['selection'],'source_commit':suite['source_commit'],
        'repo_revision':_git_revision(),'python':sys.version.split()[0],
        'platform':platform.platform(),'machine':platform.machine(),
        'cpu_count':os.cpu_count(),'cvc5_version':_version('cvc5'),
        'z3_version':_version('z3'),'timeout_seconds':timeout,
        'z3_proof_timeout_seconds':z3_timeout,'repetitions':repeats,
        'notes':('One subprocess per engine per task per repetition; wall-clock '
                 'includes interpreter/solver startup. Independent Z3 proof '
                 'time is excluded from synthesis elapsed_ns. An output outside '
                 'the restricted checker grammar is unverified, NOT failed. '
                 'This curated set and small repeats do not establish SOTA.'),
        'results':results}


def main() -> int:
    parser=argparse.ArgumentParser()
    parser.add_argument('--worker',type=Path,help=argparse.SUPPRESS)
    parser.add_argument('--timeout',type=float,default=5)
    parser.add_argument('--z3-timeout',type=float,default=10)
    parser.add_argument('--repeats',type=int,default=1)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--require-proved',default='max5.sl,max6.sl')
    args=parser.parse_args()
    if args.worker is not None:
        return _own_worker(args.worker)
    report=run(timeout=args.timeout,z3_timeout=args.z3_timeout,repeats=args.repeats)
    print(json.dumps({'benchmarks':len(report['results']),
                      'per_task':[{'task':r['benchmark'],
                          'algogenesis':[x['algogenesis']['status'] for x in r['runs']],
                          'cvc5':[x['cvc5']['status'] for x in r['runs']]}
                        for r in report['results']]},indent=2))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    requirements={x for x in args.require_proved.split(',') if x}
    known={r['benchmark'] for r in report['results']}
    if not requirements.issubset(known):
        raise ValueError('required benchmark missing from frozen manifest')
    return 0 if all(any(run['algogenesis']['status']=='proved' for run in row['runs'])
                    for row in report['results'] if row['benchmark'] in requirements) else 1


if __name__=='__main__':
    raise SystemExit(main())
