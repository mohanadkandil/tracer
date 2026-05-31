"""Faker-driven generators for 5 Bosch-style doc types. DE + EN. Filled + blank."""

from __future__ import annotations

import random
import uuid
from dataclasses import dataclass
from typing import Callable

from faker import Faker

from .schemas import DocType, Example, Lang, TextBuilder

# ---------- Faker pools ----------

FAKERS: dict[Lang, Faker] = {
    "de": Faker("de_DE"),
    "en": Faker("en_US"),
}


def _seed_all(seed: int) -> None:
    Faker.seed(seed)
    random.seed(seed)


# ---------- BOSCH employee roster ----------
# Closed set of identities that recur across documents. This is what makes the
# mosaic graph light up: same Hans Müller appears in 14 docs across HR, Finance,
# IT — exactly the cross-document re-identification pattern we pitch.

# (name, employee_id, email, dept_de, dept_en)
ROSTER: list[tuple[str, str, str, str, str]] = [
    ("Hans Müller",       "E-43217", "hans.mueller@bosch.example",      "Entwicklung",            "Engineering"),
    ("Anna Becker",       "E-22184", "anna.becker@bosch.example",       "Finanzen",               "Finance"),
    ("Tobias Wagner",     "E-91054", "tobias.wagner@bosch.example",     "Compliance & Risiko",    "Compliance & Risk"),
    ("Elena Fischer",     "E-31706", "elena.fischer@bosch.example",     "Digitale Betriebsführung", "Digital Operations"),
    ("Jonas Keller",      "E-50488", "jonas.keller@bosch.example",      "Einkauf",                "Procurement Ops"),
    ("Miriam Braun",      "E-67739", "miriam.braun@bosch.example",      "Recht",                  "Legal"),
    ("Philipp Neumann",   "E-12055", "philipp.neumann@bosch.example",   "Projektmanagement",      "Project Management"),
    ("Sara Hoffmann",     "E-20491", "sara.hoffmann@bosch.example",     "Projektmanagement",      "Project Management"),
    ("David Schmid",      "E-31705", "david.schmid@bosch.example",      "Entwicklung",            "Engineering"),
    ("Laura König",       "E-44820", "laura.koenig@bosch.example",      "Qualitätssicherung",     "Quality Assurance"),
    ("Klaus Hartmann",    "E-58371", "klaus.hartmann@bosch.example",    "Produktion",             "Manufacturing"),
    ("Ute Schäfer",       "E-66192", "ute.schaefer@bosch.example",      "Personalabteilung",      "Human Resources"),
    ("Stefan Bauer",      "E-77831", "stefan.bauer@bosch.example",      "Lieferkette",            "Supply Chain"),
    ("Katja Meyer",       "E-83014", "katja.meyer@bosch.example",       "IT-Service",             "IT Service Desk"),
    ("Andreas Lorenz",    "E-19527", "andreas.lorenz@bosch.example",    "Identity & Access",      "Identity & Access"),
    ("Monika Vogel",      "E-25683", "monika.vogel@bosch.example",      "Forschung & Entwicklung", "Research & Development"),
    ("Wolfgang Krause",   "E-37118", "wolfgang.krause@bosch.example",   "Recht",                  "Legal"),
    ("Ingrid Berger",     "E-49265", "ingrid.berger@bosch.example",     "Finanzen",               "Finance"),
    ("Matthias Hoffmann", "E-54072", "matthias.hoffmann@bosch.example", "Entwicklung",            "Engineering"),
    ("Claudia Roth",      "E-68943", "claudia.roth@bosch.example",      "Compliance & Risiko",    "Compliance & Risk"),
]


def pick_employee(lang: Lang) -> dict:
    """Sample one identity from the roster. Returns dict shaped for generators."""
    name, emp_id, email, dept_de, dept_en = random.choice(ROSTER)
    return {
        "name": name,
        "emp_id": emp_id,
        "email": email,
        "dept": dept_de if lang == "de" else dept_en,
    }


def pick_manager(employee_name: str) -> str:
    """Pick a manager who is not the employee themselves."""
    candidates = [r[0] for r in ROSTER if r[0] != employee_name]
    return random.choice(candidates)


