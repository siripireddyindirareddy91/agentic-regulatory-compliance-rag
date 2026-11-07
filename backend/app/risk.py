WEIGHTS={'severity':.35,'likelihood':.25,'regulatory_impact':.25,'operational_impact':.15}
def configured_weights(db,tenant):
    from sqlalchemy import select
    from .models import Setting
    setting=db.scalar(select(Setting).where(Setting.institution_id==tenant,Setting.key=='risk_weights'))
    return setting.value if setting else WEIGHTS
def assess(factors, weights=None):
    weights=weights or WEIGHTS
    if abs(sum(weights.values())-1)>0.001: raise ValueError('Risk weights must total 1')
    if set(factors)!=set(WEIGHTS) or any(not 1<=v<=5 for v in factors.values()): raise ValueError('All four risk factors must be between 1 and 5')
    score=round(sum(factors[k]*weights[k] for k in WEIGHTS),2)
    level='Critical' if score>=4.2 else 'High' if score>=3.4 else 'Medium' if score>=2.4 else 'Low'
    return score,level
