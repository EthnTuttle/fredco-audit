#!/usr/bin/env python3
"""
Download data from public sources for FCPS audit.

Usage:
    python scripts/download_data.py --all
    python scripts/download_data.py --source fcps
    python scripts/download_data.py --source vdoe
    python scripts/download_data.py --source apa
"""

import argparse
import json
import os
import subprocess
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

# Base directories
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"

# Division codes for filtering
DIVISION_CODES = {
    "frederick": "069",
    "clarke": "043",
    "fauquier": "061",
    "shenandoah": "171",
    "warren": "187",
    "loudoun": "107",
}

# Data source URLs
SOURCES = {
    "fcps": {
        "budget_page": "https://www.frederickcountyschoolsva.net/about/budget",
        "output_dir": RAW_DIR / "fcps",
    },
    "vdoe": {
        "base_url": "https://www.doe.virginia.gov/data-policy-funding/data-reports/statistics-reports/superintendent-s-annual-report",
        "output_dir": RAW_DIR / "vdoe",
    },
    "apa": {
        "comparative_report": "https://dlasprodpublic.blob.core.windows.net/apa/549A9D64-9A00-45D1-A88F-5FE9C1BFAD8E.xlsx",
        "output_dir": RAW_DIR / "apa" / "comparative",
    },
    "vpap": {
        "spending_visual": "https://www.vpap.org/visuals/visual/back-to-school-spending-on-teaching-fy2024",
        "output_dir": RAW_DIR / "vpap" / "visuals",
    },
}

# Request headers to mimic browser
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Referer": "https://www.doe.virginia.gov/",
}

# VDOE Superintendent's Annual Report - Direct download URLs
# These URLs are for the official VDOE data tables
VDOE_TABLE_URLS = {
    "table-8": {  # Number of Days Taught, ADA, ADM (Enrollment)
        "2024-25": "https://www.doe.virginia.gov/home/showpublisheddocument/74065/639004519261330000",
        "2023-24": "https://www.doe.virginia.gov/home/showpublisheddocument/57636/638629416751370000",
        "2022-23": "https://www.doe.virginia.gov/home/showpublisheddocument/50076/638321092834370000",
        "2021-22": "https://www.doe.virginia.gov/home/showpublisheddocument/19287/638042787714630000",
        "2020-21": "https://www.doe.virginia.gov/home/showpublisheddocument/19301/638042791091270000",
        "2019-20": "https://www.doe.virginia.gov/home/showpublisheddocument/19323/638042793435930000",
    },
    "table-15": {  # Per Pupil Expenditures (XLSM or ZIP)
        "2023-24": "https://www.doe.virginia.gov/home/showpublisheddocument/60388/638809985334430000",
        "2022-23": "https://www.doe.virginia.gov/home/showpublisheddocument/54399/638562109182270000",  # ZIP
        "2021-22": "https://www.doe.virginia.gov/home/showpublisheddocument/44327/638180142004800000",  # ZIP
        "2020-21": "https://www.doe.virginia.gov/home/showpublisheddocument/39444/638066222557500000",
        "2019-20": "https://www.doe.virginia.gov/home/showpublisheddocument/42861/638133561521670000",
    },
    "table-17": {  # Pupil-to-Teacher Ratios
        "2023-24": "https://www.doe.virginia.gov/home/showpublisheddocument/60288/638774664072470000",
        "2022-23": "https://www.doe.virginia.gov/home/showpublisheddocument/54195/638503230223070000",
        "2021-22": "https://www.doe.virginia.gov/home/showpublisheddocument/44373/638185291091570000",
        "2020-21": "https://www.doe.virginia.gov/home/showpublisheddocument/19315/638042791125000000",
        "2019-20": "https://www.doe.virginia.gov/home/showpublisheddocument/19341/638042793500770000",
    },
    "table-18": {  # Administrative, Service and Support Personnel Positions
        "2023-24": "https://www.doe.virginia.gov/home/showpublisheddocument/60290/638774664079170000",
        "2022-23": "https://www.doe.virginia.gov/home/showpublisheddocument/54227/638507556129670000",
        "2021-22": "https://www.doe.virginia.gov/home/showpublisheddocument/44339/638180976020370000",
        "2020-21": "https://www.doe.virginia.gov/home/showpublisheddocument/19317/638042791130170000",
        "2019-20": "https://www.doe.virginia.gov/home/showpublisheddocument/19343/638042793508570000",
    },
    "table-19": {  # Total Instructional Positions and Average Annual Salaries
        "2023-24": "https://www.doe.virginia.gov/home/showpublisheddocument/60304/638774758522230000",
        "2022-23": "https://www.doe.virginia.gov/home/showpublisheddocument/54229/638507556136330000",
        "2021-22": "https://www.doe.virginia.gov/home/showpublisheddocument/44341/638180976025200000",
        "2020-21": "https://www.doe.virginia.gov/home/showpublisheddocument/19319/638042791136400000",
        "2019-20": "https://www.doe.virginia.gov/home/showpublisheddocument/19345/638042793515470000",
    },
}


