import sys, json
sys.path.insert(0, 'src')
from tools.student_submission_gui.experiments import load_experiments
print('experiments:', [(e['id'], e['name']) for e in load_experiments()])
from tools.auto_grading.config import AutoGradingConfig
p = AutoGradingConfig().get_rubric_path('2026F-PT-NEV-00')
print('rubric path:', p, 'exists:', p.exists())
r = json.load(open(p, encoding='utf-8'))
print('rubric:', r['experiment_name'], '| categories:', len(r['categories']),
      '| total pts:', sum(c['points'] for c in r['categories']))
