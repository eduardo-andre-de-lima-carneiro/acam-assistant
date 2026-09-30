"""WSGI entry point for production servers: ``gunicorn acam.web.wsgi:app``.

Configuration comes from the environment (``ACAM_HOME``,
``ACAM_ALLOW_SIGNUP``, ``ACAM_SECURE_COOKIES``, ``ANTHROPIC_API_KEY``…).
"""

from . import create_app

app = create_app()
