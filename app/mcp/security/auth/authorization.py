
"""
Authorization system for the Model Context Protocol (MCP).

This module provides interfaces and implementations for controlling
what actions authenticated users can perform.
"""

from enum import Enum
from typing import Dict, List, Optional, Pattern, Union
import re


class ResourceType(str, Enum):
    """Types of resources that can be protected."""
    
    ADAPTER = "adapter"
    DATA = "data"
    FUNCTION = "function"
    SYSTEM = "system"


class Action(str, Enum):
    """Actions that can be performed on resources."""
    
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    EXECUTE = "execute"
    ADMIN = "admin"


class Permission:
    """Represents a permission to perform an action on a resource."""
    
    def __init__(self, resource_type: ResourceType, resource_id: str, action: Action):
        """Initialize a permission.
        
        Args:
            resource_type: Type of resource
            resource_id: ID of the resource
            action: Action to perform
        """
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.action = action
    
    @classmethod
    def from_string(cls, permission_str: str) -> "Permission":
        """Parse a permission string (e.g., 'adapter:postgres:read').
        
        Args:
            permission_str: String representation of the permission
            
        Returns:
            Permission: Parsed permission
            
        Raises:
            ValueError: If the permission string is invalid
        """
        parts = permission_str.split(":", 2)
        if len(parts) != 3:
            raise ValueError(f"Invalid permission format: {permission_str}")
        
        return cls(
            resource_type=ResourceType(parts[0]),
            resource_id=parts[1],
            action=Action(parts[2])
        )
    
    def to_string(self) -> str:
        """Convert to string representation.
        
        Returns:
            str: String representation of the permission
        """
        return f"{self.resource_type}:{self.resource_id}:{self.action}"
    
    def matches(self, resource_type: ResourceType, resource_id: str, action: Action) -> bool:
        """Check if this permission matches the given parameters.
        
        Args:
            resource_type: Type of resource to check
            resource_id: ID of the resource to check
            action: Action to check
            
        Returns:
            bool: True if the permission matches, False otherwise
        """
        # Check resource type
        if self.resource_type != resource_type:
            return False
        
        # Check resource ID (support wildcards)
        if self.resource_id != "*" and self.resource_id != resource_id:
            # Check for pattern match
            if self.resource_id.endswith("*"):
                prefix = self.resource_id[:-1]
                if not resource_id.startswith(prefix):
                    return False
            else:
                return False
        
        # Check action
        if self.action != Action.ADMIN and self.action != action:
            return False
        
        return True


class Role:
    """Represents a role with a set of permissions."""
    
    def __init__(self, name: str, permissions: List[Permission]):
        """Initialize a role.
        
        Args:
            name: Name of the role
            permissions: List of permissions granted by the role
        """
        self.name = name
        self.permissions = permissions


class AuthorizationManager:
    """Manages roles and permissions for authorization."""
    
    def __init__(self):
        """Initialize the authorization manager."""
        self._roles: Dict[str, Role] = {}
    
    def add_role(self, role: Role) -> None:
        """Add a role to the manager.
        
        Args:
            role: The role to add
        """
        self._roles[role.name] = role
    
    def get_role(self, role_name: str) -> Optional[Role]:
        """Get a role by name.
        
        Args:
            role_name: Name of the role
            
        Returns:
            Optional[Role]: The role if found, None otherwise
        """
        return self._roles.get(role_name)
    
    def list_roles(self) -> List[str]:
        """List all role names.
        
        Returns:
            List[str]: List of role names
        """
        return list(self._roles.keys())
    
    def check_permission(
        self,
        roles: List[str],
        permissions: List[str],
        resource_type: ResourceType,
        resource_id: str,
        action: Action
    ) -> bool:
        """Check if the given roles and permissions allow the action.
        
        Args:
            roles: List of role names
            permissions: List of permission strings
            resource_type: Type of resource
            resource_id: ID of the resource
            action: Action to perform
            
        Returns:
            bool: True if the action is allowed, False otherwise
        """
        # Check direct permissions first
        for perm_str in permissions:
            try:
                permission = Permission.from_string(perm_str)
                if permission.matches(resource_type, resource_id, action):
                    return True
            except ValueError:
                continue
        
        # Check role-based permissions
        for role_name in roles:
            if role_name not in self._roles:
                continue
                
            role = self._roles[role_name]
            for permission in role.permissions:
                if permission.matches(resource_type, resource_id, action):
                    return True
        
        return False


# Create some predefined roles
def create_admin_role() -> Role:
    """Create an admin role with full permissions.
    
    Returns:
        Role: Admin role
    """
    return Role(
        name="admin",
        permissions=[
            Permission(ResourceType.ADAPTER, "*", Action.ADMIN),
            Permission(ResourceType.DATA, "*", Action.ADMIN),
            Permission(ResourceType.FUNCTION, "*", Action.ADMIN),
            Permission(ResourceType.SYSTEM, "*", Action.ADMIN),
        ]
    )


def create_read_only_role() -> Role:
    """Create a read-only role.
    
    Returns:
        Role: Read-only role
    """
    return Role(
        name="read_only",
        permissions=[
            Permission(ResourceType.ADAPTER, "*", Action.READ),
            Permission(ResourceType.DATA, "*", Action.READ),
            Permission(ResourceType.FUNCTION, "*", Action.READ),
        ]
    )


def create_data_scientist_role() -> Role:
    """Create a data scientist role.
    
    Returns:
        Role: Data scientist role
    """
    return Role(
        name="data_scientist",
        permissions=[
            Permission(ResourceType.ADAPTER, "*", Action.READ),
            Permission(ResourceType.DATA, "*", Action.READ),
            Permission(ResourceType.DATA, "*", Action.EXECUTE),
            Permission(ResourceType.FUNCTION, "*", Action.EXECUTE),
        ]
    )