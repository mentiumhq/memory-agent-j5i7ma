"""
Core authentication module for the Memory Agent system.
Implements JWT-based authentication, token management, and role-based access control.

External Dependencies:
- python-jose[cryptography]==3.3.0: JWT token handling
- pydantic==2.0.0: Data validation
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, List
import uuid
from pydantic import BaseModel, Field, validator
from jose import jwt, JWTError

from config.settings import Settings
from core.errors import SecurityError, ErrorCode

# Role-based permission matrix
ROLE_PERMISSIONS = {
    'agent': ['store', 'retrieve', 'search'],
    'executor': ['store', 'retrieve', 'search', 'admin'],
    'admin': ['store', 'retrieve', 'search', 'admin'],
    'system': ['store', 'retrieve', 'search', 'admin']
}

class TokenPayload(BaseModel):
    """
    Pydantic model for JWT token payload validation with comprehensive security checks.
    Implements strict validation for all token claims.
    """
    sub: str = Field(..., min_length=3, max_length=128)
    role: str = Field(..., regex='^[a-z]+$')
    exp: Optional[datetime] = None
    jti: Optional[str] = Field(None, regex='^[0-9a-f-]+$')
    iss: Optional[str] = None
    aud: Optional[str] = None

    @validator('role')
    def validate_role(cls, v):
        """Validate role against defined permissions."""
        if v not in ROLE_PERMISSIONS:
            raise ValueError(f"Invalid role: {v}")
        return v

    @validator('jti')
    def validate_jti(cls, v):
        """Validate token unique identifier format."""
        if v and not uuid.UUID(v):
            raise ValueError("Invalid token identifier format")
        return v

    def validate_payload(self) -> bool:
        """
        Comprehensive validation of token payload with security checks.
        
        Returns:
            bool: True if payload passes all security validations
        """
        try:
            # Validate required claims
            if not all([self.sub, self.role]):
                return False
            
            # Validate role permissions
            if self.role not in ROLE_PERMISSIONS:
                return False
            
            # Validate expiration
            if self.exp and self.is_expired():
                return False
            
            # Validate optional claims format
            if self.jti and not uuid.UUID(self.jti, version=4):
                return False
                
            return True
        except Exception:
            return False

    def is_expired(self, grace_period_seconds: Optional[int] = None) -> bool:
        """
        Check if token has expired with optional grace period.
        
        Args:
            grace_period_seconds: Optional grace period in seconds
            
        Returns:
            bool: True if token is expired
        """
        if not self.exp:
            return False
            
        now = datetime.now(timezone.utc)
        if grace_period_seconds:
            now += timedelta(seconds=grace_period_seconds)
            
        return now > self.exp

def create_access_token(
    subject: str,
    role: str,
    expires_delta: Optional[timedelta] = None,
    issuer: Optional[str] = None,
    audience: Optional[str] = None
) -> str:
    """
    Create a secure JWT access token with comprehensive claims.
    
    Args:
        subject: Token subject (usually user/agent ID)
        role: User role from ROLE_PERMISSIONS
        expires_delta: Optional token expiration time
        issuer: Optional token issuer
        audience: Optional token audience
        
    Returns:
        str: Securely encoded JWT token
        
    Raises:
        SecurityError: If token creation fails
    """
    try:
        # Validate role
        if role not in ROLE_PERMISSIONS:
            raise SecurityError(
                "Invalid role specified",
                ErrorCode.AUTHENTICATION_ERROR,
                {"role": role}
            )

        # Calculate expiration
        if expires_delta:
            expire = datetime.now(timezone.utc) + expires_delta
        else:
            expire = datetime.now(timezone.utc) + timedelta(
                minutes=Settings.ACCESS_TOKEN_EXPIRE_MINUTES
            )

        # Create token payload
        token_payload = {
            "sub": subject,
            "role": role,
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "nbf": datetime.now(timezone.utc),
            "jti": str(uuid.uuid4())
        }

        # Add optional claims
        if issuer:
            token_payload["iss"] = issuer
        if audience:
            token_payload["aud"] = audience

        # Create token
        encoded_token = jwt.encode(
            token_payload,
            Settings.SECRET_KEY,
            algorithm=Settings.ALGORITHM
        )

        return encoded_token

    except Exception as e:
        raise SecurityError(
            "Token creation failed",
            ErrorCode.AUTHENTICATION_ERROR,
            {"error": str(e)}
        )

def verify_token(
    token: str,
    issuer: Optional[str] = None,
    audience: Optional[str] = None
) -> TokenPayload:
    """
    Verify and decode JWT token with comprehensive security checks.
    
    Args:
        token: JWT token string
        issuer: Optional expected issuer
        audience: Optional expected audience
        
    Returns:
        TokenPayload: Validated token payload
        
    Raises:
        SecurityError: If token validation fails
    """
    try:
        # Decode and verify token
        payload = jwt.decode(
            token,
            Settings.SECRET_KEY,
            algorithms=[Settings.ALGORITHM],
            issuer=issuer,
            audience=audience
        )

        # Create and validate token payload
        token_payload = TokenPayload(**payload)
        if not token_payload.validate_payload():
            raise SecurityError(
                "Invalid token payload",
                ErrorCode.AUTHENTICATION_ERROR
            )

        # Check expiration
        if token_payload.is_expired():
            raise SecurityError(
                "Token has expired",
                ErrorCode.AUTHENTICATION_ERROR
            )

        return token_payload

    except JWTError as e:
        raise SecurityError(
            "Token validation failed",
            ErrorCode.AUTHENTICATION_ERROR,
            {"error": str(e)}
        )
    except Exception as e:
        raise SecurityError(
            "Token processing failed",
            ErrorCode.AUTHENTICATION_ERROR,
            {"error": str(e)}
        )

def check_permissions(
    role: str,
    required_permission: str,
    context_permissions: Optional[List[str]] = None
) -> bool:
    """
    Check role permissions with comprehensive validation.
    
    Args:
        role: User role from ROLE_PERMISSIONS
        required_permission: Permission to check
        context_permissions: Optional context-specific permissions
        
    Returns:
        bool: True if role has required permission
        
    Raises:
        SecurityError: If permission check fails
    """
    try:
        # Validate role
        if role not in ROLE_PERMISSIONS:
            raise SecurityError(
                "Invalid role",
                ErrorCode.AUTHORIZATION_ERROR,
                {"role": role}
            )

        # Get base permissions
        base_permissions = ROLE_PERMISSIONS[role]

        # Merge with context permissions
        permissions = set(base_permissions)
        if context_permissions:
            permissions.update(context_permissions)

        return required_permission in permissions

    except SecurityError:
        raise
    except Exception as e:
        raise SecurityError(
            "Permission check failed",
            ErrorCode.AUTHORIZATION_ERROR,
            {"error": str(e)}
        )