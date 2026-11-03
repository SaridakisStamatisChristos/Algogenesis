// Native sorting tournament: C++17, deterministic inputs and randomized rounds.
#include <algorithm>
#include <chrono>
#include <cstdint>
#include <cstdlib>
#include <iostream>
#include <limits>
#include <numeric>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>
using V = std::vector<int64_t>;
using Clock = std::chrono::steady_clock;
static void insertion(V& a, size_t lo, size_t hi) {
    for (size_t i=lo+1;i<hi;++i) {
        auto v=a[i];size_t j=i;
        while(j>lo && a[j-1]>v){a[j]=a[j-1];--j;}
        a[j]=v;
    }
}
static void three_way(V& a) {
    if(a.size()<2)return;
    bool asc=true,desc=true;
    for(size_t i=1;i<a.size();++i){asc &= a[i-1]<=a[i];desc &= a[i-1]>=a[i];}
    if(asc)return;
    if(desc){std::reverse(a.begin(),a.end());return;}
    struct Task {size_t lo,hi;int depth;};
    int depth=0;for(size_t n=a.size();n>1;n>>=1)depth+=2;
    std::vector<Task> stack{{0,a.size(),depth}};
    while(!stack.empty()){
        auto [lo,hi,d]=stack.back();stack.pop_back();
        if(hi-lo<=24){insertion(a,lo,hi);continue;}
        if(d==0){std::sort(a.begin()+lo,a.begin()+hi);continue;}
        size_t mid=lo+(hi-lo)/2;
        int64_t x=a[lo],y=a[mid],z=a[hi-1];
        int64_t pivot=x<y?(y<z?y:(x<z?z:x)):(x<z?x:(y<z?z:y));
        size_t lt=lo,i=lo,gt=hi;
        while(i<gt){
            if(a[i]<pivot)std::swap(a[lt++],a[i++]);
            else if(a[i]>pivot)std::swap(a[i],a[--gt]);
            else ++i;
        }
        if(lt-lo>1)stack.push_back({lo,lt,d-1});
        if(hi-gt>1)stack.push_back({gt,hi,d-1});
    }
}
static void sparse(V& a) {
    if(a.empty())return;
    auto [l,h]=std::minmax_element(a.begin(),a.end());
    const auto lo=*l,hi=*h;
    // Avoid signed overflow and unbounded allocation.
    auto range=static_cast<uint64_t>(hi)-static_cast<uint64_t>(lo);
    if(range>static_cast<uint64_t>(a.size())*8ULL || range>10000000ULL){
        std::sort(a.begin(),a.end());return;
    }
    std::vector<size_t> count(static_cast<size_t>(range)+1,0);
    for(auto v:a)++count[static_cast<size_t>(static_cast<uint64_t>(v)-static_cast<uint64_t>(lo))];
    size_t i=0;
    for(size_t k=0;k<count.size();++k)
        for(size_t c=count[k];c>0;--c)a[i++]=static_cast<int64_t>(static_cast<uint64_t>(lo)+k);
}
// Hybrid candidate: preserve three-way partitioning for sparse domains,
// dispatch to bounded counting when the exact integer range is economical.
// Keep the original three_way candidate as an independent control.
static void adaptive_three_way(V& a) {
    if(a.size()<2048){three_way(a);return;}
    auto [l,h]=std::minmax_element(a.begin(),a.end());
    const uint64_t range=static_cast<uint64_t>(*h)-static_cast<uint64_t>(*l);
    // Cap counting storage at ~8 MiB; avoid integer overflow and allocation
    // blowups on extreme signed values.
    if(range<=static_cast<uint64_t>(a.size())*4ULL && range<=1000000ULL){
        sparse(a);
    }else{
        three_way(a);
    }
}
static void run_merge(V& a){
    if(a.size()<2)return;
    // Detect monotone runs; stable_sort handles general merging in native code.
    bool asc=true,desc=true;
    for(size_t i=1;i<a.size();++i){asc &= a[i-1]<=a[i];desc &= a[i-1]>=a[i];}
    if(asc)return;
    if(desc){std::reverse(a.begin(),a.end());return;}
    std::stable_sort(a.begin(),a.end());
}
static double median(std::vector<double> a){
    std::sort(a.begin(),a.end());return a[a.size()/2];
}
int main(int argc,char** argv){
    int repeats=11;uint64_t seed=1729;
    if(argc>1)repeats=std::stoi(argv[1]);
    if(argc>2)seed=std::stoull(argv[2]);
    if(repeats<3 || repeats>1000)throw std::invalid_argument("repeats must be 3..1000");
    std::mt19937_64 rng(seed);
    const std::vector<std::string> names={"three_way","adaptive_three_way","sparse_distribution","run_merge","std_sort","std_stable_sort"};
    std::cout<<"n,workload,algorithm,median_ns,samples_ns\n";
    for(size_t n:{size_t(100),size_t(1000),size_t(10000),size_t(100000),size_t(1000000)}){
        for(std::string workload:{"random","sorted","reverse","duplicates","wide_range"}){
            V input(n);
            for(size_t i=0;i<n;++i){
                if(workload=="sorted")input[i]=static_cast<int64_t>(i);
                else if(workload=="reverse")input[i]=static_cast<int64_t>(n-i);
                else if(workload=="duplicates")input[i]=static_cast<int64_t>(rng()%4);
                else if(workload=="wide_range")input[i]=static_cast<int64_t>(rng());
                else input[i]=static_cast<int64_t>(rng()%(2*n+1))-static_cast<int64_t>(n);
            }
            V expected=input;std::sort(expected.begin(),expected.end());
            std::vector<std::vector<double>> times(names.size());
            std::vector<int> order(names.size());std::iota(order.begin(),order.end(),0);
            auto execute=[&](int which){
                V a=input;
                auto start=Clock::now();
                switch(which){
                    case 0:three_way(a);break;
                    case 1:adaptive_three_way(a);break;
                    case 2:sparse(a);break;
                    case 3:run_merge(a);break;
                    case 4:std::sort(a.begin(),a.end());break;
                    case 5:std::stable_sort(a.begin(),a.end());break;
                }
                auto ns=std::chrono::duration<double,std::nano>(Clock::now()-start).count();
                if(a!=expected)throw std::runtime_error("correctness failure: "+names[which]);
                return ns;
            };
            for(int k:order)execute(k); // warmup and correctness
            for(int rep=0;rep<repeats;++rep){
                std::shuffle(order.begin(),order.end(),rng);
                for(int k:order)times[k].push_back(execute(k));
            }
            for(size_t k=0;k<names.size();++k){
                std::cout<<n<<","<<workload<<","<<names[k]<<","<<median(times[k])<<",\"";
                for(size_t i=0;i<times[k].size();++i){
                    if(i)std::cout<<";";
                    std::cout<<times[k][i];
                }
                std::cout<<"\"\n";
            }
        }
    }
}
