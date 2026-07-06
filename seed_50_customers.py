"""
NagaForge — 50 Customer Seed Script (fixed for actual model fields)
Run from the Construction folder:
    pip install python-dateutil --break-system-packages
    python seed_50_customers.py

Creates:
  - 50 Companies (tenants) — India, Canada, UAE
  - 1 admin user per company   (login: <CODE>_admin / Admin@123)
  - TenantSubscription + TenantConfig per company
  - 2-4 Projects per company
  - 5-8 Workers (global, assigned to projects)
  - 2-3 Clients (global)
  - Tasks, Expenses, Invoices, Safety Incidents, Inventory
"""

import sys, os, random
from datetime import date, timedelta

try:
    from dateutil.relativedelta import relativedelta
except ImportError:
    print("Installing python-dateutil...")
    os.system("pip install python-dateutil --break-system-packages -q")
    from dateutil.relativedelta import relativedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "backend"))

from database import engine, Base, SessionLocal
import models
from auth import hash_password

Base.metadata.create_all(bind=engine)
db = SessionLocal()

# ── Helpers ──────────────────────────────────────────────────────────────────
def rdate(days_ago_max=730, days_ago_min=30):
    return date.today() - timedelta(days=random.randint(days_ago_min, days_ago_max))

# ── Reference data ────────────────────────────────────────────────────────────

COMPANIES = [
    ("Sharma Constructions Pvt Ltd",    "SCP", "India",   "Mumbai",       "INR"),
    ("GreenBuild Developers",           "GBD", "India",   "Ahmedabad",    "INR"),
    ("Metro Infra Corp",                "MIC", "India",   "Delhi",        "INR"),
    ("Tata Projects Ltd",               "TPL", "India",   "Pune",         "INR"),
    ("LNT Construction",                "LTC", "India",   "Chennai",      "INR"),
    ("NCC Limited",                     "NCC", "India",   "Hyderabad",    "INR"),
    ("Hindustan Construction",          "HCC", "India",   "Mumbai",       "INR"),
    ("Shapoorji Pallonji Group",        "SPG", "India",   "Mumbai",       "INR"),
    ("DLF Projects",                    "DLF", "India",   "Gurgaon",      "INR"),
    ("Oberoi Realty",                   "OBR", "India",   "Mumbai",       "INR"),
    ("Prestige Group",                  "PRG", "India",   "Bengaluru",    "INR"),
    ("Brigade Group",                   "BRG", "India",   "Bengaluru",    "INR"),
    ("Godrej Properties",               "GDP", "India",   "Mumbai",       "INR"),
    ("Puravankara Ltd",                 "PVR", "India",   "Bengaluru",    "INR"),
    ("Sobha Developers",                "SBH", "India",   "Bengaluru",    "INR"),
    ("Lodha Group",                     "LDH", "India",   "Mumbai",       "INR"),
    ("Sun Infrastructure",              "SIF", "India",   "Ahmedabad",    "INR"),
    ("IRB Infrastructure",              "IRB", "India",   "Mumbai",       "INR"),
    ("GMR Infrastructure",              "GMR", "India",   "Delhi",        "INR"),
    ("Adani Infra",                     "ADI", "India",   "Ahmedabad",    "INR"),
    ("Patel Engineering",               "PEL", "India",   "Mumbai",       "INR"),
    ("MHADA Projects",                  "MHD", "India",   "Mumbai",       "INR"),
    ("National Highway Infra",          "NHI", "India",   "Delhi",        "INR"),
    ("RITES Ltd",                       "RTS", "India",   "Gurugram",     "INR"),
    ("Sterlite Power",                  "STP", "India",   "Bengaluru",    "INR"),
    ("PCL Constructors",                "PCL", "Canada",  "Calgary",      "CAD"),
    ("Aecon Group",                     "ACN", "Canada",  "Toronto",      "CAD"),
    ("Graham Construction",             "GRC", "Canada",  "Edmonton",     "CAD"),
    ("EllisDon",                        "ELD", "Canada",  "Mississauga",  "CAD"),
    ("Stuart Olson",                    "SOL", "Canada",  "Calgary",      "CAD"),
    ("Bird Construction",               "BRC", "Canada",  "Toronto",      "CAD"),
    ("Clark Builders",                  "CLB", "Canada",  "Edmonton",     "CAD"),
    ("Pomerleau Inc",                   "POM", "Canada",  "Quebec City",  "CAD"),
    ("Ledcor Group",                    "LDC", "Canada",  "Vancouver",    "CAD"),
    ("Chandos Construction",            "CHS", "Canada",  "Edmonton",     "CAD"),
    ("ALEC Engineering",                "ALC", "UAE",     "Dubai",        "AED"),
    ("Arabtec Construction",            "ART", "UAE",     "Dubai",        "AED"),
    ("Drake Scull Intl",                "DSI", "UAE",     "Dubai",        "AED"),
    ("Shapoorji UAE",                   "SPU", "UAE",     "Abu Dhabi",    "AED"),
    ("Consolidated Contractors",        "CCC", "UAE",     "Dubai",        "AED"),
    ("Al Habtoor Engineering",          "AHE", "UAE",     "Dubai",        "AED"),
    ("Besix Group UAE",                 "BSX", "UAE",     "Dubai",        "AED"),
    ("Commodore LLC",                   "CMD", "UAE",     "Abu Dhabi",    "AED"),
    ("KEO International",               "KEO", "UAE",     "Abu Dhabi",    "AED"),
    ("Six Construct",                   "SXC", "UAE",     "Dubai",        "AED"),
    ("Archirodon Group",                "ARG", "UAE",     "Dubai",        "AED"),
    ("Galadari Engineering",            "GEW", "UAE",     "Dubai",        "AED"),
    ("Al Jaber Engineering",            "AJE", "UAE",     "Abu Dhabi",    "AED"),
    ("Dutco Tennant LLC",               "DTC", "UAE",     "Dubai",        "AED"),
    ("National Projects Const",         "NPC", "UAE",     "Dubai",        "AED"),
]

