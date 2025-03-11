from enum import Enum

class AccountType(str, Enum):
    PERSONAL = 'personal'
    BUSINESS = 'business'


class OrganizationRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"