# ---------- domain pools (closed-set) ----------

DEPARTMENTS_EN = [
    "Project Management",
    "Engineering",
    "Digital Operations",
    "Compliance & Risk",
    "Procurement Ops",
    "Quality Assurance",
    "Manufacturing",
    "Supply Chain",
    "Human Resources",
    "Finance",
    "IT Service Desk",
    "Identity & Access",
    "Legal",
    "Research & Development",
]

DEPARTMENTS_DE = [
    "Projektmanagement",
    "Entwicklung",
    "Digitale Betriebsführung",
    "Compliance & Risiko",
    "Einkauf",
    "Qualitätssicherung",
    "Produktion",
    "Lieferkette",
    "Personalabteilung",
    "Finanzen",
    "IT-Service",
    "Identity & Access",
    "Recht",
    "Forschung & Entwicklung",
]

SYSTEMS = [
    "Document Management Portal",
    "GRC Role Catalog",
    "ERP Sandbox",
    "Vendor Master Data",
    "BI Reporting Suite",
    "PLM System",
    "MES Production Floor",
    "Identity Provider Console",
]

EXPENSE_CATEGORIES_EN = ["Travel", "Meals", "Lodging", "Conference", "Training", "Office Supplies"]
EXPENSE_CATEGORIES_DE = ["Reise", "Verpflegung", "Übernachtung", "Konferenz", "Schulung", "Bürobedarf"]

INCIDENT_TYPES_EN = ["Data Handling", "Safety", "Security", "Access Control", "Phishing", "Lost Device"]
INCIDENT_TYPES_DE = ["Datenverarbeitung", "Sicherheit", "IT-Sicherheit", "Zugangskontrolle", "Phishing", "Verlorenes Gerät"]

DECISIONS_EN = ["Approved", "Rejected", "Approved", "Approved", "Conditionally Approved"]
DECISIONS_DE = ["Genehmigt", "Abgelehnt", "Genehmigt", "Genehmigt", "Bedingt genehmigt"]

CERTS = ["ISO 9001", "ISO 14001", "ISO 27001", "ISO 45001", "IATF 16949"]
RISK_LEVELS_EN = ["Low", "Medium", "High"]
RISK_LEVELS_DE = ["Niedrig", "Mittel", "Hoch"]

ACCESS_LEVELS_EN = ["Viewer", "Editor", "Admin", "Approver"]
ACCESS_LEVELS_DE = ["Leser", "Bearbeiter", "Administrator", "Genehmiger"]


# ---------- helpers ----------


def _employee_id() -> str:
    return f"E-{random.randint(10000, 99999)}"


def _signature_from_name(name: str) -> str:
    parts = name.replace(",", "").split()
    if len(parts) >= 2:
        return f"{parts[0][0]}. {parts[-1]}"
    return name


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:8]}"


def _amount_eur() -> str:
    return f"{random.uniform(15, 990):.2f} EUR"


def _date_en(fake: Faker) -> str:
    return fake.date_between(start_date="-2y", end_date="today").strftime("%d %b %Y")


def _date_de(fake: Faker) -> str:
    months = ["Jan", "Feb", "Mär", "Apr", "Mai", "Jun", "Jul", "Aug", "Sep", "Okt", "Nov", "Dez"]
    d = fake.date_between(start_date="-2y", end_date="today")
    return f"{d.day:02d} {months[d.month - 1]} {d.year}"


def _date(fake: Faker, lang: Lang) -> str:
    return _date_de(fake) if lang == "de" else _date_en(fake)


def _address_oneline(fake: Faker) -> str:
    raw = fake.address().replace("\n", ", ")
    return raw


def _tax_id_de() -> str:
    return f"DE{random.randint(100000000, 999999999)}"


def _tax_id_en() -> str:
    return f"VAT{random.randint(100000000, 999999999)}"


def _username(name: str) -> str:
    parts = name.replace(",", "").lower().split()
    if len(parts) >= 2:
        return f"{parts[0][0]}.{parts[-1]}"
    return parts[0]


# ---------- generators ----------


