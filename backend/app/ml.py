"""Portable inference for exported fitted sklearn TF-IDF, LR, RF and IF models."""
import json,re,math
from pathlib import Path
from functools import lru_cache
@lru_cache
def artifact():return json.loads((Path(__file__).parent/'artifacts/models.json').read_text(encoding='utf-8'))
def vector(text,m):
    tokens=re.findall(r'(?u)\b\w\w+\b',text.lower());terms=tokens+[a+' '+b for a,b in zip(tokens,tokens[1:])];x=[0.0]*len(m['idf'])
    for term in terms:
        idx=m['vocabulary'].get(term)
        if idx is not None:x[idx]+=1
    x=[v*m['idf'][i] for i,v in enumerate(x)];norm=math.sqrt(sum(v*v for v in x)) or 1
    return [v/norm for v in x]
def leaf(tree,x):
    i=0;depth=0
    while tree['left'][i]!=-1:
        i=tree['left'][i] if x[tree['feature'][i]]<=tree['threshold'][i] else tree['right'][i];depth+=1
    return i,depth
def expected(n):return 0 if n<=1 else 1 if n==2 else 2*(math.log(n-1)+.5772156649)-2*(n-1)/n
def predict(text):
    m=artifact();x=vector(text,m);scores=[sum(a*b for a,b in zip(row,x))+m['intercept'][i] for i,row in enumerate(m['coef'])];top=max(scores);exp=[math.exp(s-top) for s in scores];probs=[p/sum(exp) for p in exp];cls=max(range(len(probs)),key=probs.__getitem__)
    votes=[0.0]*len(m['classes'])
    for tree in m['random_forest']:
        i,_=leaf(tree,x);values=tree['value'][i][0];total=sum(values) or 1
        for j,v in enumerate(values):votes[j]+=v/total/len(m['random_forest'])
    paths=[]
    for tree in m['isolation_forest']:
        i,depth=leaf(tree,x);paths.append(depth+expected(tree['samples'][i]))
    anomaly=2**(-(sum(paths)/len(paths))/(expected(m['isolation_samples']) or 1))
    return {'category':m['classes'][cls] if any(x) else 'Unclassified','model_score':round(probs[cls],4),'random_forest_category':m['classes'][max(range(len(votes)),key=votes.__getitem__)],'anomaly_score':round(anomaly,4),'exploratory_anomaly':anomaly>m['isolation_threshold'],'provider':'Trained TF-IDF / Logistic Regression + Random Forest + Isolation Forest','notice':m['notice'],'version':m['version']}
