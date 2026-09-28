from __future__ import annotations
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'data'/'processed'

def norm(s): return re.sub(r'\s+',' ',str(s or '')).strip().upper()

def clean_text(s):
    if not s:return None
    s=s.replace('\u200b','').replace('\ufeff','')
    s=re.sub(r'\s+',' ',s).strip(' :;,-')
    return s or None

def code_variants(c):
    c=norm(c).replace(' ','')
    m=re.match(r'([A-Z]{2,7})([FGU])(\d{3,4}[A-Z0-9-]*)$',c)
    return [f'{m.group(1)} {m.group(2)}{m.group(3)}'] if m else [norm(c)]

def main():
    courses_path = OUT/'courses_base.json' if (OUT/'courses_base.json').exists() else OUT/'courses.json'
    courses=json.loads(courses_path.read_text(encoding='utf-8'))
    hand=json.loads((OUT/'handouts.json').read_text(encoding='utf-8'))
    # Build exact and compact lookup, preferring records whose title is substantive.
    lookup={}
    for h in hand:
        code=norm(h['course_code'])
        lookup[code]=h
        lookup[code.replace(' ','')]=h

    for c in courses:
        h=lookup.get(norm(c['course_code'])) or lookup.get(norm(c['course_code']).replace(' ',''))
        if not h:
            c['handout_verified']=False
            continue
        c['handout_verified']=True
        c['handout_count']=h.get('handout_count',1)
        c['handout_source_files']=h.get('source_files',[])
        for src,dst in [('instructor','instructor_handout'),('description','description_handout'),('scope_objective','scope_objective'),('learning_outcomes','learning_outcomes'),('prerequisites','prerequisites_handout'),('attendance_policy','attendance_policy'),('makeup_policy','makeup_policy'),('evaluation_scheme_raw','evaluation_scheme_raw'),('evaluation_components','evaluation_components')]:
            v=h.get(src)
            if isinstance(v,str): v=clean_text(v)
            if v: c[dst]=v
        for f in ['midsem','compre','quiz','assignment','project','lab']:
            c[f]=bool(h.get(f)) if h.get(f) is not None else c.get(f)
        # The handout is stronger evidence for title when timetable title is missing/placeholder.
        if h.get('title') and len(clean_text(h['title']) or '')>1:
            c['title']=clean_text(h['title'])
        c['course_handout_date']=h.get('date')
        c['course_handout_semester']=h.get('semester')

    # Add handout-only courses that do not appear in the timetable, preserving them as unscheduled.
    existing={norm(c['course_code']) for c in courses}
    for h in hand:
        code=norm(h['course_code'])
        if code in existing: continue
        title=clean_text(h.get('title')) or code
        dept=code.split()[0] if ' ' in code else code[:3]
        c={'course_code':code,'title':title,'units':None,'department':dept,'semester':h.get('semester') or 'First Semester 2026-27','sections':[],
           'category':'OPEL_OR_OTHER','description':clean_text(h.get('description') or h.get('scope_objective')) or '',
           'prerequisites_raw':[h['prerequisites']] if h.get('prerequisites') else [],'source':{'document':'course handout','files':h.get('source_files',[])},
           'handout_verified':True,'handout_count':h.get('handout_count',1),'handout_source_files':h.get('source_files',[]),
           'instructor_handout':clean_text(h.get('instructor')),'description_handout':clean_text(h.get('description')),
           'scope_objective':clean_text(h.get('scope_objective')),'learning_outcomes':clean_text(h.get('learning_outcomes')),
           'prerequisites_handout':clean_text(h.get('prerequisites')),'attendance_policy':clean_text(h.get('attendance_policy')),
           'makeup_policy':clean_text(h.get('makeup_policy')),'evaluation_scheme_raw':clean_text(h.get('evaluation_scheme_raw')),
           'evaluation_components':h.get('evaluation_components',[]),'midsem':h.get('midsem'),'compre':h.get('compre'),'quiz':h.get('quiz'),'assignment':h.get('assignment'),'project':h.get('project'),'lab':h.get('lab'),
           'course_handout_date':h.get('date'),'course_handout_semester':h.get('semester')}
        courses.append(c)

    (OUT/'courses.json').write_text(json.dumps(courses,ensure_ascii=False,indent=2),encoding='utf-8')
    meta=json.loads((OUT/'metadata.json').read_text(encoding='utf-8')) if (OUT/'metadata.json').exists() else {}
    report_path = OUT/'handout_extraction_report.json'
    files_processed = json.loads(report_path.read_text(encoding='utf-8')).get('files_processed', len(hand)) if report_path.exists() else len(hand)
    meta.update({'handout_pdfs_processed':files_processed, 'unique_handout_course_codes':len(hand),'course_records_after_merge':len(courses),'course_handouts_are_source_of_course_specific_policies':True})
    (OUT/'metadata.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'Merged {len(hand)} handout records into {len(courses)} course records; verified matches={sum(1 for c in courses if c.get("handout_verified"))}.')

if __name__ == '__main__':
    main()
