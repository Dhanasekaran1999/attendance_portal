# setup_admin.py
from app import create_app
from app.extensions import db
from app.models import Employee

app = create_app()

with app.app_context():

    # Check if already exists
    existing = Employee.query.filter_by(employee_id='EMP000').first()

    if existing:
        print("⚠️  Super Admin already exists!")
        print(f"   ID    : {existing.employee_id}")
        print(f"   Name  : {existing.name}")
        print(f"   Active: {existing.active}")
    else:
        admin = Employee(
            employee_id = 'EMP000',
            name        = 'Super Admin',
            email       = 'admin@esfita.com',
            department  = 'Management',
            designation = 'System Administrator',
            phone       = '0000000000',
            user_type   = 'Admin',
            admin       = True,
            active      = True
        )
        admin.set_password('adm@123')
        db.session.add(admin)
        db.session.commit()

        print("✅ Super Admin created successfully!")
        print("─────────────────────────────────")
        print("   Employee ID : EMP000")
        print("   Password    : adm@123")
        print("─────────────────────────────────")