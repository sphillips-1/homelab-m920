from pathlib import Path

from authentik.brands.models import Brand


stylesheet_path = Path("/branding/bookshelf.css")
background_path = "/static/dist/assets/images/bookshelf-background.svg"
interface_background = """background:
linear-gradient(rgba(22, 12, 8, 0.42), rgba(15, 8, 6, 0.68)),
url('/static/dist/assets/images/bookshelf-background.svg') center / cover fixed;
"""

if not stylesheet_path.is_file():
    raise RuntimeError(f"Bookshelf stylesheet is missing: {stylesheet_path}")

stylesheet = stylesheet_path.read_text(encoding="utf-8")
brand = Brand.objects.filter(default=True).first()
if brand is None:
    raise RuntimeError("Authentik has no default Brand to reconcile")

changed = []
if brand.branding_custom_css != stylesheet:
    brand.branding_custom_css = stylesheet
    changed.append("branding_custom_css")
if brand.branding_default_flow_background != background_path:
    brand.branding_default_flow_background = background_path
    changed.append("branding_default_flow_background")

attributes = dict(brand.attributes or {})
settings = dict(attributes.get("settings") or {})
theme = dict(settings.get("theme") or {})
if theme.get("background") != interface_background:
    theme["background"] = interface_background
    settings["theme"] = theme
    attributes["settings"] = settings
    brand.attributes = attributes
    changed.append("attributes")

if changed:
    brand.save(update_fields=changed)
    print(f"Updated default Authentik Brand: {', '.join(changed)}")
else:
    print("Default Authentik Brand bookshelf theme is already current")
