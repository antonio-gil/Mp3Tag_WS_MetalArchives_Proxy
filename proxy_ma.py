import json
import logging
import re
import signal
import sys
import time

from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs, quote
from pathlib import Path

from playwright_session import PlaywrightSessionManager
from cache_ma import save_in_cache, get_data_from_cache, cleanup_expired_cache

PORT = 5000

def get_base_dir():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    else:  # ejecución como script
        return Path(__file__).resolve().parent

base_dir = get_base_dir()
debug_dir = base_dir / "debug"
log_dir = base_dir / "logs"

debug_dir.mkdir(exist_ok=True)
log_dir.mkdir(exist_ok=True)

# Filename with Date
log_filename = datetime.now().strftime("proxy_log_%Y-%m-%d.log")
log_path = log_dir / log_filename

# Daily Log Configuration
logging.basicConfig(
    filename=str(log_path),
    level=logging.INFO,
    format="%(asctime)s - %(message)s"
)

class MAProxyHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        client_ip = self.client_address[0]
        logging.info(f"{client_ip} - GET {self.path}")

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)
        path = parsed.path

        if path == "/search":
            artist = params.get("artist", [""])[0]
            album = params.get("album", [""])[0]
            result = search_albums(artist, album)
            self._send_json(result)
        elif path == "/search_artist":
            artist = params.get("artist", [""])[0]
            result = search_artists(artist)
            self._send_json(result)
        elif path == "/search_full":
            artist = params.get("artist", [""])[0]
            album = params.get("album", [""])[0]
            result = search_albums_with_info(artist, album)
            self._send_json(result)
        elif path == "/album":
            url = params.get("url", [""])[0]
            if not url:
                self._send_json({"error": "Missing parameter: 'url'"}) #, code = 400)
                return
            result = get_album(url)
            self._send_json(result)
        elif path == "/album_full":
            url = params.get("url", [""])[0]
            if not url:
                self._send_json({"error": "Missing parameter: 'url'"}) #, code = 400)
                return
            result = get_album_with_artist_info(url)
            self._send_json(result)
        elif path == "/artist_info":
            url = params.get("url", [""])[0]
            if not url:
                self._send_json({"error": "Missing parameter: 'url'"}) #, code = 400)
                return
            result = get_artist_info(url)
            self._send_json(result)
        else:
            if path != "/favicon.ico":
                self._send_json({"error": "Invalid Path"}) #, code = 404)

    def _send_json(self, data):
        response = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(response)))
        self.end_headers()
        self.wfile.write(response)

def search_albums(artist, album):
    base_url = "https://www.metal-archives.com/search/ajax-advanced/searching/albums/"
    query_params = "?releaseYearFrom=0001&releaseYearTo=9999&sEcho=1&iColumns=4&exactBandMatch=1"
    if artist and album:
        query_params += f"&bandName={quote(artist)}&releaseTitle={quote(album)}"
    elif artist:
        query_params += f"&bandName={quote(artist)}"
    elif album:
        query_params += f"&releaseTitle={quote(album)}"
    else:
        return {"error": "Missing required values: 'artist' or 'album'"}

    full_url = base_url + query_params
    cache_key = f"search:{artist}|{album}"
    cached = get_data_from_cache(cache_key)
    if cached:
        print(f"✅ Cache found for current search: {cache_key}")
        return cached

    try:
        page = PlaywrightSessionManager.start()
        response_data = {}

        def handle_response(response):
            if "ajax-advanced/searching/albums" in response.url and response.status == 200:
                try:
                    json_data = response.json()
                    response_data.update(json_data)
                except:
                    pass

        page.on("response", handle_response)
        page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        if not response_data or "aaData" not in response_data:
            return {"error": "Couldn't capture AJAX response"}

        results = []
        for row in response_data["aaData"]:
            if len(row) < 4:
                continue

            artist_html = row[0]
            artist_text = re.sub(r"<.*?>", "", artist_html).strip()

            album_html = row[1]
            match = re.search(r'href="([^"]+)">([^<]+)', album_html)
            album_url = match.group(1) if match else ""
            album_title = match.group(2) if match else ""

            release_type = row[2].strip()
            release_date_raw = row[3]
            match_date = re.search(r'<!--\s*(\d{4}-\d{2}-\d{2})\s*-->', release_date_raw)
            release_year = match_date.group(1) if match_date else release_date_raw.strip()

            results.append({
                "artist": artist_text,
                "album": album_title,
                "metal_archives_album_url": f"http://localhost:{PORT}/album?url={quote(album_url)}",
                "metal_archives_type": release_type,
                "year": release_year
            })

        save_in_cache(cache_key, {"results": results})

        debug_path_search = debug_dir / "debug_mp3tag_output_search.txt"
        with open(debug_path_search, "w", encoding="utf-8") as log_file:
            log_file.write("🔍 Used Metal Archives URL:\n")
            log_file.write(full_url + "\n\n")
            log_file.write("📦 Data sent to Mp3tag:\n")
            log_file.write(json.dumps({"results": results}, indent=2, ensure_ascii=False))

        return {"results": results}
    except Exception as e:
        PlaywrightSessionManager.close()
        return {"error": str(e)}

