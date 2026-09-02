from pathlib import Path

from authentik.brands.models import Brand


stylesheet_path = Path("/branding/bookshelf.css")
background_path = "/static/dist/assets/images/bookshelf-background.svg"
logo_path = "/static/dist/assets/images/shelfgoblin-logo.svg"
favicon_path = "/static/dist/assets/images/shelfgoblin-favicon.svg"
legacy_interface_background = """background:
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
if brand.branding_logo != logo_path:
    brand.branding_logo = logo_path
    changed.append("branding_logo")
if brand.branding_favicon != favicon_path:
    brand.branding_favicon = favicon_path
    changed.append("branding_favicon")

attributes = dict(brand.attributes or {})
settings = dict(attributes.get("settings") or {})
theme = dict(settings.get("theme") or {})
if theme.get("background") == legacy_interface_background:
    del theme["background"]
    if theme:
        settings["theme"] = theme
    else:
        settings.pop("theme", None)
    if settings:
        attributes["settings"] = settings
    else:
        attributes.pop("settings", None)
    brand.attributes = attributes
    changed.append("attributes")

if changed:
    brand.save(update_fields=changed)
    print(f"Updated default Authentik Brand: {', '.join(changed)}")
else:
    print("Default Authentik Brand bookshelf theme is already current")
