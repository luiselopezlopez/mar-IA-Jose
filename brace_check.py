from pathlib import Path
text = Path(r'd:\repos\mar-IA-Jose\static\js\app.js').read_text(encoding='utf-8')
count = 0
import sys
line = 1
col = 0
for ch in text:
    col += 1
    if ch == '\n':
        line += 1
        col = 0
        continue
    if ch == '{':
        count += 1
    elif ch == '}':
        count -= 1
    if count < 0:
        print('negative balance at line', line, 'col', col)
        sys.exit(0)
print('final balance', count)
