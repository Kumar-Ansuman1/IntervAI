"""Compatibility entry point for the legacy Streamlit interface."""

from runpy import run_module


run_module("frontend.legacy_app", run_name="__main__")
