import os

def resolve_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        
    new_lines = []
    state = 'normal'
    
    for line in lines:
        if line.startswith('<<<<<<< HEAD'):
            state = 'in_head'
            continue
        elif line.startswith('======='):
            state = 'in_other'
            continue
        elif line.startswith('>>>>>>>'):
            state = 'normal'
            continue
            
        if state == 'normal' or state == 'in_head':
            new_lines.append(line)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.writelines(new_lines)
    print(f"Resolved {filepath}")

resolve_file('main.py')
resolve_file('templates/index.html')
resolve_file('static/app.js')
resolve_file('static/styles.css')
