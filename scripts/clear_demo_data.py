#!/usr/bin/env python3
"""Remove NagaForge generated demo records while keeping real accounts.

Run from the app server. By default it only prints what would be removed.
Pass --yes to actually delete the demo records.
"""
import argparse
import os
import sys
from pathlib import Path

from sqlalchemy import func, or_


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--app-dir", default="/opt/nagaforge-gpt")
    parser.add_argument("--database-url", default=os.environ.get("DATABASE_URL"))
    parser.add_argument("--yes", action="store_true", help="Actually delete records")
    return parser.parse_args()


def delete_query(session, model, condition, dry_run, label):
    query = session.query(model).filter(condition)
    count = query.count()
    if dry_run:
        print(f"would delete {label}: {count}")
        return count
    if count:
        query.delete(synchronize_session=False)
    print(f"deleted {label}: {count}")
    return count


def main():
    args = parse_args()
    app_dir = Path(args.app_dir).resolve()
    backend_dir = app_dir / "backend"
    sys.path.insert(0, str(backend_dir))

    if args.database_url:
        os.environ["DATABASE_URL"] = args.database_url

    from database import SessionLocal  # noqa: WPS433
    from models import (  # noqa: WPS433
        Activity,
        Attendance,
        BIMElement,
        BIMModel,
        BOQItem,
        Budget,
        BudgetItem,
        CalculationRecord,
        ChangeOrder,
        Client,
        Document,
        DocumentRevision,
        DrawingRegister,
        Equipment,
        EVMSnapshot,
        Expense,
        FuelLog,
        InventoryItem,
        Invoice,
        InvoiceItem,
        MaterialConsumption,
        MaterialTest,
        NCReport,
        PermitToWork,
        Project,
        ProjectWorker,
        QCChecklistItem,
        QCInspection,
        RFI,
        RiskAssessment,
        SafetyIncident,
        SafetyInspection,
        SiteDiary,
        SitePhoto,
        Task,
        ToolboxTalk,
        User,
        Worker,
    )

    dry_run = not args.yes
    if dry_run:
        print("Dry run only. Re-run with --yes to delete.")

    db = SessionLocal()
    try:
        demo_project_ids = [
            row[0]
            for row in db.query(Project.id).filter(
                or_(
                    func.lower(Project.name).like("demo %"),
                    Project.project_code.like("DEMO-PRJ-%"),
                )
            ).all()
        ]
        demo_worker_ids = [
            row[0]
            for row in db.query(Worker.id).filter(Worker.email.like("%.demo.work")).all()
        ]
        demo_client_ids = [
            row[0]
            for row in db.query(Client.id).filter(
                or_(
                    Client.email.like("client@%.demo"),
                    func.lower(Client.name).like("%demo client%"),
                )
            ).all()
        ]
        demo_equipment_ids = [
            row[0]
            for row in db.query(Equipment.id).filter(
                or_(
                    Equipment.vendor.like("Demo %"),
                    Equipment.name.in_(["Tower Crane TC-5013", "Concrete Pump CP-36"]),
                )
            ).all()
        ]

        print(f"demo projects found: {len(demo_project_ids)}")
        print(f"demo workers found: {len(demo_worker_ids)}")
        print(f"demo clients found: {len(demo_client_ids)}")
        print(f"demo equipment found: {len(demo_equipment_ids)}")

        if demo_project_ids:
            inspection_ids = [row[0] for row in db.query(QCInspection.id).filter(QCInspection.project_id.in_(demo_project_ids)).all()]
            model_ids = [row[0] for row in db.query(BIMModel.id).filter(BIMModel.project_id.in_(demo_project_ids)).all()]
            invoice_ids = [row[0] for row in db.query(Invoice.id).filter(Invoice.project_id.in_(demo_project_ids)).all()]
            document_ids = [row[0] for row in db.query(Document.id).filter(Document.project_id.in_(demo_project_ids)).all()]
            budget_ids = [row[0] for row in db.query(Budget.id).filter(Budget.project_id.in_(demo_project_ids)).all()]

            if inspection_ids:
                delete_query(db, QCChecklistItem, QCChecklistItem.inspection_id.in_(inspection_ids), dry_run, "QC checklist items")
            if model_ids:
                delete_query(db, BIMElement, BIMElement.model_id.in_(model_ids), dry_run, "BIM elements")
            if invoice_ids:
                delete_query(db, InvoiceItem, InvoiceItem.invoice_id.in_(invoice_ids), dry_run, "invoice items")
            if document_ids:
                delete_query(db, DocumentRevision, DocumentRevision.document_id.in_(document_ids), dry_run, "document revisions")
            if budget_ids:
                delete_query(db, BudgetItem, BudgetItem.budget_id.in_(budget_ids), dry_run, "budget items")

            for model, column, label in [
                (Attendance, Attendance.project_id, "attendance"),
                (ProjectWorker, ProjectWorker.project_id, "project workers"),
                (Task, Task.project_id, "tasks"),
                (Expense, Expense.project_id, "expenses"),
                (ChangeOrder, ChangeOrder.project_id, "change orders"),
                (RFI, RFI.project_id, "RFIs"),
                (DrawingRegister, DrawingRegister.project_id, "drawings"),
                (CalculationRecord, CalculationRecord.project_id, "calculation records"),
                (Document, Document.project_id, "documents"),
                (Invoice, Invoice.project_id, "invoices"),
                (BOQItem, BOQItem.project_id, "BOQ items"),
                (Budget, Budget.project_id, "budgets"),
                (SitePhoto, SitePhoto.project_id, "site photos"),
                (SiteDiary, SiteDiary.project_id, "site diaries"),
                (MaterialConsumption, MaterialConsumption.project_id, "material consumption"),
                (MaterialTest, MaterialTest.project_id, "material tests"),
                (QCInspection, QCInspection.project_id, "QC inspections"),
                (NCReport, NCReport.project_id, "NCRs"),
                (SafetyIncident, SafetyIncident.project_id, "safety incidents"),
                (SafetyInspection, SafetyInspection.project_id, "safety inspections"),
                (ToolboxTalk, ToolboxTalk.project_id, "toolbox talks"),
                (PermitToWork, PermitToWork.project_id, "permits to work"),
                (RiskAssessment, RiskAssessment.project_id, "risk assessments"),
                (Activity, Activity.project_id, "schedule activities"),
                (EVMSnapshot, EVMSnapshot.project_id, "EVM snapshots"),
                (BIMModel, BIMModel.project_id, "BIM models"),
                (FuelLog, FuelLog.project_id, "fuel logs"),
                (Project, Project.id, "projects"),
            ]:
                delete_query(db, model, column.in_(demo_project_ids), dry_run, label)

        if demo_equipment_ids:
            delete_query(db, FuelLog, FuelLog.equipment_id.in_(demo_equipment_ids), dry_run, "equipment fuel logs")
            delete_query(db, Equipment, Equipment.id.in_(demo_equipment_ids), dry_run, "equipment")

        if demo_worker_ids:
            delete_query(db, Attendance, Attendance.worker_id.in_(demo_worker_ids), dry_run, "worker attendance")
            delete_query(db, ProjectWorker, ProjectWorker.worker_id.in_(demo_worker_ids), dry_run, "worker assignments")
            delete_query(db, Task, Task.assignee_id.in_(demo_worker_ids), dry_run, "worker tasks")
            delete_query(db, Worker, Worker.id.in_(demo_worker_ids), dry_run, "workers")

        if demo_client_ids:
            delete_query(db, Client, Client.id.in_(demo_client_ids), dry_run, "clients")

        delete_query(db, User, User.email.like("%.nagaforge.demo"), dry_run, "demo role users")
        delete_query(db, InventoryItem, InventoryItem.supplier == "Demo Supplier", dry_run, "inventory")

        if dry_run:
            db.rollback()
            print("No data deleted.")
        else:
            db.commit()
            print("Demo data cleanup complete.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
