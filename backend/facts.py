import re
import json
from urllib.parse import urlparse

from scanner import clean_text


# ============================================================
# HELPERS
# ============================================================

def unique(items):
    result = []
    for item in items:
        if not item:
            continue
        if isinstance(item, str):
            item = item.strip()
        if item and item not in result:
            result.append(item)
    return result


# ============================================================
# RESTAURANT NAME
# ============================================================

def extract_business_name(scan):
    title = scan.get("page_title", "").strip()
    body = scan.get("body_text", "")

    # Try h1 first
    h1_list = scan.get("h1", [])
    for h1 in h1_list:
        h1 = clean_text(h1)
        if 2 <= len(h1) <= 80:
            lower = h1.lower()
            if not any(w in lower for w in ["home", "welcome", "page", "menu", "login"]):
                return h1

    # Try first meaningful short line from body
    lines = [clean_text(line) for line in body.split("\n") if clean_text(line)]
    for line in lines[:15]:
        if 2 <= len(line) <= 80:
            lower = line.lower()
            if not any(w in lower for w in [
                "home", "orders", "my account", "rewards", "logout",
                "sign in", "sign up", "welcome", "skip to",
            ]):
                return line

    # Fallback to title
    if title:
        # Strip common suffixes
        for sep in [" | ", " – ", " - ", " — ", " :: "]:
            if sep in title:
                return title.split(sep)[0].strip()
        return title

    # Final fallback to domain
    domain = urlparse(scan.get("final_url", "")).netloc
    return domain.replace("www.", "")


# ============================================================
# MENU EXTRACTION (STRUCTURED)
# ============================================================

def extract_menu_items_from_structured_data(scan):
    """Try to extract menu from JSON-LD structured data."""
    structured_data = scan.get("structured_data", [])
    items = []

    for block in structured_data:
        try:
            data = json.loads(block)
            # Handle @graph arrays
            if isinstance(data, dict) and "@graph" in data:
                data = data["@graph"]
            if not isinstance(data, list):
                data = [data]

            for entry in data:
                if not isinstance(entry, dict):
                    continue
                etype = entry.get("@type", "")
                if isinstance(etype, list):
                    etype = " ".join(etype)
                etype = str(etype).lower()

                # hasMenu / menu property
                menu_obj = entry.get("hasMenu") or entry.get("menu")
                if menu_obj and isinstance(menu_obj, dict):
                    sections = menu_obj.get("hasMenuSection", [])
                    if not isinstance(sections, list):
                        sections = [sections]
                    for section in sections:
                        category_name = section.get("name", "Menu")
                        menu_items = section.get("hasMenuItem", [])
                        if not isinstance(menu_items, list):
                            menu_items = [menu_items]
                        parsed_items = []
                        for mi in menu_items:
                            if not isinstance(mi, dict):
                                continue
                            offer = mi.get("offers", {})
                            if isinstance(offer, list):
                                offer = offer[0] if offer else {}
                            price = offer.get("price", "") if offer else ""
                            currency = offer.get("priceCurrency", "") if offer else ""
                            parsed_items.append({
                                "name": mi.get("name", ""),
                                "description": mi.get("description", ""),
                                "price": f"{currency} {price}".strip() if price else "",
                                "currency": currency,
                            })
                        if parsed_items:
                            items.append({
                                "name": category_name,
                                "items": parsed_items,
                                "source": "structured_data",
                            })

        except Exception:
            continue

    return items


