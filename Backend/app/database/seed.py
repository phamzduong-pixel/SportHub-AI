from .demo_seed import seed_demo_db

# Backward-compatible import for existing callers.
seed_db = seed_demo_db

__all__ = ['seed_db', 'seed_demo_db']
