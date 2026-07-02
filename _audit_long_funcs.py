import ast, os
results = []
for root, _, files in os.walk('src/tools'):
    for f in files:
        if not f.endswith('.py'):
            continue
        p = os.path.join(root, f)
        try:
            src = open(p, encoding='utf-8').read()
            tree = ast.parse(src)
        except Exception:
            continue
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                start = node.lineno
                end = getattr(node, 'end_lineno', start)
                length = end - start + 1
                if length > 100:
                    norm = p.replace(os.sep, '/')
                    results.append((length, norm, node.name, start, end))
results.sort(reverse=True)
for r in results[:40]:
    print(r[0], 'lines', r[1], '::', r[2], '(', r[3], '-', r[4], ')')
