"""Restricted SyGuS-IF CLIA synthesis with exact order-region certificates.

Subset: one grammar-free Int synth-fun, Int vars, quantifier-free LIA constraints,
operators + - < <= > >= = and or not =>; a candidate grammar of affine
leaves and comparisons of input variables/zero. Unsupported syntax rejects.
This is not a complete SyGuS engine. Finite search is distinct from the
order-cell theorem, which covers all integer vectors when it returns PROVED.
"""
from __future__ import annotations
from dataclasses import dataclass
from functools import lru_cache
from itertools import product
from typing import Any

class Unsupported(ValueError):
    """Requested benchmark is outside the explicitly implemented fragment."""

def parse_sexpressions(text: str) -> tuple:
    import re
    without_comments = re.sub(r';[^\n]*', '', text)
    tokens = re.findall(r'\(|\)|[^\s()]+', without_comments)
    stack: list[list] = [[]]
    for token in tokens:
        if token == '(':
            new: list = []
            stack[-1].append(new)
            stack.append(new)
        elif token == ')':
            if len(stack) == 1: raise ValueError('unmatched closing parenthesis')
            stack.pop()
        else: stack[-1].append(token)
    if len(stack) != 1: raise ValueError('unmatched opening parenthesis')
    return tuple(stack[0])

@dataclass(frozen=True)
class Problem:
    name: str
    variables: tuple[str, ...]
    constraints: tuple[Any, ...]

def parse_problem(text: str) -> Problem:
    commands = parse_sexpressions(text)
    name = None
    variables = None
    declared: set[str] = set()
    constraints = []
    found_check = False
    for cmd in commands:
        if not isinstance(cmd, list) or not cmd: raise Unsupported('invalid command')
        key = cmd[0]
        if key == 'set-logic':
            if len(cmd) != 2 or cmd[1] != 'LIA': raise Unsupported('only set-logic LIA supported')
        elif key == 'synth-fun':
            if name is not None or len(cmd) != 4 or cmd[3] != 'Int':
                raise Unsupported('single grammar-free Int synth-fun required')
            name = cmd[1]
            if not isinstance(cmd[2], list) or any(
                not isinstance(item, list) or len(item) != 2 or item[1] != 'Int'
                for item in cmd[2]):
                raise Unsupported('only Int function arguments supported')
            variables = tuple(item[0] for item in cmd[2])
            if len(set(variables)) != len(variables) or not 1 <= len(variables) <= 6:
                raise Unsupported('between one and six distinct arguments required')
        elif key == 'declare-var':
            if len(cmd) != 3 or cmd[2] != 'Int': raise Unsupported('only Int variables supported')
            if cmd[1] in declared: raise Unsupported('duplicate declared variable')
            declared.add(cmd[1])
        elif key == 'constraint':
            if len(cmd) != 2 or found_check: raise Unsupported('invalid constraint command order')
            constraints.append(cmd[1])
        elif key == 'check-synth':
            if len(cmd) != 1 or found_check: raise Unsupported('exactly one check-synth required')
            found_check = True
        elif key == 'set-info': continue
        else: raise Unsupported(f'unsupported command: {key}')
    if name is None or not found_check or not constraints or set(variables) != declared:
        raise Unsupported('missing synth-fun, check-synth, constraints or declarations')
    return Problem(name, variables, tuple(constraints))

@dataclass(frozen=True)
class Affine:
    coefficients: tuple[int, ...]
    constant: int = 0
    def at(self, values: tuple[int, ...]) -> int:
        return self.constant + sum(a*x for a,x in zip(self.coefficients,values))
    def source(self, names: tuple[str,...]) -> str:
        terms = ([str(self.constant)] if self.constant else [])
        for a,name in zip(self.coefficients,names):
            if a>0:terms.extend([name]*a)
            elif a<0:terms.extend([f'(- {name})']*(-a))
        if not terms:return '0'
        if len(terms)==1:return terms[0]
        return '(+ '+' '.join(terms)+')'

