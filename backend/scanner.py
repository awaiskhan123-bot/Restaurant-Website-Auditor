"""
FoodIntel scanner.py

Scans a restaurant / cafe / bakery website and returns data in the exact
structure the React dashboard (App.jsx) expects:

    restaurant, menu, contact, location, opening_hours, reservations,
    ordering, social_media, about, features, content, seo, technical,
    media, scanner, navigation, ai_analysis

Strategy:
  1. Fetch the home page with plain HTTP (fast).
  2. If the page is thin / blocked / JavaScript-rendered -> render with Playwright.
  3. Follow the menu / contact / about pages found on the site and merge results.
"""

import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import quote, urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

# ============================================================
# CONSTANTS
# ============================================================

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/140.0.0.0 Safari/537.36"
)

PRICE_RE = re.compile(
    r"(?:[$£€₹¥]|\bRs\.?|\bPKR|\bUSD|\bEUR|\bGBP|\bAED|\bINR|\bSAR)\s?\d[\d,]*(?:\.\d{1,2})?"
    r"|\d[\d,]*(?:\.\d{1,2})?\s?(?:[$£€₹]|\bRs\.?|\bPKR|\bAED|/-)",
    re.I,
)

TIME_RE = re.compile(
    r"\b\d{1,2}(?::\d{2})?\s?(?:am|pm|a\.m\.|p\.m\.)|\b\d{1,2}:\d{2}\b", re.I
)

DAY_RE = re.compile(
    r"\b(?:mon|tue|tues|wed|thu|thur|thurs|fri|sat|sun)(?:day|sday|nesday|rsday|urday)?\b"
    r"|\b(?:daily|everyday|every day|weekdays|weekends)\b",
    re.I,
)

STREET_RE = re.compile(
    r"\b(street|st\.?|road|rd\.?|avenue|ave\.?|blvd|boulevard|lane|ln\.?|drive|dr\.?|"
    r"plaza|square|floor|suite|ste\.?|sector|block|phase|market|mall|colony|chowk|"
    r"town|highway|hwy|way|building|bldg)\b",
    re.I,
)

POSTAL_RE = re.compile(
    r"\b[A-Z]{1,2}\d[A-Z\d]?\s?\d[A-Z]{2}\b"
    r"|\b\d{5}(?:-\d{4})?\b"
    r"|\b\d{6}\b"
    r"|\b[A-Z]\d[A-Z]\s?\d[A-Z]\d\b"
)

LINK_RULES = {
    "menu": r"\b(menu|menus|carte|food menu|our food|dishes|drinks menu|speisekarte)\b",
    "contact": r"\b(contact|contact us|contactus|get in touch|reach us|find us|locations?|visit us)\b",
    "about": r"\b(about|about us|aboutus|our story|story|who we are)\b",
    "reservation": r"\b(reservations?|reserve|book a table|book table|booking|bookings)\b",
    "ordering": r"\b(order|order online|online order|ordering|delivery|takeaway|take away|takeout|pickup|pick up)\b",
}

SOCIAL_MAP = {
    "facebook.com": "facebook",
    "fb.com": "facebook",
    "instagram.com": "instagram",
    "tiktok.com": "tiktok",
    "youtube.com": "youtube",
    "youtu.be": "youtube",
    "twitter.com": "twitter",
    "x.com": "twitter",
    "linkedin.com": "linkedin",
    "pinterest.com": "pinterest",
    "snapchat.com": "snapchat",
}

SOCIAL_KEYS = [
    "facebook", "instagram", "tiktok", "youtube", "twitter",
    "x", "linkedin", "pinterest", "snapchat", "other",
]

RESERVATION_PLATFORMS = {
    "opentable.": "OpenTable",
    "resy.com": "Resy",
    "exploretock.com": "Tock",
    "thefork.": "TheFork",
    "sevenrooms.com": "SevenRooms",
    "bookatable.": "Bookatable",
    "quandoo.": "Quandoo",
    "tablein.": "Tablein",
    "reservio.com": "Reservio",
    "dineplan.": "Dineplan",
    "tablecheck.": "TableCheck",
    "chope.co": "Chope",
    "eatapp.co": "Eat App",
    "zenchef.": "Zenchef",
    "covermanager.": "CoverManager",
}

ORDERING_PLATFORMS = {
    "ubereats.com": "Uber Eats",
    "doordash.com": "DoorDash",
    "grubhub.com": "Grubhub",
    "deliveroo.": "Deliveroo",
    "just-eat.": "Just Eat",
    "justeat.": "Just Eat",
    "foodpanda.": "Foodpanda",
    "zomato.com": "Zomato",
    "swiggy.com": "Swiggy",
    "toasttab.com": "Toast",
    "chownow.com": "ChowNow",
    "postmates.com": "Postmates",
    "menulog.com": "Menulog",
    "skipthedishes.com": "SkipTheDishes",
    "talabat.com": "Talabat",
    "square.site": "Square Online",
    "gloriafood.com": "GloriaFood",
    "slicelife.com": "Slice",
    "order.online": "Google Ordering",
    "wolt.com": "Wolt",
    "glovoapp.com": "Glovo",
}