def gen_expense(lang: Lang) -> Example:
    fake = FAKERS[lang]
    b = TextBuilder()
    emp = pick_employee(lang)
    name = emp["name"]
    emp_id = emp["emp_id"]
    mgr = pick_manager(name)
    sig = _signature_from_name(mgr)
    dept = emp["dept"]
    cat = random.choice(EXPENSE_CATEGORIES_DE if lang == "de" else EXPENSE_CATEGORIES_EN)
    date1 = _date(fake, lang)
    date2 = _date(fake, lang)
    amt = _amount_eur()
    decision = random.choice(DECISIONS_DE if lang == "de" else DECISIONS_EN)

    if lang == "de":
        b.add("Spesenabrechnung (ausgefüllt)\n")
        b.add("Zweck: Beispiel einer erfassten Reisekostenabrechnung.\n")
        b.add("Mitarbeiter: "); b.add_entity(name, "PERSON"); b.add(" ("); b.add_entity(emp_id, "EMPLOYEE_ID"); b.add(")\n")
        b.add("Abteilung: "); b.add_entity(dept, "DEPARTMENT"); b.nl()
        b.add("Datum: "); b.add_entity(date1, "DATE"); b.nl()
        b.add("Kategorie: "); b.add(cat); b.nl()
        b.add("Betrag: "); b.add(amt); b.nl()
        b.add("Beschreibung: Bahnticket für Kundenworkshop (Hin- und Rückfahrt).\n\n")
        b.add("Spesenabrechnung (ausgefüllt) - Prüfung\n")
        b.add("Zusammenfassung: Gesamtbetrag: "); b.add(amt); b.add(". Belege beigefügt.\n")
        b.add("Vorgesetzter: "); b.add_entity(mgr, "PERSON"); b.nl()
        b.add("Entscheidung: "); b.add(decision); b.nl()
        b.add("Datum: "); b.add_entity(date2, "DATE"); b.nl()
        b.add("Unterschrift: "); b.add_entity(sig, "SIGNATURE"); b.nl()
    else:
        b.add("Expense Reimbursement (Filled)\n")
        b.add("Purpose: Example of a completed expense reimbursement record.\n")
        b.add("Employee: "); b.add_entity(name, "PERSON"); b.add(" ("); b.add_entity(emp_id, "EMPLOYEE_ID"); b.add(")\n")
        b.add("Department: "); b.add_entity(dept, "DEPARTMENT"); b.nl()
        b.add("Date: "); b.add_entity(date1, "DATE"); b.nl()
        b.add("Category: "); b.add(cat); b.nl()
        b.add("Amount: "); b.add(amt); b.nl()
        b.add("Description: Train ticket for customer workshop (round trip).\n\n")
        b.add("Expense Reimbursement (Filled) - Review\n")
        b.add("Summary: Total claimed: "); b.add(amt); b.add(". Receipts attached.\n")
        b.add("Manager: "); b.add_entity(mgr, "PERSON"); b.nl()
        b.add("Decision: "); b.add(decision); b.nl()
        b.add("Date: "); b.add_entity(date2, "DATE"); b.nl()
        b.add("Signature: "); b.add_entity(sig, "SIGNATURE"); b.nl()

    return Example(id=_new_id("exp"), doc_type="expense", lang=lang, text=b.text, entities=b.entities)


