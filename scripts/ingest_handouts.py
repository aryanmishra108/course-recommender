from __future__ import annotations
import json,re,sys,zipfile,tempfile,shutil
from pathlib import Path
import pymupdf

ROOT=Path(__file__).resolve().parents[1]
HANDOUTS=ROOT/'data'/'raw'/'handouts'
OUT=ROOT/'data'/'processed'
OUT.mkdir(exist_ok=True)

CODE_RE=re.compile(r'\b[A-Z]{2,7}\s+[FGU]\s*\d{3,4}[A-Z0-9-]*\b')

def clean(s):
    s=str(s or '').replace('\u200b','').replace('\ufeff','')
    s=re.sub(r'\s+',' ',s).strip()
    return s

def normalize_code(c):
    c=clean(c).upper().replace('–','-')
    c=re.sub(r'([A-Z])\s+(\d{3,4})', r'\1\2', c)
    c=c.replace('GSF','GS F').replace('G S F','GS F')
    # Handle slash-separated prefixes sharing one suffix, e.g. CS/SS G 527.
    m=re.fullmatch(r'([A-Z]{2,7}(?:/[A-Z]{2,7})*)\s+([FGU]\d{3,4}[A-Z0-9-]*)', c)
    if m:
        return [f'{p} {m.group(2)}' for p in m.group(1).split('/')]
    return [c] if re.fullmatch(r'[A-Z]{2,7}\s+[FGU]\d{3,4}[A-Z0-9-]*',c) else []

def extract_text(path):
    doc=pymupdf.open(path)
    text='\n'.join(page.get_text('text') for page in doc)
    if len(text.strip())<100:
        # OCR only for image/scanned handouts.
        import pytesseract
        from PIL import Image
        pages=[]
        for page in doc:
            pix=page.get_pixmap(matrix=pymupdf.Matrix(2,2), alpha=False)
            img=Image.frombytes('RGB',[pix.width,pix.height],pix.samples)
            pages.append(pytesseract.image_to_string(img))
        text='\n'.join(pages)
    return text

def first_match(patterns,text,limit=1):
    for p in patterns:
        m=re.search(p,text,re.I|re.S)
        if m:
            return clean(m.group(1))[:limit]
    return None

def context(text, patterns, radius=450, max_chars=1200):
    for p in patterns:
        m=re.search(p,text,re.I)
        if m:
            s=max(0,m.start()-radius); e=min(len(text),m.end()+radius)
            return clean(text[s:e])[:max_chars]
    return None

def section(text, start_patterns, end_patterns, max_chars=7000):
    start=None
    for p in start_patterns:
        m=re.search(p,text,re.I)
        if m: start=m.end(); break
    if start is None:return ''
    end=len(text)
    for p in end_patterns:
        m=re.search(p,text[start:],re.I)
        if m: end=min(end,start+m.start())
    return clean(text[start:end])[:max_chars]

def bool_field(text, patterns):
    return bool(any(re.search(p,text,re.I) for p in patterns))

def parse_eval(text):
    sec=section(text,[r'\b7\.\s*Evaluation Scheme',r'\bEvaluation Scheme',r'\bEvaluation\s*Scheme',r'\bGrading Scheme'],[r'\b8\.\s*',r'\b9\.\s*',r'\bMake[- ]?up Policy',r'\bAttendance Policy'],6000)
    if not sec:
        sec=context(text,[r'\bEvaluation Scheme',r'\bGrading Scheme'],600,2500) or ''
    items=[]
    # Capture lines/phrases with percentages and nearby component names.
    for m in re.finditer(r'([^\n]{0,180}?)(\d{1,3})\s*%',sec):
        comp=clean(m.group(1)); wt=int(m.group(2))
        if comp and wt<=100:
            items.append({'component':comp[-180:], 'weightage_percent':wt})
    # Deduplicate preserving order.
    seen=set(); out=[]
    for x in items:
        k=(x['component'],x['weightage_percent'])
        if k not in seen:seen.add(k);out.append(x)
    return sec,out