def get_album(url):
    try:
        cleanup_expired_cache()
        cache_key = f"album:{url}"
        cached = get_data_from_cache(cache_key)
        if cached:
            print(f"✅ Cache found for album: {cache_key}")
            return cached

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_path = debug_dir / f"debug_album_html.html"
        log_path = log_dir / f"debug_album_log.txt"

        page = PlaywrightSessionManager.get_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        html = page.content()

        with open(html_path, "w", encoding="utf-8") as log_file:
            log_file.write(html)

        parsed_html = BeautifulSoup(html, "html.parser")

        def get_text(selector):
            html_element = parsed_html.select_one(selector)
            return html_element.text.strip() if html_element else ""

        def get_attr(selector, attr):
            html_element = parsed_html.select_one(selector)
            return html_element[attr].strip() if html_element and html_element.has_attr(attr) else ""

        def extract_tracks():
            tracks = []
            disc_number = "1"
            rows = parsed_html.select("table.table_lyrics tr")
            for row in rows:
                html = str(row)
                if "discRow" in html:
                    match = re.search(r'Disc\s+(\d+)', html)
                    if match:
                        disc_number = match.group(1)
                elif "wrapWords" in html:
                    cols = row.find_all("td")
                    if len(cols) >= 4:
                        title = cols[1].text.strip()
                        class_attr = cols[1].get("class", [])
                        bonus = "1" if "bonus" in class_attr else ""
                        length = cols[2].text.strip()
                        fourth_col_html = str(cols[3])
                        instrumental = "1" if "<em>instrumental</em>" in fourth_col_html.lower() else ""
                        tracks.append({
                            "discnumber": disc_number,
                            "track": title,
                            "bonus": bonus,
                            "length": length,
                            "instrumental": instrumental
                        })
            return tracks

        release_date_raw = get_text("dt:-soup-contains('Release date:') + dd") or get_text("dt:has-text('Release date:') + dd")
        release_date_formatted = format_date(release_date_raw)

        result = {
            "metal_archives_album_url": url,
            "metal_archives_band_url": get_attr("h2.band_name a", "href"),
            "coverurl": get_attr("div.album_img a", "href"),
            "album": get_text("h1.album_name") or get_text("h1.album_name.noCaps"),
            "artist": get_text("h2.band_name a") or get_text("h2.band_name.noCaps a"),
            "metal_archives_type": get_text("dt:-soup-contains('Type:') + dd"),
            "year": re.search(r"\d{4}", release_date_raw).group(0) if re.search(r"\d{4}", release_date_raw) else "",
            "metal_archives_date": release_date_formatted,
            "catalog": get_text("dt:-soup-contains('Catalog ID:') + dd"),
            "metal_archives_edition": get_text("dt:-soup-contains('Version desc.:') + dd"),
            "publisher": get_text("dt:-soup-contains('Label:') + dd"),
            "metal_archives_rating": re.search(r"\(avg\.\s*([\d\.]+)%\)", get_text("dt:-soup-contains('Reviews:') + dd") or "").group(1) + "%" if re.search(r"\(avg\.\s*([\d\.]+)%\)", get_text("dt:-soup-contains('Reviews:') + dd") or "") else "",
            "metal_archives_info": extract_addtional_info(parsed_html),
            "tracks": extract_tracks()
        }

        with open(log_path, "w", encoding="utf-8") as log_file:
            for result_key, result_value in result.items():
                if result_key == "tracks":
                    log_file.write(f"{result_key}:\n")
                    if not result_value:
                        log_file.write("  [EMPTY]\n")
                    for current_track in result_value:
                        log_file.write(f"  {current_track}\n")
                        for field, value in current_track.items():
                            if contains_unicode(value):
                                log_file.write(f"    ⚠️ {field} contains Unicode\n")
                else:
                    if not result_value:
                        log_file.write(f"{result_key}: [EMPTY]\n")
                    else:
                        log_file.write(f"{result_key}: {result_value}\n")
                        if isinstance(result_value, str) and contains_unicode(result_value):
                            log_file.write(f"  ⚠️ {result_key} contains Unicode\n")

        save_in_cache(cache_key, result)

        debug_path_album = debug_dir / "debug_mp3tag_output_album.txt"
        with open(debug_path_album, "w", encoding="utf-8") as log_file:
            log_file.write("🔍 Used Metal Archives URL:\n")
            log_file.write(url + "\n\n")
            log_file.write("📦 Data sent to Mp3tag:\n")
            log_file.write(json.dumps({"results": result}, indent=2, ensure_ascii=False))

        return result
    except Exception as e:
        PlaywrightSessionManager.close()
        return {"error": str(e)}

