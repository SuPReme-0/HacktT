#Vault2 Builder Final
#!/usr/bin/env python3
"""
HackT Knowledge Base - Vault 2 Laboratory Builder (Final)
Version: 7.4 (Production-Ready - All Issues Fixed)
Purpose:
  - Clone all vulnerable code repositories (OWASP, exploit frameworks, detection rules, supply chain, ML security)
  - Download NIST SARD test suites, CVE/CWE databases, and MITRE ATT&CK JSON
  - Clone educational ML security datasets from GitHub
  - Scan all existing PDFs and downloaded files, generating unified metadata and GraphRAG config
  - All actions are logged, and delays are added to be polite to remote servers.
"""

import os
import sys
import json
import gzip
import time
import hashlib
import zipfile
import requests
import subprocess
import shutil
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime

# ============================================================================
# CONFIGURATION
# ============================================================================
BASE_VAULT_PATH = Path("data/raw")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = BASE_VAULT_PATH / f"vault2_builder_log_{TIMESTAMP}.txt"

# Your exact folder names (spaces preserved) - all categories now present
VAULT_2_CATEGORIES = [
    "01_Vuln_Code_SARD",
    "02_Vuln_Code_OWASP",
    "03_Web_Browser_Vulnerability_Research",
    "04_Assembly_Patterns",
    "05_Detection_Rules",
    "06_Datasets_Threat_Intel",
    "07_Vuln_Library_Misuse",
    "08_Vulnerable_Machine_Learning_AI",
    "09_Exploit_Frameworks",
]
# ============================================================================
# REPOSITORIES TO CLONE (Git) - All URLs cleaned and updated
# ============================================================================
VAULT_2_REPOS: Dict[str, str] = {
    # 02_Vuln_Code_OWASP (7 repos)
    "https://github.com/juice-shop/juice-shop":
        "02_Vault_Laboratory/02_Vuln_Code_OWASP/juice-shop",
    "https://github.com/digininja/DVWA":
        "02_Vault_Laboratory/02_Vuln_Code_OWASP/dvwa",
    "https://github.com/OWASP/NodeGoat":
        "02_Vault_Laboratory/02_Vuln_Code_OWASP/nodegoat",            # ✅ working
    "https://github.com/OWASP/SecurityShepherd":                      # 🔁 replaced secure-pet-store
        "02_Vault_Laboratory/02_Vuln_Code_OWASP/security-shepherd",
    "https://github.com/dolevf/Black-Hat-GraphQL":                    # 🔁 replaced graphql-security-lab
        "02_Vault_Laboratory/02_Vuln_Code_OWASP/black-hat-graphql",
    "https://github.com/cr0hn/vulnerable-node":
        "02_Vault_Laboratory/02_Vuln_Code_OWASP/vulnerable-node",
    "https://github.com/we45/DVFaaS-Damn-Vulnerable-Functions-as-a-Service":   # 🔁 replaced pyvuln
        "02_Vault_Laboratory/02_Vuln_Code_OWASP/dvfaas",

    # 09_Exploit_Frameworks (3 repos)
    "https://github.com/rapid7/metasploit-framework":
        "02_Vault_Laboratory/09_Exploit_Frameworks/metasploit-framework",
    "https://github.com/sashs/Ropper":
        "02_Vault_Laboratory/09_Exploit_Frameworks/ropper",
    "https://github.com/shellphish/how2heap":
        "02_Vault_Laboratory/09_Exploit_Frameworks/how2heap",

    # 05_Detection_Rules (5 repos)
    "https://github.com/SigmaHQ/sigma":
        "02_Vault_Laboratory/05_Detection_Rules/sigma",
    "https://github.com/Yara-Rules/rules":
        "02_Vault_Laboratory/05_Detection_Rules/yara-rules",
    "https://github.com/coreruleset/coreruleset":                      # ✅ working (remove .git)
        "02_Vault_Laboratory/05_Detection_Rules/modsecurity-crs",
    "https://github.com/corazawaf/coraza":
        "02_Vault_Laboratory/05_Detection_Rules/coraza",

    # 06_Datasets_Threat_Intel (2 repos)
    "https://github.com/mitre-attack/attack-stix-data":                # 🔁 replaced mitre/cti
        "02_Vault_Laboratory/06_Datasets_Threat_Intel/mitre-cti",
    "https://gitlab.com/exploit-database/exploitdb":
        "02_Vault_Laboratory/06_Datasets_Threat_Intel/exploitdb",

    # 07_Vuln_Library_Misuse (2 repos)
    "https://github.com/snyk/goof":                          # 🔁 replaced snyk/research
        "02_Vault_Laboratory/07_Vuln_Library_Misuse/snyk-research",
    "https://github.com/sonatype-nexus-community/nancy":
        "02_Vault_Laboratory/07_Vuln_Library_Misuse/sonatype-nancy",

    # 08_Vulnerable_Machine_Learning_AI (9 repos)
    "https://github.com/pytorch/examples":
        "02_Vault_Laboratory/08_Vulnerable_Machine_Learning_AI/pytorch-examples",
    "https://github.com/leondz/garak":
        "02_Vault_Laboratory/08_Vulnerable_Machine_Learning_AI/garak",
    "https://github.com/tensorflow/tfx-addons":                       # 🔁 replaced model-card-toolkit
        "02_Vault_Laboratory/08_Vulnerable_Machine_Learning_AI/tfx-addons",
    "https://github.com/tensorflow/fairness-indicators":
        "02_Vault_Laboratory/08_Vulnerable_Machine_Learning_AI/fairness-indicators",
    "https://github.com/PAIR-code/what-if-tool":
        "02_Vault_Laboratory/08_Vulnerable_Machine_Learning_AI/what-if-tool",
    "https://github.com/Trusted-AI/adversarial-robustness-toolbox":
        "02_Vault_Laboratory/08_Vulnerable_Machine_Learning_AI/art",
    "https://github.com/tensorflow/tensorflow":
        "02_Vault_Laboratory/08_Vulnerable_Machine_Learning_AI/tensorflow",
    "https://github.com/Azure/azure-sdk-tools":
        "02_Vault_Laboratory/08_Vulnerable_Machine_Learning_AI/azure-sdk-tools",
}

