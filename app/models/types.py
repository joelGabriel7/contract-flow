from enum import Enum

class AccountType(str, Enum):
    PERSONAL = 'personal'
    BUSSINESS = 'bussiness'


class OrganizationRole(str, Enum):
    ADMIN = "admin"
    EDITOR = "editor"
    VIEWER = "viewer"