"""
Helper script to install dependencies for Azure Functions.
This script installs dependencies to the .python_packages directory,
which is where Azure Functions looks for packages when running in the cloud.
"""
import os
import sys
import subprocess
import logging
import importlib.util

# Configure logging
logging.basicConfig(level=logging.INFO)

def check_module_exists(module_name):
    """Check if a module can be imported."""
    return importlib.util.find_spec(module_name) is not None

def install_dependencies():
    """Install dependencies to .python_packages directory."""
    # Get the directory where this script is located
    dir_path = os.path.dirname(os.path.realpath(__file__))
    
    # Create .python_packages directory if it doesn't exist
    python_packages_dir = os.path.join(dir_path, ".python_packages", "lib", "site-packages")
    os.makedirs(python_packages_dir, exist_ok=True)
    
    # Get the path to the requirements.txt file
    requirements_path = os.path.join(dir_path, "requirements.txt")
    
    # Check if requirements.txt exists
    if not os.path.exists(requirements_path):
        logging.error(f"requirements.txt not found at {requirements_path}")
        return False
    
    # Install dependencies to .python_packages directory
    logging.info(f"Installing dependencies from {requirements_path} to {python_packages_dir}")
    try:
        subprocess.check_call([
            sys.executable, 
            "-m", 
            "pip", 
            "install", 
            "-r", 
            requirements_path,
            "--target", 
            python_packages_dir
        ])
        logging.info("Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        logging.error(f"Error installing dependencies: {e}")
        return False

def verify_dependencies():
    """Verify that required dependencies are installed."""
    required_modules = ["requests", "openai", "supabase", "dotenv"]
    missing_modules = []
    
    for module in required_modules:
        if check_module_exists(module):
            logging.info(f"Module {module} is available")
        else:
            logging.error(f"Module {module} is NOT available")
            missing_modules.append(module)
    
    if missing_modules:
        logging.error(f"Missing required modules: {', '.join(missing_modules)}")
        return False
    
    logging.info("All required dependencies are installed")
    return True

def main():
    """Main function."""
    logging.info("Starting dependency installation")
    
    # Install dependencies
    if install_dependencies():
        # Verify dependencies
        if verify_dependencies():
            logging.info("Dependency installation completed successfully")
        else:
            logging.error("Dependency verification failed")
    else:
        logging.error("Dependency installation failed")

if __name__ == "__main__":
    main()