@dataclass(frozen=True)
class Guard:
    left:int|None
    right:int|None
    op:str
    def check(self,values:tuple[int,...])->bool:
        a=0 if self.left is None else values[self.left]
        b=0 if self.right is None else values[self.right]
        if self.op=='<=':return a<=b
        if self.op=='<':return a<b
        raise ValueError('unsupported guard')
    def source(self,names:tuple[str,...])->str:
        a='0' if self.left is None else names[self.left]
        b='0' if self.right is None else names[self.right]
        return f'({self.op} {a} {b})'

@dataclass(frozen=True)
class Tree:
    leaf:Affine|None=None
    guard:Guard|None=None
    yes:Tree|None=None
    no:Tree|None=None
    def at(self,values:tuple[int,...])->int:
        if self.leaf is not None:return self.leaf.at(values)
        return (self.yes if self.guard.check(values) else self.no).at(values)
    def source(self,names:tuple[str,...])->str:
        if self.leaf is not None:return self.leaf.source(names)
        return f'(ite {self.guard.source(names)} {self.yes.source(names)} {self.no.source(names)})'
    def nodes(self)->int:
        return 1 if self.leaf is not None else 1+self.yes.nodes()+self.no.nodes()

def _linear(expr,env:dict[str,Affine],variables:tuple[str,...],call):
    if isinstance(expr,str):
        if expr in env:return env[expr]
        if expr.lstrip('-').isdigit():return Affine((0,)*len(variables),int(expr))
        if expr=='true':return True
        if expr=='false':return False
        raise Unsupported(f'unknown atom: {expr}')
    if not isinstance(expr,list) or not expr:raise Unsupported('invalid expression')
    op,*args=expr
    if op=='ite':raise Unsupported('ite in specifications is not supported (only synthesized candidates)')
    if op==call[0]:
        if len(args)!=len(variables):raise Unsupported('wrong synth-fun arity')
        arguments=tuple(_linear(arg,env,variables,call) for arg in args)
        return call[1](arguments)
    values=[_linear(arg,env,variables,call) for arg in args]
    if op in ('+','-'):
        if not values:raise Unsupported('arithmetic needs operands')
        if any(not isinstance(v,Affine) for v in values):raise Unsupported('numeric operands required')
        if op=='+' or len(values)>1:
            first,others=values[0],values[1:]
            if op=='-' and len(values)!=2:raise Unsupported('binary subtraction only')
            result=first
            for second in others:
                factor=1 if op=='+' else -1
                result=Affine(tuple(a+factor*b for a,b in zip(result.coefficients,second.coefficients)),
                              result.constant+factor*second.constant)
            return result
        return Affine(tuple(-a for a in values[0].coefficients),-values[0].constant)
    if op in ('=','<=','<','>=','>'):
        if len(values)!=2 or any(not isinstance(v,Affine) for v in values):
            raise Unsupported('only two numeric operands supported')
        return ('compare',op,values[0],values[1])
    if op in ('and','or'):
        if not values:raise Unsupported('nonempty Boolean operation expected')
        return (op,tuple(values))
    if op=='not':
        if len(values)!=1:raise Unsupported('not expects one argument')
        return ('not',values[0])
    if op=='=>':
        if len(values)!=2:raise Unsupported('=> expects two arguments')
        return ('or',(('not',values[0]),values[1]))
    raise Unsupported(f'unsupported expression operator: {op}')

def _numeric_eval(value,point):
    if not isinstance(value,Affine):raise Unsupported('numeric expression expected')
    return value.at(point)

def _truth(value,point):
    if isinstance(value,bool):return value
    if not isinstance(value,tuple):raise Unsupported('Boolean expression required')
    if value[0]=='compare':
        _,op,a,b=value
        x,y=a.at(point),b.at(point)
        return {'=':x==y,'<=':x<=y,'<':x<y,'>=':x>=y,'>':x>y}[op]
    if value[0]=='and':return all(_truth(v,point) for v in value[1])
    if value[0]=='or':return any(_truth(v,point) for v in value[1])
    if value[0]=='not':return not _truth(value[1],point)
    raise Unsupported('Boolean expression required')

