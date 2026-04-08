import re

from bs4 import BeautifulSoup

from moodler_mcp.client import fetch_page


async def scrape_course_contents(course_id: int) -> list[dict]:
    """Scrape the course page to extract sections and activities.

    Returns a list of section dicts, each containing:
    - name: section title
    - summary: section summary text
    - modules: list of activity dicts with name, type, url, description
    """
    html = await fetch_page(f"/course/view.php?id={course_id}")
    soup = BeautifulSoup(html, "html.parser")

    sections = []

    for section_el in soup.select("li[id^='section-']"):
        section_name_el = section_el.select_one(
            "[data-sectionname], .sectionname, .section-title"
        )
        section_name = ""
        if section_name_el:
            section_name = (
                section_name_el.get("data-sectionname")
                or section_name_el.get_text(strip=True)
                or ""
            )

        summary_el = section_el.select_one(".summary, .section_availability")
        summary = summary_el.get_text(strip=True) if summary_el else ""

        modules = []
        seen_ids = set()
        for activity in section_el.select("li.activity"):
            mod_id = ""
            id_attr = activity.get("id", "")
            id_match = re.search(r"module-(\d+)", id_attr)
            if id_match:
                mod_id = id_match.group(1)
                if mod_id in seen_ids:
                    continue
                seen_ids.add(mod_id)

            mod_name = activity.get("data-activityname", "")
            if not mod_name:
                mod_name_el = activity.select_one(
                    ".activityname .instancename, .aalink .instancename, "
                    ".activity-name-text, .cm_name"
                )
                if not mod_name_el:
                    continue
                # Get text but remove hidden accessibility labels
                for child in mod_name_el.select(".accesshide, .sr-only"):
                    child.decompose()
                mod_name = mod_name_el.get_text(strip=True)

            mod_type = ""
            classes = activity.get("class", [])
            if isinstance(classes, list):
                classes = " ".join(classes)
            type_match = re.search(r"modtype_(\w+)", classes)
            if type_match:
                mod_type = type_match.group(1)

            mod_url = ""
            link = activity.select_one("a[href*='/mod/']")
            if link:
                mod_url = link.get("href", "")

            desc_el = activity.select_one(".contentafterlink, .activity-description")
            description = desc_el.get_text(strip=True) if desc_el else ""

            modules.append({
                "id": mod_id,
                "name": mod_name,
                "type": mod_type,
                "url": mod_url,
                "description": description,
            })

        sections.append({
            "name": section_name,
            "summary": summary,
            "modules": modules,
        })

    return sections
