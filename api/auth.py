# api/auth.py
"""
Authentication and Authorization
Azure AD integration with RBAC
"""

from fastapi import HTTPException, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from typing import Dict, List, Optional
import os
import logging
import httpx

security = HTTPBearer()
logger = logging.getLogger(__name__)

# Azure AD Configuration
AZURE_AD_TENANT_ID = os.environ.get('AZURE_AD_TENANT_ID')
AZURE_AD_CLIENT_ID = os.environ.get('AZURE_AD_CLIENT_ID')
AZURE_AD_JWKS_URL = f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}/discovery/v2.0/keys"

# Cache for JWKS keys
_jwks_cache = None

async def get_jwks_keys():
    """Fetch and cache JWKS keys from Azure AD"""
    global _jwks_cache
    
    if _jwks_cache is None:
        async with httpx.AsyncClient() as client:
            response = await client.get(AZURE_AD_JWKS_URL)
            _jwks_cache = response.json()
    
    return _jwks_cache

async def verify_token(
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> Dict:
    """
    Verify JWT token from Azure AD
    
    Returns:
        User information dictionary with roles and permissions
    """
    token = credentials.credentials
    
    try:
        # For MVP: Simple validation
        # For Production: Full Azure AD validation
        
        if os.environ.get('ENV') == 'mvp':
            # MVP: Basic token validation
            return verify_token_mvp(token)
        else:
            # Production: Full Azure AD validation
            return await verify_token_production(token)
    
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(
            status_code=401,
            detail="Invalid authentication credentials"
        )

def verify_token_mvp(token: str) -> Dict:
    """
    MVP token verification (simplified)
    For development and initial deployment
    """
    # Check if token matches expected format
    if not token or token == "":
        raise HTTPException(status_code=401, detail="Missing token")
    
    # For MVP, use a simple API key approach
    valid_api_keys = {
        os.environ.get('MVP_API_KEY', 'mvp-key-12345'): {
            'user_id': 'system@company.com',
            'name': 'System User',
            'roles': ['researcher', 'admin'],
            'allowed_species': ['poultry', 'swine', 'aquaculture']
        }
    }
    
    if token in valid_api_keys:
        return valid_api_keys[token]
    
    raise HTTPException(status_code=401, detail="Invalid API key")

async def verify_token_production(token: str) -> Dict:
    """
    Production token verification with Azure AD
    Full JWT validation with JWKS
    """
    try:
        # Get JWKS keys
        jwks = await get_jwks_keys()
        
        # Decode JWT header to get key ID
        unverified_header = jwt.get_unverified_header(token)
        
        # Find matching key
        rsa_key = {}
        for key in jwks['keys']:
            if key['kid'] == unverified_header['kid']:
                rsa_key = {
                    'kty': key['kty'],
                    'kid': key['kid'],
                    'use': key['use'],
                    'n': key['n'],
                    'e': key['e']
                }
                break
        
        if not rsa_key:
            raise HTTPException(status_code=401, detail="Invalid token key")
        
        # Verify and decode token
        payload = jwt.decode(
            token,
            rsa_key,
            algorithms=['RS256'],
            audience=AZURE_AD_CLIENT_ID,
            issuer=f"https://login.microsoftonline.com/{AZURE_AD_TENANT_ID}/v2.0"
        )
        
        # Extract user information
        user_info = {
            'user_id': payload.get('preferred_username') or payload.get('email'),
            'name': payload.get('name'),
            'roles': extract_roles_from_token(payload),
            'allowed_species': get_user_species_access(payload)
        }
        
        return user_info
    
    except JWTError as e:
        logger.error(f"JWT validation failed: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid token")

def extract_roles_from_token(payload: Dict) -> List[str]:
    """
    Extract roles from Azure AD token
    Checks both 'roles' claim and 'groups' claim
    """
    roles = []
    
    # Check roles claim
    if 'roles' in payload:
        roles.extend(payload['roles'])
    
    # Map groups to roles (configure in Azure AD)
    group_role_mapping = {
        os.environ.get('ADMIN_GROUP_ID', ''): 'admin',
        os.environ.get('RESEARCHER_GROUP_ID', ''): 'researcher',
        os.environ.get('VIEWER_GROUP_ID', ''): 'viewer'
    }
    
    if 'groups' in payload:
        for group_id in payload['groups']:
            if group_id in group_role_mapping:
                roles.append(group_role_mapping[group_id])
    
    return list(set(roles))  # Remove duplicates

def get_user_species_access(payload: Dict) -> List[str]:
    """
    Determine which species the user can access
    Based on roles or group memberships
    """
    roles = extract_roles_from_token(payload)
    
    # Admins get access to all species
    if 'admin' in roles:
        return ['poultry', 'swine', 'aquaculture', 'ruminants', 'companion']
    
    # Map roles to species access
    # TODO: Implement more granular permissions
    return ['poultry', 'swine']  # Default access

async def check_species_access(user: Dict, species: List[str]):
    """
    Verify user has access to requested species
    
    Args:
        user: User information from verify_token
        species: List of species user wants to access
        
    Raises:
        HTTPException: If access denied
    """
    allowed_species = user.get('allowed_species', [])
    
    for s in species:
        if s not in allowed_species:
            logger.warning(f"Access denied for user {user.get('user_id')} to species: {s}")
            raise HTTPException(
                status_code=403,
                detail=f"Access denied for species: {s}"
            )

def require_role(required_role: str):
    """
    Dependency to require specific role
    Usage: @app.get("/admin", dependencies=[Depends(require_role("admin"))])
    """
    async def check_role(user: Dict = Depends(verify_token)):
        if required_role not in user.get('roles', []):
            raise HTTPException(
                status_code=403,
                detail=f"Role '{required_role}' required"
            )
        return user
    
    return check_role
