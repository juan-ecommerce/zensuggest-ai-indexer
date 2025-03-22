import os
import base64
import requests
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

# Try to import dotenv, but make it optional
try:
    from dotenv import load_dotenv
    load_dotenv()
    logging.info("Successfully loaded environment variables from .env file")
except ImportError:
    logging.info("python-dotenv not available, assuming environment variables are already set")

@dataclass
class ZendeskConfig:
    subdomain: str
    email: str
    api_token: str
    
    @classmethod
    def from_env(cls) -> 'ZendeskConfig':
        """Create ZendeskConfig from environment variables."""
        return cls(
            subdomain=os.getenv("ZENDESK_SUBDOMAIN", ""),
            email=os.getenv("ZENDESK_EMAIL", ""),
            api_token=os.getenv("ZENDESK_API_TOKEN", "")
        )

class ZendeskAPI:
    def __init__(self, config: ZendeskConfig):
        self.config = config
        self.base_url = f"https://{config.subdomain}.zendesk.com/api/v2"
        self.headers = self._create_auth_headers()

    def _create_auth_headers(self) -> Dict[str, str]:
        """Create authentication headers for Zendesk API."""
        credentials = f"{self.config.email}/token:{self.config.api_token}"
        encoded_credentials = base64.b64encode(credentials.encode()).decode()
        return {
            "Authorization": f"Basic {encoded_credentials}",
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", params: Optional[Dict] = None) -> Dict:
        """Make a request to the Zendesk API."""
        url = f"{self.base_url}/{endpoint}"
        try:
            logging.info(f"Making request to Zendesk API: {method} {url}")
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            logging.error(f"HTTP Error from Zendesk API: {e}")
            logging.error(f"Response content: {e.response.text}")
            raise Exception(f"Zendesk API HTTP Error: {e}. Response: {e.response.text}")
        except requests.exceptions.ConnectionError as e:
            logging.error(f"Connection Error to Zendesk API: {e}")
            raise Exception(f"Failed to connect to Zendesk API: {e}")
        except requests.exceptions.Timeout as e:
            logging.error(f"Timeout Error from Zendesk API: {e}")
            raise Exception(f"Zendesk API request timed out: {e}")
        except requests.exceptions.RequestException as e:
            logging.error(f"Error making request to Zendesk API {endpoint}: {e}")
            raise Exception(f"Zendesk API request failed: {e}")
        except Exception as e:
            logging.error(f"Unexpected error when calling Zendesk API: {e}")
            raise Exception(f"Unexpected error with Zendesk API: {e}")

    def get_all_tickets(self, include_comments: bool = True) -> List[Dict[str, Any]]:
        """
        Fetch all tickets from Zendesk.
        If include_comments is True, also fetch comments for each ticket.
        """
        tickets = []
        page = 1
        while True:
            params = {
                "page": page,
                "per_page": 100,
                "sort_by": "created_at",
                "sort_order": "desc"
            }
            response = self._make_request("tickets.json", params=params)
            
            if not response or "tickets" not in response:
                break
                
            current_tickets = response["tickets"]
            if not current_tickets:
                break
                
            if include_comments:
                for ticket in current_tickets:
                    ticket["comments"] = self.get_ticket_comments(ticket["id"])
                    
            tickets.extend(current_tickets)
            page += 1
            
        return tickets

    def get_ticket_comments(self, ticket_id: int) -> List[Dict[str, Any]]:
        """Fetch all comments for a specific ticket."""
        response = self._make_request(f"tickets/{ticket_id}/comments.json")
        return response.get("comments", [])

    def get_users(self) -> List[Dict[str, Any]]:
        """Fetch all users from Zendesk."""
        users = []
        page = 1
        while True:
            params = {
                "page": page,
                "per_page": 100
            }
            response = self._make_request("users.json", params=params)
            
            if not response or "users" not in response:
                break
                
            current_users = response["users"]
            if not current_users:
                break
                
            users.extend(current_users)
            page += 1
            
        return users

    def get_organizations(self) -> List[Dict[str, Any]]:
        """Fetch all organizations from Zendesk."""
        orgs = []
        page = 1
        while True:
            params = {
                "page": page,
                "per_page": 100
            }
            response = self._make_request("organizations.json", params=params)
            
            if not response or "organizations" not in response:
                break
                
            current_orgs = response["organizations"]
            if not current_orgs:
                break
                
            orgs.extend(current_orgs)
            page += 1
            
        return orgs

    def get_ticket_details(self, status: str = "solved") -> List[Dict[str, Any]]:
        """
        Fetch specific ticket details:
        - ticket_url
        - subject (raw_subject)
        - body (description)
        - created (created_at)
        - last_update (updated_at)
        - organisation_id (organization_id)
        - comments (concatenated comment texts)

        Args:
            status: Filter tickets by status (default: "solved")
        """
        tickets = []
        page = 1
        while True:
            # Use the search endpoint with a query to filter by status
            params = {
                "page": page,
                "per_page": 100,
                "query": f"type:ticket status:{status}",
                "sort_by": "created_at",
                "sort_order": "desc"
            }
            response = self._make_request("search.json", params=params)
            
            if not response or "results" not in response:
                break
                
            current_tickets = response.get("results", [])
            if not current_tickets:
                break
                
            for ticket in current_tickets:
                # Get comments for this ticket
                comments = self.get_ticket_comments(ticket['id'])
                # Extract only the comment bodies and join them with a separator
                comment_texts = [comment.get('body', '') for comment in comments]
                
                # Create a ticket details dictionary
                ticket_details = {
                    'id': ticket.get('id'),
                    'url': f"https://{self.config.subdomain}.zendesk.com/agent/tickets/{ticket.get('id')}",
                    'subject': ticket.get('subject', 'No subject'),
                    'description': ticket.get('description', ''),
                    'created_at': ticket.get('created_at'),
                    'updated_at': ticket.get('updated_at'),
                    'organization_id': ticket.get('organization_id'),
                    'status': ticket.get('status'),
                    'priority': ticket.get('priority'),
                    'comments': comment_texts,
                    'requester': ticket.get('requester_id'),
                    'assignee': ticket.get('assignee_id'),
                    'tags': ticket.get('tags', [])
                }
                
                tickets.append(ticket_details)
                
            page += 1
            if len(current_tickets) < 100:  # Last page
                break
                
        logging.info(f"Found {len(tickets)} tickets with status '{status}'")
        return tickets

def main():
    """Test the ZendeskAPI class."""
    config = ZendeskConfig.from_env()
    zendesk = ZendeskAPI(config)
    
    # Get ticket details
    tickets = zendesk.get_ticket_details()
    
    # Print ticket information
    for i, ticket in enumerate(tickets[:5]):  # Print first 5 tickets only
        print(f"\nTicket #{i+1}:")
        print(f"ID: {ticket['id']}")
        print(f"URL: {ticket['url']}")
        print(f"Subject: {ticket['subject']}")
        print(f"Created: {ticket['created_at']}")
        print(f"Updated: {ticket['updated_at']}")
        print(f"Comments: {len(ticket['comments'])}")

if __name__ == "__main__":
    main()