def parse_file(path):
    text=extract_text(path).replace('\u200b','').replace('\ufeff','')
    codes=[]
    for m in CODE_RE.finditer(text[:12000]):
        for c in normalize_code(m.group(0)):
            if c not in codes: codes.append(c)
    # Prefer only the course-number line so prerequisite/reference codes are not mistaken for aliases.
    code=first_match([r'Course\s+(?:No\.?|Number|Code)\s*[:.]?\s*([^\n]+)',r'CourseNo\.?\s*[:.]?\s*([^\n]+)',r'Course\s+Number\s*&\s*Title\s*[:.]?\s*([^\n]+)'],text,300)
    aliases=[]
    if code:
        for raw in CODE_RE.findall(code):
            for c in normalize_code(raw):
                if c not in aliases: aliases.append(c)
        # Special compact forms such as GSF243.
        for raw in re.findall(r'\b[A-Z]{2,7}\s*[FGU]\s*\d{3,4}[A-Z0-9-]*\b',code,re.I):
            for c in normalize_code(raw):
                if c not in aliases: aliases.append(c)
        # Shared suffix: CS/SS G527.
        m=re.search(r'([A-Z]{2,7}(?:\s*/\s*[A-Z]{2,7})+)\s+([FGU]\s*\d{3,4}[A-Z0-9-]*)',code,re.I)
        if m:
            suffix=re.sub(r'\s+','',m.group(2)).upper()
            for pfx in re.split(r'\s*/\s*',m.group(1)):
                c=f'{pfx.strip().upper()} {suffix}'
                if c not in aliases: aliases.append(c)
    if not aliases:
        # Compact forms such as GSF243 occasionally omit the separator.
        m=re.search(r'\b([A-Z]{2,7})([FGU])\s*(\d{3,4})[A-Z0-9-]*\b',code or '',re.I)
        if m:
            aliases=[f'{m.group(1).upper()} {m.group(2).upper()}{m.group(3)}']
        else:
            aliases=codes[:3]
    # Filename is a reliable fallback for the common numbered handout naming convention.
    if not aliases:
        fm=re.match(r'\d+_([A-Z]{2,7})_([FGU]\d{3,4}[A-Z0-9-]*)',path.stem,re.I)
        if fm: aliases=[f'{fm.group(1).upper()} {fm.group(2).upper()}']
    # If the filename identifies the course and the handout text contains a shared-prefix code, preserve it too.
    fm=re.match(r'\d+_([A-Z]{2,7})_([FGU]\d{3,4}[A-Z0-9-]*)',path.stem,re.I)
    if fm:
        fc=f'{fm.group(1).upper()} {fm.group(2).upper()}'
        if fc not in aliases: aliases.insert(0,fc)
    title=first_match([r'Course\s+Title\s*[:.]?\s*([^\n]+)',r'COURSE TITLE\s*[:.]?\s*([^\n]+)',r'Title\s+of\s+the\s+Course\s*[:.]?\s*([^\n]+)',r'Course\s+Name\s*[:.]?\s*([^\n]+)',r'Name\s+of\s+the\s+course\s*[:.]?\s*([^\n]+)',r'CourseTitle\s*[:.]?\s*([^\n]+)'],text,300)
    if not title:
        m=re.search(r'Course\s+Number\s*&\s*Title\s*[:.]?\s*([^\n]+)',text,re.I)
        if m:
            line=clean(m.group(1))
            # Strip one or more course-code aliases from the beginning.
            line=re.sub(r'^[A-Z]{2,7}(?:\s*/\s*[A-Z]{2,7})*\s+[FGU]\s*\d{3,4}[A-Z0-9-]*\s*','',line,flags=re.I)
            title=line or None
    instructor=first_match([r'Instructor[- ]in[- ]charge\s*[:.]?\s*([^\n]+)',r'Instructor\s+In\s+Charge\s*[:.]?\s*([^\n]+)',r'Instructor-in-Charge\s*[:.]?\s*([^\n]+)'],text,500)
    date=first_match([r'(?:Dated|Date)\s*[:.]?\s*([^\n]+)',r'(?:Dated|Date)\s+([^\n]+)'],text,100)
    semester=first_match([r'(First|Second|Summer)\s+Semester\s+20\d{2}[-–](?:20)?\d{2}',r'(First|Second|Summer)\s+Semester\s+20\d{2}[-–](?:20)?\d{2}'],text,100)
    if semester:
        m=re.search(r'((?:First|Second|Summer)\s+Semester\s+20\d{2}[-–](?:20)?\d{2})',text,re.I); semester=clean(m.group(1)) if m else semester
    desc=section(text,[r'\b1\.\s*Course\s+description\s*:?',r'\b1\.\s*Course\s+Description\s*:?',r'Course\s+Description\s*:'],[r'\b2\.\s*Scope',r'\b2\.\s*Scope\s*&\s*Objective',r'\b3\.\s*(?:Learning|Course Learning)'],4500)
    scope=section(text,[r'\b2\.\s*Scope\s*(?:&|and)?\s*Objective\s*(?:of\s+the\s+course)?\s*:?',r'\bScope\s+and\s+Objective\s*(?:of\s+the\s+course)?\s*:?',r'\bScope\s*&\s*Objective\s*:'],[r'\b3\.\s*(?:Course\s+)?Learning\s+Outcomes?',r'\b4\.\s*(?:Text|Course)'],4500)
    outcomes=section(text,[r'\b3\.\s*(?:Course\s+)?Learning\s+Outcomes?\s*:?',r'\bLearning\s+Outcomes\s*:'],[r'\b4\.\s*(?:Text|Reference)',r'\b5\.\s*(?:Course|Method)',r'\bEvaluation'],5000)
    prereq=first_match([r'Prerequisites?\s*[:.]\s*([^\n]+)',r'Pre[- ]requisites?\s*[:.]\s*([^\n]+)'],text,1000)
    eval_sec,eval_items=parse_eval(text)
    attendance=context(text,[r'Attendance\s+Policy',r'attendance\s+(?:is|required|will)',r'minimum\s+attendance'],500,1600)
    makeup=context(text,[r'Make[- ]?up\s+Policy',r'Makeup\s+Policy',r'Make[- ]?up'],500,1800)
    midsem=bool_field(text,[r'\bMid[- ]?Sem(?:ester)?(?:\s+(?:Test|Exam|Examination))?\b',r'\bMid[- ]Term\b'])
    compre=bool_field(text,[r'\bComprehensive\b',r'\bCompre\b'])
    quiz=bool_field(text,[r'\bQuiz(?:zes)?\b'])
    assignment=bool_field(text,[r'\bAssignments?\b'])
    project=bool_field(text,[r'\b(?:Course\s+)?Project\b',r'\bProject\s+Work\b'])
    lab=bool_field(text,[r'\bLab(?:oratory)?\b',r'\bPractical\b'])
    evaluation_lower=eval_sec.lower()
    # More reliable component detection from evaluation section when available.
    return {
        'source_file':path.name,
        'source_path':str(Path('handouts') / path.name),
        'course_codes':aliases,
        'course_code_raw':code,
        'title':title,
        'instructor':instructor,
        'date':date,
        'semester':semester,
        'description':desc,
        'scope_objective':scope,
        'learning_outcomes':outcomes,
        'prerequisites':prereq,
        'evaluation_scheme_raw':eval_sec,
        'evaluation_components':eval_items,
        'attendance_policy':attendance,
        'makeup_policy':makeup,
        'midsem':midsem,
        'compre':compre,
        'quiz':quiz,
        'assignment':assignment,
        'project':project,
        'lab':lab,
        'text_length':len(text),
        'ocr_used':len(text.strip())<100,
    }