def finite_constraints(problem:Problem,tree:Tree,point:tuple[int,...])->bool:
    if len(point)!=len(problem.variables):raise ValueError('arity mismatch')
    n=len(point)
    basis={name:Affine(tuple(int(i==j) for i in range(n))) for j,name in enumerate(problem.variables)}
    def invoke(args):
        vals=tuple(_numeric_eval(arg,point) for arg in args)
        return Affine((0,)*n,tree.at(vals))
    return all(_truth(_linear(form,basis,problem.variables,(problem.name,invoke)),point)
               for form in problem.constraints)

def _pair_symmetric(problem:Problem)->bool:
    """Recognize an explicit universal f(x,y)=f(y,x) constraint."""
    if len(problem.variables)!=2:return False
    x,y=problem.variables
    direct=[problem.name,x,y]
    reversed_call=[problem.name,y,x]
    return any(form==['=',direct,reversed_call] or form==['=',reversed_call,direct]
               for form in problem.constraints)

def _sample_output(problem,point):
    n=len(point)
    basis={name:Affine(tuple(int(i==j) for i in range(n))) for j,name in enumerate(problem.variables)}
    expected=tuple(basis[name] for name in problem.variables)
    symmetric=_pair_symmetric(problem)
    values=set(point)|{0,1,-1}
    values.update(a+b for a,b in product(point,repeat=2))
    values.update(a-b for a,b in product(point,repeat=2))
    accepted=[]
    for guess in sorted(values):
        def invoke(args):
            if args!=expected and not (symmetric and args==expected[::-1]):
                raise Unsupported('unsupported nonlocal or permuted synth-fun call')
            return Affine((0,)*n,guess)
        if all(_truth(_linear(form,basis,problem.variables,(problem.name,invoke)),point)
               for form in problem.constraints):
            accepted.append(guess)
    if not accepted:raise Unsupported('no satisfying output found in the explored value universe')
    if len(accepted)>1 and not symmetric:
        raise Unsupported('ambiguous pointwise target without an explicit symmetry constraint')
    # Deterministic heuristic only. Both full-grid and universal checks remain mandatory.
    return max(accepted) if symmetric else accepted[0]

def _guards(n):
    indices=list(range(n))+[None]
    return tuple(Guard(a,b,op) for a in indices for b in indices if a!=b
                 for op in ('<=','<'))

def _leaves(n):
    out=[]
    for j in range(n):out.append(Affine(tuple(int(i==j) for i in range(n))))
    out.append(Affine((0,)*n))
    for j in range(n):
        for k in range(n):
            if j==k:continue
            for s in (1,-1):
                coeffs=[0]*n
                coeffs[j]=1
                coeffs[k]=s
                out.append(Affine(tuple(coeffs)))
    return tuple(dict.fromkeys(out))

def _fit_tree(points,labels,n,*,depth,budget):
    leaves=_leaves(n)
    guards=_guards(n)
    work=0
    @lru_cache(None)
    def find(indices,remaining):
        nonlocal work
        work+=1
        if work>budget:raise RuntimeError('partition budget exceeded')
        for leaf in leaves:
            if all(leaf.at(points[i])==labels[i] for i in indices):return Tree(leaf=leaf)
        if remaining==0:return None
        for guard in guards:
            yes=tuple(i for i in indices if guard.check(points[i]))
            if not yes or len(yes)==len(indices):continue
            no=tuple(i for i in indices if not guard.check(points[i]))
            left=find(yes,remaining-1)
            if left is None:continue
            right=find(no,remaining-1)
            if right is not None:return Tree(guard=guard,yes=left,no=right)
        return None
    return find(tuple(range(len(points))),depth),work

@lru_cache(None)
def _cells(n):
    """All weak orders among inputs and zero, each feasible in Z^n."""
    seen=set()
    for point in product(range(-n,n+1),repeat=n):
        distinct=sorted(set(point)|{0})
        key=tuple(distinct.index(x) for x in point)+(distinct.index(0),)
        seen.add(key)
    return tuple(sorted(seen))

