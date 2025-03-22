import datetime
import logging
import azure.functions as func
import os
import sys
import importlib.util
import traceback

# Add the current directory to sys.path first, then the parent directory
dir_path = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, dir_path)  # First check in the current directory
parent_dir = os.path.abspath(os.path.join(dir_path, os.pardir))
sys.path.insert(1, parent_dir)  # Then check in the parent directory

# Add .python_packages directory to sys.path if it exists
python_packages_dir = os.path.join(dir_path, ".python_packages", "lib", "site-packages")
if os.path.exists(python_packages_dir):
    sys.path.insert(0, python_packages_dir)
    logging.info(f"Added .python_packages directory to sys.path: {python_packages_dir}")

def check_module_exists(module_name):
    """Check if a module can be imported."""
    return importlib.util.find_spec(module_name) is not None

def main(mytimer: func.TimerRequest) -> None:
    """
    Azure Function entry point that runs on a timer trigger.
    This function indexes Zendesk tickets into Supabase for RAG.
    """
    utc_timestamp = datetime.datetime.utcnow().replace(
        tzinfo=datetime.timezone.utc).isoformat()
    
    if mytimer.past_due:
        logging.info('The timer is past due!')
    
    logging.info('========== ZENDESK TICKET INDEXER STARTED ==========')
    logging.info('Python timer trigger function started at %s', utc_timestamp)
    
    # Log environment variables (without sensitive values)
    logging.info('========== ENVIRONMENT VARIABLES ==========')
    env_vars = [
        "SUPABASE_URL", "SUPABASE_SERVICE_KEY", "OPENAI_API_KEY", "ZENDESK_SUBDOMAIN", 
        "ZENDESK_EMAIL", "ZENDESK_API_TOKEN", "LLM_MODEL"
    ]
    for var in env_vars:
        logging.info(f'{var} exists: {"Yes" if os.getenv(var) else "No"}')
    
    # Log system information
    logging.info('========== SYSTEM INFORMATION ==========')
    logging.info(f'Python version: {sys.version}')
    logging.info(f'Current directory: {os.getcwd()}')
    logging.info(f'Function directory: {dir_path}')
    logging.info(f'Parent directory: {parent_dir}')
    logging.info(f'sys.path: {sys.path}')
    
    # Check for required dependencies
    logging.info('========== CHECKING DEPENDENCIES ==========')
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
        logging.error("Please ensure all dependencies are installed in requirements.txt")
        
    # Import and run the ticket indexing functionality
    try:
        logging.info('========== STARTING TICKET INDEXING ==========')
        
        # Try to manually import the required modules to see detailed errors
        try:
            logging.info("Attempting to import requests...")
            import requests
            logging.info("Successfully imported requests")
        except ImportError as e:
            logging.error(f"Failed to import requests: {str(e)}")
            
        try:
            logging.info("Attempting to import openai...")
            import openai
            logging.info("Successfully imported openai")
        except ImportError as e:
            logging.error(f"Failed to import openai: {str(e)}")
            
        try:
            logging.info("Attempting to import supabase...")
            from supabase import create_client
            logging.info("Successfully imported supabase")
        except ImportError as e:
            logging.error(f"Failed to import supabase: {str(e)}")
        
        # Now try to import the modules
        logging.info("Importing zendesk_data_fetcher...")
        import zendesk_data_fetcher
        logging.info("Successfully imported zendesk_data_fetcher")
        
        logging.info("Importing zendesk_ticket_indexing_docs...")
        import zendesk_ticket_indexing_docs
        logging.info("Successfully imported zendesk_ticket_indexing_docs")
        
        # Run the indexing function
        import asyncio
        logging.info("Running zendesk_ticket_indexing_docs.main()...")
        asyncio.run(zendesk_ticket_indexing_docs.main())
        logging.info('========== TICKET INDEXING COMPLETED SUCCESSFULLY ==========')
    except Exception as e:
        logging.error(f'Error during ticket indexing: {str(e)}')
        logging.error(f'Traceback: {traceback.format_exc()}')
    
    logging.info('========== ZENDESK TICKET INDEXER COMPLETED ==========')
    logging.info('Python timer trigger function completed at %s', 
                 datetime.datetime.utcnow().replace(
                     tzinfo=datetime.timezone.utc).isoformat())