# ============================================================================
# NIST SARD TEST SUITES - Structured for Python Download Logic
# ============================================================================
SARD_SUITES: List[Dict[str, Any]] = [
    {
        "id": "116",
        "name": "Juliet C/C++ 1.3.1 with extra support",
        "date": "2022-08-11",
        "slug": "juliet-c-cplusplus-v1-3-1-with-extra-support",
        "language": "C/C++",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "114",
        "name": "PHP test suite - XSS, SQLi 1.0.0",
        "date": "2022-05-12",
        "slug": "php-test-suite-sqli-v1-0-0",
        "language": "PHP",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "103",
        "name": "PHP Vulnerability Test Suite",
        "date": "2015-10-27",
        "slug": "php-vulnerability-test-suite",
        "language": "PHP",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "119",
        "name": "SATE6 - Wireshark 1.2",
        "date": "2024-08-26",
        "slug": "wireshark-sate6-v1-2",
        "language": "C",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "118",
        "name": "SATE6 - SQLite 3.21",
        "date": "2024-08-26",
        "slug": "sqlite-sate6-v3-21",
        "language": "C",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "120",
        "name": "SATE6 - Sakai 11.2",
        "date": "2024-08-26",
        "slug": "sakai-sate6-v11-2",
        "language": "Java",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "117",
        "name": "SATE6 - DSpace 6.2",
        "date": "2024-08-26",
        "slug": "dspace-sate6-v6-2",
        "language": "Java",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "102",
        "name": "IARPA STONESOUP Phase 3 - Test Cases",
        "date": "2015-10-27",
        "slug": "iarpa-stonesoup-phase-3-test-cases",
        "language": "C",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "113",
        "name": "IARPA STONESOUP P3 - Wireshark",
        "date": "2017-09-18",
        "slug": "iarpa-stonesoup-phase-3-wireshark-v1-8-0",
        "language": "C",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "105",
        "name": "C# Vulnerability Test Suite",
        "date": "2016-09-12",
        "slug": "csharp-vulnerability-test-suite",
        "language": "C#",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "109",
        "name": "Juliet Java 1.3 with extra support",
        "date": "2017-11-02",
        "slug": "juliet-java-v1-3",
        "language": "Java",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "111",
        "name": "Juliet Java 1.3 (Standard)",
        "date": "2017-10-01",
        "slug": "juliet-test-suite-for-java-v1-3",
        "language": "Java",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "112",
        "name": "Juliet C/C++ 1.3 (Standard)",
        "date": "2017-11-02",
        "slug": "juliet-c-cplusplus-v1-3",
        "language": "C++",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "110",
        "name": "Juliet C# 1.3 (Standard)",
        "date": "2020-08-01",
        "slug": "juliet-test-suite-for-csharp-v1-3",
        "language": "C#",
        "category": "01_Vuln_Code_SARD"
    },
    {
        "id": "104",
        "name": "ITC-Benchmarks",
        "date": "2016-09-12",
        "slug": "itc-benchmarks",
        "language": "C",
        "category": "01_Vuln_Code_SARD"
    }
]