RESTAURANT_TYPES = {
    "restaurant", "foodestablishment", "cafeorcoffeeshop", "bakery", "barorpub",
    "fastfoodrestaurant", "icecreamshop", "nightclub", "winery", "brewery",
    "localbusiness", "hotel", "lodgingbusiness",
}

NOISE_ITEM_WORDS = re.compile(
    r"\b(subtotal|total|shipping|cart|checkout|tax|delivery fee|minimum order|"
    r"add to cart|gift card|sign up|newsletter|copyright)\b",
    re.I,
)

HEADING_TAGS = ["h1", "h2", "h3", "h4", "h5"]


# ============================================================
# BASIC HELPERS
# ============================================================

def normalize_url(url: str) -> str:
    url = (url or "").strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url


def clean_text(text) -> str:
    if not text:
        return ""
    return re.sub(r"\s+", " ", str(text)).strip()


def unique_list(items):
    seen = set()
    result = []
    for item in items:
        if item is None:
            continue
        item = str(item).strip()
        key = item.lower()
        if item and key not in seen:
            seen.add(key)
            result.append(item)
    return result


def get_host(url: str) -> str:
    try:
        return urlparse(url).netloc.lower().split(":")[0].replace("www.", "")
    except Exception:
        return ""


def is_internal_url(url: str, base_url: str) -> bool:
    return get_host(url) == get_host(base_url)


def as_list(value):
    if value is None:
        return []
    return value if isinstance(value, list) else [value]


# ============================================================
# JSON-LD
# ============================================================

def parse_json_ld(raw_scripts):
    nodes = []

    def walk(obj):
        if isinstance(obj, list):
            for item in obj:
                walk(item)
        elif isinstance(obj, dict):
            nodes.append(obj)
            for value in obj.values():
                if isinstance(value, (dict, list)):
                    walk(value)

    for raw in raw_scripts:
        try:
            walk(json.loads(raw))
        except Exception:
            continue

    return nodes


def node_types(node):
    return {str(t).lower().split("/")[-1] for t in as_list(node.get("@type"))}


def format_address(addr):
    if isinstance(addr, str):
        return clean_text(addr)
    if not isinstance(addr, dict):
        return ""
    country = addr.get("addressCountry")
    if isinstance(country, dict):
        country = country.get("name", "")
    parts = [
        addr.get("streetAddress"),
        addr.get("addressLocality"),
        addr.get("addressRegion"),
        addr.get("postalCode"),
        country,
    ]
    return clean_text(", ".join(str(p) for p in parts if p))


def ld_price(offers):
    for offer in as_list(offers):
        if isinstance(offer, dict) and offer.get("price") not in (None, ""):
            currency = offer.get("priceCurrency", "")
            return clean_text(f"{currency} {offer['price']}")
    return ""


def ld_menu_items(nodes):
    """Menu data published as schema.org Menu / MenuSection / MenuItem."""
    categories = []
    seen_items = set()

    def item_dict(obj):
        if not isinstance(obj, dict) or not obj.get("name"):
            return None
        return {
            "name": clean_text(obj.get("name")),
            "description": clean_text(obj.get("description", "")),
            "price": ld_price(obj.get("offers")),
        }

    for node in nodes:
        if "menusection" in node_types(node):
            items = []
            for raw in as_list(node.get("hasMenuItem")):
                item = item_dict(raw)
                if item:
                    items.append(item)
                    seen_items.add(id(raw))
            if items:
                categories.append({
                    "name": clean_text(node.get("name")) or "Menu",
                    "items": items,
                    "source": "json-ld",
                })

    loose = []
    for node in nodes:
        if "menuitem" in node_types(node) and id(node) not in seen_items:
            item = item_dict(node)
            if item:
                loose.append(item)
    if loose:
        categories.append({"name": "Menu", "items": loose, "source": "json-ld"})

    return categories


def ld_hours(node):
    hours = []
    for value in as_list(node.get("openingHours")):
        if isinstance(value, str):
            hours.append(clean_text(value))
    for spec in as_list(node.get("openingHoursSpecification")):
        if not isinstance(spec, dict):
            continue
        days = [str(d).split("/")[-1] for d in as_list(spec.get("dayOfWeek"))]
        opens, closes = spec.get("opens"), spec.get("closes")
        if days and opens and closes:
            hours.append(f"{', '.join(days)}: {opens} - {closes}")
    return unique_list(hours)


# ============================================================
# EXTRACTION HELPERS
# ============================================================

def classify_link(text, href):
    parsed = urlparse(href)
    tokens = re.sub(
        r"[^a-z0-9]+", " ", f"{text} {parsed.path} {parsed.query}".lower()
    )
    return [cat for cat, pattern in LINK_RULES.items() if re.search(pattern, tokens)]


