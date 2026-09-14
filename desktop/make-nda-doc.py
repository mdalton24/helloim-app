from docx import Document
from docx.shared import Pt, Inches, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.section import WD_SECTION
import os

OUT = "/tmp/NameOS-Designer-NDA.docx"
d = Document()
st = d.styles["Normal"]; st.font.name = "Calibri"; st.font.size = Pt(11)
st.paragraph_format.space_after = Pt(8)

def h(t, lvl=1): d.add_heading(t, level=lvl)
def p(t, bold=False, italic=False, align=None, size=None):
    par = d.add_paragraph(); r = par.add_run(t)
    r.bold = bold; r.italic = italic
    if size: r.font.size = Pt(size)
    if align: par.alignment = align
    return par

title = d.add_heading("MUTUAL NON-DISCLOSURE AND WORK PRODUCT AGREEMENT", 0)
title.alignment = WD_ALIGN_PARAGRAPH.CENTER

p("vDesktop, LLC", bold=True, align=WD_ALIGN_PARAGRAPH.CENTER)
p("NameOS — design and user-experience engagement",
  italic=True, align=WD_ALIGN_PARAGRAPH.CENTER)

p("")
p("This Agreement is entered into as of ______________________ (the “Effective "
  "Date”) by and between:")

t = d.add_table(rows=2, cols=2); t.style = "Table Grid"
c = t.rows[0].cells
c[0].text = "Company"
c[1].text = ("vDesktop, LLC, a limited liability company\n"
             "Address: ______________________________________\n"
             "Email:   ______________________________________")
c = t.rows[1].cells
c[0].text = "Recipient"
c[1].text = ("Name:    ______________________________________\n"
             "Entity (if any): ______________________________\n"
             "Address: ______________________________________\n"
             "Email:   ______________________________________")

p("")
p("Company and Recipient are each a “Party” and together the “Parties.”")

h("1. Purpose", 1)
p("Company is developing a desktop software product presently known as NameOS. Company "
  "wishes to engage Recipient to review, critique and produce design and user-experience "
  "work for that product and its associated website (the “Purpose”). To do so, "
  "Company will disclose non-public information about the product, including its "
  "interface, screenshots, source materials, roadmap, positioning and competitive "
  "analysis. This Agreement governs that disclosure and the ownership of anything "
  "Recipient produces.")

h("2. Confidential Information", 1)
p("“Confidential Information” means any non-public information disclosed by a "
  "Party to the other, in any form, whether or not marked confidential, that a reasonable "
  "person would understand to be confidential given its nature and the circumstances of "
  "disclosure. Without limiting that, it expressly includes:")
for i in [
  "The document titled “NameOS — interface breakdown” and every screenshot, "
  "image, wireframe, token value and description contained in it;",
  "Any pre-release build, installer, binary or source code of NameOS, and any credential, "
  "key or account made available to Recipient;",
  "Product plans, roadmap, unreleased features, pricing intentions, positioning, "
  "competitive analysis, user research, and business or financial information;",
  "The existence, scope and terms of this Agreement and of any engagement between the "
  "Parties;",
  "Any information Recipient learns about Company’s customers, testers or personnel.",
]:
    d.add_paragraph(i, style="List Bullet")

h("3. What is not confidential", 1)
p("Confidential Information does not include information that Recipient can demonstrate by "
  "written record: (a) was already lawfully known to Recipient without any obligation of "
  "confidence before disclosure; (b) is or becomes public through no act or omission of "
  "Recipient; (c) is lawfully received from a third party free of any obligation of "
  "confidence; or (d) was independently developed by Recipient without use of or reference "
  "to the Confidential Information.")

h("4. Obligations", 1)
p("Recipient shall:")
for i in [
  "Use the Confidential Information solely for the Purpose and for no other reason;",
  "Not disclose it to any third party without Company’s prior written consent, except "
  "to Recipient’s own employees or subcontractors who need it for the Purpose and who "
  "are bound by written obligations at least as protective as these — for whose acts "
  "and omissions Recipient remains fully responsible;",
  "Protect it with at least the degree of care Recipient uses for its own confidential "
  "information, and in no event less than reasonable care;",
  "Not copy, reproduce, publish, post or transmit it beyond what the Purpose requires;",
  "Not upload, paste or submit it to any third-party artificial-intelligence service, "
  "large language model, cloud tool or online platform that may retain, train on or "
  "disclose it, without Company’s prior written consent;",
  "Not reverse engineer, decompile or disassemble any software provided, except to the "
  "extent that restriction is unenforceable by law;",
  "Notify Company promptly in writing on becoming aware of any unauthorised use or "
  "disclosure, and cooperate in limiting the harm.",
]:
    d.add_paragraph(i, style="List Bullet")

h("5. Compelled disclosure", 1)
p("If Recipient is required by law, subpoena or court order to disclose Confidential "
  "Information, Recipient may do so, provided that Recipient gives Company prompt written "
  "notice (unless legally prohibited), discloses only the portion legally required, and "
  "makes reasonable efforts to obtain confidential treatment for it.")

h("6. No publicity, no portfolio use", 1)
p("Recipient shall not name Company, vDesktop, LLC, NameOS, or any product, screenshot or "
  "asset covered by this Agreement in any portfolio, case study, website, social media "
  "post, presentation, pitch or press statement without Company’s prior written "
  "consent, which Company may grant or withhold at its sole discretion. This restriction "
  "survives termination. Company may grant portfolio permission in writing for specified "
  "materials after public launch.")