PROJECT_NAMES = [
    "Residential Tower Phase {}", "Commercial Complex Block {}",
    "Highway Widening Project {}", "Metro Rail Package {}",
    "Industrial Warehouse {}", "Data Centre Build-Out {}",
    "Airport Terminal {}", "Bridge Rehabilitation {}",
    "Hospital Extension {}", "School Building {}",
    "Mixed-Use Development {}", "Water Treatment Plant {}",
    "Solar Farm EPC {}", "Office Park {}",
    "Affordable Housing Scheme {}",
]

WORKER_ROLES = ["site_manager","engineer","architect","foreman","safety_officer","surveyor"]

FIRST_NAMES = ["Arjun","Priya","Rajesh","Sunita","Mohammed","Lakshmi","Vikram",
               "Anita","Deepak","Kavita","Robert","John","Sara","Alex","Raj",
               "Ahmed","Fatima","James","Chen","Aisha","Ravi","Meera","Kumar"]
LAST_NAMES  = ["Nair","Kumar","Sharma","Patel","Ali","Iyer","Singh","Gupta",
               "Reddy","Menon","Thompson","Mitchell","Hassan","Verma","Khan",
               "Al Rashid","Williams","Brown","Lee","Chen","Das","Joshi","Rao"]

PLANS = ["starter","starter","professional","professional","enterprise"]

EXPENSE_CATS = ["material","labor","equipment","subcontract","overhead","professional"]

MATERIAL_TYPES = [
    ("Portland Cement 53 Grade","bags","CEM",380,100),
    ("TMT Bars 12mm Fe415","kg","STL012",65,2000),
    ("TMT Bars 16mm Fe415","kg","STL016",68,1500),
    ("River Sand (washed)","cum","SND",1800,50),
    ("20mm Aggregates","cum","AGG020",1400,80),
    ("Waterproofing Compound","ltr","WPC",250,200),
    ("Hollow Blocks 8 inch","pcs","HLW",32,5000),
    ("Structural Steel Plates","kg","STLP",78,800),
    ("Safety Helmets","pcs","SAF001",450,30),
    ("PVC Pipes 110mm","mtr","PVC",145,300),
]

