import requests
import logging
from MCP_Enhancement.config import get_settings

# Initialize logger and settings
logger = logging.getLogger(__name__)
settings = get_settings()


def get_fineract_auth():
    """Fetches credentials from the unified settings object."""
    return (settings.fineract_username, settings.fineract_password)


def get_fineract_headers():
    """Mandatory headers for Mifos/Fineract API."""
    return {
        "Fineract-Platform-TenantId": settings.fineract_tenant_id,
        "Content-Type": "application/json"
    }


def search_clients(display_name: str) -> str:
    """
    Search for clients in the Mifos sandbox by name.
    Example query: 'Miguel'
    """
    # URL: https://sandbox.mifos.community/fineract-provider/api/v1/clients
    url = f"{settings.fineract_base_url}/clients"
    params = {"displayName": display_name}

    try:
        response = requests.get(
            url,
            params=params,
            auth=get_fineract_auth(),
            headers=get_fineract_headers(),
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            clients = data.get("pageItems", [])
            if not clients:
                return f"🔍 No clients found matching '{display_name}'."

            # Format the output for the AI
            res = f"✅ Found {len(clients)} client(s):\n"
            for c in clients[:3]:  # Limit to top 3 for brevity
                res += f"- ID: {c.get('id')} | Name: {c.get('displayName')} | Office: {c.get('officeName')}\n"
            return res

        return f"❌ Error {response.status_code}: {response.text}"

    except Exception as e:
        logger.error(f"Fineract Search Failed: {e}")
        return f"⚠️ Connection Failed: {str(e)}"


def get_loan_details(client_id: int) -> str:
    """
    Fetches loan account summary for a specific client ID.
    Example: 1 (for first client)
    """
    # URL: https://sandbox.mifos.community/fineract-provider/api/v1/clients/{id}/accounts
    url = f"{settings.fineract_base_url}/clients/{client_id}/accounts"

    try:
        response = requests.get(
            url,
            auth=get_fineract_auth(),
            headers=get_fineract_headers(),
            timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            loans = data.get("loanAccounts", [])
            if not loans:
                return f"ℹ️ No active loans found for Client ID {client_id}."

            res = f"🏦 Loan Summary for Client {client_id}:\n"
            for l in loans:
                res += (f"- Account: {l.get('accountNo')} | "
                        f"Amount: {l.get('loanAmount')} | "
                        f"Status: {l.get('status', {}).get('value')}\n")
            return res

        return f"❌ Error {response.status_code}: {response.text}"

    except Exception as e:
        logger.error(f"Fineract Loan Details Failed: {e}")
        return f"⚠️ Connection Failed: {str(e)}"