h("7. Work product and ownership", 1)
p("All designs, wireframes, mockups, prototypes, icons, illustrations, layouts, "
  "specifications, code, copy, research and other materials created by Recipient in "
  "connection with the Purpose (the “Work Product”) are works made for hire owned "
  "by Company. To the extent any Work Product does not qualify as a work made for hire, "
  "Recipient hereby irrevocably assigns to Company all right, title and interest in and to "
  "it worldwide, including all copyright, trademark, trade secret, moral and other "
  "intellectual property rights, effective on creation and without further consideration "
  "beyond that owed under the Parties’ engagement.")
p("Recipient shall execute any further documents Company reasonably requests to perfect, "
  "record or enforce that assignment.")
p("Pre-existing tools. If Recipient incorporates into the Work Product any material "
  "Recipient owned before this engagement or developed independently of it, Recipient "
  "shall identify that material in writing and grants Company a perpetual, worldwide, "
  "irrevocable, royalty-free, sublicensable licence to use, modify and distribute it as "
  "part of the Work Product. Recipient shall not incorporate any third-party or "
  "open-source material whose licence would restrict Company’s use or require "
  "disclosure of Company’s own code, without Company’s prior written consent.")
p("Originality. Recipient warrants that the Work Product is original to Recipient, does "
  "not infringe the rights of any third party, and does not include material generated by "
  "a third-party service under terms that would encumber Company’s ownership of it.")

h("8. No licence, no obligation", 1)
p("Nothing in this Agreement grants Recipient any licence or right in Company’s "
  "intellectual property except the limited right to use Confidential Information for the "
  "Purpose. Confidential Information is provided “as is,” without warranty of any "
  "kind. Nothing in this Agreement obligates either Party to disclose anything, to enter "
  "into any further agreement, or to proceed with any engagement.")

h("9. Return and destruction", 1)
p("On Company’s written request, or on termination of the engagement, Recipient shall "
  "promptly deliver to Company or destroy all Confidential Information and all copies, "
  "notes and derivatives of it in Recipient’s possession or control, in every medium "
  "and on every device and cloud account, and shall certify that destruction in writing "
  "within ten (10) days. Recipient may retain one archival copy solely to the extent "
  "required by law or by an automated backup system it cannot reasonably purge; any such "
  "retained copy remains subject to this Agreement for as long as it is retained.")

h("10. Term and survival", 1)
p("This Agreement takes effect on the Effective Date and continues for three (3) years "
  "after the last disclosure of Confidential Information, except that obligations "
  "concerning any information that constitutes a trade secret continue for as long as that "
  "information remains a trade secret under applicable law. Sections 6, 7, 9, 10, 11 and 12 "
  "survive termination.")

h("11. Remedies", 1)
p("Recipient acknowledges that a breach of this Agreement may cause Company irreparable "
  "harm for which monetary damages would be an inadequate remedy, and agrees that Company "
  "is entitled to seek injunctive relief and specific performance in addition to any other "
  "remedy available at law or in equity, without the necessity of posting a bond. The "
  "prevailing Party in any action to enforce this Agreement is entitled to recover its "
  "reasonable attorneys’ fees and costs.")

h("12. General", 1)
p("Governing law. This Agreement is governed by the laws of the State of "
  "______________________, without regard to its conflict-of-laws rules, and the Parties "
  "consent to the exclusive jurisdiction and venue of the state and federal courts located "
  "in ______________________ County in that state.")
p("Entire agreement. This Agreement is the entire understanding between the Parties on its "
  "subject matter and supersedes all prior discussions. It may be amended only in a writing "
  "signed by both Parties.")
p("No waiver. A failure to enforce any provision is not a waiver of it or of any other "
  "provision.")
p("Severability. If any provision is held unenforceable, it shall be modified to the "
  "minimum extent necessary to make it enforceable, and the remainder stays in force.")
p("Assignment. Recipient may not assign this Agreement without Company’s written "
  "consent. Company may assign it in connection with a merger, reorganisation or sale of "
  "substantially all of its assets.")
p("Independent contractor. Nothing here creates an employment, partnership, joint venture "
  "or agency relationship between the Parties.")
p("Counterparts and signatures. This Agreement may be signed in counterparts and by "
  "electronic signature, each of which is an original and all of which together are one "
  "instrument.")

d.add_page_break()
h("Signatures", 1)
p("The Parties execute this Agreement as of the Effective Date.")
p("")

sig = d.add_table(rows=5, cols=2); sig.style = "Table Grid"
labels = [
  ("COMPANY — vDesktop, LLC", "RECIPIENT"),
  ("Signature: ______________________________", "Signature: ______________________________"),
  ("Name: ___________________________________", "Name: ___________________________________"),
  ("Title: __________________________________", "Title: __________________________________"),
  ("Date: ___________________________________", "Date: ___________________________________"),
]
for i,(a,b) in enumerate(labels):
    sig.rows[i].cells[0].text = a
    sig.rows[i].cells[1].text = b
sig.rows[0].cells[0].paragraphs[0].runs[0].bold = True
sig.rows[0].cells[1].paragraphs[0].runs[0].bold = True

p("")
p("")
note = d.add_paragraph()
r = note.add_run("Note for Company: this is a working draft prepared for a design "
  "engagement, not legal advice. Two blanks must be filled before it is sent — the "
  "governing state and county in Section 12, and the address block on page one. Have "
  "counsel review it before it is used repeatedly.")
r.italic = True; r.font.size = Pt(9); r.font.color.rgb = RGBColor(0x60,0x60,0x60)

d.save(OUT)
print("saved", OUT, os.path.getsize(OUT))