def extract_links(soup, base_url, html_lower):
    internal, external = [], []
    categorized = {key: [] for key in LINK_RULES}

    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()

        if not href or href.startswith(("#", "javascript:", "mailto:", "tel:", "sms:", "whatsapp:")):
            continue

        absolute = urldefrag(urljoin(base_url, href))[0]

        if not absolute.startswith(("http://", "https://")):
            continue

        text = clean_text(tag.get_text(" ", strip=True))

        if is_internal_url(absolute, base_url):
            internal.append(absolute)
        else:
            external.append(absolute)

        for category in classify_link(text, absolute):
            categorized[category].append(absolute)

    # Links to known booking / delivery platforms count regardless of anchor text.
    for link in external:
        low = link.lower()
        if any(re.search(r"(?<![a-z0-9-])" + re.escape(k), low) for k in RESERVATION_PLATFORMS):
            categorized["reservation"].append(link)
        if any(re.search(r"(?<![a-z0-9-])" + re.escape(k), low) for k in ORDERING_PLATFORMS):
            categorized["ordering"].append(link)

    return {
        "internal": unique_list(internal),
        "external": unique_list(external),
        "categorized": {k: unique_list(v) for k, v in categorized.items()},
    }


def detect_platforms(html_lower, catalog):
    found = []
    for key, name in catalog.items():
        if re.search(r"(?<![a-z0-9-])" + re.escape(key), html_lower):
            found.append(name)
    return unique_list(found)


def extract_social(links):
    result = {key: [] for key in SOCIAL_KEYS}

    for link in links:
        parsed = urlparse(link)
        host = parsed.netloc.lower().split(":")[0].replace("www.", "")
        path = parsed.path.lower()

        if len(path.strip("/")) < 2:
            continue
        if any(bad in link.lower() for bad in ("sharer", "/share", "intent/", "plugins/", "dialog/")):
            continue

        for domain, key in SOCIAL_MAP.items():
            if host == domain or host.endswith("." + domain):
                result[key].append(link)
                break

    return {k: unique_list(v) for k, v in result.items()}


def extract_emails(text):
    found = re.findall(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}", text or "")
    good = []
    for email in found:
        low = email.lower()
        if low.endswith((".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")):
            continue
        if any(bad in low for bad in ("sentry", "wixpress", "example.com", "domain.com", "your@")):
            continue
        good.append(email)
    return unique_list(good)


def extract_phones_from_text(text):
    found = re.findall(r"\+?\d[\d\s().-]{7,}\d", text or "")
    phones = []
    for phone in found:
        phone = clean_text(phone)
        digits = re.sub(r"\D", "", phone)
        if not 8 <= len(digits) <= 15:
            continue
        if re.fullmatch(r"\d{4}[-/.]\d{1,2}[-/.]\d{1,2}", phone):
            continue
        phones.append(phone)
    return unique_list(phones)


def dedupe_phones(phones):
    seen, result = set(), []
    for phone in phones:
        digits = re.sub(r"\D", "", phone)
        key = digits[-9:] if len(digits) >= 9 else digits
        if key and key not in seen:
            seen.add(key)
            result.append(phone)
    return result


def extract_addresses_from_lines(lines):
    out = []
    for line in lines:
        if not 12 <= len(line) <= 160:
            continue
        if PRICE_RE.search(line) or TIME_RE.search(line) or DAY_RE.search(line):
            continue
        if len(line.split()) > 20:
            continue
        if not any(ch.isdigit() for ch in line):
            continue
        if (STREET_RE.search(line) and ("," in line or len(line) >= 20)) or (
            POSTAL_RE.search(line) and "," in line
        ):
            out.append(line)
    return unique_list(out)[:8]


def extract_hours_from_lines(lines):
    hours = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if len(line) <= 120 and DAY_RE.search(line):
            if TIME_RE.search(line):
                hours.append(line)
            elif (
                len(line) <= 40
                and i + 1 < len(lines)
                and TIME_RE.search(lines[i + 1])
                and not DAY_RE.search(lines[i + 1])
                and len(lines[i + 1]) <= 60
            ):
                hours.append(f"{line}: {lines[i + 1]}")
                i += 1
        i += 1
    return unique_list(hours)[:14]


def extract_about_text(soup):
    for heading in soup.find_all(["h1", "h2", "h3"]):
        title = clean_text(heading.get_text(" ", strip=True)).lower()
        if re.search(r"\b(about|our story|story|who we are|welcome)\b", title):
            paragraphs = []
            for sibling in heading.find_all_next(["p", "h1", "h2", "h3"], limit=8):
                if sibling.name in ("h1", "h2", "h3"):
                    if paragraphs:
                        break
                    continue
                text = clean_text(sibling.get_text(" ", strip=True))
                if len(text) >= 50:
                    paragraphs.append(text)
                if len(paragraphs) >= 3:
                    break
            if paragraphs:
                return " ".join(paragraphs)[:1500]
    return ""


# ============================================================
# MENU EXTRACTION (HTML)
# ============================================================

