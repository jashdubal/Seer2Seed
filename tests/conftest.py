"""
Configuration file for pytest that ensures the virtual environment is used.
"""
import os
import sys
import subprocess
import pytest

@pytest.hookimpl(trylast=True)
def pytest_configure(config):
    """
    Pytest hook that runs before test collection.
    This ensures we're using the virtual environment.
    """
    # Check if we're already running in the virtual environment
    venv_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.venv'))
    
    # Determine if we're in the virtual environment by checking if its site-packages is in sys.path
    if sys.platform == 'win32':
        site_packages = os.path.join(venv_path, 'Lib', 'site-packages')
    else:
        python_version = f"python{sys.version_info.major}.{sys.version_info.minor}"
        site_packages = os.path.join(venv_path, 'lib', python_version, 'site-packages')
    
    in_venv = any(p.startswith(venv_path) for p in sys.path)
    
    if not in_venv and os.path.exists(site_packages):
        print(f"Not running in virtual environment. Adding {site_packages} to path.")
        sys.path.insert(0, site_packages)
        
        # Add any other paths from the virtual environment that might be needed
        if sys.platform == 'win32':
            venv_scripts = os.path.join(venv_path, 'Scripts')
            if os.path.exists(venv_scripts) and venv_scripts not in sys.path:
                sys.path.insert(0, venv_scripts)
        else:
            venv_bin = os.path.join(venv_path, 'bin')
            if os.path.exists(venv_bin) and venv_bin not in sys.path:
                sys.path.insert(0, venv_bin)
    
    # Always ensure the project root is in the path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Removed the pytest_collect_file hook that was filtering out test_seer.py 