# ── Clear old seed data ───────────────────────────────────────────────────────
print("Clearing old seed data...")
try:
    db.query(models.TenantSubscription).delete()
    db.query(models.TenantConfig).delete()
    db.query(models.SafetyIncident).filter(models.SafetyIncident.id > 0).delete()
    db.query(models.Expense).filter(models.Expense.id > 0).delete()
    db.query(models.Invoice).filter(models.Invoice.id > 0).delete()
    db.query(models.InventoryItem).filter(models.InventoryItem.id > 0).delete()
    db.query(models.Task).filter(models.Task.id > 0).delete()
    db.query(models.Project).filter(models.Project.id > 0).delete()
    db.query(models.Worker).filter(models.Worker.id > 0).delete()
    db.query(models.Client).filter(models.Client.id > 0).delete()
    db.query(models.Company).filter(models.Company.short_name != "DEMO").delete()
    db.query(models.User).filter(models.User.username != "admin").delete()
    db.commit()
    print("  Done.\n")
except Exception as e:
    print(f"  Warning (non-fatal): {e}")
    db.rollback()

# ── Seed subscription plans ───────────────────────────────────────────────────
if db.query(models.SubscriptionPlan).count() == 0:
    db.add_all([
        models.SubscriptionPlan(name="free",display_name="Free",price_monthly=0,price_annual=0,
            max_users=3,max_projects=2,features=["projects","workers","clients"],is_active=True),
        models.SubscriptionPlan(name="starter",display_name="Starter",price_monthly=2999,price_annual=29990,
            max_users=10,max_projects=10,features=["projects","workers","clients","finance","scheduling","quality"],is_active=True),
        models.SubscriptionPlan(name="professional",display_name="Professional",price_monthly=7999,price_annual=79990,
            max_users=50,max_projects=50,features=["all"],is_active=True),
        models.SubscriptionPlan(name="enterprise",display_name="Enterprise",price_monthly=19999,price_annual=199990,
            max_users=999,max_projects=999,features=["all","white_label","api_access","saas_admin"],is_active=True),
    ])
    db.commit()
    print("Subscription plans seeded.\n")

# ── Pre-create shared Clients ─────────────────────────────────────────────────
CLIENT_DATA = [
    ("Ravi Sharma","Sharma Realty Pvt Ltd","ravi.sharma@sharmareal.com","Mumbai","India"),
    ("Anita Patel","GreenBuild Corp","anita.patel@greenbuild.com","Ahmedabad","India"),
    ("Vikram Singh","Metro Holdings","vikram.singh@methold.com","Delhi","India"),
    ("Sunita Iyer","Iyer Infra Pvt Ltd","sunita.iyer@iyerinfra.com","Chennai","India"),
    ("Mohan Das","DAS Properties","mohan.das@dasproperties.com","Kolkata","India"),
    ("Ahmed Al Rashid","Al Rashid Group","ahmed@alrashidgroup.ae","Dubai","UAE"),
    ("Sara Mitchell","Mitchell Projects","sara.mitchell@mitchell.ca","Toronto","Canada"),
    ("James Carter","Carter Builds Inc","james.carter@carterblds.ca","Calgary","Canada"),
    ("Fatima Al Zaabi","Zaabi Real Estate","fatima@zaabireal.ae","Abu Dhabi","UAE"),
    ("Rahul Verma","Verma Constructions","rahul.verma@vermacons.com","Mumbai","India"),
    ("Deepak Nair","Nair Infra","deepak.nair@nairinfra.com","Bengaluru","India"),
    ("Chen Wei","Asia Pacific Infra","chen.wei@apinfra.sg","Singapore","UAE"),
]

all_clients = []
for cn, cc, em, city, country in CLIENT_DATA:
    c = models.Client(name=cn, company=cc, email=em, city=city, country=country,
                      phone=f"+91{random.randint(7000000000,9999999999)}")
    db.add(c)
    all_clients.append(c)
db.flush()
print(f"Created {len(all_clients)} clients.\n")

# ── Pre-create Workers (global pool) ──────────────────────────────────────────
all_workers = []
used_emails = set()
used_emp_ids = set()
for i in range(300):
    fn = FIRST_NAMES[i % len(FIRST_NAMES)]
    ln = LAST_NAMES[(i * 3) % len(LAST_NAMES)]
    role = WORKER_ROLES[i % len(WORKER_ROLES)]
    em = f"{fn.lower().replace(' ','')}.{ln.lower().replace(' ','')}{i}@nagaforge.work"
    emp_id = f"EMP-{i+1:04d}"
    if em in used_emails or emp_id in used_emp_ids:
        continue
    used_emails.add(em)
    used_emp_ids.add(emp_id)
    w = models.Worker(
        first_name=fn, last_name=ln,
        employee_id=emp_id,
        email=em,
        phone=f"+91{random.randint(7000000000,9999999999)}",
        role=role, status="active",
        daily_rate=random.choice([1200,1500,1800,2200,2500,3000,3500,4000]),
        hire_date=rdate(1000, 100),
    )
    db.add(w)
    all_workers.append(w)
