from __future__ import annotations

# Standard Library
import os

# Django
import django

# Patches in values so Django functions can be accessed outside of the Django server
os.environ["DJANGO_SETTINGS_MODULE"] = "MyWaifuLovesMe.settings"
django.setup()