def gen_it_access(lang: Lang) -> Example:
    fake = FAKERS[lang]
    b = TextBuilder()
    emp = pick_employee(lang)
    name = emp["name"]
    user = _username(name)
    mgr = pick_manager(name)
    sig = _signature_from_name(mgr)
    dept = emp["dept"]
    system = random.choice(SYSTEMS)
    level = random.choice(ACCESS_LEVELS_DE if lang == "de" else ACCESS_LEVELS_EN)
    decision = random.choice(DECISIONS_DE if lang == "de" else DECISIONS_EN)
    date = _date(fake, lang)
    email = emp["email"]

    if lang == "de":
        b.add("IT-Systemzugriffsantrag (ausgefüllt)\n")
        b.add("Zweck: Beispiel eines erfassten IT-Zugriffsantrags.\n")
        b.add("Name: "); b.add_entity(name, "PERSON"); b.nl()
        b.add("Benutzer: "); b.add_entity(user, "USERNAME"); b.nl()
        b.add("E-Mail: "); b.add_entity(email, "EMAIL"); b.nl()
        b.add("Abteilung: "); b.add_entity(dept, "DEPARTMENT"); b.nl()
        b.add("Vorgesetzter: "); b.add_entity(mgr, "PERSON"); b.nl()
        b.add("System: "); b.add(system); b.nl()
        b.add("Zugriffsebene: "); b.add(level); b.nl()
        b.add("Begründung: Erforderlich für Projektdokumentation und Pflege kontrollierter Vorlagen.\n\n")
        b.add("Prüfung\n")
        b.add("Kommentare: Zugriff entspricht der Rolle; MFA verifiziert.\n")
        b.add("Genehmigung: "); b.add(decision); b.nl()
        b.add("Genehmiger: IT Governance Lead\n")
        b.add("Unterschrift: "); b.add_entity(sig, "SIGNATURE"); b.nl()
        b.add("Datum: "); b.add_entity(date, "DATE"); b.nl()
    else:
        b.add("IT System Access Request (Filled)\n")
        b.add("Purpose: Example of a completed IT access request.\n")
        b.add("Name: "); b.add_entity(name, "PERSON"); b.nl()
        b.add("Username: "); b.add_entity(user, "USERNAME"); b.nl()
        b.add("Email: "); b.add_entity(email, "EMAIL"); b.nl()
        b.add("Department: "); b.add_entity(dept, "DEPARTMENT"); b.nl()
        b.add("Manager: "); b.add_entity(mgr, "PERSON"); b.nl()
        b.add("System: "); b.add(system); b.nl()
        b.add("Access Level: "); b.add(level); b.nl()
        b.add("Justification: Required to maintain project documentation and manage controlled templates.\n\n")
        b.add("Review\n")
        b.add("Comments: Access aligns with role; MFA verified.\n")
        b.add("Approval: "); b.add(decision); b.nl()
        b.add("Approver: IT Governance Lead\n")
        b.add("Signature: "); b.add_entity(sig, "SIGNATURE"); b.nl()
        b.add("Date: "); b.add_entity(date, "DATE"); b.nl()

    return Example(id=_new_id("itr"), doc_type="it_access", lang=lang, text=b.text, entities=b.entities)


def gen_incident(lang: Lang) -> Example:
    fake = FAKERS[lang]
    b = TextBuilder()
    reporter_emp = pick_employee(lang)
    reporter = reporter_emp["name"]
    owner = pick_manager(reporter)
    sig = _signature_from_name(owner)
    dept = reporter_emp["dept"]
    itype = random.choice(INCIDENT_TYPES_DE if lang == "de" else INCIDENT_TYPES_EN)
    date1 = _date(fake, lang)
    date2 = _date(fake, lang)
    location = fake.city() + (", Floor " if lang == "en" else ", Etage ") + str(random.randint(1, 6))

    if lang == "de":
        b.add("Vorfallsmeldung (ausgefüllt)\n")
        b.add("Zweck: Beispiel eines dokumentierten Vorfalls.\n")
        b.add("Datum: "); b.add_entity(date1, "DATE"); b.nl()
        b.add("Standort: "); b.add(location); b.nl()
        b.add("Typ: "); b.add(itype); b.nl()
        b.add("Gemeldet von: "); b.add_entity(reporter, "PERSON"); b.nl()
        b.add("Abteilung: "); b.add_entity(dept, "DEPARTMENT"); b.nl()
        b.add("Beschreibung: Ein Dokument mit personenbezogenen Daten wurde versehentlich an einen falschen internen Verteiler weitergeleitet.\n\n")
        b.add("Prüfung\n")
        b.add("Grundursache: Falsche Auswahl der Empfängergruppe; keine sekundäre Prüfung.\n")
        b.add("Maßnahme: Einführung einer Pflicht-Empfängerprüfung\n")
        b.add("Verantwortlich: "); b.add_entity(owner, "PERSON"); b.nl()
        b.add("Frist: "); b.add_entity(date2, "DATE"); b.nl()
        b.add("Unterschrift: "); b.add_entity(sig, "SIGNATURE"); b.nl()
    else:
        b.add("Incident Report (Filled)\n")
        b.add("Purpose: Example of a documented incident.\n")
        b.add("Date: "); b.add_entity(date1, "DATE"); b.nl()
        b.add("Location: "); b.add(location); b.nl()
        b.add("Type: "); b.add(itype); b.nl()
        b.add("Reported by: "); b.add_entity(reporter, "PERSON"); b.nl()
        b.add("Department: "); b.add_entity(dept, "DEPARTMENT"); b.nl()
        b.add("Description: A document containing personal data was mistakenly shared to an incorrect internal distribution list.\n\n")
        b.add("Review\n")
        b.add("Root Cause: Incorrect selection of recipient group; no secondary review step.\n")
        b.add("Corrective Action: Introduce a mandatory recipient review checklist\n")
        b.add("Owner: "); b.add_entity(owner, "PERSON"); b.nl()
        b.add("Deadline: "); b.add_entity(date2, "DATE"); b.nl()
        b.add("Signature: "); b.add_entity(sig, "SIGNATURE"); b.nl()

    return Example(id=_new_id("inc"), doc_type="incident", lang=lang, text=b.text, entities=b.entities)


