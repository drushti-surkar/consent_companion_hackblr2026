"""
Generates a realistic-looking Terms of Service PDF for demo purposes.
Covers all clause types the classifier knows: data_rights, cancellation,
liability, payment, termination, arbitration, general.
Includes several high-risk clauses (risk_score 3) for dramatic demo effect.
"""

from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.enums import TA_JUSTIFY, TA_CENTER

OUTPUT = "SwiftPay_Terms_of_Service.pdf"

CLAUSES = [
    ("SWIFTPAY FINANCIAL SERVICES", "title"),
    ("Terms of Service and User Agreement", "subtitle"),
    ("Effective Date: January 1, 2025 | Version 4.2", "meta"),

    ("1. ACCEPTANCE OF TERMS", "heading"),
    ("""By downloading, installing, registering for, or using the SwiftPay application
("App"), you ("User") agree to be bound by these Terms of Service ("Terms"), our
Privacy Policy, and any additional terms incorporated herein by reference. If you do
not agree to these Terms in their entirety, you must immediately cease all use of
the App and delete it from your device. Your continued use of the App constitutes
your ongoing acceptance of any modifications to these Terms, which we may make at
any time without prior notice to you.""", "body"),

    ("2. DATA COLLECTION AND SHARING", "heading"),
    ("""2.1 SwiftPay collects the following categories of personal data: full legal name,
government-issued identification numbers (including Aadhaar, PAN, or passport),
date of birth, residential address, email address, mobile phone number, bank account
details and transaction history, device identifiers, IP address, GPS location data
(including precise real-time location when the App is in use or running in the
background), biometric data used for authentication, and any other information you
voluntarily provide.""", "body"),

    ("""2.2 You hereby grant SwiftPay an irrevocable, worldwide, royalty-free license to
use, process, transfer, and share your personal data with: (a) our parent company,
subsidiaries, and affiliated entities; (b) third-party advertising networks and data
brokers for targeted marketing purposes; (c) credit bureaus and financial
institutions; (d) government and regulatory agencies upon request; (e) prospective
buyers in the event of a merger, acquisition, or sale of all or part of our assets.
SwiftPay may sell anonymized or aggregated data derived from your usage to third
parties. You may not opt out of data sharing that is necessary for the operation of
the service.""", "body"),

    ("""2.3 SwiftPay may retain your personal data for up to ten (10) years following the
termination of your account, or longer if required by applicable law. You do not
have the right to request deletion of data that has been incorporated into aggregated
datasets or shared with third parties prior to your deletion request.""", "body"),

    ("3. LOCATION TRACKING", "heading"),
    ("""3.1 The App collects precise GPS location data continuously, including when the
App is running in the background. This location data is used to assess credit risk,
detect fraud, serve location-based advertisements, and may be shared with
third-party partners including advertisers, insurance companies, and data analytics
firms. You consent to this collection by installing the App. Disabling location
permissions will result in suspension of your account.""", "body"),

    ("4. PAYMENT TERMS AND AUTO-RENEWAL", "heading"),
    ("""4.1 SwiftPay Premium subscription is billed at ₹499 per month. Your subscription
will automatically renew at the end of each billing period unless you cancel at
least 7 days before the renewal date. Cancellation requests submitted less than 7
days before renewal will not take effect until the following billing cycle, and you
will be charged for the upcoming period.""", "body"),

    ("""4.2 In the event of a missed or failed payment, SwiftPay reserves the right to:
(a) charge a late fee of ₹250 per day until payment is received; (b) suspend or
terminate your account without notice; (c) report the delinquency to credit bureaus;
(d) engage third-party debt collection agencies and charge you for any associated
collection costs. Interest on overdue amounts accrues at 36% per annum.""", "body"),

    ("""4.3 All payments are non-refundable. SwiftPay does not provide refunds for
partially used subscription periods, even if you cancel your account or your account
is suspended due to a violation of these Terms.""", "body"),

    ("5. CANCELLATION AND TERMINATION", "heading"),
    ("""5.1 You may cancel your subscription at any time through the App settings.
Cancellation takes effect at the end of the current billing period. You will
continue to have access to the service until the end of the paid period, after which
your access will be revoked and your data may be deleted or retained per Section 2.3.""", "body"),

    ("""5.2 SwiftPay may terminate or suspend your account at any time, for any reason
or no reason, with or without notice, including but not limited to: violation of
these Terms, suspected fraudulent activity, extended inactivity, or at our sole
discretion. Upon termination, your right to use the App ceases immediately. You will
not be entitled to a refund of any prepaid fees.""", "body"),

    ("6. MANDATORY ARBITRATION AND CLASS ACTION WAIVER", "heading"),
    ("""6.1 PLEASE READ THIS SECTION CAREFULLY. IT AFFECTS YOUR LEGAL RIGHTS.
Any dispute, claim, or controversy arising out of or relating to these Terms or
your use of the App shall be resolved exclusively through binding arbitration
administered by the Indian Council of Arbitration under its rules. The arbitration
shall be conducted by a single arbitrator appointed by SwiftPay. The arbitration
shall take place in Bengaluru, Karnataka, India, regardless of where you reside.
The arbitrator's decision shall be final and binding.""", "body"),

    ("""6.2 BY AGREEING TO THESE TERMS, YOU WAIVE YOUR RIGHT TO A JURY TRIAL AND YOUR
RIGHT TO PARTICIPATE IN A CLASS ACTION LAWSUIT OR CLASS-WIDE ARBITRATION. You may
only bring claims against SwiftPay in your individual capacity. You expressly waive
any right to bring or participate in any class, collective, or representative action.""", "body"),

    ("""6.3 You must bring any claim within ninety (90) days of the date the cause of
action arose, or such claim shall be permanently barred, regardless of any statute
of limitations that would otherwise apply.""", "body"),

    ("7. LIMITATION OF LIABILITY", "heading"),
    ("""7.1 TO THE MAXIMUM EXTENT PERMITTED BY APPLICABLE LAW, SWIFTPAY SHALL NOT BE
LIABLE FOR ANY INDIRECT, INCIDENTAL, SPECIAL, CONSEQUENTIAL, OR PUNITIVE DAMAGES,
INCLUDING BUT NOT LIMITED TO LOSS OF PROFITS, DATA, GOODWILL, OR OTHER INTANGIBLE
LOSSES, ARISING OUT OF OR IN CONNECTION WITH YOUR USE OF THE APP, EVEN IF SWIFTPAY
HAS BEEN ADVISED OF THE POSSIBILITY OF SUCH DAMAGES.""", "body"),

    ("""7.2 SwiftPay's total cumulative liability to you for all claims arising from or
related to these Terms shall not exceed the amount you paid to SwiftPay in the
three (3) months preceding the event giving rise to the claim, or ₹100, whichever
is less.""", "body"),

    ("8. INTELLECTUAL PROPERTY", "heading"),
    ("""8.1 All content, features, and functionality of the App, including but not limited
to text, graphics, logos, and software, are the exclusive property of SwiftPay and
are protected by Indian and international intellectual property laws. You are granted
a limited, non-exclusive, non-transferable, revocable license to use the App solely
for personal, non-commercial purposes.""", "body"),

    ("9. CHANGES TO TERMS", "heading"),
    ("""9.1 SwiftPay reserves the right to modify these Terms at any time. We will notify
you of material changes by posting the new Terms in the App. Your continued use of
the App after such changes constitutes your acceptance. If you do not agree with the
modified Terms, your only remedy is to stop using the App and close your account.
No compensation will be provided for changes to these Terms.""", "body"),

    ("10. GOVERNING LAW", "heading"),
    ("""10.1 These Terms shall be governed by and construed in accordance with the laws
of India, without regard to conflict of law principles. Subject to the arbitration
clause in Section 6, you consent to the exclusive jurisdiction of courts located in
Bengaluru, Karnataka, India.""", "body"),

    ("11. CONTACT", "heading"),
    ("""If you have questions about these Terms, you may contact us at:
SwiftPay Financial Services Pvt. Ltd.
No. 42, 3rd Floor, MG Road, Bengaluru - 560001, Karnataka, India
legal@swiftpay.in | +91-80-4567-8900""", "body"),
]