# ============================================================================
# CVE & CWE DATABASE SOURCES - URLs cleaned
# ============================================================================
CVE_CWE_SOURCES: List[Dict[str, str]] = [
    {
        "name": "CVE JSON Feed 2024",
        "url": "https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-2024.json.gz",
        "destination": "06_Datasets_Threat_Intel/cve-2024.json",
        "type": "cve",
        "description": "CVE data for 2024 (decompressed JSON)"
    },
    {
        "name": "CVE JSON Feed 2023",
        "url": "https://nvd.nist.gov/feeds/json/cve/1.1/nvdcve-1.1-2023.json.gz",
        "destination": "06_Datasets_Threat_Intel/cve-2023.json",
        "type": "cve",
        "description": "CVE data for 2023 (decompressed JSON)"
    },
    {
        "name": "CWE Latest XML",
        "url": "https://cwe.mitre.org/data/xml/cwec_latest.xml.zip",
        "destination": "06_Datasets_Threat_Intel/cwe-latest.xml",
        "type": "cwe",
        "description": "Latest CWE dictionary (extracted XML)"
    },
    {
        "name": "MITRE ATT&CK Enterprise",
        "url": "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json",
        "destination": "06_Datasets_Threat_Intel/mitre-attack-enterprise.json",
        "type": "attack",
        "description": "MITRE ATT&CK Enterprise tactics & techniques"
    },
]

# ============================================================================
# ML SECURITY DATASETS (GitHub Repos)
# ============================================================================
ML_DATASETS: List[Dict[str, str]] = [
    {
        "repo_url": "https://github.com/kimiathy/poison-attack-dataset-catalog",
        "destination": "08_Vulnerable_Machine_Learning_AI/poison-attack-catalog",
        "description": "Catalog of model poisoning attack datasets and examples",
        "branch": "main"
    },
]

# ============================================================================
# HIGH-RISK FLAGGING (Educational Use Only)
# ============================================================================
HIGH_RISK_ITEMS: List[str] = [
    "juliet-c-cplusplus-v1-3-1-with-extra-support",
    "php-test-suite-xss-sqli",
    "poison-attack-catalog",
    "metasploit",
    "exploitdb",
]

