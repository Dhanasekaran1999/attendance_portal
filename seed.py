# seed.py  –  Run once: python seed.py

from app import create_app, db
from app.models import Employee

app = create_app()

SAMPLE_EMPLOYEES = [
    {
        "employee_id":  "EMP001",
        "name":         "Arjun Kumar",
        "email":        "arjun.kumar@company.com",
        "department":   "Engineering",
        "designation":  "Software Developer",
        "phone":        "+91-9876543210",
        "password":     "Arjun@1234",
        "admin":     False
    },
    {
        "employee_id":  "EMP002",
        "name":         "Priya Sharma",
        "email":        "priya.sharma@company.com",
        "department":   "Human Resources",
        "designation":  "HR Manager",
        "phone":        "+91-9123456780",
        "password":     "Priya@5678",
        "admin":     True
    }
]

with app.app_context():
    db.create_all()   # creates tables if they don't exist

    for emp_data in SAMPLE_EMPLOYEES:
        # Skip if already seeded
        existing = Employee.query.filter_by(employee_id=emp_data["employee_id"]).first()
        if existing:
            print(f"⚠️  {emp_data['employee_id']} already exists — skipped.")
            continue

        emp = Employee(
            employee_id=emp_data["employee_id"],
            name=emp_data["name"],
            email=emp_data["email"],
            department=emp_data["department"],
            designation=emp_data["designation"],
            phone=emp_data["phone"],
            admin=emp_data["is_admin"],  # ← changed from is_admin
            active=True  # ← changed from is_active
        )
        emp.set_password(emp_data["password"])
        db.session.add(emp)
        print(f"✅  Added: {emp_data['name']} ({emp_data['employee_id']})")

    db.session.commit()
    print("\n🎉 Seeding complete!")