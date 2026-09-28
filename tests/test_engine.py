from src.engine import Recommender
def test_parser():
 r=Recommender();q=r.parse_query('Suggest DELs related to AI with no midsem');assert q.category=='DEL' and q.no_midsem and 'ai' in q.keywords
def test_requirements():
 r=Recommender();s=r.academic_state({'program':'B.E. Computer Science','completed':['CS F111'],'current':[]});assert 'CS F111' not in s['remaining_foundation'];assert len(s['remaining_core'])==14
def test_huel():
 r=Recommender();_,_,res,_=r.recommend({'program':'B.E. Computer Science','completed':[],'current':[]},'Suggest a HUEL');assert res and all(x['course']['category']=='HUEL_CANDIDATE' for x in res)