def _sign_range(expr:Affine,order):
    """Exact min/max on integer gap cone; None denotes infinity."""
    z=order[-1]
    groups=max(order)+1
    weights=[0]*(groups-1)
    for i,coefficient in enumerate(expr.coefficients):
        position=order[i]
        if position>z:
            for j in range(z,position):weights[j]+=coefficient
        elif position<z:
            for j in range(position,z):weights[j]-=coefficient
    baseline=expr.constant+sum(weights)
    minimum=baseline if all(weight>=0 for weight in weights) else None
    maximum=baseline if all(weight<=0 for weight in weights) else None
    return minimum,maximum

def _relation(a,b,op,order):
    expression=Affine(tuple(x-y for x,y in zip(a.coefficients,b.coefficients)),a.constant-b.constant)
    minimum,maximum=_sign_range(expression,order)
    if op=='>=':
        if minimum is not None and minimum>=0:return True
        if maximum is not None and maximum<0:return False
    elif op=='>':
        if minimum is not None and minimum>0:return True
        if maximum is not None and maximum<=0:return False
    elif op=='<=':
        if maximum is not None and maximum<=0:return True
        if minimum is not None and minimum>0:return False
    elif op=='<':
        if maximum is not None and maximum<0:return True
        if minimum is not None and minimum>=0:return False
    elif op=='=':
        if minimum==maximum==0:return True
        if (minimum is not None and minimum>0) or (maximum is not None and maximum<0):return False
    else:raise Unsupported('unsupported comparison')
    return None

def _universal_truth(value,order):
    if isinstance(value,bool):return value
    if not isinstance(value,tuple):raise Unsupported('expected Boolean formula')
    if value[0]=='compare':return _relation(value[2],value[3],value[1],order)
    if value[0]=='not':
        result=_universal_truth(value[1],order)
        return None if result is None else not result
    if value[0] in ('and','or'):
        options=tuple(_universal_truth(v,order) for v in value[1])
        if value[0]=='and':return False if False in options else (True if all(v is True for v in options) else None)
        return True if True in options else (False if all(v is False for v in options) else None)
    raise Unsupported('Boolean formula outside certificate fragment')

def _symbolic_tree(tree,arguments,order):
    if tree.leaf is not None:
        value=Affine((0,)*len(arguments[0].coefficients),tree.leaf.constant)
        for a,term in zip(tree.leaf.coefficients,arguments):
            value=Affine(tuple(x+a*y for x,y in zip(value.coefficients,term.coefficients)),
                         value.constant+a*term.constant)
        return value
    def variable(index):
        return arguments[index] if index is not None else Affine((0,)*len(arguments[0].coefficients))
    choice=_relation(variable(tree.guard.left),variable(tree.guard.right),tree.guard.op,order)
    if choice is None:raise Unsupported('synthesized guard is not constant on a weak-order cell')
    return _symbolic_tree(tree.yes if choice else tree.no,arguments,order)

@dataclass(frozen=True)
class Certificate:
    proved:bool
    checked_cells:int
    counterexample:tuple[int,...]|None
    reason:str

def _validate_tree(tree:Tree,n:int):
    if not isinstance(tree,Tree):raise TypeError('expected Tree')
    if tree.leaf is not None:
        if (tree.guard is not None or tree.yes is not None or tree.no is not None
                or len(tree.leaf.coefficients)!=n
                or any(type(v) is not int for v in tree.leaf.coefficients)
                or type(tree.leaf.constant) is not int):
            raise ValueError('malformed affine leaf')
        return
    if (tree.guard is None or tree.yes is None or tree.no is None
            or tree.guard.op not in ('<','<=')
            or any(v is not None and (type(v) is not int or not 0<=v<n)
                   for v in (tree.guard.left,tree.guard.right))):
        raise ValueError('malformed guard or branch')
    _validate_tree(tree.yes,n)
    _validate_tree(tree.no,n)

