import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

import pymupdf

doc = pymupdf.open(r'd:\satish Developnent\cimet-hackthon\QA-Automation-Handout.pdf')
for i in range(len(doc)):
    print(f'=== PAGE {i+1} ===')
    print(doc[i].get_text())
    print()