def parse_menu_from_text(body_text):
    """
    Heuristic menu extraction from plain text.
    Looks for patterns like:
      Item Name   $12.99
      Item Name - description   $12
      Item Name .......... 12.00
    """
    # Price pattern (currency symbol + digits OR digits + currency word)
    price_pattern = re.compile(
        r"""
        (?:
            (?P<sym1>[\$\£\€\₹\₪\₦\₲\฿\₫\₩\¥\₺\₴\₱\﷼\৳\₡\₸])   # symbol first
            \s*
            (?P<amount1>\d{1,6}(?:[.,]\d{1,2})?)
        )
        |
        (?:
            (?P<amount2>\d{1,6}(?:[.,]\d{1,2})?)
            \s*
            (?P<sym2>[\$\£\€\₹\₪\₦\₲\฿\₫\₩\¥\₺\₴\₱\﷼\৳\₡\₸])
        )
        """,
        re.VERBOSE,
    )

    lines = [l.strip() for l in body_text.split("\n") if l.strip()]
    menu_items = []
    current_category = "Menu"

    # Detect potential category headers (short ALL-CAPS or Title Case lines)
    heading_pattern = re.compile(r"^[A-Z][A-Z0-9 '&/\-]{2,40}$")

    for line in lines:
        line_clean = clean_text(line)
        if not line_clean or len(line_clean) < 3:
            continue

        # Check if it's a category heading
        if heading_pattern.match(line_clean) and len(line_clean) <= 50:
            lower = line_clean.lower()
            category_words = [
                "appetizer", "starter", "main", "entree", "dessert", "drink",
                "beverage", "salad", "soup", "pizza", "pasta", "burger", "sandwich",
                "special", "breakfast", "lunch", "dinner", "sides", "combo",
                "snack", "grill", "seafood", "vegetarian", "vegan",
            ]
            if any(w in lower for w in category_words):
                current_category = line_clean
                continue

        # Look for price in line
        price_match = price_pattern.search(line_clean)
        if price_match:
            price_str = price_match.group(0).strip()
            # Extract item name (everything before the price)
            name_part = line_clean[:price_match.start()].strip()
            # Clean separators
            name_part = re.sub(r"[.\-_]{2,}", " ", name_part).strip()
            # Remove trailing dots/dashes
            name_part = re.sub(r"[\s.\-]+$", "", name_part).strip()

            if 3 <= len(name_part) <= 120:
                menu_items.append({
                    "category": current_category,
                    "name": name_part,
                    "description": "",
                    "price": price_str,
                    "currency": "",
                })

    # Group by category
    categories = {}
    for item in menu_items:
        cat = item["category"]
        if cat not in categories:
            categories[cat] = []
        categories[cat].append({
            "name": item["name"],
            "description": item["description"],
            "price": item["price"],
            "currency": item["currency"],
        })

    result = []
    for cat_name, cat_items in categories.items():
        result.append({
            "name": cat_name,
            "items": cat_items,
            "source": "text_extraction",
        })

    return result


def extract_menu(scan):
    """
    Extract menu information from the rendered website.
    Priority: structured data > text heuristics
    """
    # 1. Try structured data
    structured_categories = extract_menu_items_from_structured_data(scan)
    if structured_categories:
        return {
            "status": "found",
            "source_method": "structured_data",
            "categories": structured_categories,
            "source_url": scan.get("final_url", ""),
        }

    # 2. Try text extraction
    body = scan.get("body_text", "")
    text_categories = parse_menu_from_text(body)
    if text_categories:
        return {
            "status": "found",
            "source_method": "text_extraction",
            "categories": text_categories,
            "source_url": scan.get("final_url", ""),
        }

    # 3. Check if menu page links exist even if content not extractable
    nav = scan.get("links", {}).get("categorized", {})
    menu_links = nav.get("menu", [])

    return {
        "status": "not_extracted",
        "source_method": "none",
        "categories": [],
        "menu_links": menu_links[:5],
        "source_url": scan.get("final_url", ""),
        "note": "Menu content could not be extracted. Check menu links for manual review.",
    }


# ============================================================
# OPENING HOURS
# ============================================================