def certify(problem:Problem,tree:Tree)->Certificate:
    """Exact order-cell proof for all integers, otherwise abstain."""
    n=len(problem.variables)
    if n > 4:
        raise Unsupported('internal weak-order certificate supports at most four arguments')
    _validate_tree(tree,n)
    identity=tuple(Affine(tuple(int(i==j) for i in range(n))) for j in range(n))
    env=dict(zip(problem.variables,identity))
    checked=0
    for cell in _cells(n):
        def invoke(args):return _symbolic_tree(tree,args,cell)
        for form in problem.constraints:
            symbolic=_linear(form,env,problem.variables,(problem.name,invoke))
            result=_universal_truth(symbolic,cell)
            if result is not True:
                witness=tuple(rank-cell[-1] for rank in cell[:-1]) if result is False else None
                return Certificate(False,checked,witness,
                                   'counterexample cell' if result is False else 'unknown sign within order cell')
        checked+=1
    return Certificate(True,checked,None,'exact integer-gap order partition')

@dataclass(frozen=True)
class Result:
    tree:Tree|None
    candidate_count:int
    examples:int
    verified_grid:int
    certificate:Certificate|None
    status:str

def synthesize(problem:Problem,*,domain=range(-2,3),max_depth=3,
               max_rounds=80,max_partitions=250000)->Result:
    if not 1<=len(problem.variables)<=4 or type(max_depth) is not int or not 0<=max_depth<=4:
        raise ValueError('unsupported number of arguments or depth')
    if type(max_rounds) is not int or max_rounds<1 or type(max_partitions) is not int or max_partitions<1:
        raise ValueError('positive search budgets required')
    domain=tuple(domain)
    if not domain or any(type(value) is not int for value in domain):
        raise ValueError('nonempty integer domain required')
    universe=tuple(product(domain,repeat=len(problem.variables)))
    if not universe or len(universe)>250000:raise ValueError('empty/oversized sample domain')
    targets=tuple(_sample_output(problem,p) for p in universe)
    indexes=[0]
    seen={0}
    work=0
    for rnd in range(max_rounds):
        subset=tuple(universe[i] for i in indexes)
        labels=tuple(targets[i] for i in indexes)
        try:
            tree,spent=_fit_tree(subset,labels,len(problem.variables),
                                depth=max_depth,budget=max_partitions-work)
        except RuntimeError:
            return Result(None,work,len(indexes),len(universe),None,'budget_exhausted')
        work+=spent
        if tree is None:
            return Result(None,work,len(indexes),len(universe),None,'not_found_in_grammar')
        mismatch=next((i for i,p in enumerate(universe)
                       if tree.at(p)!=targets[i] or not finite_constraints(problem,tree,p)),None)
        if mismatch is None:
            cert=certify(problem,tree)
            return Result(tree,work,len(indexes),len(universe),cert,
                          'proved' if cert.proved else 'finite_only')
        if mismatch in seen and _pair_symmetric(problem):
            swapped=tuple(reversed(universe[mismatch]))
            partner=universe.index(swapped)
            if partner not in seen:mismatch=partner
        if mismatch in seen:raise AssertionError('candidate violates a constraint despite learned targets')
        indexes.append(mismatch)
        seen.add(mismatch)
    return Result(None,work,len(indexes),len(universe),None,'round_budget_exhausted')

def output(problem,result):
    if result.tree is None:raise ValueError('no candidate synthesized')
    args=' '.join(f'({name} Int)' for name in problem.variables)
    return f'(define-fun {problem.name} ({args}) Int {result.tree.source(problem.variables)})'

if __name__=='__main__':
    import argparse,json,pathlib
    p=argparse.ArgumentParser(description='Restricted CLIA solver with exact order-cell proof')
    p.add_argument('input',type=pathlib.Path)
    p.add_argument('--depth',type=int,default=3)
    a=p.parse_args()
    pr=parse_problem(a.input.read_text())
    result=synthesize(pr,max_depth=a.depth)
    print(json.dumps({'status':result.status,'examples':result.examples,
                      'grid_cases':result.verified_grid,'search_partitions':result.candidate_count,
                      'proved_cells':result.certificate.checked_cells if result.certificate else None,
                      'solution':output(pr,result) if result.tree else None},indent=2))
