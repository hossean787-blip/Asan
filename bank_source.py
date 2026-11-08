# -*- coding: utf-8 -*-
"""PUBLIC DEMO QUESTIONS ONLY. NOT FOR REAL EMPLOYMENT DECISIONS.

Replace this module and bank_expansion_v21.py on a private company server
with a professionally reviewed, secret bank. Never commit real answer keys.
"""
import json
from pathlib import Path

LEVELS=['easy','easy','medium','medium','hard','hard']

def _fixture(cid,category,subtopic,ordinal,difficulty):
    # Computational fixture unique by category/question, not a validated assessment item.
    n=int(cid[-2:]); base=n*17+ordinal*11
    if difficulty=='easy':
        left,right=base,ordinal+4; result=left+right
        stem=f'سؤال نمونه شماره {ordinal} از {category}: جمع دو مبلغ فرضی {left} و {right} ریال چند ریال است؟'
        rationale=f'جمع دو مبلغ فرضی {left}+{right} برابر {result} است. صرفاً برای آزمون فنی.'
    elif difficulty=='medium':
        left,right=base+120,ordinal*7; result=left-right
        stem=f'سؤال نمونه شماره {ordinal} از {category}: مبلغ {left} ریال پس از کسر {right} ریال چقدر است؟'
        rationale=f'مبلغ باقی‌مانده {left}−{right}={result} است. صرفاً برای آزمون فنی.'
    else:
        left,right,extra=base+150,ordinal*3,ordinal+2; result=left+right-extra
        stem=f'سؤال نمونه شماره {ordinal} از {category}: مانده فرضی {left} ریال با افزودن {right} و کسر {extra} ریال چقدر می‌شود؟'
        rationale=f'نتیجه {left}+{right}−{extra}={result} است. صرفاً برای آزمون فنی.'
    correct=str(result)
    vals=[str(result+7),str(result-5),str(result+13),correct]
    # Deterministic varied correct option, all 4 distinct
    shift=(n+ordinal)%4
    options=vals[shift:]+vals[:shift]
    return dict(id=f'{cid}-{ordinal:02d}',category_id=cid,category=category,
        subtopic=subtopic,difficulty=difficulty,skill_type='calculation',
        stem=stem,options=options,correct_index=options.index(correct),
        rationale=rationale,source_reference='داده ساختگی آزمایشی؛ غیرقابل استفاده در استخدام',
        review_status='draft',reviewer_id=None,last_verified_on=None,
        legal_effective_from='',legal_effective_to='',version=1)

def all_questions():
    spec=json.loads((Path(__file__).parent/'docs'/'target_plan_3000.json').read_text(encoding='utf-8'))
    out=[]
    for category in spec['categories']:
        for i,difficulty in enumerate(LEVELS,1):
            out.append(_fixture(category['id'],category['name'],category['subtopics'][(i-1)%len(category['subtopics'])],i,difficulty))
    return out