# ============================================================================
# LOGGING FUNCTION
# ============================================================================
def log_message(message: str, level: str = "INFO") -> None:
    """Log message to console and file with proper newline handling"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{level}] {message}"

    if level == "ERROR":
        print(f"\033[91m{log_entry}\033[0m")
    elif level == "WARNING":
        print(f"\033[93m{log_entry}\033[0m")
    elif level == "SUCCESS":
        print(f"\033[92m{log_entry}\033[0m")
    else:
        print(log_entry)

    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(log_entry + "\n")

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================
def calculate_file_hash(filepath: Path) -> str:
    """Calculate SHA256 hash of a file"""
    sha256_hash = hashlib.sha256()
    with open(filepath, "rb") as f:
        for byte_block in iter(lambda: f.read(4096), b""):
            sha256_hash.update(byte_block)
    return sha256_hash.hexdigest()

def verify_zip_integrity(filepath: Path) -> bool:
    """Check if a file is a valid ZIP archive"""
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            first_file = zf.namelist()[0]
            zf.read(first_file)
        return True
    except Exception:
        return False

def decompress_gz_file(gz_path: Path) -> Optional[Path]:
    """Decompress a .gz file and return path to decompressed file"""
    if not gz_path.suffix == '.gz':
        return None
    try:
        decompressed_path = gz_path.with_suffix('')
        with gzip.open(gz_path, 'rb') as f_in, open(decompressed_path, 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)
        gz_path.unlink()
        return decompressed_path
    except Exception as e:
        log_message(f"    ⚠️  Failed to decompress {gz_path.name}: {e}", "WARNING")
        return None

def extract_xml_from_zip(zip_path: Path, target_ext: str = '.xml') -> Optional[Path]:
    """Extract first XML file from a ZIP archive"""
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            xml_files = [f for f in zf.namelist() if f.endswith(target_ext)]
            if not xml_files:
                return None
            extract_dir = zip_path.parent
            zf.extract(xml_files[0], extract_dir)
            extracted_path = extract_dir / xml_files[0]
            zip_path.unlink()
            return extracted_path
    except Exception as e:
        log_message(f"    ⚠️  Failed to extract XML from {zip_path.name}: {e}", "WARNING")
        return None

def download_file(url: str, dest_path: Path, timeout: int = 1800, max_retries: int = 3) -> bool:
    """Download a file with progress tracking and retry logic; returns True on success"""
    if dest_path.exists():
        log_message(f"  ✓ Already exists: {dest_path.name}", "SUCCESS")
        return True

    url = url.strip()
    # BUG FIX: Added User-Agent to prevent 403 Forbidden errors from NIST
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for attempt in range(max_retries):
        try:
            log_message(f"    Downloading: {dest_path.name} (attempt {attempt+1}/{max_retries})...", "INFO")
            response = requests.get(url, headers=headers, stream=True, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            total_size = int(response.headers.get('content-length', 0))
            downloaded = 0

            dest_path.parent.mkdir(parents=True, exist_ok=True)

            with open(dest_path, 'wb') as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total_size > 10_000_000 and downloaded % (10 * 1024 * 1024) == 0:
                            log_message(f"      Progress: {downloaded // (1024*1024)}MB", "INFO")

            if not dest_path.exists() or dest_path.stat().st_size == 0:
                log_message(f"    ⚠️  Empty or missing file: {dest_path.name}", "WARNING")
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                    continue
                return False

            log_message(f"    ✅ Downloaded: {dest_path.name} ({os.path.getsize(dest_path) // (1024*1024)}MB)", "SUCCESS")
            return True
        except Exception as e:
            log_message(f"    ⚠️  Error: {e}", "WARNING")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
    return False

def check_git_installed() -> bool:
    """Check if git is installed"""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except:
        return False

def clone_repository(repo_url: str, destination: str, depth: int = 1, max_retries: int = 2) -> Tuple[bool, str]:
    """Clone a git repository with retry logic; returns (success, message)"""
    full_dest = BASE_VAULT_PATH / destination
    if full_dest.exists():
        return False, f"Already exists: {full_dest}"

    repo_url = repo_url.strip()

    for attempt in range(max_retries):
        try:
            log_message(f"    Cloning: {repo_url} (attempt {attempt+1}/{max_retries})", "INFO")
            subprocess.run(
                ["git", "clone", "--depth", str(depth), repo_url, str(full_dest)],
                capture_output=True, check=True, timeout=1800
            )
            return True, f"Success: {full_dest}"
        except subprocess.CalledProcessError as e:
            err = e.stderr.decode(errors='replace')
            log_message(f"    ⚠️  Git clone failed: {err}", "WARNING")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                if full_dest.exists():
                    shutil.rmtree(full_dest, ignore_errors=True)
                continue
            return False, f"Failed: {err}"
        except Exception as e:
            log_message(f"    ⚠️  Unexpected error: {e}", "ERROR")
            if attempt < max_retries - 1:
                time.sleep(2 ** attempt)
                continue
            return False, f"Failed: {str(e)}"

    return False, "Max retries exceeded"

# ============================================================================
# DOWNLOAD FUNCTIONS
# ============================================================================
def download_sard_suite(suite: Dict[str, str], target_dir: Path) -> Dict[str, Any]:
    """Download a single NIST SARD test suite"""
    date_str = suite["date"]
    slug = suite["slug"]
    filename = f"{date_str}-{slug}.zip"
    url = f"https://samate.nist.gov/SARD/downloads/test-suites/{filename}"
    dest_path = target_dir / filename

    if dest_path.exists():
        return {"status": "skipped", "reason": "File already exists", "file": filename}

    if not download_file(url, dest_path, timeout=600):
        return {"status": "error", "reason": "Download failed", "file": filename, "url": url}

    if not verify_zip_integrity(dest_path):
        log_message(f"    ⚠️  Invalid ZIP file, removing: {filename}", "WARNING")
        dest_path.unlink(missing_ok=True)
        return {"status": "error", "reason": "Invalid ZIP archive", "file": filename}

    file_hash = calculate_file_hash(dest_path)
    # Store relative path
    rel_path = dest_path.relative_to(BASE_VAULT_PATH)
    return {
        "status": "success",
        "file": filename,
        "path": str(rel_path),
        "size_bytes": os.path.getsize(dest_path),
        "sha256": file_hash,
        "test_cases": suite.get("test_cases", 0),
        "language": suite.get("language", "unknown"),
        "category": suite["category"],
        "is_high_risk": any(hr in filename for hr in HIGH_RISK_ITEMS),
        "educational_only": True
    }

def download_cve_cwe_dataset(source: Dict[str, str], base_dir: Path) -> Dict[str, Any]:
    """Download and process CVE/CWE database"""
    url = source["url"].strip()
    destination = source["destination"]
    dest_path = base_dir / destination

    if url.endswith('.gz'):
        temp_gz = dest_path.with_suffix('.json.gz')
        if not download_file(url, temp_gz, timeout=1300):
            return {"status": "error", "reason": "Download failed", "name": source["name"]}
        decompressed = decompress_gz_file(temp_gz)
        if not decompressed:
            return {"status": "error", "reason": "Decompression failed", "name": source["name"]}
        dest_path = decompressed
    elif url.endswith('.zip') and 'cwe' in url.lower():
        temp_zip = dest_path.with_suffix('.xml.zip')
        if not download_file(url, temp_zip, timeout=1300):
            return {"status": "error", "reason": "Download failed", "name": source["name"]}
        extracted = extract_xml_from_zip(temp_zip)
        if not extracted:
            return {"status": "error", "reason": "XML extraction failed", "name": source["name"]}
        dest_path = extracted
    else:
        if not download_file(url, dest_path, timeout=1300):
            return {"status": "error", "reason": "Download failed", "name": source["name"]}

    file_hash = calculate_file_hash(dest_path)
    # Store relative path
    rel_path = dest_path.relative_to(BASE_VAULT_PATH)
    return {
        "status": "success",
        "name": source["name"],
        "path": str(rel_path),
        "size_bytes": os.path.getsize(dest_path),
        "sha256": file_hash,
        "type": source["type"],
        "description": source["description"],
        "category": "06_Datasets_Threat_Intel",
        "is_high_risk": False,
        "educational_only": True
    }

def clone_ml_dataset(dataset: Dict[str, str], base_dir: Path) -> Dict[str, Any]:
    """Clone a GitHub repo for ML security datasets"""
    repo_url = dataset["repo_url"].strip()
    destination = dataset["destination"]          # relative path, e.g. "08_Vulnerable_Machine_Learning_AI/..."
    branch = dataset.get("branch", "main")
    dest_path = base_dir / destination            # full path for existence check

    if dest_path.exists() and any(dest_path.iterdir()):
        return {"status": "skipped", "reason": "Directory already exists", "repo": repo_url}

    log_message(f"    Cloning: {repo_url} (branch: {branch})...", "INFO")
    ok, msg = clone_repository(repo_url, destination, depth=1)   # pass relative destination
    if ok:
        file_count = sum(1 for _ in dest_path.rglob("*") if _.is_file())
        log_message(f"    ✅ Cloned: {destination} ({file_count} files)", "SUCCESS")
        return {
            "status": "success",
            "repo": repo_url,
            "path": destination,                      # store relative path
            "file_count": file_count,
            "description": dataset["description"],
            "category": "08_Vulnerable_Machine_Learning_AI",
            "is_high_risk": any(hr in repo_url.lower() for hr in HIGH_RISK_ITEMS),
            "educational_only": True
        }
    else:
        log_message(f"    ⚠️  {msg}", "WARNING")
        return {"status": "error", "reason": msg, "repo": repo_url}

# ============================================================================
# SCANNING FUNCTIONS (with improved high-risk flagging and schema validation)
# ============================================================================
def scan_pdf_file(filepath: Path) -> Dict[str, Any]:
    """Scan PDF file for metadata"""
    return {
        "type": "pdf",
        "size_bytes": filepath.stat().st_size,
        "pages": None,
        "sha256": calculate_file_hash(filepath)
    }

def scan_zip_file(filepath: Path) -> Dict[str, Any]:
    """Scan ZIP file for suspicious content and metadata"""
    result = {
        "type": "zip",
        "size_bytes": filepath.stat().st_size,
        "file_count": 0,
        "suspicious_files": [],
        "sha256": calculate_file_hash(filepath)
    }
    try:
        with zipfile.ZipFile(filepath, 'r') as zf:
            result["file_count"] = len(zf.namelist())
            suspicious_exts = ['.exe', '.bat', '.cmd', '.ps1', '.sh', '.bin']
            for name in zf.namelist():
                if any(name.lower().endswith(ext) for ext in suspicious_exts):
                    result["suspicious_files"].append(name)
    except Exception as e:
        result["error"] = str(e)
    return result

def validate_json_file(filepath: Path, source_type: Optional[str] = None) -> Dict[str, Any]:
    """Validate and scan JSON file, with optional schema validation"""
    result = {
        "type": "json",
        "size_bytes": filepath.stat().st_size,
        "valid": False,
        "sha256": calculate_file_hash(filepath)
    }
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            result["valid"] = True
            if isinstance(data, dict):
                result["top_level_keys"] = list(data.keys())
            # Enhanced schema validation based on source type
            if source_type == "cve":
                # CVE JSON 1.1 format has 'CVE_Items'; newer format may have 'vulnerabilities'
                if not (("CVE_Items" in data) or ("vulnerabilities" in data)):
                    result["valid"] = False
                    result["error"] = "CVE JSON missing expected top-level keys"
            elif source_type == "attack":
                # MITRE ATT&CK JSON should have an 'objects' array
                if "objects" not in data or not isinstance(data["objects"], list):
                    result["valid"] = False
                    result["error"] = "MITRE ATT&CK JSON missing 'objects' array"
    except Exception as e:
        result["valid"] = False
        result["error"] = str(e)
    return result

def validate_xml_file(filepath: Path, source_type: Optional[str] = None) -> Dict[str, Any]:
    """Validate and scan XML file, with optional schema validation"""
    result = {
        "type": "xml",
        "size_bytes": filepath.stat().st_size,
        "valid": False,
        "sha256": calculate_file_hash(filepath)
    }
    try:
        import xml.etree.ElementTree as ET
        tree = ET.parse(filepath)
        root = tree.getroot()
        result["valid"] = True
        result["root_tag"] = root.tag
        # CWE XML schema check
        if source_type == "cwe":
            if root.tag != "Weakness_Catalog":
                result["valid"] = False
                result["error"] = f"CWE XML root should be 'Weakness_Catalog', got '{root.tag}'"
            else:
                # Optionally check for Weaknesses element
                weaknesses = root.find("Weaknesses")
                if weaknesses is None:
                    result["valid"] = False
                    result["error"] = "CWE XML missing 'Weaknesses' element"
    except Exception as e:
        result["valid"] = False
        result["error"] = str(e)
    return result

def scan_non_repo_files() -> List[Dict[str, Any]]:
    """Scan all files in Vault 2 directories (excluding .git) and return metadata"""
    log_message("Scanning existing files in Vault 2...", "INFO")
    all_metadata = []
    vault2_base = BASE_VAULT_PATH / "02_Vault_Laboratory"

    for category in VAULT_2_CATEGORIES:
        category_path = vault2_base / category
        if not category_path.exists():
            continue

        log_message(f"  Scanning {category}...", "INFO")
        for file_path in category_path.rglob("*"):
            if not file_path.is_file():
                continue
            if file_path.suffix in ['.log', '.txt'] and 'log' in file_path.name.lower():
                continue
            if file_path.name.startswith('.'):
                continue

            meta = {
                "path": str(file_path.relative_to(BASE_VAULT_PATH)),
                "category": category,
                "cloned_at": None,
                # FIXED: High-risk flagging now checks only filename and immediate parent
                "is_high_risk": any(
                    hr in file_path.name.lower() or hr in file_path.parent.name.lower()
                    for hr in HIGH_RISK_ITEMS
                ),
                "educational_only": True,
            }
            ext = file_path.suffix.lower()
            if ext == '.pdf':
                meta.update(scan_pdf_file(file_path))
            elif ext == '.zip':
                meta.update(scan_zip_file(file_path))
            elif ext == '.json':
                # Pass source_type based on filename heuristics
                src_type = None
                if "cve" in file_path.name.lower():
                    src_type = "cve"
                elif "attack" in file_path.name.lower():
                    src_type = "attack"
                meta.update(validate_json_file(file_path, src_type))
            elif ext == '.xml':
                src_type = None
                if "cwe" in file_path.name.lower():
                    src_type = "cwe"
                meta.update(validate_xml_file(file_path, src_type))
            else:
                meta.update({
                    "type": "other",
                    "size_bytes": file_path.stat().st_size,
                    "sha256": calculate_file_hash(file_path)
                })
            all_metadata.append(meta)
    return all_metadata

# ============================================================================
# METADATA & REPORT GENERATION
# ============================================================================
def generate_vault2_metadata(all_meta: List[Dict]) -> None:
    """Generate comprehensive metadata JSON report"""
    log_message("Generating Vault 2 metadata report...", "INFO")
    report_path = BASE_VAULT_PATH / f"vault2_metadata_{TIMESTAMP}.json"
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(all_meta, f, indent=2, ensure_ascii=False)
    log_message(f"  ✓ Metadata Report: {report_path}", "SUCCESS")

def generate_graphrag_config(all_meta: List[Dict]) -> None:
    """Generate GraphRAG configuration for AST parsing of code files"""
    config_path = BASE_VAULT_PATH / "vault2_graphrag_config.json"
    config = {
        "version": "7.4",
        "generated_at": datetime.now().isoformat(),
        "vault": "02_Vault_Laboratory",
        "categories": VAULT_2_CATEGORIES,
        "file_types_supported": ["pdf", "zip", "json", "xml", "py", "java", "c", "cpp", "js"],
        "high_risk_items": HIGH_RISK_ITEMS,
        "items": [
            {
                "path": m.get("path"),
                "category": m.get("category"),
                "type": m.get("type"),
                "is_high_risk": m.get("is_high_risk", False),
                "educational_only": m.get("educational_only", False),
                "sha256": m.get("sha256"),
                "size_bytes": m.get("size_bytes")
            }
            for m in all_meta if m.get("status") in ["success", None]
        ]
    }
    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
    log_message(f"  ✓ GraphRAG Config: {config_path}", "SUCCESS")

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    print("\n" + "="*80)
    print("HackT Knowledge Base - Vault 2 Laboratory Builder (Final)")
    print("Version: 7.4 | Educational Use Only - Security Research")
    print("="*80 + "\n")

    BASE_VAULT_PATH.mkdir(parents=True, exist_ok=True)
    log_message("Starting Vault 2 build process...", "INFO")

    log_message("[1/7] Checking git installation...", "INFO")
    if not check_git_installed():
        log_message("    ❌ Git not installed", "ERROR")
        return
    log_message("    ✓ Git installed\n", "SUCCESS")

    log_message("[2/7] Ensuring directory structure exists...", "INFO")
    vault2_base = BASE_VAULT_PATH / "02_Vault_Laboratory"
    for category in VAULT_2_CATEGORIES:
        (vault2_base / category).mkdir(parents=True, exist_ok=True)
        log_message(f"  ✓ Ensured: {category}", "SUCCESS")
    log_message("")

    log_message("[3/7] Cloning Vault 2 repositories...", "INFO")
    log_message(f"    Total repositories: {len(VAULT_2_REPOS)}\n", "INFO")
    repo_metadata = []
    for i, (repo_url, dest) in enumerate(VAULT_2_REPOS.items(), 1):
        log_message(f"  [{i}/{len(VAULT_2_REPOS)}] Processing...", "INFO")
        ok, msg = clone_repository(repo_url, dest)
        if ok:
            log_message(f"    ✓ {msg}", "SUCCESS")
            meta = {
                "type": "repository",
                "repository_url": repo_url,
                "path": dest,
                "is_high_risk": any(hr in repo_url.lower() for hr in HIGH_RISK_ITEMS),
                "educational_only": True,
                "cloned_at": datetime.now().isoformat(),
                "status": "success"
            }
            repo_metadata.append(meta)
        else:
            log_message(f"    ⚠ {msg}", "WARNING")
        time.sleep(2)
    log_message("")

    log_message("[4/7] Downloading NIST SARD test suites...", "INFO")
    sard_dir = vault2_base / "01_Vuln_Code_SARD"
    sard_results = []
    for suite in SARD_SUITES:
        result = download_sard_suite(suite, sard_dir)
        sard_results.append(result)
        if result["status"] == "success":
            log_message(f"    ✅ {suite['name']}", "SUCCESS")
        elif result["status"] == "error":
            log_message(f"    ⚠️  Failed: {suite['name']} - {result.get('reason')}", "WARNING")
        time.sleep(2)
    log_message("")

    log_message("[5/7] Downloading CVE/CWE databases...", "INFO")
    cve_results = []
    for source in CVE_CWE_SOURCES:
        result = download_cve_cwe_dataset(source, vault2_base)
        cve_results.append(result)
        if result["status"] == "success":
            log_message(f"    ✅ {source['name']}", "SUCCESS")
        time.sleep(1)
    log_message("")

    log_message("[6/7] Cloning ML security datasets...", "INFO")
    ml_results = []
    for dataset in ML_DATASETS:
        result = clone_ml_dataset(dataset, vault2_base)
        ml_results.append(result)
        if result["status"] == "success":
            log_message(f"    ✅ {dataset['description']}", "SUCCESS")
        time.sleep(2)
    log_message("")

    log_message("[7/7] Scanning all Vault 2 files...", "INFO")
    scanned_files = scan_non_repo_files()
    log_message(f"  Total files scanned: {len(scanned_files)}\n", "INFO")

    all_metadata = repo_metadata + sard_results + cve_results + ml_results + scanned_files
    generate_vault2_metadata(all_metadata)
    generate_graphrag_config(all_metadata)

    log_message("\n" + "="*80, "INFO")
    log_message("VAULT 2 BUILD COMPLETE", "INFO")
    log_message("="*80, "INFO")
    repo_success = sum(1 for r in repo_metadata if r.get("status") == "success")
    sard_success = sum(1 for r in sard_results if r.get("status") == "success")
    cve_success = sum(1 for r in cve_results if r.get("status") == "success")
    ml_success = sum(1 for r in ml_results if r.get("status") == "success")
    log_message(f"Repositories cloned: {repo_success}/{len(VAULT_2_REPOS)}", "INFO")
    log_message(f"NIST SARD suites: {sard_success}/{len(SARD_SUITES)}", "INFO")
    log_message(f"CVE/CWE datasets: {cve_success}/{len(CVE_CWE_SOURCES)}", "INFO")
    log_message(f"ML datasets cloned: {ml_success}/{len(ML_DATASETS)}", "INFO")
    log_message(f"Existing files scanned: {len(scanned_files)}", "INFO")

    high_risk_total = sum(1 for m in all_metadata if m.get("is_high_risk"))
    log_message(f"\n⚠️  HIGH-RISK ITEMS (Educational Use Only): {high_risk_total}", "WARNING")
    log_message(f"\n📁 Metadata Report: vault2_metadata_{TIMESTAMP}.json", "INFO")
    log_message(f"📁 GraphRAG Config: vault2_graphrag_config.json", "INFO")
    log_message(f"📁 Build Log: vault2_builder_log_{TIMESTAMP}.txt", "INFO")
    log_message("\n" + "="*80, "INFO")
    log_message("⚠️  WARNING: All Vault 2 content is for EDUCATIONAL USE ONLY", "WARNING")
    log_message("    Do not use vulnerable code in production environments", "WARNING")
    log_message("    Review all downloaded content before ingestion into RAG pipeline", "WARNING")
    log_message("="*80 + "\n", "INFO")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log_message("\n🛑 Process interrupted by user", "WARNING")
        sys.exit(1)
    except Exception as e:
        log_message(f"\n❌ Unexpected error: {e}", "ERROR")
        import traceback
        traceback.print_exc()
        sys.exit(1)