def gen_supplier(lang: Lang) -> Example:
    fake = FAKERS[lang]
    b = TextBuilder()
    company = fake.company()
    addr = _address_oneline(fake)
    # Supplier-side contact stays Faker (external party — fine to have unique)
    contact_name = fake.name()
    contact_email = fake.company_email()
    contact_phone = fake.phone_number()
    tax = _tax_id_de() if lang == "de" else _tax_id_en()
    iban = fake.iban() if hasattr(fake, "iban") else f"DE{random.randint(10**19, 10**20-1)}"
    cert = random.choice(CERTS)
    risk = random.choice(RISK_LEVELS_DE if lang == "de" else RISK_LEVELS_EN)
    decision = random.choice(DECISIONS_DE if lang == "de" else DECISIONS_EN)
    # Reviewer is internal — pulled from roster so we see Bosch staff reviewing suppliers
    reviewer = pick_employee(lang)["name"]

    if lang == "de":
        b.add("Lieferantenanlage (ausgefüllt)\n")
        b.add("Zweck: Beispiel einer abgeschlossenen Lieferantenanlage.\n")
        b.add("Firma: "); b.add_entity(company, "COMPANY"); b.nl()
        b.add("Adresse: "); b.add_entity(addr, "ADDRESS"); b.nl()
        b.add("Ansprechpartner: "); b.add_entity(contact_name, "PERSON"); b.nl()
        b.add("E-Mail: "); b.add_entity(contact_email, "EMAIL"); b.nl()
        b.add("Telefon: "); b.add_entity(contact_phone, "PHONE"); b.nl()
        b.add("Steuernummer: "); b.add_entity(tax, "TAX_ID"); b.nl()
        b.add("IBAN: "); b.add_entity(iban, "IBAN"); b.nl()
        b.add("Zertifizierung: "); b.add(cert); b.nl()
        b.add("Risikostufe: "); b.add(risk); b.nl()
        b.nl()
        b.add("Prüfung\n")
        b.add("Prüfer: "); b.add_entity(reviewer, "PERSON"); b.nl()
        b.add("Kommentare: Dokumente geprüft; Bankdaten ausstehend.\n")
        b.add("Genehmigung: "); b.add(decision); b.nl()
    else:
        b.add("Supplier Onboarding (Filled)\n")
        b.add("Purpose: Example of a completed supplier onboarding record.\n")
        b.add("Company: "); b.add_entity(company, "COMPANY"); b.nl()
        b.add("Address: "); b.add_entity(addr, "ADDRESS"); b.nl()
        b.add("Contact: "); b.add_entity(contact_name, "PERSON"); b.nl()
        b.add("Email: "); b.add_entity(contact_email, "EMAIL"); b.nl()
        b.add("Phone: "); b.add_entity(contact_phone, "PHONE"); b.nl()
        b.add("Tax ID: "); b.add_entity(tax, "TAX_ID"); b.nl()
        b.add("IBAN: "); b.add_entity(iban, "IBAN"); b.nl()
        b.add("Certification: "); b.add(cert); b.nl()
        b.add("Risk Level: "); b.add(risk); b.nl()
        b.nl()
        b.add("Review\n")
        b.add("Reviewer: "); b.add_entity(reviewer, "PERSON"); b.nl()
        b.add("Comments: Documents verified; banking details pending validation.\n")
        b.add("Approval: "); b.add(decision); b.nl()

    return Example(id=_new_id("sup"), doc_type="supplier", lang=lang, text=b.text, entities=b.entities)