db.flush()
print(f"Created {len(all_workers)} workers.\n")

# ── Main company seed loop ────────────────────────────────────────────────────
print(f"Seeding {len(COMPANIES)} companies...\n")

project_counter = 1
worker_offset   = 0
client_offset   = 0

for idx, (name, code, country, city, currency) in enumerate(COMPANIES):
    plan_name = PLANS[idx % len(PLANS)]
    tld = "in" if country == "India" else ("ca" if country == "Canada" else "ae")
    email = f"admin@{code.lower()}.{tld}"

    # ── Company ──────────────────────────────────────────────────────────────
    company = models.Company(
        name=name, short_name=code,
        country=country, currency=currency,
        city=city, email=email,
        phone=f"+{random.randint(91,971)}{random.randint(7000000000,9999999999)}",
        address=f"{random.randint(1,999)}, Main Road, {city}",
        plan=plan_name, is_active=True,
    )
    db.add(company)
    db.flush()

    # ── Admin user ───────────────────────────────────────────────────────────
    uname = f"{code.lower()}_admin"
    db.add(models.User(
        username=uname,
        full_name=f"{name} Admin",
        email=email,
        hashed_password=hash_password("Admin@123"),
        role="admin",
        company_id=company.id,
        is_active=True,
    ))

    # ── Subscription ─────────────────────────────────────────────────────────
    plan_obj = db.query(models.SubscriptionPlan).filter_by(name=plan_name).first()
    if plan_obj:
        db.add(models.TenantSubscription(
            company_id=company.id,
            plan_id=plan_obj.id,
            status="active",
            trial_ends=None,
        ))

    # ── Tenant config ─────────────────────────────────────────────────────────
    colors = ["#2563eb","#16a34a","#dc2626","#9333ea","#ea580c","#0891b2","#854d0e","#1e3a8a"]
    tz = "Asia/Kolkata" if country == "India" else ("America/Toronto" if country == "Canada" else "Asia/Dubai")
    db.add(models.TenantConfig(
        company_id=company.id,
        app_name=name.split()[0] + "Pro",
        primary_color=colors[idx % len(colors)],
        timezone=tz,
        currency=currency,
    ))

    # ── Projects ──────────────────────────────────────────────────────────────
    n_projects = random.randint(2, 4)
    company_projects = []
    for pi in range(n_projects):
        pname = PROJECT_NAMES[(project_counter + pi) % len(PROJECT_NAMES)].format(f"{code}-{pi+1:02d}")
        pcode = f"PRJ-{project_counter + pi:04d}"
        status = random.choice(["active","active","active","planning","completed"])
        start = rdate(500, 90)
        end   = start + relativedelta(months=random.randint(6, 24))
        budget = random.randint(5, 200) * 1_000_000
        progress = 0 if status == "planning" else (100 if status == "completed" else random.randint(5, 85))
        spent = int(budget * progress / 100 * random.uniform(0.8, 1.1))
        client = all_clients[(client_offset + pi) % len(all_clients)]

        proj = models.Project(
            name=pname, project_code=pcode,
            description=f"{pname} — {city}, {country}",
            client_id=client.id,
            status=status,
            start_date=start, end_date=end,
            budget=budget, spent=spent,
            location=city,
            project_type=random.choice(["residential","commercial","infrastructure","industrial"]),
            progress=progress,
        )
        db.add(proj)
        company_projects.append(proj)
    db.flush()

    # ── Tasks ─────────────────────────────────────────────────────────────────
    task_titles = ["Foundation design review","Structural drawings approval",
                   "Procurement of steel","Concrete pouring basement",
                   "MEP coordination","Safety audit Q1","Site survey","BBS preparation"]
    wkrs = all_workers[worker_offset % len(all_workers): (worker_offset + 6) % len(all_workers) + 1]
    for proj in company_projects:
        for ti, tt in enumerate(task_titles[:random.randint(3, 6)]):
            assignee = wkrs[ti % len(wkrs)] if wkrs else None
            db.add(models.Task(
                project_id=proj.id,
                assignee_id=assignee.id if assignee else None,
                title=tt,
                status=random.choice(["todo","in_progress","done","in_progress"]),
                priority=random.choice(["low","medium","high","urgent"]),
                due_date=date.today() + timedelta(days=random.randint(7, 120)),
            ))

    # ── Expenses ──────────────────────────────────────────────────────────────
        for ei in range(random.randint(3, 5)):
            db.add(models.Expense(
                project_id=proj.id,
                category=random.choice(EXPENSE_CATS),
                description=f"{random.choice(EXPENSE_CATS).title()} cost — {proj.name[:30]}",
                amount=random.randint(50000, 5_000_000),
                date=rdate(300, 10),
                vendor=random.choice(["UltraTech","TATA Steel","Local Supplier","Sub-contractor A","Agency"]),
            ))

    # ── Invoices ──────────────────────────────────────────────────────────────
        inv_no = f"INV-{code}-{project_counter + company_projects.index(proj):04d}"
        subtotal = int(proj.budget * random.uniform(0.1, 0.35))
        tax_amt  = subtotal * 0.18
        inv_status = random.choice(["paid","paid","sent","draft"])
        db.add(models.Invoice(
            invoice_no=inv_no,
            client_id=proj.client_id,
            project_id=proj.id,
            status=inv_status,
            issue_date=rdate(200, 10),
            due_date=rdate(60, 5),
            subtotal=subtotal, tax_rate=18.0, tax_amount=tax_amt,
            total=subtotal + tax_amt,
            paid_amount=subtotal + tax_amt if inv_status == "paid" else 0,
            currency=currency,
        ))

    # ── Safety Incidents (random) ─────────────────────────────────────────────
        if random.random() < 0.4:
            db.add(models.SafetyIncident(
                project_id=proj.id,
                title=random.choice(["Near miss scaffold","Minor cut on hand",
                    "Tool dropped from height","Slip on wet surface","Eye irritation dust"]),
                severity=random.choice(["low","low","medium","high"]),
                incident_type=random.choice(["near_miss","incident","near_miss"]),
                incident_date=rdate(200, 10),
                location=f"Floor {random.randint(1,15)}",
                injuries=random.choice([True, False]),
                resolved=random.choice([True, True, False]),
                reported_by=wkrs[0].first_name if wkrs else "Site Engineer",
                corrective_action="Safety briefing conducted. PPE strictly enforced.",
            ))

    # ── Inventory ─────────────────────────────────────────────────────────────
    for mat_name, unit, base_sku, cost, qty_max in random.sample(MATERIAL_TYPES, k=4):
        sku = f"{base_sku}-{code}-{idx}"
        existing = db.query(models.InventoryItem).filter_by(sku=sku).first()
        if not existing:
            db.add(models.InventoryItem(
                name=mat_name, category="material",
                sku=sku, unit=unit,
                quantity=random.randint(10, qty_max),
                min_quantity=10,
                unit_cost=cost,
                supplier=random.choice(["UltraTech","TATA Steel","Asian Paints","Local","Ambuja"]),
            ))

    project_counter += n_projects
    worker_offset   += 6
    client_offset   += 2

    db.flush()
    print(f"  [{idx+1:02d}/50] {code} — {name[:42]:<42} | {plan_name:<14} | {n_projects} projects")

# ── Commit ────────────────────────────────────────────────────────────────────
db.commit()
db.close()

print("\n" + "="*65)
print("  SEED COMPLETE")
print("="*65)
print(f"  Companies    : {len(COMPANIES)}")
print(f"  Workers pool : {len(all_workers)}")
print(f"  Clients      : {len(CLIENT_DATA)}")
print()
print("  Login format : <CODE>_admin  /  Admin@123")
print("  Examples:")
print("    scp_admin  / Admin@123  (Sharma Constructions - India)")
print("    pcl_admin  / Admin@123  (PCL Constructors - Canada)")
print("    alc_admin  / Admin@123  (ALEC Engineering - UAE)")
print("    admin      / admin123   (System Admin - unchanged)")
print("="*65)
