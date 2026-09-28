from dataclasses import dataclass
from .engine import Recommender
@dataclass
class AgentTrace:
    name:str; output:object
class AcademicAgent:
    def __init__(self):self.r=Recommender()
    def run(self,p,q):
        parsed=self.r.parse_query(q); state=self.r.academic_state(p); _,_,res,sched=self.r.recommend(p,q)
        trace=[AgentTrace('IntentAgent',parsed.__dict__),AgentTrace('RequirementAgent',state),AgentTrace('EligibilityAgent',[{'code':x['course']['course_code'],'status':x['eligibility']} for x in res]),AgentTrace('PreferenceAgent',[x['course']['course_code'] for x in res]),AgentTrace('ScheduleAgent',bool(sched))]
        return res,state,trace,sched