def extract_opening_hours(scan):
    """Extract opening hours from body text and structured data."""
    hours = []

    # 1. Try JSON-LD openingHours
    for block in scan.get("structured_data", []):
        try:
            data = json.loads(block)
            if isinstance(data, dict) and "@graph" in data:
                data = data["@graph"]
            if not isinstance(data, list):
                data = [data]
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                oh = entry.get("openingHours") or entry.get("openingHoursSpecification")
                if oh:
                    if isinstance(oh, str):
                        hours.append(oh)
                    elif isinstance(oh, list):
                        hours.extend([str(h) for h in oh if h])
        except Exception:
            continue

    if hours:
        return {
            "status": "found",
            "source": "structured_data",
            "hours": unique(hours),
        }

    # 2. Text heuristic
    body = scan.get("body_text", "")
    day_pattern = re.compile(
        r"""
        (?:
            (?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|
               Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?)
            (?:\s*[-–—]\s*
            (?:Mon(?:day)?|Tue(?:sday)?|Wed(?:nesday)?|Thu(?:rsday)?|
               Fri(?:day)?|Sat(?:urday)?|Sun(?:day)?))?
        )
        \s*[:\-–]?\s*
        (?:
            \d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?
            \s*[-–—]\s*
            \d{1,2}(?::\d{2})?\s*(?:am|pm|AM|PM)?
            |
            (?:closed|open\s*24\s*hours?|24\/7)
        )
        """,
        re.VERBOSE | re.IGNORECASE,
    )

    found = unique([clean_text(m.group(0)) for m in day_pattern.finditer(body)])

    if found:
        return {
            "status": "found",
            "source": "text_extraction",
            "hours": found[:20],
        }

    return {
        "status": "not_extracted",
        "source": "none",
        "hours": [],
        "note": "Opening hours could not be extracted from this website.",
    }


# ============================================================
# CONTACT
# ============================================================

def extract_contact(scan):
    emails = unique(scan.get("emails", []))
    phones = unique(scan.get("phones", []))
    addresses = unique(scan.get("addresses", []))

    # Get contact page links
    nav = scan.get("links", {}).get("categorized", {})
    contact_links = unique(nav.get("contact", []))

    return {
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "contact_page_links": contact_links,
        "email_available": bool(emails),
        "phone_available": bool(phones),
        "address_available": bool(addresses),
    }


# ============================================================
# LOCATION
# ============================================================

def extract_location(scan):
    """Extract location/address with map link generation."""
    addresses = unique(scan.get("addresses", []))

    # Try structured data for address
    structured_address = None
    for block in scan.get("structured_data", []):
        try:
            data = json.loads(block)
            if isinstance(data, dict) and "@graph" in data:
                data = data["@graph"]
            if not isinstance(data, list):
                data = [data]
            for entry in data:
                if not isinstance(entry, dict):
                    continue
                addr = entry.get("address")
                if addr and isinstance(addr, dict):
                    parts = [
                        addr.get("streetAddress", ""),
                        addr.get("addressLocality", ""),
                        addr.get("addressRegion", ""),
                        addr.get("postalCode", ""),
                        addr.get("addressCountry", ""),
                    ]
                    full = ", ".join(p for p in parts if p)
                    if full:
                        structured_address = full
                        break
                elif addr and isinstance(addr, str):
                    structured_address = addr
                    break
        except Exception:
            continue

    primary_address = structured_address or (addresses[0] if addresses else None)
    map_link = None
    if primary_address:
        from urllib.parse import quote
        map_link = f"https://www.google.com/maps/search/?api=1&query={quote(primary_address)}"

    return {
        "primary_address": primary_address,
        "all_addresses": addresses,
        "map_link": map_link,
        "source": "structured_data" if structured_address else ("text_extraction" if addresses else "none"),
    }


# ============================================================
# RESERVATIONS
# ============================================================