def search_artists(artist):
    base_url = "https://www.metal-archives.com/search/ajax-advanced/searching/bands/"
    query_params = "?genre=&country=&yearCreationFrom=&yearCreationTo=&bandNotes=&status=&themes=&location=&bandLabelName=&sEcho=1&iColumns=3&sColumns=&iDisplayStart=0&iDisplayLength=200&exactBandMatch=1"
    if artist:
        query_params += f"&bandName={quote(artist)}"
    else:
        return {"error": "Missing required value: 'artist'"}

    full_url = base_url + query_params

    cache_key = f"search:{artist}|info"
    cached = get_data_from_cache(cache_key)
    if cached:
        print(f"✅ Cache found for current search: {cache_key}")
        return cached

    try:
        page = PlaywrightSessionManager.start()
        response_data = {}

        def handle_response(response):
            if "ajax-advanced/searching/bands" in response.url and response.status == 200:
                try:
                    json_data = response.json()
                    response_data.update(json_data)
                except:
                    pass

        page.on("response", handle_response)
        page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        if not response_data or "aaData" not in response_data:
            # PlaywrightSessionManager.close()
            return {"error": "Couldn't capture AJAX response"}

        results = []
        for row in response_data["aaData"]:
            # if len(row) < 4:
            #     continue

            artist_html = row[0]
            match = re.search(r'href="([^"]+)">([^<]+)', artist_html)
            artist_url = match.group(1) if match else ""
            artist_name = match.group(2) if match else ""

            artist_genres = row[1].strip()
            artist_country = row[2].strip()

            results.append({
                "artist": artist_name,
                "artist_genres": artist_genres,
                "metal_archives_artist_url": f"http://localhost:{PORT}/artist_info?url={quote(artist_url)}",
                "country": artist_country
            })

        save_in_cache(cache_key, {"results": results})

        debug_path_search = debug_dir / "debug_mp3tag_output_search.txt"
        with open(debug_path_search, "w", encoding="utf-8") as log_file:
            log_file.write("🔍 Used Metal Archives URL:\n")
            log_file.write(full_url + "\n\n")
            log_file.write("📦 Data sent to Mp3tag:\n")
            log_file.write(json.dumps({"results": results}, indent=2, ensure_ascii=False))

        return {"results": results}
    except Exception as e:
        PlaywrightSessionManager.close()
        return {"error": str(e)}

