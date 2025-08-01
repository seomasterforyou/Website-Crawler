import streamlit as st
import requests
import xml.etree.ElementTree as ET
import pandas as pd
from io import StringIO
from urllib.parse import urljoin, urlparse
import time

st.set_page_config(page_title="Website Crawler", layout="centered")
st.title("🌐 Website Crawler")

# Input section
base_url = st.text_input("Enter Your Website URL", placeholder="https://example.com")
remove_blogs = st.checkbox("Remove Blogs", value=False)
only_mainsite = st.checkbox("Only Mainsite", value=False)
generate_keywords = st.checkbox("Generate Keywords")
add_location_pages = st.checkbox("Location Pages Only")  # NEW CHECKBOX

main_keyword_input = ""
if generate_keywords:
    main_keyword_input = st.text_input("Enter the Mainsite Keyword with Location")

# Session state
if "filter_enabled" not in st.session_state:
    st.session_state.filter_enabled = False
if "filter_type" not in st.session_state:
    st.session_state.filter_type = ""
if "filter_keyword" not in st.session_state:
    st.session_state.filter_keyword = ""

# Filter toggle button
def toggle_filter():
    st.session_state.filter_enabled = not st.session_state.filter_enabled
    if not st.session_state.filter_enabled:
        st.session_state.filter_type = ""
        st.session_state.filter_keyword = ""

if st.session_state.filter_enabled:
    st.button("❌ Remove Filter", on_click=toggle_filter)
else:
    st.button("➕ Add Filter", on_click=toggle_filter)

if st.session_state.filter_enabled:
    st.session_state.filter_type = st.selectbox(
        "Choose Filter Type", ["URLs Containing", "URLs Not Containing"], key="filter_type_box"
    )
    st.session_state.filter_keyword = st.text_input(
        "Enter Filter Keyword", value=st.session_state.filter_keyword
    )

# Sitemap parser
def parse_urls_from_xml(xml_text):
    urls = []
    try:
        root = ET.fromstring(xml_text)
        for loc in root.findall(".//{http://www.sitemaps.org/schemas/sitemap/0.9}loc"):
            if loc.text:
                urls.append(loc.text.strip())
    except:
        pass
    return urls

# Keyword generator
def convert_url_to_keyword(url, homepage_url, main_keyword, location):
    parsed_url = urlparse(url)
    path = parsed_url.path.strip("/")
    if any(x in url.lower() for x in [
        "/about.htm", "/about-us.htm", "/market-area.htm", "/gallery.htm",
        "/video-gallery.htm", "/blog.htm", "/contact-us.htm", "/sitemap.htm"
    ]):
        return None
    if url.rstrip("/") == homepage_url.rstrip("/"):
        return main_keyword
    segments = path.split("/")
    if len(segments) == 1 and segments[0].endswith(".htm"):
        slug = segments[0].replace("-", " ").replace(".htm", "").strip().title()
        return f"{slug} Manufacturers in {location}"
    elif len(segments) == 2 and segments[1].endswith(".htm"):
        state = segments[0].replace("-", " ").title()
        slug = segments[1].replace("-", " ").replace(".htm", "").strip().title()
        return f"{slug} Manufacturers in {state}"
    elif len(segments) == 1 or (len(segments) == 2 and not segments[1].endswith(".htm")):
        state = segments[0].replace("-", " ").title()
        base = main_keyword.replace(f" in {location}", "").strip()
        return f"{base} in {state}"
    return None

