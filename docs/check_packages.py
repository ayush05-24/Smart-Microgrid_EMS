import importlib

packages = [
    'torch',
    'stable_baselines3',
    'scipy',
    'xgboost',
    'statsmodels',
    'pyomo',
    'cvxpy',
    'gurobipy',
    'pulp',
    'ortools',
    'pandas',
    'numpy',
    'sklearn',
    'matplotlib'
]

for p in packages:
    try:
        mod = importlib.import_module(p)
        print(f"{p}: Available (version {getattr(mod, '__version__', 'unknown')})")
    except ImportError:
        print(f"{p}: NOT Available")