def extract_reservations(scan):
    nav = scan.get("links", {}).get("categorized", {})
    reservation_links = unique(nav.get("reservation", []))

    body = scan.get("body_text", "").lower()
    has_reservation_text = any(w in body for w in [
        "reservation", "book a table", "book now", "reserve", "booking",
        "opentable", "resy", "sevenrooms", "tock",
    ])

    # Detect third-party booking platforms
    all_links = scan.get("links", {}).get("external", []) + scan.get("links", {}).get("internal", [])
    booking_platforms = []
    platform_domains = {
        "opentable.com": "OpenTable",
        "resy.com": "Resy",
        "sevenrooms.com": "SevenRooms",
        "tock.com": "Tock",
        "yelp.com/reservations": "Yelp Reservations",
        "tablein.com": "TableIn",
        "quandoo.": "Quandoo",
        "bookatable.": "Bookatable",
        "thefork.": "TheFork",
        "livre.": "Livre",
    }
    for link in all_links:
        for domain, name in platform_domains.items():
            if domain in link.lower() and name not in booking_platforms:
                booking_platforms.append(name)
                reservation_links.append(link)

    reservation_links = unique(reservation_links)

    return {
        "available": bool(reservation_links) or has_reservation_text,
        "reservation_links": reservation_links[:5],
        "booking_platforms": booking_platforms,
        "booking_info": "Reservation functionality detected on website." if (bool(reservation_links) or has_reservation_text) else None,
    }


# ============================================================
# ONLINE ORDERING
# ============================================================

def extract_ordering(scan):
    nav = scan.get("links", {}).get("categorized", {})
    ordering_links = unique(nav.get("ordering", []))

    body = scan.get("body_text", "").lower()
    has_ordering_text = any(w in body for w in [
        "order online", "order now", "add to cart", "place order",
        "delivery", "takeaway", "take away", "pickup", "click & collect",
    ])

    # Detect third-party ordering platforms
    all_links = scan.get("links", {}).get("external", []) + scan.get("links", {}).get("internal", [])
    ordering_platforms = []
    platform_domains = {
        "ubereats.com": "Uber Eats",
        "doordash.com": "DoorDash",
        "grubhub.com": "Grubhub",
        "deliveroo.": "Deliveroo",
        "justeat.": "Just Eat",
        "seamless.com": "Seamless",
        "postmates.com": "Postmates",
        "olo.com": "Olo",
        "toast.": "Toast",
        "square.com": "Square",
        "clover.com": "Clover",
        "chownow.com": "ChowNow",
        "foodpanda.": "Foodpanda",
        "talabat.": "Talabat",
        "zomato.": "Zomato",
        "swiggy.": "Swiggy",
    }
    for link in all_links:
        for domain, name in platform_domains.items():
            if domain in link.lower() and name not in ordering_platforms:
                ordering_platforms.append(name)
                ordering_links.append(link)

    ordering_links = unique(ordering_links)

    return {
        "available": bool(ordering_links) or has_ordering_text,
        "ordering_links": ordering_links[:5],
        "ordering_platforms": ordering_platforms,
        "delivery_info": "Online ordering/delivery detected on website." if (bool(ordering_links) or has_ordering_text) else None,
    }


# ============================================================
# SOCIAL MEDIA
# ============================================================

def extract_social(scan):
    social_links = unique(scan.get("social_links", []))

    grouped = {
        "facebook": [],
        "instagram": [],
        "twitter": [],
        "x": [],
        "tiktok": [],
        "youtube": [],
        "linkedin": [],
        "pinterest": [],
        "snapchat": [],
        "other": [],
    }

    for link in social_links:
        lower = link.lower()
        if "facebook.com" in lower:
            grouped["facebook"].append(link)
        elif "instagram.com" in lower:
            grouped["instagram"].append(link)
        elif "twitter.com" in lower:
            grouped["twitter"].append(link)
        elif "x.com" in lower:
            grouped["x"].append(link)
        elif "tiktok.com" in lower:
            grouped["tiktok"].append(link)
        elif "youtube.com" in lower or "youtu.be" in lower:
            grouped["youtube"].append(link)
        elif "linkedin.com" in lower:
            grouped["linkedin"].append(link)
        elif "pinterest.com" in lower:
            grouped["pinterest"].append(link)
        elif "snapchat.com" in lower:
            grouped["snapchat"].append(link)
        else:
            grouped["other"].append(link)

    return grouped


# ============================================================
# FEATURES
# ============================================================

