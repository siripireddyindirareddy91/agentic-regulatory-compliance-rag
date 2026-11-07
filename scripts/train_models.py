"""Train exportable sklearn models on labeled synthetic demonstration examples."""
import json,math
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.ensemble import RandomForestClassifier,IsolationForest
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score,f1_score
groups={'AML':['suspicious transaction monitoring','anti money laundering alerts','financial crime escalation','beneficial ownership screening','sanctions compliance review','transaction reporting controls'], 'Cybersecurity':['encryption access security','cyber incident response','privileged access reviews','information security controls','network vulnerability management','data encryption standards'], 'Customer Protection':['customer identity verification','customer grievance resolution','fair lending disclosure','consumer complaint handling','account opening checks','customer consent protection'], 'Operational Risk':['operational risk committee','business continuity testing','third party risk review','control assurance assessment','resilience recovery exercise','outsourcing risk assessment']}
texts=[];labels=[]
for category,terms in groups.items():
 for term in terms:
  for verb in ['must implement','shall document','is required to review','must maintain evidence of','shall regularly assess']:
   texts.append('The financial institution '+verb+' '+term+' and retain documented controls.');labels.append(category)
train,test,ytrain,ytest=train_test_split(texts,labels,test_size=.25,random_state=42,stratify=labels)
tf=TfidfVectorizer(max_features=1200,ngram_range=(1,2));x=tf.fit_transform(train);xt=tf.transform(test)
lr=LogisticRegression(max_iter=1000,random_state=42).fit(x,ytrain)
rf=RandomForestClassifier(n_estimators=24,max_depth=7,random_state=42).fit(x,ytrain)
iso=IsolationForest(n_estimators=24,max_samples=min(128,len(train)),random_state=42,contamination=.1).fit(x.toarray())
def trees(model):
 return [{'left':e.tree_.children_left.tolist(),'right':e.tree_.children_right.tolist(),'feature':e.tree_.feature.tolist(),'threshold':e.tree_.threshold.tolist(),'value':e.tree_.value.tolist(),'samples':e.tree_.n_node_samples.tolist()} for e in model.estimators_]
artifact={'version':'synthetic-demo-v1','notice':'Trained on synthetic template data. Held-out rows share vocabulary and templates with training. Metrics are demonstration diagnostics, not real-world regulatory accuracy or calibrated confidence.','vocabulary':{k:int(v) for k,v in tf.vocabulary_.items()},'idf':tf.idf_.tolist(),'classes':lr.classes_.tolist(),'coef':lr.coef_.tolist(),'intercept':lr.intercept_.tolist(),'random_forest':trees(rf),'isolation_forest':trees(iso),'isolation_samples':int(iso.max_samples_),'isolation_threshold':float(-iso.offset_),'metrics':{'training_rows':len(train),'test_rows':len(test),'logistic_accuracy':accuracy_score(ytest,lr.predict(xt)),'logistic_macro_f1':f1_score(ytest,lr.predict(xt),average='macro'),'random_forest_accuracy':accuracy_score(ytest,rf.predict(xt))}}
path=Path('backend/app/artifacts/models.json');path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(artifact),encoding='utf-8');print(json.dumps(artifact['metrics']))
