#!/usr/bin/env python3
"""
Evidence photo analyzer for the legal-evidence-photos skill.

Extracts EXIF metadata, GPS coordinates, timestamps, camera info, and
file hashes from evidence photos. Generates interactive maps, evidence
catalogs, and timelines.

Usage:
    python3 analyze_photos.py --input-dir <dir> --output-dir <dir>
"""
import argparse
import hashlib
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

# ---------------------------------------------------------------------------
# Dependency imports
# ---------------------------------------------------------------------------
try:
    from PIL import Image
    from PIL.ExifTags import TAGS, GPSTAGS
except ImportError:
    print("ERROR: 'Pillow' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    import exifread
except ImportError:
    print("ERROR: 'exifread' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    import folium
    from folium.plugins import MarkerCluster
except ImportError:
    print("ERROR: 'folium' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    from geopy.geocoders import Nominatim
    from geopy.exc import GeocoderTimedOut, GeocoderServiceError
except ImportError:
    print("ERROR: 'geopy' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

try:
    import xlsxwriter
except ImportError:
    print("ERROR: 'XlsxWriter' package not installed. Run check_dependencies.py first.", file=sys.stderr)
    sys.exit(2)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tiff", ".tif", ".heic"}

# Software tags that may indicate editing
EDITING_SOFTWARE = [
    "photoshop", "gimp", "lightroom", "snapseed", "vsco", "afterlight",
    "pixelmator", "affinity", "capture one", "darktable", "rawtherapee",
    "adobe", "paint.net", "corel", "acdsee",
]


# ---------------------------------------------------------------------------
# EXIF extraction
# ---------------------------------------------------------------------------
def compute_file_hashes(filepath: str) -> dict:
    """Compute MD5 and SHA256 hashes for a file."""
    md5 = hashlib.md5()
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            while True:
                chunk = f.read(8192)
                if not chunk:
                    break
                md5.update(chunk)
                sha256.update(chunk)
        return {
            "md5": md5.hexdigest(),
            "sha256": sha256.hexdigest(),
        }
    except OSError as e:
        print(f"  Hash computation failed for {filepath}: {e}", file=sys.stderr)
        return {"md5": None, "sha256": None}


def dms_to_decimal(dms_values, ref: str) -> Optional[float]:
    """Convert GPS DMS (degrees, minutes, seconds) to decimal degrees."""
    try:
        if hasattr(dms_values, 'values'):
            # exifread IfdTag
            vals = dms_values.values
            degrees = float(vals[0].num) / float(vals[0].den)
            minutes = float(vals[1].num) / float(vals[1].den)
            seconds = float(vals[2].num) / float(vals[2].den)
        elif isinstance(dms_values, (list, tuple)):
            degrees = float(dms_values[0])
            minutes = float(dms_values[1])
            seconds = float(dms_values[2])
        else:
            return None

        decimal = degrees + (minutes / 60.0) + (seconds / 3600.0)
        if ref in ("S", "W"):
            decimal = -decimal
        return round(decimal, 6)
    except (TypeError, ValueError, IndexError, ZeroDivisionError, AttributeError):
        return None


def extract_exif_exifread(filepath: str) -> dict:
    """Extract EXIF data using exifread library."""
    metadata = {}
    try:
        with open(filepath, "rb") as f:
            tags = exifread.process_file(f, details=False)

        if not tags:
            return metadata

        # Date/time
        for tag_name in ["EXIF DateTimeOriginal", "EXIF DateTimeDigitized", "Image DateTime"]:
            if tag_name in tags:
                metadata["date_taken"] = str(tags[tag_name])
                break

        # Camera info
        if "Image Make" in tags:
            metadata["camera_make"] = str(tags["Image Make"]).strip()
        if "Image Model" in tags:
            metadata["camera_model"] = str(tags["Image Model"]).strip()

        # Software
        if "Image Software" in tags:
            metadata["software"] = str(tags["Image Software"]).strip()

        # Dimensions
        if "EXIF ExifImageWidth" in tags:
            metadata["width"] = int(str(tags["EXIF ExifImageWidth"]))
        if "EXIF ExifImageLength" in tags:
            metadata["height"] = int(str(tags["EXIF ExifImageLength"]))

        # GPS
        gps_lat = tags.get("GPS GPSLatitude")
        gps_lat_ref = tags.get("GPS GPSLatitudeRef")
        gps_lon = tags.get("GPS GPSLongitude")
        gps_lon_ref = tags.get("GPS GPSLongitudeRef")

        if gps_lat and gps_lat_ref and gps_lon and gps_lon_ref:
            lat = dms_to_decimal(gps_lat, str(gps_lat_ref))
            lon = dms_to_decimal(gps_lon, str(gps_lon_ref))
            if lat is not None and lon is not None:
                metadata["gps_lat"] = lat
                metadata["gps_lon"] = lon

        # GPS altitude
        if "GPS GPSAltitude" in tags:
            try:
                alt = tags["GPS GPSAltitude"].values[0]
                metadata["gps_altitude"] = round(float(alt.num) / float(alt.den), 1)
            except (AttributeError, ZeroDivisionError, IndexError):
                pass

        # Orientation
        if "Image Orientation" in tags:
            metadata["orientation"] = str(tags["Image Orientation"])

        # Exposure
        if "EXIF ExposureTime" in tags:
            metadata["exposure_time"] = str(tags["EXIF ExposureTime"])
        if "EXIF FNumber" in tags:
            metadata["f_number"] = str(tags["EXIF FNumber"])
        if "EXIF ISOSpeedRatings" in tags:
            metadata["iso"] = str(tags["EXIF ISOSpeedRatings"])
        if "EXIF FocalLength" in tags:
            metadata["focal_length"] = str(tags["EXIF FocalLength"])

    except Exception as e:
        print(f"  exifread extraction failed for {filepath}: {e}", file=sys.stderr)

    return metadata


def extract_exif_pillow(filepath: str) -> dict:
    """Extract EXIF data using Pillow as fallback."""
    metadata = {}
    try:
        img = Image.open(filepath)

        # Basic dimensions
        metadata["width"] = img.width
        metadata["height"] = img.height
        metadata["format"] = img.format

        exif_data = img._getexif()
        if not exif_data:
            return metadata

        for tag_id, value in exif_data.items():
            tag_name = TAGS.get(tag_id, str(tag_id))

            if tag_name == "DateTimeOriginal":
                metadata["date_taken"] = str(value)
            elif tag_name == "DateTime":
                metadata.setdefault("date_taken", str(value))
            elif tag_name == "Make":
                metadata["camera_make"] = str(value).strip()
            elif tag_name == "Model":
                metadata["camera_model"] = str(value).strip()
            elif tag_name == "Software":
                metadata["software"] = str(value).strip()
            elif tag_name == "GPSInfo":
                gps_data = {}
                for gps_tag_id, gps_value in value.items():
                    gps_tag_name = GPSTAGS.get(gps_tag_id, str(gps_tag_id))
                    gps_data[gps_tag_name] = gps_value

                if "GPSLatitude" in gps_data and "GPSLongitude" in gps_data:
                    lat_ref = gps_data.get("GPSLatitudeRef", "N")
                    lon_ref = gps_data.get("GPSLongitudeRef", "E")
                    lat = dms_to_decimal(gps_data["GPSLatitude"], lat_ref)
                    lon = dms_to_decimal(gps_data["GPSLongitude"], lon_ref)
                    if lat is not None and lon is not None:
                        metadata["gps_lat"] = lat
                        metadata["gps_lon"] = lon

        img.close()
    except Exception as e:
        print(f"  Pillow extraction failed for {filepath}: {e}", file=sys.stderr)

    return metadata


def extract_metadata(filepath: str) -> dict:
    """Extract metadata from a photo using multiple methods."""
    # Try exifread first (more comprehensive for EXIF)
    metadata = extract_exif_exifread(filepath)

    # Fill in gaps with Pillow
    pillow_meta = extract_exif_pillow(filepath)
    for key, value in pillow_meta.items():
        if key not in metadata:
            metadata[key] = value

    return metadata


# ---------------------------------------------------------------------------
# Tampering detection
# ---------------------------------------------------------------------------
def check_tampering_indicators(filepath: str, metadata: dict) -> list[str]:
    """Check for indicators that a photo may have been edited or tampered with."""
    flags = []

    # Check software tag for known editing software
    software = metadata.get("software", "").lower()
    for editor in EDITING_SOFTWARE:
        if editor in software:
            flags.append(f"Editing software detected: {metadata.get('software', '')}")
            break

    # Check if file modification date differs significantly from EXIF date
    try:
        file_mtime = datetime.fromtimestamp(os.path.getmtime(filepath))
        date_taken_str = metadata.get("date_taken")
        if date_taken_str:
            # EXIF dates are typically in format "YYYY:MM:DD HH:MM:SS"
            try:
                date_taken = datetime.strptime(date_taken_str, "%Y:%m:%d %H:%M:%S")
                diff_days = abs((file_mtime - date_taken).days)
                if diff_days > 365:
                    flags.append(
                        f"File modification date ({file_mtime.strftime('%Y-%m-%d')}) "
                        f"differs from EXIF date ({date_taken.strftime('%Y-%m-%d')}) "
                        f"by {diff_days} days (expected for copied/transferred files, but may warrant review)"
                    )
            except ValueError:
                pass
    except OSError:
        pass

    # Check for missing EXIF data (suspicious for modern cameras)
    if not metadata.get("camera_make") and not metadata.get("camera_model"):
        ext = Path(filepath).suffix.lower()
        if ext in (".jpg", ".jpeg"):
            flags.append("No camera identification in EXIF (possible screenshot or processed image)")

    # Check for inconsistent dimensions (e.g., cropped)
    if metadata.get("width") and metadata.get("height"):
        w, h = metadata["width"], metadata["height"]
        # Extremely unusual aspect ratios may indicate cropping
        ratio = max(w, h) / max(min(w, h), 1)
        if ratio > 4.0:
            flags.append(f"Unusual aspect ratio ({w}x{h}) - possible crop or panorama")

    return flags


# ---------------------------------------------------------------------------
# Reverse geocoding
# ---------------------------------------------------------------------------
def reverse_geocode(lat: float, lon: float) -> Optional[str]:
    """Reverse geocode GPS coordinates to an address."""
    try:
        geolocator = Nominatim(user_agent="legal-evidence-analyzer/1.0")
        location = geolocator.reverse(f"{lat}, {lon}", exactly_one=True, timeout=10)
        if location:
            return location.address
    except (GeocoderTimedOut, GeocoderServiceError) as e:
        print(f"  Geocoding failed for ({lat}, {lon}): {e}", file=sys.stderr)
    except Exception as e:
        print(f"  Geocoding error for ({lat}, {lon}): {e}", file=sys.stderr)
    return None


# ---------------------------------------------------------------------------
# Analysis pipeline
# ---------------------------------------------------------------------------
def analyze_directory(input_dir: str) -> list[dict]:
    """Analyze all supported photos in a directory."""
    input_dir = os.path.abspath(input_dir)
    results = []

    # Find all supported image files
    files = []
    for entry in sorted(os.listdir(input_dir)):
        full_path = os.path.join(input_dir, entry)
        if os.path.isfile(full_path) and Path(entry).suffix.lower() in SUPPORTED_EXTENSIONS:
            files.append(full_path)

    if not files:
        return results

    print(f"Analyzing {len(files)} photo(s)...", file=sys.stderr)

    for i, filepath in enumerate(files, 1):
        filename = os.path.basename(filepath)
        print(f"  [{i}/{len(files)}] {filename}", file=sys.stderr)

        # Extract metadata
        metadata = extract_metadata(filepath)

        # Compute file hashes
        hashes = compute_file_hashes(filepath)

        # Get file size
        file_size = os.path.getsize(filepath)

        # Check for tampering
        tampering_flags = check_tampering_indicators(filepath, metadata)

        # Reverse geocode if GPS data available
        address = None
        if "gps_lat" in metadata and "gps_lon" in metadata:
            address = reverse_geocode(metadata["gps_lat"], metadata["gps_lon"])
            # Rate limit for Nominatim
            time.sleep(1.1)

        # Parse date for sorting
        date_taken = metadata.get("date_taken")
        date_parsed = None
        if date_taken:
            try:
                date_parsed = datetime.strptime(date_taken, "%Y:%m:%d %H:%M:%S")
            except ValueError:
                try:
                    date_parsed = datetime.strptime(date_taken, "%Y-%m-%d %H:%M:%S")
                except ValueError:
                    pass

        photo_result = {
            "filename": filename,
            "filepath": filepath,
            "file_size_bytes": file_size,
            "file_size_human": format_file_size(file_size),
            "md5": hashes["md5"],
            "sha256": hashes["sha256"],
            "date_taken": date_taken,
            "date_taken_parsed": date_parsed.isoformat() if date_parsed else None,
            "camera_make": metadata.get("camera_make"),
            "camera_model": metadata.get("camera_model"),
            "software": metadata.get("software"),
            "width": metadata.get("width"),
            "height": metadata.get("height"),
            "dimensions": f"{metadata.get('width', '?')}x{metadata.get('height', '?')}",
            "format": metadata.get("format"),
            "gps_lat": metadata.get("gps_lat"),
            "gps_lon": metadata.get("gps_lon"),
            "gps_altitude": metadata.get("gps_altitude"),
            "address": address,
            "orientation": metadata.get("orientation"),
            "exposure_time": metadata.get("exposure_time"),
            "f_number": metadata.get("f_number"),
            "iso": metadata.get("iso"),
            "focal_length": metadata.get("focal_length"),
            "tampering_flags": tampering_flags,
            "tampering_flag_count": len(tampering_flags),
        }
        results.append(photo_result)

    return results


def format_file_size(size_bytes: int) -> str:
    """Format file size in human-readable format."""
    for unit in ("B", "KB", "MB", "GB"):
        if size_bytes < 1024:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024
    return f"{size_bytes:.1f} TB"


# ---------------------------------------------------------------------------
# Output generation
# ---------------------------------------------------------------------------
def write_evidence_catalog(results: list[dict], output_dir: str):
    """Write evidence catalog spreadsheet."""
    path = os.path.join(output_dir, "evidence_catalog.xlsx")
    workbook = xlsxwriter.Workbook(path)
    worksheet = workbook.add_worksheet("Evidence Catalog")

    # Formats
    header_fmt = workbook.add_format({
        "bold": True, "bg_color": "#2C3E50", "font_color": "#FFFFFF",
        "border": 1, "text_wrap": True,
    })
    cell_fmt = workbook.add_format({"border": 1, "text_wrap": True, "valign": "top"})
    flag_fmt = workbook.add_format({
        "border": 1, "text_wrap": True, "valign": "top",
        "bg_color": "#FFCCCC",
    })

    # Headers
    headers = [
        "#", "Filename", "Date Taken", "GPS Lat", "GPS Lon", "Address",
        "Camera", "Dimensions", "File Size", "MD5", "SHA256",
        "Tampering Flags",
    ]
    for col, header in enumerate(headers):
        worksheet.write(0, col, header, header_fmt)

    # Column widths
    widths = [5, 30, 20, 12, 12, 40, 25, 15, 12, 35, 66, 50]
    for col, width in enumerate(widths):
        worksheet.set_column(col, col, width)

    # Data rows
    for row_idx, photo in enumerate(results, 1):
        camera = " ".join(filter(None, [photo.get("camera_make"), photo.get("camera_model")]))
        flags = "; ".join(photo["tampering_flags"]) if photo["tampering_flags"] else ""
        fmt = flag_fmt if photo["tampering_flags"] else cell_fmt

        worksheet.write(row_idx, 0, row_idx, cell_fmt)
        worksheet.write(row_idx, 1, photo["filename"], cell_fmt)
        worksheet.write(row_idx, 2, photo.get("date_taken", ""), cell_fmt)
        worksheet.write(row_idx, 3, photo.get("gps_lat", ""), cell_fmt)
        worksheet.write(row_idx, 4, photo.get("gps_lon", ""), cell_fmt)
        worksheet.write(row_idx, 5, photo.get("address", ""), cell_fmt)
        worksheet.write(row_idx, 6, camera, cell_fmt)
        worksheet.write(row_idx, 7, photo.get("dimensions", ""), cell_fmt)
        worksheet.write(row_idx, 8, photo.get("file_size_human", ""), cell_fmt)
        worksheet.write(row_idx, 9, photo.get("md5", ""), cell_fmt)
        worksheet.write(row_idx, 10, photo.get("sha256", ""), cell_fmt)
        worksheet.write(row_idx, 11, flags, fmt)

    # Auto-filter
    worksheet.autofilter(0, 0, len(results), len(headers) - 1)

    workbook.close()
    print(f"Written: {path}", file=sys.stderr)


def write_evidence_map(results: list[dict], output_dir: str):
    """Write interactive Folium map with photo locations."""
    gps_photos = [p for p in results if p.get("gps_lat") and p.get("gps_lon")]

    if not gps_photos:
        print("  No GPS data found; skipping map generation.", file=sys.stderr)
        return

    # Center map on mean coordinates
    avg_lat = sum(p["gps_lat"] for p in gps_photos) / len(gps_photos)
    avg_lon = sum(p["gps_lon"] for p in gps_photos) / len(gps_photos)

    m = folium.Map(location=[avg_lat, avg_lon], zoom_start=14)
    marker_cluster = MarkerCluster().add_to(m)

    for photo in gps_photos:
        camera = " ".join(filter(None, [photo.get("camera_make"), photo.get("camera_model")]))
        popup_html = f"""
        <b>{photo['filename']}</b><br>
        Date: {photo.get('date_taken', 'Unknown')}<br>
        Camera: {camera or 'Unknown'}<br>
        Coords: {photo['gps_lat']}, {photo['gps_lon']}<br>
        Address: {photo.get('address', 'N/A')}<br>
        Hash: {photo.get('md5', 'N/A')[:16]}...
        """

        icon_color = "red" if photo["tampering_flags"] else "blue"
        folium.Marker(
            location=[photo["gps_lat"], photo["gps_lon"]],
            popup=folium.Popup(popup_html, max_width=300),
            tooltip=photo["filename"],
            icon=folium.Icon(color=icon_color, icon="camera", prefix="fa"),
        ).add_to(marker_cluster)

    path = os.path.join(output_dir, "evidence_map.html")
    m.save(path)
    print(f"Written: {path}", file=sys.stderr)


def write_evidence_timeline(results: list[dict], output_dir: str):
    """Write HTML timeline sorted by date."""
    # Sort by parsed date (photos without dates go last)
    dated = [p for p in results if p.get("date_taken_parsed")]
    undated = [p for p in results if not p.get("date_taken_parsed")]
    dated.sort(key=lambda x: x["date_taken_parsed"])
    sorted_photos = dated + undated

    html_parts = [
        "<!DOCTYPE html>",
        "<html><head>",
        "<meta charset='utf-8'>",
        "<title>Evidence Photo Timeline</title>",
        "<style>",
        "body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }",
        "h1 { color: #2C3E50; }",
        ".timeline { position: relative; padding-left: 40px; }",
        ".timeline::before { content: ''; position: absolute; left: 15px; top: 0; bottom: 0; width: 3px; background: #2C3E50; }",
        ".entry { position: relative; margin-bottom: 20px; padding: 15px; background: white; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }",
        ".entry::before { content: ''; position: absolute; left: -32px; top: 20px; width: 12px; height: 12px; border-radius: 50%; background: #3498DB; border: 3px solid #2C3E50; }",
        ".entry.flagged::before { background: #E74C3C; }",
        ".entry h3 { margin: 0 0 8px 0; color: #2C3E50; }",
        ".entry .meta { color: #7F8C8D; font-size: 0.9em; }",
        ".entry .flags { color: #E74C3C; font-weight: bold; margin-top: 8px; }",
        ".summary { background: #2C3E50; color: white; padding: 15px; border-radius: 8px; margin-bottom: 20px; }",
        "</style>",
        "</head><body>",
        "<h1>Evidence Photo Timeline</h1>",
    ]

    # Summary box
    total = len(results)
    with_date = len(dated)
    with_gps = len([p for p in results if p.get("gps_lat")])
    with_flags = len([p for p in results if p.get("tampering_flags")])
    html_parts.append(f"<div class='summary'>")
    html_parts.append(f"<strong>Total Photos:</strong> {total} | ")
    html_parts.append(f"<strong>With Date:</strong> {with_date} | ")
    html_parts.append(f"<strong>With GPS:</strong> {with_gps} | ")
    html_parts.append(f"<strong>Flagged:</strong> {with_flags}")
    html_parts.append(f"</div>")

    html_parts.append("<div class='timeline'>")

    for photo in sorted_photos:
        flagged_class = " flagged" if photo["tampering_flags"] else ""
        camera = " ".join(filter(None, [photo.get("camera_make"), photo.get("camera_model")]))

        html_parts.append(f"<div class='entry{flagged_class}'>")
        html_parts.append(f"<h3>{photo['filename']}</h3>")
        html_parts.append(f"<div class='meta'>")
        html_parts.append(f"Date: {photo.get('date_taken', 'Unknown')} | ")
        html_parts.append(f"Camera: {camera or 'Unknown'} | ")
        html_parts.append(f"Size: {photo.get('file_size_human', '?')} | ")
        html_parts.append(f"Dimensions: {photo.get('dimensions', '?')}")
        if photo.get("address"):
            html_parts.append(f"<br>Location: {photo['address']}")
        html_parts.append(f"</div>")
        if photo["tampering_flags"]:
            html_parts.append(f"<div class='flags'>Flags: {'; '.join(photo['tampering_flags'])}</div>")
        html_parts.append("</div>")

    html_parts.append("</div>")
    html_parts.append("</body></html>")

    path = os.path.join(output_dir, "evidence_timeline.html")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(html_parts))
    print(f"Written: {path}", file=sys.stderr)


def write_metadata_report(results: list[dict], output_dir: str):
    """Write full structured metadata per photo as JSON."""
    path = os.path.join(output_dir, "metadata_report.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"Written: {path}", file=sys.stderr)


def write_analysis_summary(results: list[dict], output_dir: str):
    """Write human-readable analysis summary."""
    total = len(results)
    with_gps = [p for p in results if p.get("gps_lat")]
    with_date = [p for p in results if p.get("date_taken")]
    with_flags = [p for p in results if p.get("tampering_flags")]

    # Date range
    dates_parsed = [p["date_taken_parsed"] for p in results if p.get("date_taken_parsed")]
    if dates_parsed:
        dates_parsed.sort()
        date_range = f"{dates_parsed[0]} to {dates_parsed[-1]}"
    else:
        date_range = "No dates available"

    # Cameras found
    cameras = set()
    for p in results:
        cam = " ".join(filter(None, [p.get("camera_make"), p.get("camera_model")]))
        if cam:
            cameras.add(cam)

    lines = []
    lines.append("=" * 72)
    lines.append("EVIDENCE PHOTO ANALYSIS SUMMARY")
    lines.append("=" * 72)
    lines.append("")
    lines.append(f"Total photos analyzed:     {total}")
    lines.append(f"Photos with GPS data:      {len(with_gps)}")
    lines.append(f"Photos with date/time:     {len(with_date)}")
    lines.append(f"Photos with tampering flags: {len(with_flags)}")
    lines.append(f"Date range:                {date_range}")
    lines.append(f"Cameras/devices found:     {len(cameras)}")
    lines.append("")

    if cameras:
        lines.append("-" * 72)
        lines.append("CAMERAS/DEVICES IDENTIFIED")
        lines.append("-" * 72)
        for cam in sorted(cameras):
            count = sum(1 for p in results
                        if " ".join(filter(None, [p.get("camera_make"), p.get("camera_model")])) == cam)
            lines.append(f"  - {cam} ({count} photos)")
        lines.append("")

    if with_gps:
        lines.append("-" * 72)
        lines.append("GPS LOCATIONS FOUND")
        lines.append("-" * 72)
        for p in with_gps:
            addr = p.get("address", "Address not resolved")
            lines.append(f"  - {p['filename']}: ({p['gps_lat']}, {p['gps_lon']})")
            lines.append(f"    {addr}")
        lines.append("")

    if with_flags:
        lines.append("-" * 72)
        lines.append("TAMPERING FLAGS")
        lines.append("-" * 72)
        for p in with_flags:
            lines.append(f"  - {p['filename']}:")
            for flag in p["tampering_flags"]:
                lines.append(f"      * {flag}")
        lines.append("")

    lines.append("-" * 72)
    lines.append("OUTPUT FILES")
    lines.append("-" * 72)
    lines.append(f"  evidence_catalog.xlsx   - Complete evidence catalog spreadsheet")
    if with_gps:
        lines.append(f"  evidence_map.html       - Interactive map with photo locations")
    lines.append(f"  evidence_timeline.html  - Chronological photo timeline")
    lines.append(f"  metadata_report.json    - Full structured metadata per photo")
    lines.append(f"  analysis_summary.txt    - This summary")
    lines.append("")
    lines.append("  DISCLAIMER: This analysis is for informational purposes.")
    lines.append("  Tampering flags are indicators, not definitive proof of manipulation.")
    lines.append("  Forensic analysis by a qualified expert may be needed for court use.")
    lines.append("")
    lines.append("=" * 72)

    path = os.path.join(output_dir, "analysis_summary.txt")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"Written: {path}", file=sys.stderr)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main():
    parser = argparse.ArgumentParser(
        description="Analyze evidence photos for EXIF metadata, GPS, tampering indicators, and generate reports."
    )
    parser.add_argument("--input-dir", required=True, help="Directory containing evidence photos")
    parser.add_argument("--output-dir", required=True, help="Directory for output files")
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    # Validate input directory
    if not os.path.isdir(input_dir):
        print(json.dumps({"error": f"Input directory not found: {input_dir}"}))
        sys.exit(1)

    # Check for supported files
    supported_files = [
        f for f in os.listdir(input_dir)
        if os.path.isfile(os.path.join(input_dir, f))
        and Path(f).suffix.lower() in SUPPORTED_EXTENSIONS
    ]

    if not supported_files:
        print(json.dumps({
            "error": f"No supported image files found in {input_dir}",
            "supported_formats": sorted(SUPPORTED_EXTENSIONS),
        }))
        sys.exit(1)

    # Create output directory
    os.makedirs(output_dir, exist_ok=True)

    # Run analysis
    results = analyze_directory(input_dir)

    if not results:
        print(json.dumps({"error": "No photos could be analyzed"}))
        sys.exit(1)

    # Generate outputs
    print("Generating evidence catalog...", file=sys.stderr)
    write_evidence_catalog(results, output_dir)

    print("Generating evidence map...", file=sys.stderr)
    write_evidence_map(results, output_dir)

    print("Generating timeline...", file=sys.stderr)
    write_evidence_timeline(results, output_dir)

    print("Writing metadata report...", file=sys.stderr)
    write_metadata_report(results, output_dir)

    print("Writing analysis summary...", file=sys.stderr)
    write_analysis_summary(results, output_dir)

    # Summary stats for stdout
    with_gps = len([p for p in results if p.get("gps_lat")])
    with_date = len([p for p in results if p.get("date_taken")])
    with_flags = len([p for p in results if p.get("tampering_flags")])
    cameras = set()
    for p in results:
        cam = " ".join(filter(None, [p.get("camera_make"), p.get("camera_model")]))
        if cam:
            cameras.add(cam)

    dates_parsed = sorted([p["date_taken_parsed"] for p in results if p.get("date_taken_parsed")])

    # Print summary JSON to stdout for Claude to parse
    print(json.dumps({
        "status": "success",
        "total_photos": len(results),
        "photos_with_gps": with_gps,
        "photos_with_date": with_date,
        "photos_with_tampering_flags": with_flags,
        "cameras_found": sorted(cameras),
        "date_range": {
            "earliest": dates_parsed[0] if dates_parsed else None,
            "latest": dates_parsed[-1] if dates_parsed else None,
        },
        "output_dir": output_dir,
        "files": [f for f in [
            "evidence_catalog.xlsx",
            "evidence_map.html" if with_gps else None,
            "evidence_timeline.html",
            "metadata_report.json",
            "analysis_summary.txt",
        ] if f],
    }))


if __name__ == "__main__":
    main()