def extract_features(scan):
    text = scan.get("body_text", "").lower()
    buttons = " ".join(scan.get("buttons", [])).lower()
    combined = f"{text} {buttons}"

    return {
        "menu": bool(
            scan.get("links", {}).get("categorized", {}).get("menu")
        ) or "add to cart" in combined or "menu" in combined,

        "contact": (
            bool(scan.get("links", {}).get("categorized", {}).get("contact"))
            or "contact" in combined
        ),

        "about": (
            bool(scan.get("links", {}).get("categorized", {}).get("about"))
            or "about us" in combined
            or "our story" in combined
        ),

        "reservation": (
            bool(scan.get("links", {}).get("categorized", {}).get("reservation"))
            or "reservation" in combined
            or "book a table" in combined
        ),

        "online_ordering": (
            bool(scan.get("links", {}).get("categorized", {}).get("ordering"))
            or "add to cart" in combined
            or "order online" in combined
            or "delivery" in combined
        ),

        "social_media": bool(scan.get("social_links")),
        "email": bool(scan.get("emails")),
        "phone": bool(scan.get("phones")),
        "address": bool(scan.get("addresses")),
    }


# ============================================================
# SEO
# ============================================================

def extract_seo(scan):
    title = scan.get("page_title", "")
    description = scan.get("meta_description", "")
    canonical = scan.get("canonical_url", "")
    h1 = scan.get("h1", [])
    h2 = scan.get("h2", [])

    return {
        "title": title,
        "title_length": len(title),
        "meta_description": description,
        "meta_description_length": len(description),
        "canonical_url": canonical,
        "h1": h1,
        "h1_count": len(h1),
        "h2": h2[:10],
        "structured_data_count": len(scan.get("structured_data", [])),
        "mobile_viewport": scan.get("mobile_responsive", False),
    }


# ============================================================
# CONTENT
# ============================================================

def extract_content(scan):
    body = scan.get("body_text", "")
    return {
        "word_count": scan.get("word_count", len(body.split())),
        "preview": body[:2000],
    }


# ============================================================
# MEDIA
# ============================================================

def extract_media(scan):
    images = scan.get("images", [])
    with_alt = [img for img in images if img.get("alt")]
    return {
        "total_images": len(images),
        "images_with_alt": len(with_alt),
        "images_without_alt": len(images) - len(with_alt),
        "images": images[:50],
    }


# ============================================================
# NAVIGATION
# ============================================================

def extract_navigation(scan):
    links = scan.get("links", {})
    categorized = links.get("categorized", {})
    return {
        "internal_links": links.get("internal", [])[:50],
        "external_links": links.get("external", [])[:50],
        "menu_links": categorized.get("menu", []),
        "contact_links": categorized.get("contact", []),
        "about_links": categorized.get("about", []),
        "reservation_links": categorized.get("reservation", []),
        "ordering_links": categorized.get("ordering", []),
    }


# ============================================================
# FAVICON / LOGO URL
# ============================================================

def extract_favicon_url(scan):
    """Return absolute favicon URL if available."""
    favicon_url = scan.get("favicon_url", "")
    if favicon_url:
        return favicon_url
    # Try to build fallback from domain
    final_url = scan.get("final_url", "")
    if final_url:
        parsed = urlparse(final_url)
        return f"{parsed.scheme}://{parsed.netloc}/favicon.ico"
    return ""


# ============================================================
# ABOUT SECTION
# ============================================================

def extract_about(scan):
    """Extract about/description content."""
    meta_desc = scan.get("meta_description", "")
    body = scan.get("body_text", "")

    # Look for about-related paragraphs
    about_keywords = ["about us", "our story", "who we are", "our mission", "established"]
    about_text = ""

    lines = body.split(" ")
    # Find about context in body
    body_lower = body.lower()
    for kw in about_keywords:
        idx = body_lower.find(kw)
        if idx != -1:
            excerpt = body[idx:idx + 800].strip()
            if len(excerpt) > 50:
                about_text = excerpt
                break

    return {
        "description": meta_desc or (body[:500] if body else ""),
        "about_text": about_text or meta_desc or "",
        "about_links": scan.get("links", {}).get("categorized", {}).get("about", []),
    }


