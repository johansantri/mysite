# instructor/utils.py
import os
from django.template.loader import render_to_string
from weasyprint import HTML
from django.conf import settings

def generate_certificate_file(context, output_filename):
    html_string = render_to_string("instructor/certificate_template.html", context)
    output_path = os.path.join(settings.MEDIA_ROOT, "certificates", output_filename)
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    HTML(string=html_string).write_pdf(output_path)
    return output_path
