"""
Azure AD authentication for AIAPI.
Uses fastapi-azure-auth to validate JWT tokens from Azure AD.
Toggle AUTH_ENABLED=false to disable authentication (uses a template user).
"""
import os
from fastapi import Request
from fastapi_azure_auth import SingleTenantAzureAuthorizationCodeBearer
from pydantic import BaseModel
from typing import Optional

AUTH_ENABLED = False #os.environ.get("AUTH_ENABLED", "true").lower() in ("true", "1", "yes")
TEMPLATE_USER_ID = "templateUser" #os.environ.get("TEMPLATE_USER_ID", "templateUser")

APP_CLIENT_ID = "015029a3-a2a2-42d6-9223-15a09a76d93d"
TENANT_ID = "0ae51e19-07c8-4e4b-bb6d-648ee58410f4"

# v1.0 tokens use "api://<client_id>" as audience, not just the client_id
APP_AUDIENCE = f"api://{APP_CLIENT_ID}"

azure_scheme = SingleTenantAzureAuthorizationCodeBearer(
    app_client_id=APP_AUDIENCE,
    tenant_id=TENANT_ID,
    scopes={
        f"api://{APP_CLIENT_ID}/EV.bedeault": "user_access",
    },
)
# Override OpenID config URL to use v1.0 endpoint.
# Azure AD issues v1.0 tokens (issuer: https://sts.windows.net/{tenant}/)
# but the library defaults to v2.0 (issuer: .../v2.0), causing "invalid claims".
azure_scheme.openid_config.config_url = (
    f"https://login.microsoftonline.com/{TENANT_ID}/.well-known/openid-configuration"
)


class User(BaseModel):
    id: str
    name: Optional[str] = None


def get_user(request: Request) -> User:
    """Extract authenticated user from JWT claims."""
    return User(
        id=request.state.user.claims["oid"],
        name=request.state.user.claims.get("name"),
    )