def gen_training(lang: Lang) -> Example:
    fake = FAKERS[lang]
    b = TextBuilder()
    emp = pick_employee(lang)
    name = emp["name"]
    emp_id = emp["emp_id"]
    instructor = pick_manager(name)
    sig = _signature_from_name(instructor)
    dept = emp["dept"]
    date = _date(fake, lang)
    course = random.choice(["GDPR Awareness", "Information Security Basics", "Code of Conduct", "Anti-Bribery", "Fire Safety", "Cyber Hygiene"])
    score = random.randint(60, 100)

    if lang == "de":
        b.add("Schulungsbewertung (ausgefüllt)\n")
        b.add("Teilnehmer: "); b.add_entity(name, "PERSON"); b.add(" ("); b.add_entity(emp_id, "EMPLOYEE_ID"); b.add(")\n")
        b.add("Abteilung: "); b.add_entity(dept, "DEPARTMENT"); b.nl()
        b.add("Kurs: "); b.add(course); b.nl()
        b.add("Datum: "); b.add_entity(date, "DATE"); b.nl()
        b.add("Ergebnis: "); b.add(f"{score} / 100"); b.nl()
        b.add("Status: "); b.add("Bestanden" if score >= 70 else "Nicht bestanden"); b.nl()
        b.add("Dozent: "); b.add_entity(instructor, "PERSON"); b.nl()
        b.add("Unterschrift: "); b.add_entity(sig, "SIGNATURE"); b.nl()
    else:
        b.add("Training Evaluation (Filled)\n")
        b.add("Participant: "); b.add_entity(name, "PERSON"); b.add(" ("); b.add_entity(emp_id, "EMPLOYEE_ID"); b.add(")\n")
        b.add("Department: "); b.add_entity(dept, "DEPARTMENT"); b.nl()
        b.add("Course: "); b.add(course); b.nl()
        b.add("Date: "); b.add_entity(date, "DATE"); b.nl()
        b.add("Score: "); b.add(f"{score} / 100"); b.nl()
        b.add("Status: "); b.add("Passed" if score >= 70 else "Failed"); b.nl()
        b.add("Instructor: "); b.add_entity(instructor, "PERSON"); b.nl()
        b.add("Signature: "); b.add_entity(sig, "SIGNATURE"); b.nl()

    return Example(id=_new_id("trn"), doc_type="training", lang=lang, text=b.text, entities=b.entities)


# ---------- blank templates (no PII) ----------

BLANK_TEMPLATES_EN = {
    "expense": "Expense Form\nPurpose: Expense reimbursement.\nEmployee: ______\nDepartment: ______\nDate: ______\nCategory: ______\nAmount: ______\nDescription: ______\n\nReview\nManager: ______\nDecision: ______\nSignature: ______\nDate: ______\n",
    "it_access": "IT System Access Request Form\nName: ______\nUsername: ______\nEmail: ______\nDepartment: ______\nManager: ______\nSystem: ______\nAccess Level: ______\nJustification: ______\n\nReview\nApproval: ______\nApprover: ______\nSignature: ______\nDate: ______\n",
    "incident": "Incident Report\nDate: ______\nLocation: ______\nType: ______\nReported by: ______\nDescription: ______\n\nReview\nRoot Cause: ______\nCorrective Action: ______\nOwner: ______\nDeadline: ______\n",
    "supplier": "Supplier Onboarding\nCompany: ______\nAddress: ______\nContact: ______\nEmail: ______\nPhone: ______\nTax ID: ______\nIBAN: ______\nCertification: ______\nRisk Level: ______\n\nReview\nReviewer: ______\nApproval: ______\n",
    "training": "Training Evaluation\nParticipant: ______\nDepartment: ______\nCourse: ______\nDate: ______\nScore: ______\nStatus: ______\nInstructor: ______\nSignature: ______\n",
}

