"""Legt den Projektordner auf den Importpfad, damit die Tests die
Flugskripte importieren können."""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
