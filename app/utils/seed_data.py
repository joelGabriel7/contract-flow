# app/scripts/seed_data.py
from uuid import uuid4

from sqlmodel import Session, create_engine
from app.core.security import get_password_hash
from app.models.users import User
from app.models.organization import Organization, OrganizationUser, OrganizationRole
from app.models.types import AccountType
from app.core.config import get_settings

settings = get_settings()
engine = create_engine(settings.DATABASE_URL)

def create_seed_data():
   with Session(engine) as session:
       # Crear usuarios personales
       personal_users = [
           User(
               id=uuid4(),
               email=f"user{i}@example.com",
               password_hash=get_password_hash("password123"),
               full_name=f"Test User {i}",
               account_type=AccountType.PERSONAL,
               is_verified=True
           ) for i in range(1, 30)
       ]
       
       # Crear usuarios business
       business_users = [
           User(
               id=uuid4(),
               email=f"business{i}@example.com",
               password_hash=get_password_hash("password123"),
               full_name=f"Business User {i}",
               account_type=AccountType.BUSSINESS,
               is_verified=True
           ) for i in range(1, 30)
       ]

       # Crear organizaciones
       organizations = [
           Organization(
               id=uuid4(),
               name=f"Test Organization {i}"
           ) for i in range(1, 30)
       ]

       # Guardar todo en la base de datos
       for user in personal_users + business_users:
           session.add(user)
       
       for org in organizations:
           session.add(org)
           
       session.commit()

       # Crear relaciones usuario-organización
       org_users = [
           OrganizationUser(
               organization_id=organizations[0].id,
               user_id=business_users[0].id,
               role=OrganizationRole.ADMIN
           ),
           OrganizationUser(
               organization_id=organizations[1].id,
               user_id=business_users[1].id,
               role=OrganizationRole.ADMIN
           )
       ]

       for org_user in org_users:
           session.add(org_user)

       session.commit()

       print("Datos de prueba creados exitosamente:")
       print("\nUsuarios personales:")
       for user in personal_users:
           print(f"Email: {user.email}, Password: password123")
       
       print("\nUsuarios business:")
       for user in business_users:
           print(f"Email: {user.email}, Password: password123")
       
       print("\nOrganizaciones:")
       for org in organizations:
           print(f"ID: {org.id}, Nombre: {org.name}")

if __name__ == "__main__":
   create_seed_data()