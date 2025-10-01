import subprocess
import sys
import os

def run_tests():
    """Runs all tests in the tests directory."""
    
    # Get the project root directory
    project_root = os.path.dirname(os.path.abspath(__file__))
    
    # Add project root to PYTHONPATH for the subprocess
    env = os.environ.copy()
    env['PYTHONPATH'] = project_root + (os.pathsep + env.get('PYTHONPATH', ''))
    
    try:
        # Run pytest on the entire tests directory
        result = subprocess.run(
            ["pytest", "tests/", "-v"], 
            check=True, 
            cwd=project_root,
            env=env
        )
        print("✅ All tests passed successfully!")
    except subprocess.CalledProcessError as e:
        print(f"❌ Tests failed with exit code {e.returncode}")
        sys.exit(1)
    except FileNotFoundError:
        print("❌ pytest not found. Please install pytest: pip install pytest")
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