def get_artist_info(url):
    try:
        cleanup_expired_cache()
        cache_key = f"band:{url}"
        cached = get_data_from_cache(cache_key)
        if cached:
            print(f"✅ Cache found for selected band: {cache_key}")
            return cached

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        html_path = debug_dir / "debug_band_html.html"
        log_path = debug_dir / "debug_band_log.txt"

        page = PlaywrightSessionManager.get_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        html = page.content()

        with open(html_path, "w", encoding="utf-8") as log_file:
            log_file.write(html)

        parsed_html = BeautifulSoup(html, "html.parser")

        def get_text(selector):
            el = parsed_html.select_one(selector)
            return el.text.strip() if el else ""

        def get_dd_text(label):
            dt = parsed_html.find("dt", string=re.compile(label))
            dd = dt.find_next_sibling("dd") if dt else None
            return dd.text.strip() if dd else ""

        result = {
            "metal_archives_band_url": url,
            "country": get_dd_text("Country of origin:"),
            "metal_archives_location": get_dd_text("Location:"),
            "metal_archives_status": get_dd_text("Status:"),
            "metal_archives_formation_year": get_dd_text("Formed in:"),
            "genre": get_dd_text("Genre:"),
            "metal_archives_lyrical_themes": get_dd_text("Themes:")
        }

        with open(log_path, "w", encoding="utf-8") as log_file:
            for key, value in result.items():
                log_file.write(f"{key}: {value}\n")
                if contains_unicode(value):
                    log_file.write(f"  ⚠️ {key} contains Unicode\n")

        debug_path_band = debug_dir / "debug_mp3tag_output_band.txt"
        with open(debug_path_band, "w", encoding="utf-8") as log_file:
            log_file.write("🔍 Used Metal Archives URL:\n")
            log_file.write(url + "\n\n")
            log_file.write("📦 Data sent to Mp3tag:\n")
            log_file.write(json.dumps({"results": result}, indent=2, ensure_ascii=False))

        save_in_cache(cache_key, result)
        return result

    except Exception as e:
        PlaywrightSessionManager.close()
        return {"error": str(e)}