def extract_menu_from_dom(soup):
    """
    Finds the smallest page blocks that contain exactly one price
    (typical menu item card / list row / table row) and reads
    name, description and price from each. The category is the nearest
    preceding heading.
    """
    qualifying = {}

    for el in soup.find_all(["li", "article", "tr", "div", "p", "section", "dl", "dd"]):
        text = el.get_text(" ", strip=True)
        if not text or len(text) > 350:
            continue
        if len(PRICE_RE.findall(text)) != 1:
            continue
        if NOISE_ITEM_WORDS.search(text):
            continue
        if el.find_parent(["nav", "footer", "header"]):
            continue
        qualifying[id(el)] = el

    # keep only the biggest qualifying block (skip blocks whose parent also qualifies)
    containers = [
        el for el in qualifying.values()
        if el.parent is None or id(el.parent) not in qualifying
    ]

    contained_headings = set()
    for container in containers:
        for h in container.find_all(HEADING_TAGS):
            contained_headings.add(id(h))

    categories = {}
    order = []
    seen = set()

    for container in containers:
        parts = [clean_text(s) for s in container.stripped_strings]
        parts = [p for p in parts if p]
        joined = " ".join(parts)

        match = PRICE_RE.search(joined)
        if not match:
            continue
        price = clean_text(match.group(0))

        # name: heading/strong inside the block, else first text part that isn't a price
        name = ""
        named = container.find(["h1", "h2", "h3", "h4", "h5", "h6", "strong", "b"])
        if named:
            name = clean_text(named.get_text(" ", strip=True))
            if PRICE_RE.fullmatch(name):
                name = ""
        if not name:
            for part in parts:
                stripped = PRICE_RE.sub("", part).strip(" .-–—:|·•…_/")
                if len(stripped) >= 2:
                    name = stripped
                    break

        name = PRICE_RE.sub("", name).strip(" .-–—:|·•…_/")
        if not (2 <= len(name) <= 90) or not re.search(r"[A-Za-z\u0600-\u06FF]", name):
            continue
        if DAY_RE.search(name) and TIME_RE.search(joined):
            continue

        desc_parts = []
        for part in parts:
            cleaned = PRICE_RE.sub("", part).strip(" .-–—:|·•…_/")
            if cleaned and cleaned != name and name not in cleaned[: len(name) + 1] and len(cleaned) > 3:
                desc_parts.append(cleaned)
        description = clean_text(" ".join(desc_parts))[:250]

        key = (name.lower(), price)
        if key in seen:
            continue
        seen.add(key)

        # category = nearest previous heading that is not an item title
        heading = container.find_previous(HEADING_TAGS)
        while heading is not None and id(heading) in contained_headings:
            heading = heading.find_previous(HEADING_TAGS)
        category = clean_text(heading.get_text(" ", strip=True)) if heading else ""
        if not category or len(category) > 60:
            category = "Menu"

        if category not in categories:
            categories[category] = {"name": category, "items": [], "source": "html"}
            order.append(category)
        categories[category]["items"].append(
            {"name": name, "description": description, "price": price}
        )

    result = [categories[name] for name in order if categories[name]["items"]]
    total = sum(len(c["items"]) for c in result)
    return result if total >= 2 else []


# ============================================================
# HTTP FETCH
# ============================================================

def fetch_http(url, timeout=15):
    start = time.perf_counter()
    try:
        response = requests.get(
            url,
            headers={
                "User-Agent": USER_AGENT,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=timeout,
            allow_redirects=True,
        )

        if response.status_code >= 400:
            return {"success": False, "error": f"HTTP {response.status_code}",
                    "status_code": response.status_code}

        content_type = response.headers.get("content-type", "").lower()
        if "html" not in content_type and "xml" not in content_type:
            return {"success": False, "error": f"Unsupported content type: {content_type}"}

        if not response.encoding or response.encoding.lower() == "iso-8859-1":
            response.encoding = response.apparent_encoding or "utf-8"

        return {
            "success": True,
            "html": response.text,
            "status_code": response.status_code,
            "final_url": response.url,
            "response_time_ms": round((time.perf_counter() - start) * 1000, 2),
            "content_length": len(response.content),
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ============================================================
# PLAYWRIGHT RENDERING
# ============================================================

def render_with_playwright(url):
    start = time.perf_counter()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1440, "height": 900},
                locale="en-US",
                ignore_https_errors=True,
            )
            page = context.new_page()
            page.set_default_timeout(10000)

            response = None
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=25000)
            except PlaywrightTimeoutError:
                pass

            try:
                page.wait_for_load_state("networkidle", timeout=7000)
            except PlaywrightTimeoutError:
                pass

            page.wait_for_timeout(2500)

            # scroll to trigger lazy-loaded content
            try:
                page.evaluate(
                    """
                    async () => {
                        for (let i = 0; i < 4; i++) {
                            window.scrollBy(0, document.body.scrollHeight / 4);
                            await new Promise(r => setTimeout(r, 400));
                        }
                        window.scrollTo(0, 0);
                    }
                    """
                )
            except Exception:
                pass

            page.wait_for_timeout(1000)

            html = page.content()
            final_url = page.url
            status_code = response.status if response else 200
            browser.close()

        return {
            "success": True,
            "html": html,
            "final_url": final_url,
            "status_code": status_code,
            "response_time_ms": round((time.perf_counter() - start) * 1000, 2),
        }

    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ============================================================
# PAGE PARSER
# ============================================================

