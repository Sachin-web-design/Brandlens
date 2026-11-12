"""Creates the demo logo and the sample files used to try the upload feature (all fictional, generated here)."""
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
A, S = ROOT / "data" / "assets", ROOT / "data" / "samples"
A.mkdir(parents=True, exist_ok=True)
S.mkdir(parents=True, exist_ok=True)
G, MINT, CHAR = (15, 110, 86), (225, 245, 238), (44, 44, 42)


def font(n):
    return ImageFont.load_default(size=n)


def logo():
    im = Image.new("RGB", (256, 256), G)
    d = ImageDraw.Draw(im)
    d.ellipse((38, 38, 218, 218), fill=(255, 255, 255))
    d.ellipse((88, 70, 190, 172), fill=G)
    d.polygon([(70, 200), (128, 120), (186, 200)], fill=(255, 255, 255))
    d.rectangle((118, 150, 138, 210), fill=G)
    im.save(A / "logo.png")
    return im


def ok_post(lg):
    im = Image.new("RGB", (800, 800), MINT)
    d = ImageDraw.Draw(im)
    d.rectangle((0, 560, 800, 800), fill=G)
    d.text((60, 120), "Whole oats.", fill=CHAR, font=font(96))
    d.text((60, 250), "8 g of protein", fill=CHAR, font=font(70))
    d.text((60, 600), "Nourish Daily oat bar", fill=(255, 255, 255), font=font(48))
    im.paste(lg.resize((130, 130)), (630, 620))
    im.save(S / "ok_post.png")


def bad_post():
    im = Image.new("RGB", (800, 800), (255, 255, 255))
    d = ImageDraw.Draw(im)
    d.rectangle((0, 0, 800, 330), fill=(255, 46, 147))
    d.rectangle((0, 560, 800, 800), fill=(235, 255, 40))
    d.text((60, 400), "MEGA SALE TODAY", fill=(205, 205, 205), font=font(80))
    d.text((60, 500), "Everything must go", fill=(215, 215, 215), font=font(52))
    im.save(S / "bad_post.png")


def brief():
    from docx import Document
    from docx.shared import Inches
    d = Document()
    d.add_heading("Launch brief: campus stall week", 1)
    d.add_paragraph("Hey guys, our new oat bar is the best snack on campus. One bar costs Rs 59 and it is guaranteed "
                    "to keep you full. Partnered with a student creator for the launch.")
    d.add_paragraph("Each bar has 8 g of protein and is made with whole oats.")
    d.add_picture(str(S / "ok_post.png"), width=Inches(2.2))
    d.add_picture(str(S / "bad_post.png"), width=Inches(2.2))
    d.save(S / "launch_brief.docx")
    # give the first picture an alt text and leave the second without one
    from docx import Document as D2
    dd = D2(str(S / "launch_brief.docx"))
    ns = "{http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing}docPr"
    props = list(dd.element.body.iter(ns))
    props[0].set("descr", "Nourish Daily oat bar post with the text Whole oats, 8 g of protein")
    props[1].set("descr", "")
    dd.save(S / "launch_brief.docx")


def flyer():
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(str(S / "campus_flyer.pdf"), pagesize=A4)
    y = 780
    for line in ["Nourish Daily oat bars: the best snack for the fest!!!",
                 "100% safe and guaranteed to help you lose weight.",
                 "Each bar has 12 g of protein. Only Rs 49.",
                 "Diwali special: flat 20% off on all bars.",
                 "Made with whole oats and no added preservatives."]:
        c.drawString(60, y, line)
        y -= 28
    c.save()


if __name__ == "__main__":
    lg = logo()
    ok_post(lg)
    bad_post()
    brief()
    flyer()
    print("samples written to", S)
