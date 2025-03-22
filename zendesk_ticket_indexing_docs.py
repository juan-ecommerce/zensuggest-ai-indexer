import os
import asyncio
import logging
from typing import List, Dict, Any
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import urlparse

# Configure basic logging
logging.basicConfig(level=logging.INFO)

# Try to import optional dependencies
DEPENDENCIES_AVAILABLE = True
MISSING_DEPENDENCIES = []

# Try to import dotenv
try:
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("Successfully loaded environment variables from .env file")
except ImportError:
    logging.info("python-dotenv not available, assuming environment variables are already set")
    MISSING_DEPENDENCIES.append("python-dotenv")

# Try to import OpenAI
try:
    from openai import AsyncOpenAI
except ImportError:
    logging.warning("OpenAI package not available")
    DEPENDENCIES_AVAILABLE = False
    MISSING_DEPENDENCIES.append("openai")

# Try to import Supabase
try:
    from supabase import create_client, Client
except ImportError:
    logging.warning("Supabase package not available")
    DEPENDENCIES_AVAILABLE = False
    MISSING_DEPENDENCIES.append("supabase")

# Try to import ZendeskAPI
try:
    from zendesk_data_fetcher import ZendeskAPI, ZendeskConfig
except ImportError:
    logging.warning("ZendeskAPI module not available")
    DEPENDENCIES_AVAILABLE = False
    MISSING_DEPENDENCIES.append("zendesk_data_fetcher")

# Initialize clients only if dependencies are available
if DEPENDENCIES_AVAILABLE:
    # Initialize OpenAI and Supabase clients
    openai_client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    
    # Create Supabase client with direct initialization to avoid proxy issues
    try:
        # First try with standard initialization
        from supabase import create_client
        
        # Get Supabase credentials from environment
        supabase_url = os.getenv("SUPABASE_URL")
        supabase_key = os.getenv("SUPABASE_SERVICE_KEY")
        
        # Direct initialization of SyncClient to bypass proxy issues
        try:
            # Try standard client creation first
            supabase = create_client(supabase_url, supabase_key)
        except TypeError as e:
            if "unexpected keyword argument 'proxy'" in str(e):
                logging.info("Using direct Supabase client initialization to avoid proxy issues")
                # Import necessary components for direct initialization
                from supabase._sync.client import SyncClient
                from postgrest._sync.client import SyncQueryBuilder
                
                # Create client directly without using create_client function
                supabase = SyncClient(supabase_url, supabase_key, {})
                
                # Initialize the client's components manually if needed
                if not hasattr(supabase, 'table'):
                    logging.info("Initializing Supabase table interface manually")
                    schema = "public"
                    rest_url = f"{supabase_url}/rest/v1"
                    supabase.postgrest = SyncQueryBuilder(rest_url, {
                        "Authorization": f"Bearer {supabase_key}",
                        "apikey": supabase_key
                    }, schema)
                    
                    # Add table method
                    supabase.table = lambda table_name: supabase.postgrest.from_(table_name)
            else:
                # If it's a different error, re-raise it
                raise
    except Exception as e:
        logging.error(f"Failed to initialize Supabase client: {str(e)}")
        raise

    # Cache for Zendesk tickets
    _zendesk_tickets_cache = None

    @dataclass
    class ProcessedChunk:
        url: str
        chunk_number: int
        title: str
        summary: str
        content: str
        metadata: Dict[str, Any]
        embedding: List[float]

    def chunk_text(text: str, chunk_size: int = 5000) -> List[str]:
        """Split text into chunks, respecting code blocks and paragraphs."""
        chunks = []
        start = 0
        text_length = len(text)

        while start < text_length:
            # Calculate end position
            end = start + chunk_size

            # If we're at the end of the text, just take what's left
            if end >= text_length:
                chunks.append(text[start:].strip())
                break

            # Try to find a code block boundary first (```)
            chunk = text[start:end]
            code_block = chunk.rfind('```')
            
            # If we found a code block marker and it's not at the very beginning
            if code_block > 0 and code_block < end - 3:
                # Find the next code block marker after this one
                next_code_block = text.find('```', start + code_block + 3)
                
                # If there is a closing marker, include the entire code block
                if next_code_block > 0:
                    end = next_code_block + 3
                    chunks.append(text[start:end].strip())
                    start = end
                    continue
            
            # Try to find a paragraph boundary
            paragraph = chunk.rfind('\n\n')
            if paragraph > 0:
                end = start + paragraph
                chunks.append(text[start:end].strip())
                start = end
                continue
            
            # If we can't find a good boundary, just use the chunk size
            chunks.append(text[start:end].strip())
            start = end
            
        return chunks

    async def get_embedding(text: str) -> List[float]:
        """Get embedding vector from OpenAI."""
        if not text.strip():
            return []
        
        response = await openai_client.embeddings.create(
            input=text,
            model="text-embedding-ada-002"
        )
        return response.data[0].embedding

    async def process_chunk(chunk: str, chunk_number: int, ticket: Dict[str, Any]) -> ProcessedChunk:
        """Process a single chunk of text."""
        # Get embedding for the chunk
        embedding = await get_embedding(chunk)
        
        # Create a URL for the ticket
        subdomain = os.getenv("ZENDESK_SUBDOMAIN")
        url = f"https://{subdomain}.zendesk.com/agent/tickets/{ticket['id']}"
        
        # Create metadata
        metadata = {
            "ticket_id": ticket['id'],
            "created_at": ticket['created_at'],
            "updated_at": ticket['updated_at'],
            "status": ticket['status'],
            "requester": ticket['requester'],
            "assignee": ticket['assignee'],
            "tags": ticket['tags'],
            "source": "zendesk"
        }
        
        # Create a summary (just use the subject for now)
        summary = ticket['subject']
        
        return ProcessedChunk(
            url=url,
            chunk_number=chunk_number,
            title=ticket['subject'],
            summary=summary,
            content=chunk,
            metadata=metadata,
            embedding=embedding
        )

    async def insert_chunk(chunk: ProcessedChunk):
        """Insert a processed chunk into Supabase."""
        # Convert the chunk to a dictionary
        chunk_dict = {
            "url": chunk.url,
            "chunk_number": chunk.chunk_number,
            "title": chunk.title,
            "summary": chunk.summary,
            "content": chunk.content,
            "metadata": chunk.metadata,
            "embedding": chunk.embedding
        }
        
        # Insert into Supabase
        response = supabase.table("zendesk_tickets").insert(chunk_dict).execute()
        
        # Check for errors
        if hasattr(response, 'error') and response.error:
            logging.error(f"Error inserting chunk: {response.error}")
            raise Exception(f"Supabase error: {response.error}")

    async def process_and_store_ticket(ticket: Dict[str, Any]):
        """Process a ticket and store its chunks in parallel."""
        # Get chunks from the ticket
        chunks = chunk_text(ticket['comments'])
        logging.info(f"Ticket #{ticket['id']} split into {len(chunks)} chunks")
        
        # Process chunks in parallel
        tasks = [
            process_chunk(chunk, i, ticket) 
            for i, chunk in enumerate(chunks)
        ]
        processed_chunks = await asyncio.gather(*tasks)
        logging.info(f"Processed {len(processed_chunks)} chunks for ticket #{ticket['id']}")
        
        # Store chunks in parallel
        insert_tasks = [
            insert_chunk(chunk) 
            for chunk in processed_chunks
        ]
        await asyncio.gather(*insert_tasks)
        logging.info(f"Stored {len(processed_chunks)} chunks in Supabase for ticket #{ticket['id']}")

