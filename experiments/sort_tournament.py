"""Experimental adaptive sorting mechanisms. Integer inputs; returns a fresh list."""
from bisect import bisect_right

def run_merge(values):
    """Natural nondecreasing runs; stable iterative pairwise merge, O(n log n) worst."""
    a=list(values)
    if len(a)<2:return a
    runs=[]; start=0
    for i in range(1,len(a)):
        if a[i]<a[i-1]:
            runs.append(a[start:i]);start=i
    runs.append(a[start:])
    while len(runs)>1:
        merged=[]
        for k in range(0,len(runs),2):
            if k+1==len(runs):
                merged.append(runs[k]);continue
            x,y=runs[k],runs[k+1];i=j=0;out=[]
            while i<len(x) and j<len(y):
                if x[i]<=y[j]:out.append(x[i]);i+=1
                else:out.append(y[j]);j+=1
            out.extend(x[i:]);out.extend(y[j:]);merged.append(out)
        runs=merged
    return runs[0]

def sparse_distribution(values, max_ratio=8):
    """Range-bounded stable counting; comparison fallback prevents huge allocations."""
    a=list(values)
    if not a:return a
    lo=min(a);hi=max(a);width=hi-lo+1
    if width>max_ratio*len(a):return run_merge(a)
    counts=[0]*width
    for v in a:counts[v-lo]+=1
    out=[]
    for i,c in enumerate(counts):out.extend([lo+i]*c)
    return out

def three_way_blocks(values, cutoff=24):
    """Iterative three-way quicksort with median-of-three pivots and depth fallback."""
    a=list(values);n=len(a)
    if n<2:return a
    stack=[(0,n,2*n.bit_length())]
    while stack:
        lo,hi,depth=stack.pop()
        if hi-lo<=cutoff:
            for i in range(lo+1,hi):
                x=a[i];j=i
                while j>lo and a[j-1]>x:a[j]=a[j-1];j-=1
                a[j]=x
            continue
        if depth==0:
            a[lo:hi]=run_merge(a[lo:hi]);continue
        mid=(lo+hi)//2
        pivot=sorted((a[lo],a[mid],a[hi-1]))[1]
        lt=i=lo;gt=hi
        while i<gt:
            if a[i]<pivot:a[lt],a[i]=a[i],a[lt];lt+=1;i+=1
            elif a[i]>pivot:gt-=1;a[i],a[gt]=a[gt],a[i]
            else:i+=1
        if lt-lo>1:stack.append((lo,lt,depth-1))
        if hi-gt>1:stack.append((gt,hi,depth-1))
    return a

CANDIDATES={"run_merge":run_merge,"sparse_distribution":sparse_distribution,
            "three_way_blocks":three_way_blocks}