BLANK_TEMPLATES_DE = {
    "expense": "Spesenabrechnung\nMitarbeiter: ______\nAbteilung: ______\nDatum: ______\nKategorie: ______\nBetrag: ______\nBeschreibung: ______\n\nPrüfung\nVorgesetzter: ______\nEntscheidung: ______\nUnterschrift: ______\nDatum: ______\n",
    "it_access": "IT-Systemzugriffsantrag\nName: ______\nBenutzer: ______\nE-Mail: ______\nAbteilung: ______\nVorgesetzter: ______\nSystem: ______\nZugriffsebene: ______\nBegründung: ______\n\nPrüfung\nGenehmigung: ______\nGenehmiger: ______\nUnterschrift: ______\nDatum: ______\n",
    "incident": "Vorfallsmeldung\nDatum: ______\nStandort: ______\nTyp: ______\nGemeldet von: ______\nBeschreibung: ______\n\nPrüfung\nGrundursache: ______\nMaßnahme: ______\nVerantwortlich: ______\nFrist: ______\n",
    "supplier": "Lieferantenanlage\nFirma: ______\nAdresse: ______\nAnsprechpartner: ______\nE-Mail: ______\nTelefon: ______\nSteuernummer: ______\nIBAN: ______\nZertifizierung: ______\nRisikostufe: ______\n\nPrüfung\nPrüfer: ______\nGenehmigung: ______\n",
    "training": "Schulungsbewertung\nTeilnehmer: ______\nAbteilung: ______\nKurs: ______\nDatum: ______\nErgebnis: ______\nStatus: ______\nDozent: ______\nUnterschrift: ______\n",
}


def gen_blank(lang: Lang, doc_type: DocType) -> Example:
    text = (BLANK_TEMPLATES_DE if lang == "de" else BLANK_TEMPLATES_EN)[doc_type]
    return Example(
        id=_new_id(f"blank-{doc_type}"),
        doc_type=doc_type,
        lang=lang,
        is_template=True,
        is_filled=False,
        text=text,
        entities=[],
    )


GENERATORS: dict[str, Callable[[Lang], Example]] = {
    "expense": gen_expense,
    "it_access": gen_it_access,
    "incident": gen_incident,
    "supplier": gen_supplier,
    "training": gen_training,
}


@dataclass
class Mix:
    doc_type: DocType
    weight: float


DEFAULT_MIX: list[Mix] = [
    Mix("expense", 0.22),
    Mix("it_access", 0.22),
    Mix("incident", 0.18),
    Mix("supplier", 0.20),
    Mix("training", 0.18),
]


def sample_doc_type(rng: random.Random) -> DocType:
    r = rng.random()
    acc = 0.0
    for m in DEFAULT_MIX:
        acc += m.weight
        if r <= acc:
            return m.doc_type
    return DEFAULT_MIX[-1].doc_type


def generate_filled(n: int, lang_ratio_de: float = 0.5, seed: int = 42) -> list[Example]:
    _seed_all(seed)
    rng = random.Random(seed)
    out: list[Example] = []
    for _ in range(n):
        lang: Lang = "de" if rng.random() < lang_ratio_de else "en"
        dt = sample_doc_type(rng)
        ex = GENERATORS[dt](lang)
        assert ex.validate_spans(), f"span mismatch in {ex.id}"
        out.append(ex)
    return out


def generate_blanks(n: int, lang_ratio_de: float = 0.5, seed: int = 43) -> list[Example]:
    _seed_all(seed)
    rng = random.Random(seed)
    out: list[Example] = []
    doc_types: list[DocType] = ["expense", "it_access", "incident", "supplier", "training"]
    for _ in range(n):
        lang: Lang = "de" if rng.random() < lang_ratio_de else "en"
        dt = rng.choice(doc_types)
        out.append(gen_blank(lang, dt))
    return out