def ensure_dirs():
    """Create all necessary directories."""
    for source in SOURCES.values():
        output_dir = source.get("output_dir")
        if output_dir:
            output_dir.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories for FCPS
    (RAW_DIR / "fcps" / "budgets").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "fcps" / "acfr").mkdir(parents=True, exist_ok=True)
    (RAW_DIR / "fcps" / "monthly-reports").mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories for VDOE tables
    for table in ["table-8", "table-15", "table-17", "table-18", "table-19"]:
        (RAW_DIR / "vdoe" / table).mkdir(parents=True, exist_ok=True)


def download_file(url: str, output_path: Path, description: str = "", use_wget: bool = False) -> bool:
    """
    Download a file from URL to output_path.
    
    Returns True if successful, False otherwise.
    
    Args:
        url: The URL to download from
        output_path: Local path to save the file
        description: Optional description for progress bar
        use_wget: If True, use wget instead of requests (for sites with strict bot protection)
    """
    if use_wget:
        return download_file_wget(url, output_path, description)
    
    try:
        response = requests.get(url, headers=HEADERS, stream=True, timeout=60)
        response.raise_for_status()
        
        total_size = int(response.headers.get("content-length", 0))
        
        with open(output_path, "wb") as f:
            if total_size > 0:
                with tqdm(total=total_size, unit="B", unit_scale=True, desc=description or output_path.name) as pbar:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
                        pbar.update(len(chunk))
            else:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
        
        print(f"  Downloaded: {output_path.name}")
        return True
        
    except requests.RequestException as e:
        print(f"  Error downloading {url}: {e}")
        return False