def search_albums_with_info(artist, album):
    base_url = "https://www.metal-archives.com/search/ajax-advanced/searching/albums/"
    query_params = "?releaseYearFrom=0001&releaseYearTo=9999&sEcho=1&iColumns=4&exactBandMatch=1"
    if artist and album:
        query_params += f"&bandName={quote(artist)}&releaseTitle={quote(album)}"
    elif artist:
        query_params += f"&bandName={quote(artist)}"
    elif album:
        query_params += f"&releaseTitle={quote(album)}"
    else:
        return {"error": "Missing required values: 'artist' or 'album'"}

    full_url = base_url + query_params

    cache_key = f"search_full:{artist}|{album}"
    cached = get_data_from_cache(cache_key)
    if cached:
        print(f"✅ Cache found for current search: {cache_key}")
        return cached

    try:
        page = PlaywrightSessionManager.start()
        response_data = {}

        def handle_response(response):
            if "ajax-advanced/searching/albums" in response.url and response.status == 200:
                try:
                    json_data = response.json()
                    response_data.update(json_data)
                except:
                    pass

        page.on("response", handle_response)
        page.goto(full_url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)

        if not response_data or "aaData" not in response_data:
            # PlaywrightSessionManager.close()
            return {"error": "Couldn't capture AJAX response"}

        results = []
        for row in response_data["aaData"]:
            if len(row) < 4:
                continue

            artist_html = row[0]
            artist_text = re.sub(r"<.*?>", "", artist_html).strip()

            album_html = row[1]
            match = re.search(r'href="([^"]+)">([^<]+)', album_html)
            album_url = match.group(1) if match else ""
            album_title = match.group(2) if match else ""

            release_type = row[2].strip()
            release_date_raw = row[3]
            match_date = re.search(r'<!--\s*(\d{4}-\d{2}-\d{2})\s*-->', release_date_raw)
            release_year = match_date.group(1) if match_date else release_date_raw.strip()

            results.append({
                "artist": artist_text,
                "album": album_title,
                "metal_archives_album_url": f"http://localhost:{PORT}/album_full?url={quote(album_url)}",
                "metal_archives_type": release_type,
                "year": release_year
            })

        save_in_cache(cache_key, {"results": results})

        debug_path_search = debug_dir / "debug_mp3tag_output_search.txt"
        with open(debug_path_search, "w", encoding="utf-8") as log_file:
            log_file.write("🔍 Usedd Metal Archives URL:\n")
            log_file.write(full_url + "\n\n")
            log_file.write("📦 Data sent to Mp3tag:\n")
            log_file.write(json.dumps({"results": results}, indent=2, ensure_ascii=False))

        return {"results": results}
    except Exception as e:
        PlaywrightSessionManager.close()
        return {"error": str(e)}

def get_album_with_artist_info(url):
    try:
        cleanup_expired_cache()
        cache_key = f"album_with_artist:{url}"
        cached = get_data_from_cache(cache_key)
        if cached:
            print(f"✅ Cache found for album + artist: {cache_key}")
            return cached

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_path = debug_dir / f"debug_album_with_artist_log_{timestamp}.txt"

        album_data = get_album(url)
        if "error" in album_data:
            return album_data

        artist_url = album_data.get("metal_archives_band_url", "")
        if not artist_url:
            return {"error": "Artist's URL not found on album's data"}

        artist_data = get_artist_info(artist_url)
        if "error" in artist_data:
            return artist_data

        result = {
            "metal_archives_album_url": url,
            "metal_archives_artist_url": artist_url,
            "album_data": album_data,
            "artist_data": artist_data
        }

        save_in_cache(cache_key, result)

        debug_path = debug_dir / "debug_mp3tag_output_album_with_artist.txt"
        with open(debug_path, "w", encoding="utf-8") as log_file:
            log_file.write("🔍 Used Metal Archives URL:\n")
            log_file.write(url + "\n\n")
            log_file.write("📦 Data sent to Mp3tag:\n")
            log_file.write(json.dumps({"results": result}, indent=2, ensure_ascii=False))

        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write("🔍 Consolidating album + artist\n\n")
            for section, data in result.items():
                log_file.write(f"{section}:\n")
                if isinstance(data, dict):
                    for key, value in data.items():
                        log_file.write(f"  {key}: {value}\n")
                        if isinstance(value, str) and contains_unicode(value):
                            log_file.write(f"    ⚠️ {key} contains Unicode\n")
                else:
                    log_file.write(f"  {data}\n")

        return result

    except Exception as e:
        PlaywrightSessionManager.close()
        return {"error": str(e)}

def format_date(release_date_raw):
    months = {
        "January": "01", "February": "02", "March": "03", "April": "04",
        "May": "05", "June": "06", "July": "07", "August": "08",
        "September": "09", "October": "10", "November": "11", "December": "12"
    }
    release_date_raw = release_date_raw.strip()

    for month, number in months.items():
        release_date_raw = release_date_raw.replace(month, number)

    # Case: "07 23rd, 2002" → "2002-07-23"
    match = re.search(r"(\d{2})\s+(\d{1,2})(?:st|nd|rd|th)?,?\s*(\d{4})", release_date_raw)
    if match:
        return f"{match.group(3)}-{match.group(1)}-{match.group(2).zfill(2)}"

    # Case: "07, 2002" → "2002-07-01"
    match = re.search(r"(\d{2}),?\s*(\d{4})", release_date_raw)
    if match:
        return f"{match.group(2)}-{match.group(1)}-01"

    # Case: "2002" → "2002-01-01"
    match = re.search(r"^(\d{4})$", release_date_raw)
    if match:
        return f"{match.group(1)}-01-01"

    return ""

