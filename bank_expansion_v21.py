# -*- coding: utf-8 -*-
"""PUBLIC DEMO EXTENSION ONLY. Real bank must be private on server."""
import json
from pathlib import Path
from bank_source import _fixture

def extra_questions():
    spec=json.loads((Path(__file__).parent/'docs'/'target_plan_3000.json').read_text(encoding='utf-8'))
    out=[]
    for c in spec['categories']:
        for i,level in ((7,'medium'),(8,'hard')):
            q=_fixture(c['id'],c['name'],c['subtopics'][(i-1)%len(c['subtopics'])],i,level)
            q['id']=f"{c['id']}-EX{i-6:02d}"
            out.append(q)
    return out