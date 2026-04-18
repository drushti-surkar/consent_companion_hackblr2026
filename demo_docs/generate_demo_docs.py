"""
Generate 3 realistic demo documents with high-risk clauses for Consent Companion demos.

Documents:
  1. Rental Agreement — Bengaluru landlord with predatory clauses
  2. BPO Employment Offer Letter — exploitative non-compete + notice period
  3. HealthTrack App Privacy Policy — aggressive health data monetization
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER, TA_LEFT
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, HRFlowable
from reportlab.lib import colors

W, H = A4

def base_styles():
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "DocTitle", parent=styles["Title"],
        fontSize=16, leading=22, spaceAfter=6, alignment=TA_CENTER,
        textColor=colors.HexColor("#1a1a2e"),
    )
    subtitle = ParagraphStyle(
        "DocSubtitle", parent=styles["Normal"],
        fontSize=10, leading=14, spaceAfter=14, alignment=TA_CENTER,
        textColor=colors.HexColor("#444"),
    )
    heading = ParagraphStyle(
        "SecHeading", parent=styles["Normal"],
        fontSize=12, leading=16, spaceBefore=14, spaceAfter=6,
        fontName="Helvetica-Bold", textColor=colors.HexColor("#1a1a2e"),
    )
    body = ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9, leading=14, spaceAfter=6, alignment=TA_JUSTIFY,
    )
    fine = ParagraphStyle(
        "Fine", parent=styles["Normal"],
        fontSize=7.5, leading=11, spaceAfter=4, alignment=TA_JUSTIFY,
        textColor=colors.HexColor("#555"),
    )
    clause_num = ParagraphStyle(
        "ClauseNum", parent=styles["Normal"],
        fontSize=9, leading=14, spaceAfter=4, fontName="Helvetica-Bold",
    )
    return dict(title=title, subtitle=subtitle, heading=heading,
                body=body, fine=fine, clause_num=clause_num)

def hr():
    return HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#cccccc"), spaceAfter=8, spaceBefore=4)

# ─────────────────────────────────────────────────────────────
# DOCUMENT 1: Rental Agreement
# ─────────────────────────────────────────────────────────────

def make_rental_agreement():
    path = "Bengaluru_Rental_Agreement.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2.2*cm, bottomMargin=2.2*cm)
    s = base_styles()
    story = []

    story += [
        Paragraph("RESIDENTIAL LEASE AGREEMENT", s["title"]),
        Paragraph("THIS AGREEMENT is entered into on 1st April 2025<br/>BETWEEN the Landlord and the Tenant as described below", s["subtitle"]),
        hr(),
        Paragraph("PARTIES", s["heading"]),
        Paragraph("<b>Landlord:</b> Shri Ramesh Naidu, S/o Late Gopinath Naidu, residing at No. 14, 3rd Cross, Koramangala 5th Block, Bengaluru – 560095.", s["body"]),
        Paragraph("<b>Tenant:</b> [Tenant Name], aged [Age], employed at [Employer Name], presently residing at [Current Address].", s["body"]),
        Paragraph("<b>Property:</b> Flat No. 301, 3rd Floor, 'Sai Residency', No. 78, 12th Main Road, HSR Layout Sector 2, Bengaluru – 560102 (hereinafter 'the Premises').", s["body"]),
        Spacer(1, 6),
        hr(),
        Paragraph("SECTION 1 — TERM AND RENT", s["heading"]),
        Paragraph("1.1  The lease shall commence on <b>1st April 2025</b> and shall continue for a period of <b>eleven (11) months</b>.", s["body"]),
        Paragraph("1.2  The monthly rent shall be <b>Rs. 28,000/- (Rupees Twenty-Eight Thousand Only)</b>, payable on or before the <b>5th of each calendar month</b>.", s["body"]),
        Paragraph("1.3  <b>LATE PAYMENT PENALTY:</b> In the event rent is not received by the Landlord by the 7th of the month, the Tenant shall be liable to pay a late fee of Rs. 500/- per day for each day of delay beyond the 7th, compounding daily. This penalty shall be deemed agreed upon by execution of this agreement and no separate notice is required.", s["body"]),
        Paragraph("1.4  The Landlord reserves the right to revise the monthly rent by up to <b>15% upon giving 7 (seven) days written notice</b> to the Tenant. Such revision may occur at any time during the lease term and shall not be subject to challenge by the Tenant.", s["body"]),
        Spacer(1, 6),
        Paragraph("SECTION 2 — SECURITY DEPOSIT", s["heading"]),
        Paragraph("2.1  The Tenant agrees to pay a refundable security deposit of <b>Rs. 1,12,000/- (Four months' rent)</b> prior to taking possession.", s["body"]),
        Paragraph("2.2  The security deposit shall be refunded within <b>60 (sixty) days</b> of the Tenant vacating the premises, subject to deductions at the Landlord's sole discretion for: (a) any alleged damage to property; (b) any unpaid utility bills; (c) any cleaning charges assessed by the Landlord; (d) any re-painting costs if the Tenant has occupied the premises for more than 6 months; (e) any 'restoration costs' deemed necessary by the Landlord. The Landlord's assessment of deductions shall be final and binding.", s["body"]),
        Paragraph("2.3  No interest shall be payable by the Landlord on the security deposit amount regardless of the duration of the tenancy.", s["body"]),
        Spacer(1, 6),
        Paragraph("SECTION 3 — TERMINATION AND NOTICE PERIOD", s["heading"]),
        Paragraph("3.1  The Tenant is required to give the Landlord a minimum of <b>60 (sixty) days written notice</b> before vacating the premises.", s["body"]),
        Paragraph("3.2  The Landlord may terminate this agreement and require the Tenant to vacate within <b>15 (fifteen) days</b> for any of the following reasons: (a) non-payment of rent; (b) breach of any condition; (c) the Landlord's personal requirement of the premises; (d) any reason the Landlord deems appropriate at his discretion.", s["body"]),
        Paragraph("3.3  If the Tenant fails to vacate within the notice period, the Tenant shall be liable to pay <b>double the monthly rent</b> for every additional day of occupation, which may be recovered from the security deposit and/or through legal proceedings.", s["body"]),
        Spacer(1, 6),
        Paragraph("SECTION 4 — MAINTENANCE AND UTILITIES", s["heading"]),
        Paragraph("4.1  The Tenant shall bear all costs of electricity, water, gas, internet, and maintenance of fittings within the flat.", s["body"]),
        Paragraph("4.2  Any structural repair, maintenance of external walls, roof, or common area is the Landlord's responsibility; however, the Landlord may recover up to 50% of such costs from the Tenant if the Landlord determines (in his sole opinion) that Tenant usage contributed to the requirement for repair.", s["body"]),
        Paragraph("4.3  The Tenant shall not make any modifications, additions, or improvements to the premises without prior written consent of the Landlord. Any modifications made with or without consent shall become the property of the Landlord upon vacation.", s["body"]),
        Spacer(1, 6),
        Paragraph("SECTION 5 — RESTRICTIONS", s["heading"]),
        Paragraph("5.1  No pets of any kind are permitted on the premises.", s["body"]),
        Paragraph("5.2  Sub-letting or sharing of the premises with any person not listed in this agreement is strictly prohibited. Violation shall result in immediate termination.", s["body"]),
        Paragraph("5.3  The Tenant shall not use the premises for any commercial purpose, religious assembly, or political gathering.", s["body"]),
        Spacer(1, 6),
        Paragraph("SECTION 6 — ENTRY BY LANDLORD", s["heading"]),
        Paragraph("6.1  The Landlord or his authorised representative shall have the right to enter and inspect the premises at any reasonable time with <b>24 hours verbal or written notice</b>. In cases of alleged emergency, the Landlord may enter without any prior notice.", s["body"]),
        Paragraph("6.2  The Tenant consents to the Landlord photographing or video-recording the premises during any inspection for documentation purposes.", s["body"]),
        Spacer(1, 6),
        Paragraph("SECTION 7 — DISPUTE RESOLUTION", s["heading"]),
        Paragraph("7.1  Any dispute arising from this agreement shall first be referred to mediation conducted by a mediator appointed solely by the Landlord, at the Tenant's cost.", s["body"]),
        Paragraph("7.2  If mediation fails, disputes shall be subject to the exclusive jurisdiction of courts located in Bengaluru Urban district.", s["body"]),
        Spacer(1, 6),
        hr(),
        Paragraph("BY SIGNING BELOW, THE TENANT ACKNOWLEDGES HAVING READ, UNDERSTOOD, AND AGREED TO ALL TERMS AND CONDITIONS OF THIS AGREEMENT.", s["fine"]),
        Spacer(1, 20),
        Paragraph("Landlord Signature: ____________________    Date: __________", s["body"]),
        Spacer(1, 10),
        Paragraph("Tenant Signature:   ____________________    Date: __________", s["body"]),
        Spacer(1, 10),
        Paragraph("Witness 1: ____________________    Witness 2: ____________________", s["body"]),
    ]

    doc.build(story)
    print(f"Created: {path}")


# ─────────────────────────────────────────────────────────────
# DOCUMENT 2: BPO Employment Offer Letter
# ─────────────────────────────────────────────────────────────

def make_employment_offer():
    path = "TechServe_Employment_Offer.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2.2*cm, bottomMargin=2.2*cm)
    s = base_styles()
    story = []

    story += [
        Paragraph("TECHSERVE SOLUTIONS PRIVATE LIMITED", s["title"]),
        Paragraph("CIN: U72200KA2018PTC112345 | Registered Office: Plot 47, Electronic City Phase 1, Bengaluru – 560100", s["subtitle"]),
        hr(),
        Paragraph("EMPLOYMENT OFFER LETTER — CONFIDENTIAL", s["heading"]),
        Spacer(1, 6),
        Paragraph("Date: 3rd April 2025", s["body"]),
        Paragraph("Dear [Candidate Name],", s["body"]),
        Paragraph("We are pleased to offer you employment at TechServe Solutions Private Limited ('the Company') in the role of <b>Customer Experience Associate</b> at our Bengaluru operations centre, subject to the terms and conditions set forth in this letter.", s["body"]),
        Spacer(1, 8),
        Paragraph("CLAUSE 1 — COMPENSATION", s["heading"]),
        Paragraph("1.1  <b>Cost to Company (CTC):</b> Rs. 3,60,000/- per annum (Rs. 30,000/- per month). This is inclusive of all allowances, provident fund contributions, and statutory deductions.", s["body"]),
        Paragraph("1.2  <b>In-Hand Salary:</b> Your actual monthly take-home salary after all deductions shall be approximately Rs. 24,200/-. The difference between CTC and in-hand is not refundable under any circumstance.", s["body"]),
        Paragraph("1.3  Variable Performance Bonus of up to 10% of annual CTC is discretionary and shall be payable at the sole discretion of the Company based on parameters defined by Management. No entitlement to any bonus exists unless expressly communicated in writing separately.", s["body"]),
        Spacer(1, 6),
        Paragraph("CLAUSE 2 — PROBATION PERIOD", s["heading"]),
        Paragraph("2.1  You shall be on probation for the first <b>12 (twelve) months</b> of employment. During the probation period, your employment may be terminated by the Company with <b>7 (seven) days notice or payment in lieu thereof</b>.", s["body"]),
        Paragraph("2.2  During probation, you are not eligible for annual leave, sick leave beyond 3 days, or any Company health benefits.", s["body"]),
        Paragraph("2.3  Confirmation of employment post-probation is at the Company's sole discretion and is not automatic.", s["body"]),
        Spacer(1, 6),
        Paragraph("CLAUSE 3 — NOTICE PERIOD", s["heading"]),
        Paragraph("3.1  Post-confirmation, the Employee is required to serve a <b>90 (ninety) day notice period</b> before resignation, failing which the Employee shall pay the Company an amount equivalent to 3 months' gross salary as liquidated damages.", s["body"]),
        Paragraph("3.2  The Company reserves the right to terminate the Employee's services at any time by providing <b>30 (thirty) days notice</b> or payment in lieu thereof, at the Company's discretion.", s["body"]),
        Paragraph("3.3  The Company may, at its discretion, place the Employee on <b>garden leave</b> during the notice period, during which the Employee shall remain employed but shall not be permitted to attend office or access Company systems, yet remain bound by all confidentiality and non-compete obligations.", s["body"]),
        Spacer(1, 6),
        Paragraph("CLAUSE 4 — NON-COMPETE AND NON-SOLICITATION", s["heading"]),
        Paragraph("4.1  For a period of <b>24 (twenty-four) months following cessation of employment</b>, for any reason, the Employee shall not directly or indirectly:", s["body"]),
        Paragraph("(a) be employed by, consult for, or hold any interest in any entity engaged in customer experience, business process outsourcing, or voice-based support services within India;", s["body"]),
        Paragraph("(b) solicit or entice any current or former client of the Company with whom the Employee had contact during the last 12 months of employment;", s["body"]),
        Paragraph("(c) engage any current employee of the Company for employment elsewhere.", s["body"]),
        Paragraph("4.2  The Employee acknowledges that this restriction is reasonable given access to proprietary client information. Breach shall entitle the Company to seek injunctive relief and damages without proof of actual loss.", s["body"]),
        Spacer(1, 6),
        Paragraph("CLAUSE 5 — INTELLECTUAL PROPERTY", s["heading"]),
        Paragraph("5.1  All work product, inventions, processes, scripts, or methodologies created by the Employee during the course of employment, whether or not during working hours or using Company equipment, shall be the exclusive property of the Company.", s["body"]),
        Paragraph("5.2  The Employee hereby irrevocably assigns all present and future intellectual property rights in such work product to the Company.", s["body"]),
        Spacer(1, 6),
        Paragraph("CLAUSE 6 — MANDATORY OVERTIME AND SHIFT CHANGES", s["heading"]),
        Paragraph("6.1  The Employee agrees that the nature of the Company's business may require <b>overtime work, weekend shifts, and night shifts</b> at short notice. Refusal to comply with shift change requirements after due notice shall be treated as a disciplinary matter.", s["body"]),
        Paragraph("6.2  Overtime compensation shall be payable only where mandated by applicable law; otherwise, overtime is considered included within the agreed CTC.", s["body"]),
        Spacer(1, 6),
        Paragraph("CLAUSE 7 — TRAINING BOND", s["heading"]),
        Paragraph("7.1  The Company shall invest approximately Rs. 45,000/- in initial training for the Employee. In the event the Employee voluntarily resigns or is terminated for cause within <b>24 months of joining</b>, the Employee shall repay the Company the full training cost of Rs. 45,000/- as a debt, recoverable from final settlement.", s["body"]),
        Spacer(1, 6),
        Paragraph("CLAUSE 8 — MONITORING AND PRIVACY", s["heading"]),
        Paragraph("8.1  The Employee consents to monitoring of all communications made through Company systems including email, messaging platforms, and phone calls.", s["body"]),
        Paragraph("8.2  The Company may conduct background verification, drug testing, and periodic health assessments at its discretion.", s["body"]),
        Spacer(1, 6),
        Paragraph("CLAUSE 9 — GOVERNING LAW AND DISPUTE RESOLUTION", s["heading"]),
        Paragraph("9.1  This offer is governed by the laws of India. Any dispute shall be subject to binding arbitration conducted in Bengaluru before a single arbitrator appointed by the Company, whose decision shall be final.", s["body"]),
        Spacer(1, 6),
        hr(),
        Paragraph("This offer is valid for <b>5 (five) business days</b> from the date of issue. By signing below, you confirm unconditional acceptance of all terms and conditions in this offer letter.", s["fine"]),
        Spacer(1, 16),
        Paragraph("Authorised Signatory: ____________________    Designation: HR Manager", s["body"]),
        Spacer(1, 10),
        Paragraph("Employee Acceptance: ____________________    Date: __________", s["body"]),
    ]

    doc.build(story)
    print(f"Created: {path}")


# ─────────────────────────────────────────────────────────────
# DOCUMENT 3: HealthTrack App Privacy Policy
# ─────────────────────────────────────────────────────────────

def make_healthtrack_privacy():
    path = "HealthTrack_App_Privacy_Policy.pdf"
    doc = SimpleDocTemplate(path, pagesize=A4,
                            leftMargin=2.2*cm, rightMargin=2.2*cm,
                            topMargin=2.2*cm, bottomMargin=2.2*cm)
    s = base_styles()
    story = []

    story += [
        Paragraph("HEALTHTRACK INDIA PVT. LTD.", s["title"]),
        Paragraph("Privacy Policy and Terms of Service | Version 4.2 | Effective: 1 January 2025<br/>This document governs your use of the HealthTrack mobile application and all associated services.", s["subtitle"]),
        hr(),
        Paragraph("PLEASE READ THIS DOCUMENT CAREFULLY. BY CREATING AN ACCOUNT OR USING THE APP, YOU AGREE TO THESE TERMS IN THEIR ENTIRETY.", s["fine"]),
        Spacer(1, 8),

        Paragraph("SECTION 1 — INFORMATION WE COLLECT", s["heading"]),
        Paragraph("1.1  We collect the following categories of information when you use HealthTrack:", s["body"]),
        Paragraph("(a) <b>Personal Identifiers:</b> Full name, date of birth, Aadhaar number (optional but encouraged for identity verification), PAN number (for insurance integration), mobile number, email address, and residential address.", s["body"]),
        Paragraph("(b) <b>Health and Medical Data:</b> Symptoms you enter, medications you log, diagnoses confirmed or suspected, lab reports you upload, menstrual cycle data, pregnancy status, mental health questionnaire responses, body weight, blood glucose readings, blood pressure logs, and sleep patterns.", s["body"]),
        Paragraph("(c) <b>Biometric Data:</b> Heart rate data from connected wearables, step counts, ECG readings if enabled, and SpO2 measurements.", s["body"]),
        Paragraph("(d) <b>Behavioural Data:</b> App usage patterns, features accessed, time spent on each screen, search queries entered within the app.", s["body"]),
        Paragraph("(e) <b>Device Information:</b> Device model, operating system, IP address, approximate location (city-level), mobile carrier.", s["body"]),
        Spacer(1, 6),

        Paragraph("SECTION 2 — HOW WE USE YOUR INFORMATION", s["heading"]),
        Paragraph("2.1  We use your information for the following purposes:", s["body"]),
        Paragraph("(a) Providing personalised health recommendations and symptom analysis.", s["body"]),
        Paragraph("(b) <b>Sharing with third-party insurance partners</b> to generate insurance quotes and assess eligibility. By using this app, you consent to your health data being shared with insurance companies in our partner network for underwriting purposes.", s["body"]),
        Paragraph("(c) <b>Sharing with pharmaceutical companies</b> for research, product development, and targeted health communication campaigns. Your data is shared in 'de-identified' form; however, HealthTrack does not guarantee that re-identification is impossible.", s["body"]),
        Paragraph("(d) <b>Sale of anonymised and aggregated health datasets</b> to healthcare analytics firms, hospital chains, diagnostic laboratories, and government health agencies. The proceeds from such data sales contribute to keeping the app free for users.", s["body"]),
        Paragraph("(e) Internal analytics, machine learning model training, and product improvement.", s["body"]),
        Paragraph("(f) <b>Targeted advertising</b> based on your health conditions and behaviours, displayed within the app and shared with advertising networks.", s["body"]),
        Spacer(1, 6),

        Paragraph("SECTION 3 — SHARING WITH THIRD PARTIES", s["heading"]),
        Paragraph("3.1  We may share your personal and health data with:", s["body"]),
        Paragraph("(a) Insurance companies, TPAs (Third-Party Administrators), and health benefit managers.", s["body"]),
        Paragraph("(b) Pharmaceutical manufacturers and clinical research organisations.", s["body"]),
        Paragraph("(c) Hospital groups and diagnostic chains for appointment facilitation and record sharing.", s["body"]),
        Paragraph("(d) Employers, where the employer has a corporate wellness subscription — your individual-level data may be accessible to your employer's HR system unless you opt out at the time of account creation (opt-out is not available post account creation).", s["body"]),
        Paragraph("(e) Government agencies and law enforcement upon request without prior notice to the user.", s["body"]),
        Paragraph("(f) Data brokers and analytics companies for market research.", s["body"]),
        Spacer(1, 6),

        Paragraph("SECTION 4 — DATA RETENTION", s["heading"]),
        Paragraph("4.1  We retain your personal and health data for a minimum of <b>10 (ten) years</b> from the date of collection, even after account deletion. Anonymised data may be retained indefinitely.", s["body"]),
        Paragraph("4.2  Account deletion removes your login access but does not result in deletion of health data already collected and shared with third parties.", s["body"]),
        Paragraph("4.3  Backups of your data are maintained on servers in India, Singapore, and the United States. Data processed in Singapore and the US is subject to the privacy laws of those jurisdictions in addition to Indian law.", s["body"]),
        Spacer(1, 6),

        Paragraph("SECTION 5 — SUBSCRIPTION AND CANCELLATION", s["heading"]),
        Paragraph("5.1  HealthTrack Premium is available at Rs. 299/- per month or Rs. 2,499/- per year.", s["body"]),
        Paragraph("5.2  All subscriptions auto-renew at the then-current price without prior notification. You must cancel at least <b>48 hours before the renewal date</b> to avoid being charged.", s["body"]),
        Paragraph("5.3  Cancellation of subscription does not entitle the user to any refund of amounts already charged, including amounts charged for the current billing period.", s["body"]),
        Paragraph("5.4  HealthTrack reserves the right to change subscription pricing with 7 days' notice communicated via in-app notification only (no email or SMS obligation).", s["body"]),
        Spacer(1, 6),

        Paragraph("SECTION 6 — LIMITATION OF LIABILITY", s["heading"]),
        Paragraph("6.1  HealthTrack is a general wellness application. It is <b>not a medical device, not a diagnostic tool, and not a substitute for professional medical advice</b>. Any health recommendations generated are informational only.", s["body"]),
        Paragraph("6.2  HealthTrack shall not be liable for any harm, medical condition, misdiagnosis, delay in treatment, financial loss, or any other consequence resulting from reliance on information provided by the app, to the maximum extent permitted by applicable law.", s["body"]),
        Paragraph("6.3  Our total aggregate liability to any user shall not exceed the amount paid by the user in subscription fees in the 3 months preceding the claim — subject to a maximum of Rs. 897/- (three months' Premium subscription).", s["body"]),
        Spacer(1, 6),

        Paragraph("SECTION 7 — ARBITRATION AND WAIVER OF CLASS ACTIONS", s["heading"]),
        Paragraph("7.1  <b>YOU AGREE THAT ANY DISPUTE WITH HEALTHTRACK SHALL BE RESOLVED THROUGH BINDING ARBITRATION AND NOT THROUGH COURT PROCEEDINGS.</b> By using this app you waive the right to participate in any class-action lawsuit against HealthTrack.", s["body"]),
        Paragraph("7.2  Arbitration shall be conducted by an arbitrator appointed by HealthTrack from its panel of approved arbitrators, in Bengaluru, in English, at the user's cost unless the arbitrator determines the claim is meritorious.", s["body"]),
        Spacer(1, 6),

        Paragraph("SECTION 8 — CHANGES TO THIS POLICY", s["heading"]),
        Paragraph("8.1  HealthTrack may update this Privacy Policy at any time. Continued use of the app after the effective date of any change constitutes your acceptance of the new policy. We may or may not notify users of changes via in-app notification.", s["body"]),
        Spacer(1, 6),
        hr(),
        Paragraph("By tapping 'I Agree' or continuing to use HealthTrack, you confirm you have read, understood, and accepted this Privacy Policy and Terms of Service in their entirety, including the sharing of your health data with insurance partners, pharmaceutical companies, and advertisers.", s["fine"]),
    ]

    doc.build(story)
    print(f"Created: {path}")


if __name__ == "__main__":
    import os
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    make_rental_agreement()
    make_employment_offer()
    make_healthtrack_privacy()
    print("\nAll 3 demo documents generated successfully.")
