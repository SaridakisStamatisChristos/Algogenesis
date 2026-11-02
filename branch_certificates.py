"""Exact equivalence of piecewise-affine decision trees over x, y and zero.

The lines x=0, y=0, x=y partition the plane into 13 relatively open
cells. Every supported decision tree is affine on each cell. An affine
basis (3 points in sectors, 2 on rays, 1 at origin) proves equality on
the entire cell, hence for all integer x,y, without extrapolation.
"""
from __future__ import annotations
from dataclasses import dataclass
from branch_synthesis import Node

def _sign(n):
    return (n>0)-(n<0)

def _rank(points):
    if not points:return 0
    if len(points)==1:return 1
    x0,y0=points[0]
    if all((x,y)==(x0,y0) for x,y in points[1:]):return 1
    if any((x1-x0)*(y2-y0)!=(x2-x0)*(y1-y0)
           for x1,y1 in points[1:] for x2,y2 in points[1:]):return 3
    return 2

def _cells():
    groups={}
    for x in range(-3,4):
        for y in range(-3,4):
            groups.setdefault((_sign(x),_sign(y),_sign(x-y)),[]).append((x,y))
    assert len(groups)==13
    result={}
    for key,points in sorted(groups.items()):
        required=1 if key==(0,0,0) else (3 if 0 not in key else 2)
        basis=[]
        for p in points:
            if _rank(tuple(basis)+(p,))>_rank(tuple(basis)):
                basis.append(p)
            if len(basis)==required:break
        assert len(basis)==required
        result[key]=tuple(basis)
    return result

CELLS=_cells()

def _validate(node):
    if node.leaf is not None:
        if any(type(v) is not int for v in (node.leaf.a,node.leaf.b,node.leaf.c)):
            raise TypeError('affine coefficients must be integers')
        return
    g=node.guard
    if g is None or g.op not in ('lt','le','eq') or g.lhs not in ('x','y','zero') or g.rhs not in ('x','y','zero'):
        raise ValueError('unsupported comparison guard')
    _validate(node.yes)
    _validate(node.no)

@dataclass(frozen=True)
class Certificate:
    equivalent:bool
    checked_cells:int
    checked_witnesses:int
    counterexample:tuple[int,int]|None
    method:str='exact-hyperplane-arrangement-affine-basis'

def certify(left:Node,right:Node)->Certificate:
    """Exact equality for all integer x,y within the supported grammar."""
    _validate(left)
    _validate(right)
    checked=0
    for basis in CELLS.values():
        for x,y in basis:
            checked+=1
            if left.evaluate(x,y)!=right.evaluate(x,y):
                return Certificate(False,13,checked,(x,y))
    return Certificate(True,13,checked,None)

def leaf(a=0,b=0,c=0):
    from branch_synthesis import Affine
    return Node(leaf=Affine(a,b,c))

def branch(guard,yes,no):
    return Node(guard=guard,yes=yes,no=no)
