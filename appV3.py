"""Compatibility entry point for the adaptive Streamlit interface."""

from runpy import run_module


run_module("frontend.adaptive_app", run_name="__main__")