def download_file_wget(url: str, output_path: Path, description: str = "") -> bool:
    """
    Download a file using wget (for sites with strict bot protection).
    
    The VDOE website blocks requests library but accepts wget with proper headers.
    """
    try:
        cmd = [
            "wget",
            "--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "--referer=https://www.doe.virginia.gov/",
            "-q",  # Quiet mode
            "-O", str(output_path),
            url
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        
        if result.returncode == 0 and output_path.exists() and output_path.stat().st_size > 0:
            print(f"  Downloaded: {output_path.name}")
            return True
        else:
            print(f"  Error downloading {url}: wget returned {result.returncode}")
            if result.stderr:
                print(f"    {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        print(f"  Error downloading {url}: timeout")
        return False
    except FileNotFoundError:
        print("  Error: wget not found. Please install wget or download files manually.")
        return False


def save_metadata(output_dir: Path, source_name: str, files: list):
    """Save download metadata to JSON file."""
    metadata = {
        "source": source_name,
        "downloaded_date": datetime.now().isoformat(),
        "files": files,
    }
    
    metadata_path = output_dir / "metadata.json"
    with open(metadata_path, "w") as f:
        json.dump(metadata, f, indent=2)


def download_fcps():
    """
    Download FCPS budget documents.
    
    This function scrapes the FCPS budget page and downloads available PDFs.
    """
    print("\n=== Downloading FCPS Budget Documents ===")
    
    output_dir = SOURCES["fcps"]["output_dir"]
    budget_url = SOURCES["fcps"]["budget_page"]
    
    try:
        response = requests.get(budget_url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "lxml")
        
        # Find all PDF links
        pdf_links = []
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if href.lower().endswith(".pdf"):
                full_url = urljoin(budget_url, href)
                pdf_links.append({
                    "url": full_url,
                    "text": link.get_text(strip=True),
                    "filename": os.path.basename(urlparse(href).path),
                })
        
        if not pdf_links:
            print("  No PDF links found on budget page.")
            print("  You may need to manually download budget documents from:")
            print(f"  {budget_url}")
            return
        
        print(f"  Found {len(pdf_links)} PDF links")
        
        downloaded_files = []
        for pdf in pdf_links:
            # Categorize by filename
            filename = pdf["filename"].lower()
            if "budget" in filename:
                subdir = output_dir / "budgets"
            elif "acfr" in filename or "comprehensive" in filename:
                subdir = output_dir / "acfr"
            else:
                subdir = output_dir / "budgets"
            
            subdir.mkdir(parents=True, exist_ok=True)
            output_path = subdir / pdf["filename"]
            
            if download_file(pdf["url"], output_path, pdf["text"][:50]):
                downloaded_files.append({
                    "filename": pdf["filename"],
                    "url": pdf["url"],
                    "description": pdf["text"],
                })
        
        save_metadata(output_dir, "fcps", downloaded_files)
        print(f"  Total downloaded: {len(downloaded_files)} files")
        
    except requests.RequestException as e:
        print(f"  Error accessing FCPS budget page: {e}")
        print("  You may need to manually download budget documents.")


def download_vdoe():
    """
    Download VDOE Superintendent's Annual Report tables.
    
    Downloads Tables 8, 15, 17, 18, and 19 for available years using direct URLs.
    
    Tables:
    - Table 8: Number of Days Taught, ADA, ADM (Enrollment)
    - Table 15: Per Pupil Expenditures
    - Table 17: Pupil-to-Teacher Ratios
    - Table 18: Administrative, Service and Support Personnel Positions
    - Table 19: Total Instructional Positions and Average Annual Salaries
    """
    print("\n=== Downloading VDOE Superintendent's Annual Report ===")
    
    output_dir = SOURCES["vdoe"]["output_dir"]
    downloaded_files = []
    
    table_descriptions = {
        "table-8": "Number of Days Taught, ADA, ADM",
        "table-15": "Per Pupil Expenditures",
        "table-17": "Pupil-to-Teacher Ratios",
        "table-18": "Administrative Personnel Positions",
        "table-19": "Instructional Positions and Salaries",
    }
    
    for table_name, years_data in VDOE_TABLE_URLS.items():
        subdir = output_dir / table_name
        subdir.mkdir(parents=True, exist_ok=True)
        
        print(f"\n  {table_name.upper()}: {table_descriptions.get(table_name, '')}")
        
        for year, url in years_data.items():
            # Determine file extension based on table and year
            if table_name == "table-15":
                if year in ["2022-23", "2021-22"]:
                    ext = ".zip"
                else:
                    ext = ".xlsm"
            elif table_name == "table-8":
                ext = ".xlsx"
            else:
                ext = ".xlsx"
            
            filename = f"{table_name.replace('-', '')}_{year}{ext}"
            output_path = subdir / filename
            
            if download_file(url, output_path, f"{table_name} {year}", use_wget=True):
                downloaded_files.append({
                    "filename": filename,
                    "url": url,
                    "table": table_name,
                    "year": year,
                    "description": f"{table_descriptions.get(table_name, '')} - {year}",
                })
    
    # Extract any ZIP files
    print("\n  Extracting ZIP files...")
    for table_dir in (output_dir / "table-15").iterdir():
        if table_dir.suffix.lower() == ".zip":
            try:
                with zipfile.ZipFile(table_dir, 'r') as zip_ref:
                    zip_ref.extractall(output_dir / "table-15")
                print(f"    Extracted: {table_dir.name}")
            except zipfile.BadZipFile:
                print(f"    Warning: Could not extract {table_dir.name}")
    
    save_metadata(output_dir, "vdoe", downloaded_files)
    print(f"\n  Total downloaded: {len(downloaded_files)} files")


def download_apa():
    """
    Download Virginia APA Comparative Report.
    """
    print("\n=== Downloading Virginia APA Comparative Report ===")
    
    output_dir = SOURCES["apa"]["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    
    url = SOURCES["apa"]["comparative_report"]
    filename = "apa_comparative_report.xlsx"
    output_path = output_dir / filename
    
    if download_file(url, output_path, "APA Comparative Report"):
        save_metadata(output_dir, "apa", [{
            "filename": filename,
            "url": url,
            "description": "Virginia APA Comparative Report - Education Expenditures",
        }])


def download_vpap():
    """
    Download VPAP instructional spending data/visualizations.
    
    Note: VPAP may have data in HTML tables or embedded charts.
    This downloads the page HTML for later parsing.
    """
    print("\n=== Downloading VPAP Instructional Spending Data ===")
    
    output_dir = SOURCES["vpap"]["output_dir"]
    output_dir.mkdir(parents=True, exist_ok=True)
    
    url = SOURCES["vpap"]["spending_visual"]
    
    try:
        response = requests.get(url, headers=HEADERS, timeout=30)
        response.raise_for_status()
        
        # Save the HTML page
        output_path = output_dir / "back-to-school-spending-fy2024.html"
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(response.text)
        
        print(f"  Downloaded: {output_path.name}")
        
        # Try to find any embedded data or CSV links
        soup = BeautifulSoup(response.text, "lxml")
        data_links = []
        
        for link in soup.find_all("a", href=True):
            href = link["href"]
            if any(ext in href.lower() for ext in [".csv", ".xlsx", ".json"]):
                data_links.append(urljoin(url, href))
        
        if data_links:
            print(f"  Found {len(data_links)} data file links")
            for data_url in data_links:
                filename = os.path.basename(urlparse(data_url).path)
                download_file(data_url, output_dir / filename)
        
        save_metadata(output_dir, "vpap", [{
            "filename": "back-to-school-spending-fy2024.html",
            "url": url,
            "description": "VPAP Back to School Spending on Teaching FY2024",
        }])
        
    except requests.RequestException as e:
        print(f"  Error accessing VPAP page: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Download public data for FCPS audit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python scripts/download_data.py --all
    python scripts/download_data.py --source fcps
    python scripts/download_data.py --source vdoe
    python scripts/download_data.py --source apa
    python scripts/download_data.py --source vpap
        """
    )
    
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download from all sources"
    )
    parser.add_argument(
        "--source",
        choices=["fcps", "vdoe", "apa", "vpap"],
        help="Download from specific source"
    )
    
    args = parser.parse_args()
    
    if not args.all and not args.source:
        parser.print_help()
        sys.exit(1)
    
    print("FCPS Audit Data Downloader")
    print("=" * 50)
    print(f"Data directory: {DATA_DIR}")
    print(f"Download date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    ensure_dirs()
    
    if args.all or args.source == "fcps":
        download_fcps()
    
    if args.all or args.source == "vdoe":
        download_vdoe()
    
    if args.all or args.source == "apa":
        download_apa()
    
    if args.all or args.source == "vpap":
        download_vpap()
    
    print("\n" + "=" * 50)
    print("Download complete!")
    print("\nNote: Some files may need to be downloaded manually if")
    print("automatic scraping couldn't find them. Check the output above.")
    print("\nNext steps:")
    print("  1. Review downloaded files in data/raw/")
    print("  2. Run parse_pdf.py to extract PDF tables")
    print("  3. Run parse_excel.py to process spreadsheets")


if __name__ == "__main__":
    main()