def merge_records(records):
    merged={}
    for r in records:
        for code in r['course_codes']:
            x=merged.setdefault(code,{'course_code':code,'handout_files':[],'aliases':[],'records':[]})
            x['handout_files'].append(r['source_file'])
            x['records'].append(r)
    out=[]
    for code,x in merged.items():
        rs=x['records']
        # Prefer current 2026-27 records, then latest-looking/longest text.
        rs=sorted(rs,key=lambda r: ('2026-27' not in (r.get('semester') or '') and '2026–27' not in (r.get('semester') or ''), -(r.get('text_length') or 0)))
        best=rs[0]
        fields=['title','instructor','date','semester','description','scope_objective','learning_outcomes','prerequisites','attendance_policy','makeup_policy']
        x['handout_count']=len(rs)
        x['duplicates'] = len(rs)>1
        for f in fields:
            vals=[r.get(f) for r in rs if r.get(f)]
            x[f]=vals[0] if vals else None
        # Preserve evidence across duplicates.
        x['midsem']=any(r.get('midsem') for r in rs)
        x['compre']=any(r.get('compre') for r in rs)
        for f in ['quiz','assignment','project','lab']:
            x[f]=any(r.get(f) for r in rs)
        comps=[]
        for r in rs:
            comps.extend(r.get('evaluation_components') or [])
        seen=set(); x['evaluation_components']=[]
        for c in comps:
            k=(c.get('component'),c.get('weightage_percent'))
            if k not in seen:seen.add(k);x['evaluation_components'].append(c)
        x['evaluation_scheme_raw']=next((r.get('evaluation_scheme_raw') for r in rs if r.get('evaluation_scheme_raw')),None)
        x['source_files']=x.pop('handout_files')
        x.pop('records',None)
        out.append(x)
    return sorted(out,key=lambda x:x['course_code'])

def main(input_path=None):
    """Extract Part-II handouts from a directory or ZIP archive."""
    input_path = Path(input_path) if input_path else HANDOUTS
    temp_dir = None
    if input_path.is_file() and input_path.suffix.lower() == '.zip':
        temp_dir = Path(tempfile.mkdtemp(prefix='bits_handouts_'))
        with zipfile.ZipFile(input_path) as z:
            z.extractall(temp_dir)
        files = sorted(temp_dir.rglob('*.pdf'))
    elif input_path.is_dir():
        files = sorted(input_path.rglob('*.pdf'))
    else:
        files = []

    records=[]; errors=[]
    try:
        for i,p in enumerate(files,1):
            try:
                records.append(parse_file(p))
            except Exception as e:
                errors.append({'file':str(p.name),'error':repr(e)})
            if i%50==0: print(f'Processed {i}/{len(files)}')
        merged=merge_records(records)
        (OUT/'handouts.json').write_text(json.dumps(merged,ensure_ascii=False,indent=2),encoding='utf-8')
        (OUT/'handout_extraction_report.json').write_text(json.dumps({'files_found':len(files),'files_processed':len(records),'unique_course_codes':len(merged),'errors':errors,'ocr_files':[r['source_file'] for r in records if r.get('ocr_used')]},ensure_ascii=False,indent=2),encoding='utf-8')
        print(f'Processed {len(records)} PDFs -> {len(merged)} unique course-code records; errors={len(errors)}')
        if errors: print(errors[:10])
        return len(records), len(merged), errors
    finally:
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

if __name__=='__main__':main()