# ============================================================
# MAIN FACT EXTRACTION
# ============================================================

def extract_facts(scan):

    if not scan.get("scan_successful"):
        return {
            "scan_successful": False,
            "error": scan.get("error", "Website scan failed."),
        }

    contact = extract_contact(scan)
    social = extract_social(scan)
    features = extract_features(scan)
    location = extract_location(scan)
    reservations = extract_reservations(scan)
    ordering = extract_ordering(scan)
    opening_hours = extract_opening_hours(scan)
    about = extract_about(scan)
    menu = extract_menu(scan)
    favicon_url = extract_favicon_url(scan)

    return {
        "scan_successful": True,

        "website": scan.get("website"),
        "requested_url": scan.get("requested_url"),
        "final_url": scan.get("final_url"),
        "scanner_method": scan.get("scanner_method"),
        "status_code": scan.get("status_code"),
        "response_time_ms": scan.get("response_time_ms"),

        # -----------------------------------------------
        # RESTAURANT OVERVIEW
        # -----------------------------------------------
        "restaurant": {
            "name": extract_business_name(scan),
            "description": about["description"],
            "language": scan.get("language", ""),
            "favicon_url": favicon_url,
        },

        # -----------------------------------------------
        # MENU
        # -----------------------------------------------
        "menu": menu,

        # -----------------------------------------------
        # CONTACT
        # -----------------------------------------------
        "contact": contact,

        # -----------------------------------------------
        # LOCATION
        # -----------------------------------------------
        "location": location,

        # -----------------------------------------------
        # OPENING HOURS
        # -----------------------------------------------
        "opening_hours": opening_hours,

        # -----------------------------------------------
        # RESERVATIONS
        # -----------------------------------------------
        "reservations": reservations,

        # -----------------------------------------------
        # ONLINE ORDERING
        # -----------------------------------------------
        "ordering": ordering,

        # -----------------------------------------------
        # SOCIAL MEDIA
        # -----------------------------------------------
        "social_media": social,

        # -----------------------------------------------
        # ABOUT
        # -----------------------------------------------
        "about": about,

        # -----------------------------------------------
        # FEATURES
        # -----------------------------------------------
        "features": features,

        # -----------------------------------------------
        # CONTENT
        # -----------------------------------------------
        "content": extract_content(scan),

        # -----------------------------------------------
        # SEO
        # -----------------------------------------------
        "seo": extract_seo(scan),

        # -----------------------------------------------
        # MEDIA
        # -----------------------------------------------
        "media": extract_media(scan),

        # -----------------------------------------------
        # NAVIGATION
        # -----------------------------------------------
        "navigation": extract_navigation(scan),

        # -----------------------------------------------
        # FORMS / CTA
        # -----------------------------------------------
        "forms": {"count": scan.get("forms", 0)},
        "calls_to_action": {"buttons": scan.get("buttons", [])[:50]},

        # -----------------------------------------------
        # TECHNICAL
        # -----------------------------------------------
        "technical": {
            "https": (
                urlparse(scan.get("final_url", "")).scheme.lower() == "https"
            ),
            "mobile_responsive": scan.get("mobile_responsive", False),
            "favicon": scan.get("favicon", False),
            "canonical": bool(scan.get("canonical_url")),
            "structured_data": bool(scan.get("structured_data")),
            "javascript_app": scan.get("javascript_app", False),
        },

        # -----------------------------------------------
        # SCANNER STATS
        # -----------------------------------------------
        "scanner": {
            "method": scan.get("scanner_method"),
            "html_size": scan.get("html_size", 0),
            "word_count": scan.get("word_count", 0),
            "image_count": len(scan.get("images", [])),
            "internal_link_count": len(
                scan.get("links", {}).get("internal", [])
            ),
            "external_link_count": len(
                scan.get("links", {}).get("external", [])
            ),
        },
    }