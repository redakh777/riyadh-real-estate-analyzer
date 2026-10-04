import re
from urllib.parse import urlsplit


def extract_district(row):
    link = str(row.get("link", ""))
    path_parts = [part for part in urlsplit(link).path.strip("/").split("/") if part]

    try:
        city_index = path_parts.index("riyadh")
    except ValueError:
        city_index = -1

    district_index = city_index + 2
    if city_index >= 0 and district_index < len(path_parts):
        district_slug = path_parts[district_index].strip()
        if district_slug and district_slug.lower() not in {
            "all",
            "properties",
            "real-estate",
        }:
            return " ".join(
                word.capitalize()
                for word in district_slug.replace("_", "-").split("-")
                if word
            )

    raw_info = str(row.get("raw_info", ""))
    match = re.search(
        r"\bin Riyadh\s+(.+?)(?:§|[�$¥€]|\d|/annually|\bannually\b|\bmonthly\b|$)",
        raw_info,
        re.IGNORECASE,
    )
    if match:
        district = match.group(1).strip(" ,-\t\r\n")
        if district:
            return district.title()

    return "Riyadh General"
