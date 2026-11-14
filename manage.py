#!/usr/bin/env python
"""Django's command-line utility for administrative tasks."""
import os
import sys


def main():
    """Run administrative tasks."""
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "smart_chili.settings")
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Django belum terinstall. Jalankan: pip install -r requirements.txt\n"
            "Atau gunakan: python standalone_server.py untuk menjalankan server tanpa install tambahan."
        ) from exc
    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