def parse_page(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    html_lower = html.lower()

    # ---- JSON-LD (read before scripts are removed)
    ld_raw = []
    for script in soup.find_all("script", type=re.compile(r"ld\+json", re.I)):
        content = script.string or script.get_text()
        if content and content.strip():
            ld_raw.append(content.strip())
    ld_nodes = parse_json_ld(ld_raw)

    # ---- head info
    title = clean_text(soup.title.get_text()) if soup.title else ""

    def meta(**attrs):
        tag = soup.find("meta", attrs=attrs)
        return clean_text(tag.get("content", "")) if tag else ""

    meta_description = meta(name=re.compile(r"^description$", re.I))
    og_title = meta(property="og:title")
    og_site_name = meta(property="og:site_name")
    og_description = meta(property="og:description")
    viewport = soup.find("meta", attrs={"name": re.compile(r"^viewport$", re.I)})

    canonical = ""
    canonical_tag = soup.find("link", rel=lambda v: v and "canonical" in v)
    if canonical_tag and canonical_tag.get("href"):
        canonical = urljoin(base_url, canonical_tag["href"])

    favicon_url = ""
    favicon_tag = soup.find("link", rel=lambda v: v and "icon" in " ".join(v if isinstance(v, list) else [v]).lower())
    if favicon_tag and favicon_tag.get("href"):
        favicon_url = urljoin(base_url, favicon_tag["href"])

    language = (soup.html.get("lang", "") if soup.html else "") or ""

    # ---- tel: / mailto: links (before cleanup)
    tel_phones, mail_emails = [], []
    for tag in soup.find_all("a", href=True):
        href = tag["href"].strip()
        if href.lower().startswith("tel:"):
            tel_phones.append(clean_text(href[4:].split("?")[0].replace("%20", " ")))
        elif href.lower().startswith("mailto:"):
            mail_emails.append(href[7:].split("?")[0])

    address_tags = [clean_text(a.get_text(" ", strip=True)) for a in soup.find_all("address")]

    # ---- remove non-visible junk so text extraction is clean
    for tag in soup(["script", "style", "noscript", "template", "svg", "iframe"]):
        tag.decompose()

    h1 = unique_list(clean_text(t.get_text(" ", strip=True)) for t in soup.find_all("h1"))
    h2 = unique_list(clean_text(t.get_text(" ", strip=True)) for t in soup.find_all("h2"))
    h3 = unique_list(clean_text(t.get_text(" ", strip=True)) for t in soup.find_all("h3"))

    lines = []
    for raw in soup.get_text("\n").split("\n"):
        text = clean_text(raw)
        if text and (not lines or lines[-1] != text):
            lines.append(text)

    body_text = clean_text(soup.get_text(" "))
    text_lower = body_text.lower()

    links = extract_links(soup, base_url, html_lower)

    images = []
    for img in soup.find_all("img"):
        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
        if not src or src.startswith("data:"):
            continue
        images.append({"url": urljoin(base_url, src), "alt": clean_text(img.get("alt", ""))})

    # ---- JSON-LD business node
    business = None
    for node in ld_nodes:
        if node_types(node) & RESTAURANT_TYPES and node.get("name"):
            business = node
            break

    ld_phones, ld_emails, ld_addresses, ld_hours_list = [], [], [], []
    ld_name = ld_description = ""
    if business:
        ld_name = clean_text(business.get("name"))
        ld_description = clean_text(business.get("description", ""))
        if business.get("telephone"):
            ld_phones.append(clean_text(business["telephone"]))
        if business.get("email"):
            ld_emails.append(clean_text(business["email"]))
        address = format_address(business.get("address"))
        if address:
            ld_addresses.append(address)
        ld_hours_list = ld_hours(business)

    # ---- contact
    phones = dedupe_phones(ld_phones + tel_phones)
    if not phones:
        phones = dedupe_phones(extract_phones_from_text("\n".join(lines)))[:5]

    emails = unique_list(ld_emails + mail_emails + extract_emails(body_text))

    addresses = unique_list(ld_addresses + address_tags + extract_addresses_from_lines(lines))
    address_source = "JSON-LD" if ld_addresses else "HTML"

    # ---- hours
    hours = ld_hours_list or extract_hours_from_lines(lines)
    hours_source = "JSON-LD" if ld_hours_list else "HTML text"

    # ---- menu
    menu_categories = ld_menu_items(ld_nodes)
    menu_method = "json-ld"
    if not menu_categories:
        menu_categories = extract_menu_from_dom(soup)
        menu_method = "html"

    # ---- name / description
    name = ld_name or og_site_name
    if not name:
        segments = [s.strip() for s in re.split(r"\s[\|\-–—·:]\s", og_title or title) if s.strip()]
        for seg in segments:
            if seg.lower() not in {"home", "welcome", "menu", "homepage"}:
                name = seg
                break
    if not name:
        name = get_host(base_url)

    description = ld_description or meta_description or og_description

    # ---- signals
    reservation_text_signal = re.search(
        r"\b(reserve a table|book a table|table reservations?|reservations?|book your table)\b",
        text_lower,
    )
    ordering_text_signal = re.search(
        r"\b(order online|online order(?:ing)?|order now|delivery|takeaway|take-away|takeout|pick-?up|home delivery)\b",
        text_lower,
    )

    def snippet(pattern):
        for line in lines:
            if len(line) <= 200 and re.search(pattern, line, re.I):
                return line
        return ""

    js_markers = ['id="root"', "id='root'", "__next_data__", 'id="__next"', "ng-version",
                  "data-reactroot", "__nuxt", "expo", "id=\"app\""]

    return {
        "title": title,
        "name": name,
        "description": description,
        "meta_description": meta_description,
        "language": language,
        "canonical": canonical,
        "favicon_url": favicon_url,
        "mobile_viewport": viewport is not None,
        "h1": h1, "h2": h2, "h3": h3,
        "lines": lines,
        "body_text": body_text,
        "word_count": len(body_text.split()),
        "links": links,
        "images": images,
        "forms": len(soup.find_all("form")),
        "phones": phones,
        "emails": emails,
        "addresses": addresses,
        "address_source": address_source,
        "hours": hours,
        "hours_source": hours_source,
        "menu_categories": menu_categories,
        "menu_method": menu_method,
        "social": extract_social(links["external"] + links["internal"]),
        "reservation_platforms": detect_platforms(html_lower, RESERVATION_PLATFORMS),
        "ordering_platforms": detect_platforms(html_lower, ORDERING_PLATFORMS),
        "reservation_signal": bool(reservation_text_signal),
        "ordering_signal": bool(ordering_text_signal),
        "booking_info": snippet(r"reserv|book a table|book your table"),
        "delivery_info": snippet(r"order online|delivery|takeaway|take-away|takeout|pick-?up"),
        "about_text": extract_about_text(soup),
        "structured_data": [raw[:10000] for raw in ld_raw],
        "structured_data_count": len(ld_raw),
        "javascript_app": any(marker in html_lower for marker in js_markers),
        "html_size": len(html),
    }


def page_is_thin(page):
    return page["word_count"] < 120 or len(page["links"]["internal"]) < 3


# ============================================================
# MERGE / SUBPAGES
# ============================================================

def fetch_subpage(url):
    result = fetch_http(url, timeout=12)
    if not result.get("success"):
        return None
    try:
        return parse_page(result["html"], result["final_url"])
    except Exception:
        return None


def merge_menu(category_lists):
    merged = {}
    order = []
    seen = set()
    for categories in category_lists:
        for cat in categories:
            name = cat["name"]
            for item in cat.get("items", []):
                key = (item["name"].lower(), item.get("price", ""))
                if key in seen:
                    continue
                seen.add(key)
                if name not in merged:
                    merged[name] = {"name": name, "items": [], "source": cat.get("source", "")}
                    order.append(name)
                merged[name]["items"].append(item)
    return [merged[n] for n in order]


def is_pdf(url):
    return urlparse(url).path.lower().endswith(".pdf")


# ============================================================
# RULE-BASED ANALYSIS (fallback when no LLM is connected)
# ============================================================

def build_analysis(facts):
    features = facts["features"]
    menu_items = sum(len(c["items"]) for c in facts["menu"]["categories"])
    score = 0
    strengths, problems, missing, recs = [], [], [], []

    def check(ok, points, strength=None, problem=None, miss=None, rec=None):
        nonlocal score
        if ok:
            score += points
            if strength:
                strengths.append(strength)
        else:
            if problem:
                problems.append(problem)
            if miss:
                missing.append(miss)
            if rec:
                recs.append(rec)

    check(menu_items >= 3, 20, "Menu items are readable on the website.",
          "Menu could not be read as structured items.", "Readable online menu",
          "Publish the menu as real HTML text (not images/PDF only), ideally with prices.")
    check(features["phone"], 10, "Phone number is published.", miss="Phone number",
          rec="Show a clickable phone number in the header and footer.")
    check(features["email"], 5, "Email address is published.", miss="Email address")
    check(features["address"], 10, "Address is published.", miss="Address",
          rec="Add a full street address and a map link.")
    check(bool(facts["opening_hours"]["hours"]), 10, "Opening hours are listed.",
          miss="Opening hours", rec="Add opening hours (and mark them up with schema.org).")
    check(facts["reservations"]["available"], 7, "Reservations are supported.",
          miss="Reservations", rec="Add a table-booking link or widget.")
    check(facts["ordering"]["available"], 7, "Online ordering / delivery is supported.",
          miss="Online ordering", rec="Add an online ordering or delivery link.")
    check(features["social_media"], 6, "Social media profiles are linked.", miss="Social media links",
          rec="Link your Instagram / Facebook / TikTok profiles.")
    check(facts["technical"]["https"], 5, "Site uses HTTPS.", "Site is not served over HTTPS.")
    check(facts["technical"]["mobile_responsive"], 5, "Mobile viewport is configured.",
          "No mobile viewport tag found.")
    check(bool(facts["seo"]["meta_description"]), 5, "Meta description is set.",
          "Meta description is missing.", rec="Write a 120-160 character meta description.")
    check(facts["seo"]["h1_count"] == 1, 4, "Exactly one H1 heading.",
          f"Page has {facts['seo']['h1_count']} H1 headings (should be 1).")
    check(facts["technical"]["structured_data"], 6, "Structured data (JSON-LD) is present.",
          "No structured data found.", rec="Add Restaurant / Menu JSON-LD so Google can show rich results.")

    priority = "High" if score < 50 else "Medium" if score < 75 else "Low"
    name = facts["restaurant"]["name"]
    summary = (
        f"{name} scored {score}/100 in the automatic audit. "
        f"{menu_items} menu items, {len(facts['contact']['phones'])} phone number(s) and "
        f"{len(facts['contact']['emails'])} email(s) were detected."
    )

    return {
        "score": min(score, 100),
        "priority": priority,
        "summary": summary,
        "strengths": strengths,
        "problems": problems,
        "missing_features": missing,
        "recommendations": recs,
        "ai_status": "rule-based",
    }


# ============================================================
# MAIN SCANNER
# ============================================================

def scan_website(url: str):
    requested_url = normalize_url(url)
    total_start = time.perf_counter()

    # ---------------- 1. HTTP first
    http_result = fetch_http(requested_url)
    page = None
    method = "HTTP"
    status_code = http_result.get("status_code")
    final_url = http_result.get("final_url", requested_url)
    warning = None

    if http_result.get("success"):
        try:
            page = parse_page(http_result["html"], http_result["final_url"])
        except Exception as exc:
            warning = f"HTTP parse failed: {exc}"

    # ---------------- 2. Browser fallback when thin / blocked
    if page is None or page_is_thin(page):
        browser_result = render_with_playwright(requested_url)

        if browser_result.get("success"):
            try:
                rendered = parse_page(browser_result["html"], browser_result["final_url"])
                if page is None or rendered["word_count"] >= page["word_count"]:
                    page = rendered
                    method = "PLAYWRIGHT"
                    status_code = browser_result["status_code"]
                    final_url = browser_result["final_url"]
            except Exception as exc:
                warning = f"Browser parse failed: {exc}"
        elif page is None:
            return {
                "scan_successful": False,
                "website": requested_url,
                "requested_url": requested_url,
                "error": (
                    f"Website could not be scanned. HTTP: {http_result.get('error')}. "
                    f"Browser: {browser_result.get('error')}"
                ),
            }
        else:
            warning = f"Browser rendering failed ({browser_result.get('error')}); HTTP content used."

    # ---------------- 3. Follow menu / contact / about pages
    cat = page["links"]["categorized"]

    def internal_only(urls):
        return [u for u in urls if is_internal_url(u, final_url)
                and u.rstrip("/") != final_url.rstrip("/")]

    menu_links_all = cat["menu"]
    menu_pages = [u for u in internal_only(menu_links_all) if not is_pdf(u)][:2]
    contact_pages = internal_only(cat["contact"])[:1]
    about_pages = internal_only(cat["about"])[:1]

    sub_urls = unique_list(menu_pages + contact_pages + about_pages)
    sub_pages = {}

    if sub_urls:
        with ThreadPoolExecutor(max_workers=4) as pool:
            for sub_url, parsed in zip(sub_urls, pool.map(fetch_subpage, sub_urls)):
                if parsed:
                    sub_pages[sub_url] = parsed

    # JS-rendered menu page? try the browser once for the first menu page.
    if menu_pages and not page["menu_categories"]:
        first = sub_pages.get(menu_pages[0])
        if not first or not first["menu_categories"]:
            rendered_menu = render_with_playwright(menu_pages[0])
            if rendered_menu.get("success"):
                try:
                    sub_pages[menu_pages[0]] = parse_page(
                        rendered_menu["html"], rendered_menu["final_url"]
                    )
                except Exception:
                    pass

    # ---------------- 4. Merge everything
    all_pages = [page] + list(sub_pages.values())

    menu_categories = merge_menu([p["menu_categories"] for p in all_pages])
    menu_source_url = None
    menu_source_method = None
    for sub_url in menu_pages:
        sp = sub_pages.get(sub_url)
        if sp and sp["menu_categories"]:
            menu_source_url, menu_source_method = sub_url, sp["menu_method"]
            break
    if menu_categories and not menu_source_url:
        menu_source_url, menu_source_method = final_url, page["menu_method"]

    if not menu_categories:
        for sub_url in menu_pages:
            sp = sub_pages.get(sub_url)
            if sp and sp["word_count"] >= 50:
                menu_categories.append({
                    "name": "Menu page text",
                    "items": [],
                    "raw_content": sp["body_text"][:2000],
                    "source": sub_url,
                })
                break

    phones = dedupe_phones([ph for p in all_pages for ph in p["phones"]])[:8]
    emails = unique_list([e for p in all_pages for e in p["emails"]])[:8]
    addresses = unique_list([a for p in all_pages for a in p["addresses"]])[:10]
    hours = next((p["hours"] for p in all_pages if p["hours"]), [])
    hours_source = next((p["hours_source"] for p in all_pages if p["hours"]), "")
    about_text = next(
        (sub_pages[u]["about_text"] for u in about_pages if u in sub_pages and sub_pages[u]["about_text"]),
        page["about_text"],
    )

    social = {key: [] for key in SOCIAL_KEYS}
    for p in all_pages:
        for key, vals in p["social"].items():
            social[key] = unique_list(social[key] + vals)

    reservation_links = unique_list(cat["reservation"])
    ordering_links = unique_list(cat["ordering"])
    reservation_platforms = unique_list([x for p in all_pages for x in p["reservation_platforms"]])
    ordering_platforms = unique_list([x for p in all_pages for x in p["ordering_platforms"]])
    reservation_available = bool(reservation_links or reservation_platforms or page["reservation_signal"])
    ordering_available = bool(ordering_links or ordering_platforms or page["ordering_signal"])

    contact_links = unique_list(cat["contact"])[:5]
    about_links = unique_list(cat["about"])[:5]
    menu_links = unique_list(menu_links_all)[:10]

    primary_address = addresses[0] if addresses else ""
    map_link = (
        f"https://www.google.com/maps/search/?api=1&query={quote(primary_address)}"
        if primary_address else ""
    )

    has_social = any(social[k] for k in SOCIAL_KEYS)
    menu_item_count = sum(len(c["items"]) for c in menu_categories)

    images = page["images"]
    internal_count = len(page["links"]["internal"])
    external_count = len(page["links"]["external"])

    total_ms = round((time.perf_counter() - total_start) * 1000, 2)
    is_https = final_url.startswith("https://")

    facts = {
        "scan_successful": True,
        "scanner_method": method,
        "website": requested_url,
        "requested_url": requested_url,
        "final_url": final_url,
        "status_code": status_code or 200,
        "response_time_ms": total_ms,

        "restaurant": {
            "name": page["name"],
            "description": page["description"],
            "language": page["language"],
            "favicon_url": page["favicon_url"],
        },

        "menu": {
            "categories": menu_categories,
            "menu_links": menu_links,
            "source_url": menu_source_url,
            "source_method": menu_source_method,
            "total_items": menu_item_count,
        },

        "contact": {
            "phones": phones,
            "emails": emails,
            "addresses": addresses,
            "contact_page_links": contact_links,
        },

        "location": {
            "primary_address": primary_address,
            "all_addresses": addresses,
            "map_link": map_link,
            "source": page["address_source"] if addresses else "",
        },

        "opening_hours": {"hours": hours, "source": hours_source},

        "reservations": {
            "available": reservation_available,
            "booking_info": page["booking_info"],
            "reservation_links": reservation_links,
            "booking_platforms": reservation_platforms,
        },

        "ordering": {
            "available": ordering_available,
            "delivery_info": page["delivery_info"],
            "ordering_links": ordering_links,
            "ordering_platforms": ordering_platforms,
        },

        "social_media": social,

        "about": {"about_text": about_text, "about_links": about_links},

        "navigation": {
            "contact_links": contact_links,
            "menu_links": menu_links,
            "about_links": about_links,
        },

        "features": {
            "menu": bool(menu_item_count or menu_links),
            "reservation": reservation_available,
            "online_ordering": ordering_available,
            "contact": bool(phones or emails or contact_links),
            "social_media": has_social,
            "email": bool(emails),
            "phone": bool(phones),
            "address": bool(addresses),
        },

        "content": {"word_count": page["word_count"]},

        "seo": {
            "title": page["title"],
            "title_length": len(page["title"]),
            "meta_description": page["meta_description"],
            "meta_description_length": len(page["meta_description"]),
            "canonical_url": page["canonical"],
            "h1": page["h1"],
            "h2": page["h2"],
            "h1_count": len(page["h1"]),
            "structured_data_count": page["structured_data_count"],
            "mobile_viewport": page["mobile_viewport"],
        },

        "technical": {
            "https": is_https,
            "mobile_responsive": page["mobile_viewport"],
            "javascript_app": page["javascript_app"],
            "structured_data": page["structured_data_count"] > 0,
            "favicon": bool(page["favicon_url"]),
            "canonical": bool(page["canonical"]),
        },

        "media": {
            "total_images": len(images),
            "images_without_alt": sum(1 for i in images if not i["alt"]),
        },

        "scanner": {
            "html_size": page["html_size"],
            "word_count": page["word_count"],
            "image_count": len(images),
            "internal_link_count": internal_count,
            "external_link_count": external_count,
            "pages_followed": list(sub_pages.keys()),
        },

        # ---- legacy flat keys (kept so older backend code keeps working)
        "page_title": page["title"],
        "meta_description": page["meta_description"],
        "word_count": page["word_count"],
        "emails": emails,
        "phones": phones,
        "addresses": addresses,
        "links": page["links"],
        "images": images,
        "h1": page["h1"], "h2": page["h2"], "h3": page["h3"],
        "social_links": [l for v in social.values() for l in v],
        "canonical_url": page["canonical"],
        "favicon_url": page["favicon_url"],
        "mobile_responsive": page["mobile_viewport"],
        "language": page["language"],
        "structured_data": page["structured_data"],
        "body_text": page["body_text"][:15000],
    }

    if warning:
        facts["warning"] = warning

    facts["ai_analysis"] = build_analysis(facts)
    return facts