def contains_unicode(text_to_validate):
    return any(ord(current_character) > 127 for current_character in text_to_validate)

def extract_addtional_info(parsed_html):
    container = parsed_html.select_one("div#album_tabs_notes .ui-tabs-panel-content")
    if not container:
        return ""

    test_blocks = []
    for p in container.find_all("p"):
        for br in p.find_all("br"):
            br.replace_with("\r\n")

        for tag in p.find_all(["i", "b", "a", "td"]):
            tag.unwrap()

        additional_info_text = p.get_text(separator="", strip=True)

        if additional_info_text.strip().lower() in ["recording information:", "title translation:"]:
            additional_info_text += "\r\n"

        if additional_info_text:
            test_blocks.append(additional_info_text)

    final_text = "\r\n\r\n".join(test_blocks)
    final_text = re.sub(r"(\r?\n){3,}", "\r\n\r\n", final_text)
    final_text = re.sub(r"[^\S\r\n]{2,}", " ", final_text)
    return final_text.strip()

def preload_proxy():
    try:
        page = PlaywrightSessionManager.get_page(new=True)
        page.goto("https://www.metal-archives.com/", wait_until="domcontentloaded", timeout=10000)
        print("🔥 Proxy Preloaded with Metal Archives Home Page")
    except Exception as e:
        print(f"⚠️ Error while preloading: {e}")

def preload_with_validation(retries = 3, wait_between_retries = 5):
    for attempt in range(1, retries + 1):
        try:
            print(f"🚀 Preload attempt {attempt}...")
            page = PlaywrightSessionManager.get_page(new=True)
            start_time = time.time()
            page.goto("https://www.metal-archives.com/", wait_until="domcontentloaded", timeout=10000)
            elapsed_time = time.time() - start_time

            page_title = page.title()
            if "Just a moment" in page_title or "Checking your browser" in page_title:
                print("🛑 Cloudflare Challenge detected on Title")
                raise Exception("Cloudflare challenge")

            if page.query_selector("#cf-spinner") or page.query_selector("form#challenge-form"):
                print("🛑 Cloudflare Challenge detected in DOM")
                raise Exception("Cloudflare DOM challenge")

            print(f"✅ Success! Preload completed in {elapsed_time:.2f} seconds")
            return True

        except Exception as thrown_exception:
            print(f"⚠️ Preload failed: {thrown_exception}")
            if attempt < retries:
                print(f"⏳ Waiting {wait_between_retries} seconds before retry...")
                time.sleep(wait_between_retries)
            else:
                print("❌ Preload couldn't be completed. Proxy could be blocked by Metal Archives.")
                return False
            
def graceful_shutdown(signum, frame):
    print("\n🛑 Graceful shutdown triggered")
    server.shutdown()

if __name__ == "__main__":
    preload_was_successful = preload_with_validation()
    if not preload_was_successful:
        print("⚠️ Proxy will start without Preload. There could be errors on first search.")
    cleanup_expired_cache()
    server = HTTPServer(("localhost", PORT), MAProxyHandler)

    try:
        print(f"🚀 Proxy MA with Playwright available at http://localhost:{PORT}")
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user (Ctrl+C)")
        signal.signal(signal.SIGINT, graceful_shutdown)
    finally:
        # server.server_close()
        if PlaywrightSessionManager.is_active():
            PlaywrightSessionManager.close()
        print("✅ Resources correctly released.")