def build_pdf():
    doc = SimpleDocTemplate(
        OUTPUT,
        pagesize=A4,
        leftMargin=2.5*cm, rightMargin=2.5*cm,
        topMargin=2.5*cm, bottomMargin=2.5*cm,
    )
    styles = getSampleStyleSheet()

    title_style = ParagraphStyle("title", parent=styles["Normal"],
        fontSize=18, fontName="Helvetica-Bold", alignment=TA_CENTER, spaceAfter=4)
    subtitle_style = ParagraphStyle("subtitle", parent=styles["Normal"],
        fontSize=13, fontName="Helvetica", alignment=TA_CENTER, spaceAfter=4)
    meta_style = ParagraphStyle("meta", parent=styles["Normal"],
        fontSize=9, fontName="Helvetica", alignment=TA_CENTER, spaceAfter=20, textColor="#888888")
    heading_style = ParagraphStyle("heading", parent=styles["Normal"],
        fontSize=11, fontName="Helvetica-Bold", spaceBefore=14, spaceAfter=6)
    body_style = ParagraphStyle("body", parent=styles["Normal"],
        fontSize=9.5, fontName="Helvetica", leading=15, alignment=TA_JUSTIFY, spaceAfter=8)

    style_map = {
        "title": title_style,
        "subtitle": subtitle_style,
        "meta": meta_style,
        "heading": heading_style,
        "body": body_style,
    }

    story = []
    for text, style_key in CLAUSES:
        story.append(Paragraph(text.replace("\n", " "), style_map[style_key]))
        if style_key == "meta":
            story.append(Spacer(1, 0.3*cm))

    doc.build(story)
    print(f"Generated: {OUTPUT}")


if __name__ == "__main__":
    build_pdf()
