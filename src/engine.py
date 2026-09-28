from __future__ import annotations
import json,re
from dataclasses import dataclass
from pathlib import Path
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

DATA=Path(__file__).resolve().parents[1]/'data'/'processed'

@dataclass
class Query:
    category:str|None=None
    keywords:list[str]|None=None
    no_midsem:bool=False
    no_attendance:bool=False
    no_8am:bool=False
    free_days:list[str]|None=None
    compact:bool=False
    project_based:bool=False
    lenient_makeup:bool=False
    max_results:int=5

class Recommender:
    def __init__(self):
        self.courses=json.loads((DATA/'courses.json').read_text(encoding='utf-8'))
        self.rules=json.loads((DATA/'programme_rules.json').read_text(encoding='utf-8'))
        self.by_code={c['course_code']:c for c in self.courses}
        docs=[' '.join([c.get('course_code',''),c.get('title',''),c.get('description',''),c.get('description_handout','') or '',c.get('scope_objective','') or '',c.get('learning_outcomes','') or '']) for c in self.courses]
        self.vec=TfidfVectorizer(stop_words='english',ngram_range=(1,2))
        self.mat=self.vec.fit_transform(docs)
    def parse_query(self,text):
        q=text.lower()
        if re.search(r'\bdels?\b|discipline elective',q): cat='DEL'
        elif re.search(r'\bhuels?\b|humanities?',q): cat='HUEL'
        elif re.search(r'\bopels?\b|open elective',q): cat='OPEL'
        elif re.search(r'\bcdc\b|core',q): cat='CDC'
        else: cat=None
        stop={'suggest','find','give','me','an','a','the','with','without','no','and','or','course','courses','related','to','that','is','are','i','want','need','prefer','please','for','my','this','semester','lenient','makeup','make','midsem','attendance','requirement','requirements','dels','del','huels','huel','opels','opel','cdc','class','classes'}
        toks=re.findall(r'[a-z][a-z0-9+-]*',q)
        kws=list(dict.fromkeys(t for t in toks if t not in stop and len(t)>=2))
        return Query(category=cat,keywords=kws,
          no_midsem=bool(re.search(r'no\s+(midsem|mid-sem|mid semester)|without\s+(a\s+)?midsem',q)),
          no_attendance=bool(re.search(r'no\s+attendance|without\s+attendance',q)),
          no_8am=bool(re.search(r'no\s+8\s*am|avoid\s+8\s*am',q)),
          free_days=[d for d in ['monday','tuesday','wednesday','thursday','friday','saturday'] if re.search(rf'\b{d}\b.*\bfree\b|\bfree\b.*\b{d}\b',q)],
          compact=('compact' in q or 'long gaps' in q),project_based=bool(re.search(r'project[- ]based|project',q)),lenient_makeup=bool(re.search(r'lenient.*makeup|makeup.*lenient',q)))
    def academic_state(self,p):
        rule=self.rules['B.E. Computer Science']; done=set(p.get('completed',[])); cur=set(p.get('current',[]))
        rf=[x for x in rule['foundation_courses'] if x not in done and x not in cur]
        rc=[x for x in rule['core_courses'] if x not in done and x not in cur]
        huel=[self.by_code.get(x,{}) for x in done if self.by_code.get(x,{}).get('category')=='HUEL_CANDIDATE']
        de=[self.by_code.get(x,{}) for x in done if self.by_code.get(x,{}).get('department')=='CS' and x not in rule['core_courses']]
        hu=sum(float(x.get('units') or 0) for x in huel)
        deu=sum(float(x.get('units') or 0) for x in de)
        return {'remaining_foundation':rf,'remaining_core':rc,'huel_courses_done':len(huel),'huel_units_done':hu,'huel_courses_remaining':max(0,rule['huel_courses_required']-len(huel)),'huel_units_remaining':max(0,rule['huel_units_required']-hu),'de_units_done':deu,'de_units_remaining':max(0,rule['discipline_elective_units']-deu),'registration_limit':self.rules['global_registration']['first_degree_max_units']}
    def eligibility(self,c,p,state):
        code=c['course_code']; done=set(p.get('completed',[])); cur=set(p.get('current',[]))
        if code in done:return 'ineligible',['Already completed']
        if code in cur:return 'ineligible',['Already in current semester']
        if c.get('category')=='CDC' and code not in state['remaining_core']:return 'ineligible',['Core requirement already satisfied']
        raw=' '.join(c.get('prerequisites_raw',[])) + ' ' + (c.get('prerequisites_handout') or ''); pre=re.findall(r'\b[A-Z]{2,6}\s+[FG][0-9]{3,4}[A-Z0-9T-]*\b',raw); miss=[x for x in pre if x not in done]
        if miss:return 'ineligible',[f'Missing prerequisite: {x}' for x in miss]
        if re.search(r'\sG\d',code):return 'verification_required',['G-level course; first-degree access must be verified']
        if c.get('category') in {'OPEL_OR_OTHER','HUEL_OR_OPEL_CANDIDATE'}:return 'verification_required',['Elective category/eligibility is not fully provable from supplied timetable data']
        return 'eligible',[]
    def slots(self,c):
        groups={'L':[],'T':[],'P':[]}
        for s in c.get('sections',[]):groups.setdefault(s['type'],[]).append(s)
        opts=[]
        for l in groups['L'] or [None]:
          for t in groups['T'] or [None]:
            for p in groups['P'] or [None]:
              opts.append([x for x in (l,t,p) if x])
              if len(opts)>=80:return opts
        return opts or [[]]
    @staticmethod
    def conflict(a,b):
        sa={(d,h) for sec in a for d,h in sec.get('slots',[])}; sb={(d,h) for sec in b for d,h in sec.get('slots',[])}
        return bool(sa&sb)
    def schedule(self,courses,p):
        fixed=[self.slots(self.by_code[x])[0] for x in p.get('current',[]) if x in self.by_code]
        def dfs(i,acc):
            if i==len(courses):return acc
            for opt in self.slots(courses[i]):
                if any(self.conflict(opt,x) for x in fixed+acc):continue
                r=dfs(i+1,acc+[opt])
                if r is not None:return r
            return None
        return dfs(0,[])
    def recommend(self,p,text):
        q=self.parse_query(text); state=self.academic_state(p); scored=[]
        qv=self.vec.transform([' '.join(q.keywords)]) if q.keywords else None
        for idx,c in enumerate(self.courses):
            if q.category=='DEL' and c.get('department')!='CS':continue
            if q.category=='HUEL' and c.get('category')!='HUEL_CANDIDATE':continue
            if q.category=='CDC' and c.get('category')!='CDC':continue
            if q.category=='OPEL' and c.get('category')=='CDC':continue
            status,reasons=self.eligibility(c,p,state)
            if status=='ineligible':continue
            if q.no_midsem and c.get('midsem'):continue
            if q.no_attendance and not c.get('attendance_policy'):
                status='verification_required'; reasons=reasons+['Course-specific attendance policy is not stated in the supplied Part II handout']
            sim=float(cosine_similarity(qv,self.mat[idx])[0,0]) if qv is not None else 0.0
            score=sim+(0.18 if q.project_based and 'project' in (c.get('title','')+' '+c.get('description','')).lower() else 0)
            if q.no_8am and any(h==1 for s in c.get('sections',[]) for _,h in s.get('slots',[])):score-=.25
            if q.free_days:
                bad={d[:1].upper() if d!='thursday' else 'Th' for d in q.free_days}
                if any(d in bad for s in c.get('sections',[]) for d,_ in s.get('slots',[])):score-=.15
            scored.append((score,status,reasons,c))
        scored.sort(key=lambda x:x[0],reverse=True)
        results=[{'course':c,'score':round(score,3),'eligibility':st,'reasons':rs} for score,st,rs,c in scored[:q.max_results]]
        return q,state,results,self.schedule([x['course'] for x in results],p)
