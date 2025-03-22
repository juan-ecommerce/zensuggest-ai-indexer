import sys
import importlib
import logging
import os

# Configure logging
logging.basicConfig(level=logging.INFO)

def check_module_version(module_name):
    """Check the version of an installed module."""
    try:
        module = importlib.import_module(module_name)
        version = getattr(module, "__version__", "Unknown")
        logging.info(f"Module {module_name} version: {version}")
        return version
    except ImportError:
        logging.error(f"Module {module_name} is not installed")
        return None

def check_supabase_internals():
    """Check the internal structure of the supabase module."""
    try:
        from supabase._sync.client import SyncClient
        logging.info("SyncClient class is available")
        
        # Check if SyncClient.__init__ accepts proxy parameter
        import inspect
        sig = inspect.signature(SyncClient.__init__)
        params = list(sig.parameters.keys())
        logging.info(f"SyncClient.__init__ parameters: {params}")
        
        # Check httpx version
        try:
            import httpx
            logging.info(f"httpx version: {httpx.__version__}")
            
            # Check if httpx.Client accepts proxy parameter
            sig = inspect.signature(httpx.Client.__init__)
            has_proxy = 'proxy' in sig.parameters
            logging.info(f"httpx.Client.__init__ has proxy parameter: {has_proxy}")
        except ImportError:
            logging.error("httpx is not installed")
        
        return True
    except (ImportError, AttributeError) as e:
        logging.error(f"Error checking supabase internals: {e}")
        return False

def main():
    """Verify all dependencies and their versions."""
    logging.info("========== VERIFYING DEPENDENCIES ==========")
    
    # Log Python version and environment
    logging.info(f"Python version: {sys.version}")
    logging.info(f"Current directory: {os.getcwd()}")
    
    # Check key modules
    modules = ["requests", "openai", "supabase", "dotenv", "httpx"]
    for module in modules:
        check_module_version(module)
    
    # Check supabase internals
    check_supabase_internals()
    
    logging.info("========== DEPENDENCY VERIFICATION COMPLETE ==========")

if __name__ == "__main__":
    main()
