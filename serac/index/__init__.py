"""
Database

Load in order to ensure models are always ready for generate_mapping
"""
from .database import get_current_db  # noqa
from .models import Action, File  # noqa
from . import index  # noqa