# Crawl button
if st.button("Crawl Website"):
    if not base_url.startswith("http"):
        st.error("❌ Please enter a valid URL starting with http:// or https://")
    else:
        all_urls = []
        timeout = 8
        max_sitemaps_to_try = 50
        max_consecutive_failures = 2
        consecutive_failures = 0

        progress_text = st.empty()
        progress_bar = st.progress(0)
        progress_text.markdown("🚀 **Your Website is getting crawled...**")

        # Load /sitemap.xml
        try:
            res = requests.get(urljoin(base_url, "/sitemap.xml"), timeout=timeout)
            if res.status_code == 200 and "<loc>" in res.text:
                urls = parse_urls_from_xml(res.text)
                all_urls.extend(urls)
        except:
            pass

        # Try sitemap1.xml to sitemapN.xml
        for i in range(1, max_sitemaps_to_try + 1):
            sitemap_url = urljoin(base_url, f"/sitemap{i}.xml")
            try:
                res = requests.get(sitemap_url, timeout=timeout)
                if res.status_code == 200 and "<loc>" in res.text:
                    urls = parse_urls_from_xml(res.text)
                    if urls:
                        all_urls.extend(urls)
                        consecutive_failures = 0
                    else:
                        consecutive_failures += 1
                else:
                    consecutive_failures += 1
            except:
                consecutive_failures += 1

            progress_percent = int((i / max_sitemaps_to_try) * 100)
            progress_bar.progress(min(progress_percent, 100))
            time.sleep(0.05)

            if consecutive_failures >= 2:
                break

        all_urls = sorted(set(all_urls))

        # 🔴 Always exclude these slugs
        excluded_slugs = [
            "/market-area.htm", "/about-us.htm", "/gallery.htm", "/video-gallery.htm",
            "/blog.htm", "/contact-us.htm", "/sitemap.htm"
        ]
        all_urls = [url for url in all_urls if all(slug not in url.lower() for slug in excluded_slugs)]

        # Remove blogs (if extra check)
        if remove_blogs:
            all_urls = [url for url in all_urls if "/blog" not in url]

        # Only Mainsite
        if only_mainsite:
            filtered = []
            for url in all_urls:
                try:
                    path = url.split("//", 1)[-1].split("/", 1)[-1]
                    if path.count("/") == 0 and path.endswith(".htm"):
                        filtered.append(url)
                except:
                    pass
            homepage = base_url.rstrip("/")
            if not homepage.endswith(".htm"):
                filtered.insert(0, homepage)
            all_urls = filtered

        # Add Location Pages Only (NEW LOGIC)
        if add_location_pages:
            all_urls = [
                url for url in all_urls 
                if url.rstrip("/").count("/") == 3 and url.endswith("/")
            ]

        # Apply filter
        if st.session_state.filter_enabled and st.session_state.filter_type and st.session_state.filter_keyword.strip():
            keyword = st.session_state.filter_keyword.strip().lower()
            if st.session_state.filter_type == "URLs Containing":
                all_urls = [url for url in all_urls if keyword in url.lower()]
            elif st.session_state.filter_type == "URLs Not Containing":
                all_urls = [url for url in all_urls if keyword not in url.lower()]

        # Generate keywords
        final_data = []
        if generate_keywords and main_keyword_input.strip():
            location = main_keyword_input.strip().rsplit(" in ", 1)[-1]
            homepage_url = base_url.rstrip("/")
            for url in all_urls:
                keyword = convert_url_to_keyword(url, homepage_url, main_keyword_input.strip(), location)
                if keyword:
                    final_data.append((url, keyword))
        else:
            final_data = [(url, "") for url in all_urls]

        # Output results
        progress_bar.progress(100)
        progress_text.markdown("✅ **Website crawl complete.**")

        if final_data:
            st.success(f"✅ Processed {len(final_data)} items.")
            df = pd.DataFrame(final_data, columns=["URL", "Keyword"])
            st.dataframe(df.head(50), use_container_width=True)

            # Download CSV
            csv_buffer = StringIO()
            df.to_csv(csv_buffer, index=False)
            st.download_button("📥 Download as CSV", data=csv_buffer.getvalue(), file_name="url_keywords.csv", mime="text/csv")

            # Download TXT
            txt_data = "\n".join([f"{url} -> {kw}" for url, kw in final_data])
            st.download_button("📄 Download as TXT", data=txt_data, file_name="url_keywords.txt", mime="text/plain")
        else:
            st.error("❌ No matching results found.")
