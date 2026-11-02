"""Counterexample-guided synthesis with exact equivalence to a reference AST.

Unlike finite-domain CEGIS, this mode accepts an explicit reference program
in the supported piecewise-affine grammar and uses branch_certificates.certify
to verify all integer input pairs. Finite examples only guide candidate search.
"""
from __future__ import annotations
from dataclasses import dataclass
from itertools import product
from branch_synthesis import Affine, Guard, Node, GUARDS, _learn
from branch_certificates import certify, Certificate

@dataclass(frozen=True)
class ExactResult:
    program:Node|None
    rounds:int
    counterexamples:tuple[tuple[int,int],...]
    partitions:int
    certificate:Certificate|None
    exhausted:bool

def synthesize_exact(reference:Node,*,max_depth=2,coefficient_bound=1,
                     constant_bound=1,max_rounds=80,max_partitions=200000,
                     initial_examples=((0,0),)):
    """Search for a small AST exactly equivalent to the supplied reference AST.

    Every accepted solution is certified for all integer x,y, not just sampled
    inputs. If search budgets are exhausted, returns no solution.
    """
    certify(reference,reference)  # validate grammar, coefficients and guards
    if not 0<=max_depth<=4 or not 0<=coefficient_bound<=3 or not 0<=constant_bound<=5:
        raise ValueError('invalid grammar budget')
    if max_rounds<1 or max_partitions<1:
        raise ValueError('invalid search budget')
    examples=list(initial_examples)
    if not examples or any(not isinstance(p,tuple) or len(p)!=2 or any(type(v) is not int for v in p) for p in examples):
        raise ValueError('initial examples must be integer pairs')
    examples=list(dict.fromkeys(examples))
    leaves=tuple(sorted((Affine(a,b,c) for a,b,c in product(
        range(-coefficient_bound,coefficient_bound+1),
        range(-coefficient_bound,coefficient_bound+1),
        range(-constant_bound,constant_bound+1))),
        key=lambda e:(abs(e.a)+abs(e.b)+abs(e.c),abs(e.c),e)))
    total=0
    counterexamples=[]
    for rnd in range(1,max_rounds+1):
        samples=tuple((p,reference.evaluate(*p)) for p in examples)
        candidate,visited,exhausted=_learn(samples,leaves,max_depth,max_partitions-total)
        total+=visited
        if exhausted:
            return ExactResult(None,rnd,tuple(counterexamples),total,None,True)
        if candidate is None:
            return ExactResult(None,rnd,tuple(counterexamples),total,None,False)
        proof=certify(candidate,reference)
        if proof.equivalent:
            return ExactResult(candidate,rnd,tuple(counterexamples),total,proof,False)
        witness=proof.counterexample
        if witness in examples:
            raise AssertionError('candidate contradicts learned counterexample')
        examples.append(witness)
        counterexamples.append(witness)
    return ExactResult(None,max_rounds,tuple(counterexamples),total,None,True)

if __name__=='__main__':
    from branch_certificates import branch,leaf
    targets={
        'maximum':branch(Guard('x','lt','y'),leaf(0,1),leaf(1,0)),
        'absdiff':branch(Guard('x','lt','y'),leaf(-1,1),leaf(1,-1)),
        'clamp':branch(Guard('x','lt','zero'),leaf(),
                      branch(Guard('y','lt','zero'),leaf(),
                             branch(Guard('x','lt','y'),leaf(1,0),leaf(0,1))))
    }
    for name,ref in targets.items():
        result=synthesize_exact(ref)
        print(name,'rounds=',result.rounds,'certified=',bool(result.certificate and result.certificate.equivalent),
              'program=',result.program.describe() if result.program else None)