async def main():
    """Main function that runs the Zendesk ticket indexing process."""
    import logging
    logging.info("Starting Zendesk ticket indexing process")
    
    # Check if all dependencies are available
    if not DEPENDENCIES_AVAILABLE:
        logging.error(f"Missing dependencies: {', '.join(MISSING_DEPENDENCIES)}")
        logging.error("Cannot run indexing process without required dependencies")
        logging.error("Please ensure all dependencies are installed in requirements.txt")
        return
    
    # Log environment variables (without values)
    env_vars = [
        "SUPABASE_URL", "OPENAI_API_KEY", "ZENDESK_SUBDOMAIN", 
        "ZENDESK_EMAIL", "ZENDESK_API_TOKEN", "LLM_MODEL"
    ]
    for var in env_vars:
        logging.info(f"{var} exists: {'Yes' if os.getenv(var) else 'No'}")
    
    try:
        config = ZendeskConfig.from_env()
        zendesk = ZendeskAPI(config)
        tickets = zendesk.get_ticket_details()
        
        logging.info(f"Found {len(tickets)} tickets to process")
        
        # Log the URLs of all tickets that will be processed
        subdomain = os.getenv("ZENDESK_SUBDOMAIN")
        logging.info("Tickets to be processed:")
        for ticket in tickets:
            ticket_url = f"https://{subdomain}.zendesk.com/agent/tickets/{ticket['id']}"
            logging.info(f"- Ticket #{ticket['id']}: {ticket['subject']} ({ticket_url})")
        
        # Process tickets with progress tracking
        processed_count = 0
        for ticket in tickets:
            ticket_url = f"https://{subdomain}.zendesk.com/agent/tickets/{ticket['id']}"
            logging.info(f"Processing ticket #{ticket['id']}: {ticket['subject']}")
            
            await process_and_store_ticket(ticket)
            
            processed_count += 1
            logging.info(f"Completed processing ticket #{ticket['id']} ({processed_count}/{len(tickets)})")
        
        logging.info(f"Zendesk ticket indexing completed. Processed {processed_count} tickets.")
    except Exception as e:
        logging.error(f"Error during Zendesk ticket indexing: {str(e)}")
        import traceback
        logging.error(f"Traceback: {traceback.format_exc()}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
