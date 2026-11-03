"""Experimental adaptive sorting mechanisms. Integer inputs; returns a fresh list."""
from bisect import bisect_right

def run_merge(values):
    """Natural nondecreasing runs; stable iterative pairwise merge, O(n log n) worst."""
    a=list(values)
    if len(a)<2:return a
    runs=[]; start=0; n=len(a)
    while start<n:
        end=start+1
        if end<n and a[end]<a[start]:
            while end<n and a[end]<a[end-1]:end+=1
            runs.append(a[start:end][::-1])
        else:
            while end<n and a[end]>=a[end-1]:end+=1
            runs.append(a[start:end])
        start=end
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
    """Adaptive iterative three-way introsort with ordered-input fast paths.

    Median-of-three block partitioning, insertion-sort leaves, and bounded-depth
    merge fallback. Worst-case O(n log n) time; fresh-list result.
    """
    a = list(values)
    n = len(a)
    if n < 2:
        return a
    # Linear-time ordered-input detection avoids destructive partitioning of
    # already monotone data (the previous implementation was especially slow).
    nondecreasing = nonincreasing = True
    for i in range(1, n):
        if a[i] < a[i - 1]:
            nondecreasing = False
        if a[i] > a[i - 1]:
            nonincreasing = False
        if not nondecreasing and not nonincreasing:
            break
    if nondecreasing:
        return a
    if nonincreasing:
        a.reverse()
        return a

    stack = [(0, n, 2 * n.bit_length())]
    while stack:
        lo, hi, depth = stack.pop()
        size = hi - lo
        if size <= cutoff:
            for i in range(lo + 1, hi):
                x = a[i]
                j = i
                while j > lo and a[j - 1] > x:
                    a[j] = a[j - 1]
                    j -= 1
                a[j] = x
            continue
        if depth == 0:
            a[lo:hi] = run_merge(a[lo:hi])
            continue
        mid = lo + size // 2
        x, y, z = a[lo], a[mid], a[hi - 1]
        # Inlined median-of-three avoids allocating and sorting a tuple
        # for each partition.
        if x < y:
            pivot = y if y < z else (z if x < z else x)
        else:
            pivot = x if x < z else (z if y < z else y)
        # Python-level element swapping is expensive. Partition the current
        # block with C-backed list-comprehension loops, then write it back.
        # This trades bounded temporary memory for lower interpreter overhead.
        block = a[lo:hi]
        lower = [v for v in block if v < pivot]
        equal = [v for v in block if v == pivot]
        upper = [v for v in block if v > pivot]
        lt = lo + len(lower)
        gt = lt + len(equal)
        a[lo:hi] = lower + equal + upper
        # Process smaller partition first to limit explicit stack growth.
        left = (lo, lt, depth - 1)
        right = (gt, hi, depth - 1)
        if lt - lo < hi - gt:
            if hi - gt > 1:
                stack.append(right)
            if lt - lo > 1:
                stack.append(left)
        else:
            if lt - lo > 1:
                stack.append(left)
            if hi - gt > 1:
                stack.append(right)
    return a

CANDIDATES={"run_merge":run_merge,"sparse_distribution":sparse_distribution,
            "three_way_blocks":three_way_blocks}
