"""Textual SyGuS define-fun checker for the supported CLIA subset.

Independently re-parses solution text into a fresh tree, then certifies against
original constraints for all integer inputs by the order-region verifier.
This is a second serialization/AST check, NOT an independent theorem prover.
"""
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from sygus_clia import (Unsupported,parse_sexpressions,parse_problem,Problem,
                         Affine,Guard,Tree,Certificate,certify)

@dataclass(frozen=True)
class TextCheck:
    candidate:Tree
    certificate:Certificate
    input_function:str

def _parse_affine(expr,vars):
    n=len(vars)
    if isinstance(expr,str):
        if expr in vars:return Affine(tuple(int(i==vars.index(expr)) for i in range(n)))
        if expr.lstrip('-').isdigit():return Affine((0,)*n,int(expr))
        raise Unsupported('nonlinear or unknown numeric atom in candidate')
    if not isinstance(expr,list) or not expr:raise Unsupported('malformed numeric expression')
    op,*args=expr
    if op not in ('+','-') or not args:
        raise Unsupported('candidate leaf must be integer-affine')
    if op=='-' and len(args)>2:
        raise Unsupported('candidate subtraction must be unary or binary')
    values=tuple(_parse_affine(x,vars) for x in args)
    if op=='-' and len(values)==1:
        v=values[0]
        return Affine(tuple(-x for x in v.coefficients),-v.constant)
    result=values[0]
    for value in values[1:]:
        sign=1 if op=='+' else -1
        result=Affine(tuple(x+sign*y for x,y in zip(result.coefficients,value.coefficients)),
                      result.constant+sign*value.constant)
    return result

def _parse_guard(expr,vars):
    if not isinstance(expr,list) or len(expr)!=3:
        raise Unsupported('candidate guard must be a binary comparison')
    op,left,right=expr
    if op not in ('<=','<'):
        raise Unsupported('candidate guard operator outside restricted grammar')
    def idx(v):
        if v=='0':return None
        if v in vars:return vars.index(v)
        raise Unsupported('candidate guard must compare argument variables or zero')
    return Guard(idx(left),idx(right),op)

def _parse_tree(expr,vars):
    if isinstance(expr,list) and expr and expr[0]=='ite':
        if len(expr)!=4:raise Unsupported('malformed candidate conditional')
        return Tree(guard=_parse_guard(expr[1],vars),
                    yes=_parse_tree(expr[2],vars),no=_parse_tree(expr[3],vars))
    return Tree(leaf=_parse_affine(expr,vars))

def parse_candidate(problem:Problem,solution:str)->Tree:
    roots=parse_sexpressions(solution)
    if len(roots)!=1:raise Unsupported('exactly one define-fun expression required')
    definition=roots[0]
    if not isinstance(definition,list) or len(definition)!=5 or definition[0]!='define-fun':
        raise Unsupported('expected define-fun name (args) Int body')
    _,name,args,result_type,body=definition
    if name!=problem.name or result_type!='Int':
        raise Unsupported('candidate function name or return type mismatch')
    if (not isinstance(args,list) or len(args)!=len(problem.variables)
            or any(not isinstance(pair,list) or len(pair)!=2 or pair!=[name,'Int']
                   for pair,name in zip(args,problem.variables))):
        raise Unsupported('candidate signature mismatch')
    return _parse_tree(body,problem.variables)

def check_solution(source:str,solution:str)->TextCheck:
    problem=parse_problem(source)
    tree=parse_candidate(problem,solution)
    return TextCheck(tree,certify(problem,tree),problem.name)

if __name__=='__main__':
    import argparse,json
    parser=argparse.ArgumentParser(description='Universal checker for restricted CLIA solution text')
    parser.add_argument('benchmark',type=Path)
    parser.add_argument('solution',type=Path)
    args=parser.parse_args()
    verdict=check_solution(args.benchmark.read_text(),args.solution.read_text())
    print(json.dumps({'proved':verdict.certificate.proved,
                      'cells':verdict.certificate.checked_cells,
                      'witness':verdict.certificate.counterexample,
                      'method':verdict.certificate.reason},indent=2))
