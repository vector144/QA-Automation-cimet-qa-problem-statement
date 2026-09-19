import re
from pathlib import Path

content = Path(r"C:\Users\satis\.gemini\antigravity-ide\brain\564aeeb2-54bf-47a3-97a9-c2cee60db7d2\.system_generated\steps\492\content.md").read_text(encoding="utf-8")
matches = re.findall(r'href=[\"\'](/[^/\"\']+/(?:design-md)?[^\"\']*)[\"\']', content)
unique = sorted(set(matches))
for u in unique:
    if "design-md" in u:
        print(u)
