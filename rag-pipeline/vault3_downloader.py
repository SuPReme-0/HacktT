#Vault3_builder final
#!/usr/bin/env python3
"""
HackT Knowledge Base - Complete Vault 3 Repository Downloader
Version: 8.1 (Final Production-Ready Edition with Security Scanning)
Architecture: Hybrid RAG (Semantic + Sparse + GraphRAG + PageIndex)
Purpose: Clone, validate, and SECURITY SCAN all repositories into proper Vault 3 folder structure
Security Features Added:
- ✅ Dependency vulnerability scanning (pip-audit)
- ✅ Secret scanning (gitleaks)
- ✅ SAST scanning (bandit for Python)
- ✅ Git history analysis
- ✅ Risk level classification
- ✅ CVE flagging for high-profile repos
- ✅ GraphRAG configuration generation
"""

import os
import subprocess
import shutil
import requests
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
from datetime import datetime
import time

# ============================================================================
# CONFIGURATION
# ============================================================================
BASE_VAULT_PATH = Path("data/raw")
TIMESTAMP = datetime.now().strftime("%Y%m%d_%H%M%S")
LOG_FILE = BASE_VAULT_PATH / f"download_log_{TIMESTAMP}.txt"

# ============================================================================
# VAULT 3 REPOSITORY MAPPING (COMPLETE - ALL CATEGORIES)
# FIXED: Removed duplicate entries (google/styleguide, sqlalchemy)
# FIXED: Added CVE-flagged repos for awareness
# ============================================================================
VAULT_3_REPOS: Dict[str, str] = {
    # =========================================================================
    # 01_Secure_Code_C_CPP (9 Repos)
    # =========================================================================
    "https://github.com/openbsd/src":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/openbsd-src",
    "https://github.com/jedisct1/libsodium":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/libsodium",
    "https://github.com/google/sanitizers":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/google-sanitizers",
    "https://github.com/madler/zlib":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/zlib",
    "https://github.com/sqlite/sqlite":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/sqlite",
    "https://github.com/google/styleguide":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/cpplint",
    "https://github.com/nlohmann/json":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/nlohmann-json",
    "https://github.com/google/googletest":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/googletest",
    "https://github.com/ttroy50/cmake-examples":
        "03_Vault_Showroom/01_Secure_Code_C_CPP/cmake-examples",

    # =========================================================================
    # 02_Secure_Code_Java (9 Repos - DUPLICATE google/styleguide REMOVED)
    # =========================================================================
    "https://github.com/spring-projects/spring-security":
        "03_Vault_Showroom/02_Secure_Code_Java/spring-security",
    "https://github.com/ESAPI/esapi-java-legacy":
        "03_Vault_Showroom/02_Secure_Code_Java/owasp-esapi",
    "https://github.com/google/guava":
        "03_Vault_Showroom/02_Secure_Code_Java/google-guava",
    "https://github.com/iluwatar/java-design-patterns":
        "03_Vault_Showroom/02_Secure_Code_Java/java-design-patterns",
    "https://github.com/apache/shiro":
        "03_Vault_Showroom/02_Secure_Code_Java/apache-shiro",
    "https://github.com/hibernate/hibernate-orm":
        "03_Vault_Showroom/02_Secure_Code_Java/hibernate-orm",
    "https://github.com/FasterXML/jackson-databind":
        "03_Vault_Showroom/02_Secure_Code_Java/jackson-databind",
    "https://github.com/spring-projects/spring-security-samples":
        "03_Vault_Showroom/02_Secure_Code_Java/spring-guides",
    "https://github.com/junit-team/junit5":
        "03_Vault_Showroom/02_Secure_Code_Java/junit",

    # =========================================================================
    # 03_Secure_Code_Python (20 Repos - DUPLICATE sqlalchemy REMOVED)
    # =========================================================================
    "https://github.com/pyca/cryptography":
        "03_Vault_Showroom/03_Secure_Code_Python/pyca-cryptography",
    "https://github.com/psf/requests":
        "03_Vault_Showroom/03_Secure_Code_Python/requests",
    "https://github.com/PyCQA/bandit":
        "03_Vault_Showroom/03_Secure_Code_Python/bandit",
    "https://github.com/tiangolo/fastapi":
        "03_Vault_Showroom/03_Secure_Code_Python/fastapi",
    "https://github.com/django/django":
        "03_Vault_Showroom/03_Secure_Code_Python/django",
    "https://github.com/pallets/flask":
        "03_Vault_Showroom/03_Secure_Code_Python/flask",
    "https://github.com/sqlalchemy/sqlalchemy":
        "03_Vault_Showroom/03_Secure_Code_Python/sqlalchemy",
    "https://github.com/celery/celery":
        "03_Vault_Showroom/03_Secure_Code_Python/celery",
    "https://github.com/pydantic/pydantic":
        "03_Vault_Showroom/03_Secure_Code_Python/pydantic",
    "https://github.com/pypa/sampleproject":
        "03_Vault_Showroom/03_Secure_Code_Python/pypa-sampleproject",
    "https://github.com/audreyr/cookiecutter-pypackage":
        "03_Vault_Showroom/03_Secure_Code_Python/cookiecutter-pypackage",
    "https://github.com/python-poetry/poetry":
        "03_Vault_Showroom/03_Secure_Code_Python/poetry",
    "https://github.com/pytest-dev/pytest":
        "03_Vault_Showroom/03_Secure_Code_Python/pytest",
    "https://github.com/pallets/click":
        "03_Vault_Showroom/03_Secure_Code_Python/click",
    "https://github.com/python-attrs/attrs":
        "03_Vault_Showroom/03_Secure_Code_Python/attrs",
    "https://github.com/encode/httpx":
        "03_Vault_Showroom/03_Secure_Code_Python/httpx",
    "https://github.com/Textualize/rich":
        "03_Vault_Showroom/03_Secure_Code_Python/rich",
    "https://github.com/psf/black":
        "03_Vault_Showroom/03_Secure_Code_Python/black",
    "https://github.com/python/mypy":
        "03_Vault_Showroom/03_Secure_Code_Python/mypy",
    "https://github.com/python/typeshed":
        "03_Vault_Showroom/03_Secure_Code_Python/typeshed",
    "https://github.com/vinta/awesome-python":
        "03_Vault_Showroom/03_Secure_Code_Python/awesome-python",

    # =========================================================================
    # 04_Secure_Code_Web_Frontend (17 Repos)
    # =========================================================================
    "https://github.com/facebook/react":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/react",
    "https://github.com/vuejs/core":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/vuejs-core",
    "https://github.com/angular/angular":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/angular",
    "https://github.com/vercel/next.js":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/nextjs",
    "https://github.com/cure53/DOMPurify":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/dompurify",
    "https://github.com/helmetjs/helmet":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/helmetjs",
    "https://github.com/expressjs/express":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/expressjs",
    "https://github.com/apollographql/apollo-client":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/apollo-client",
    "https://github.com/axios/axios":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/axios",
    "https://github.com/tailwindlabs/tailwindcss":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/tailwindcss",
    "https://github.com/twbs/bootstrap":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/bootstrap",
    "https://github.com/webpack/webpack":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/webpack",
    "https://github.com/babel/babel":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/babel",
    "https://github.com/microsoft/TypeScript":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/typescript",
    "https://github.com/standard/standard":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/standard-js",
    "https://github.com/goldbergyoni/nodebestpractices":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/nodebestpractices",
    "https://github.com/facebook/create-react-app":
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend/create-react-app",

    # =========================================================================
    # 05_Secure_Code_Go_Rust (8 Repos)
    # =========================================================================
    "https://github.com/golang-standards/project-layout":
        "03_Vault_Showroom/05_Secure_Code_Go_Rust/go-project-layout",
    "https://github.com/spf13/cobra":
        "03_Vault_Showroom/05_Secure_Code_Go_Rust/cobra",
    "https://github.com/gin-gonic/gin":
        "03_Vault_Showroom/05_Secure_Code_Go_Rust/gin",
    "https://github.com/go-gorm/gorm":
        "03_Vault_Showroom/05_Secure_Code_Go_Rust/gorm",
    "https://github.com/tokio-rs/tokio":
        "03_Vault_Showroom/05_Secure_Code_Go_Rust/tokio",
    "https://github.com/serde-rs/serde":
        "03_Vault_Showroom/05_Secure_Code_Go_Rust/serde",
    "https://github.com/clap-rs/clap":
        "03_Vault_Showroom/05_Secure_Code_Go_Rust/clap",
    "https://github.com/rust-lang/rust-by-example":
        "03_Vault_Showroom/05_Secure_Code_Go_Rust/rust-by-example",

    # =========================================================================
    # 06_Secure_Code_Database (5 Repos - sqlalchemy DUPLICATE REMOVED)
    # =========================================================================
    "https://github.com/postgres/postgres":
        "03_Vault_Showroom/06_Secure_Code_Database/postgres",
    "https://github.com/mongodb/mongo":
        "03_Vault_Showroom/06_Secure_Code_Database/mongodb",
    "https://github.com/redis/redis":
        "03_Vault_Showroom/06_Secure_Code_Database/redis",
    "https://github.com/elastic/elasticsearch":
        "03_Vault_Showroom/06_Secure_Code_Database/elasticsearch",
    "https://github.com/mysql/mysql-server":
        "03_Vault_Showroom/06_Secure_Code_Database/mysql-server",

    # =========================================================================
    # 07_Secure_Code_DevOps_Cloud (9 Repos)
    # =========================================================================
    "https://github.com/kubernetes/kubernetes":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/kubernetes",
    "https://github.com/hashicorp/terraform":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/terraform",
    "https://github.com/moby/moby":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/docker-moby",
    "https://github.com/ansible/ansible":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/ansible",
    "https://github.com/prometheus/prometheus":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/prometheus",
    "https://github.com/grafana/grafana":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/grafana",
    "https://github.com/helm/helm":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/helm",
    "https://github.com/actions/starter-workflows":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/github-actions",
    "https://github.com/cisofy/lynis":
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud/lynis",

    # =========================================================================
    # 08_Secure_Code_Machine_Learning_AI (17 Repos)
    # =========================================================================
    "https://github.com/huggingface/transformers":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/transformers",
    "https://github.com/pytorch/pytorch":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/pytorch",
    "https://github.com/tensorflow/tensorflow":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/tensorflow",
    "https://github.com/scikit-learn/scikit-learn":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/scikit-learn",
    "https://github.com/langchain-ai/langchain":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/langchain",
    "https://github.com/run-llama/llama_index":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/llama-index",
    "https://github.com/Trusted-AI/adversarial-robustness-toolbox":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/art",
    "https://github.com/mlflow/mlflow":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/mlflow",
    "https://github.com/protectai/llm-guard":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/llm-guard",
    "https://github.com/OpenMined/PySyft":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/pysyft",
    "https://github.com/microsoft/SEAL":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/seal",
    "https://github.com/protectai/model-scanner":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/model-scanner",
    "https://github.com/imartinez/privateGPT":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/privategpt",
    "https://github.com/tensorflow/model-card-toolkit":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/model-card-toolkit",
    "https://github.com/tensorflow/fairness-indicators":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/fairness-indicators",
    "https://github.com/PAIR-code/what-if-tool":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/what-if-tool",
    "https://github.com/Azure/counterfit":
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI/counterfit",

    # =========================================================================
    # 09_Architecture_Decision_Records (4 Repos)
    # =========================================================================
    "https://github.com/cockroachdb/cockroach":
        "03_Vault_Showroom/09_Architecture_Decision_Records/cockroachdb",
    "https://github.com/python/peps":
        "03_Vault_Showroom/09_Architecture_Decision_Records/python-peps",
    "https://github.com/rust-lang/rfcs":
        "03_Vault_Showroom/09_Architecture_Decision_Records/rust-rfcs",
    "https://github.com/Netflix/ocelli":
        "03_Vault_Showroom/09_Architecture_Decision_Records/netflix-ocelli",

    # =========================================================================
    # 10_Tool_Configs_Kali (6 Repos)
    # =========================================================================
    "https://github.com/nmap/nmap":
        "03_Vault_Showroom/10_Tool_Configs_Kali/nmap",
    "https://github.com/BloodHoundAD/BloodHound":
        "03_Vault_Showroom/10_Tool_Configs_Kali/bloodhound",
    "https://github.com/NationalSecurityAgency/ghidra":
        "03_Vault_Showroom/10_Tool_Configs_Kali/ghidra",
    "https://github.com/github/securitylab":
        "03_Vault_Showroom/10_Tool_Configs_Kali/github-securitylab",
    "https://github.com/snort3/snort3":
        "03_Vault_Showroom/10_Tool_Configs_Kali/snort3",
    "https://github.com/sonatype-nexus-community/nancy":
        "03_Vault_Showroom/10_Tool_Configs_Kali/nancy",
}

# ============================================================================
# VAULT 1 DOCUMENTATION REPOS (Not Code - Documentation Only)
# ============================================================================
VAULT_1_DOCS: Dict[str, str] = {
    "https://github.com/realpython/python-guide":
        "01_Vault_Library/13_Codebooks_Programming_Core/python-guide",
    "https://github.com/sqlite/sqlite":
        "01_Vault_Library/11_Manuals_Tools/sqlite",
}

# ============================================================================
# INVALID REPOS (Do Not Download)
# ============================================================================
INVALID_REPOS: List[str] = [
    "https://github.com/tensorflow/tensorflow/security",
]

# ============================================================================
# HIGH-RISK REPOS (Flag for Educational Use Only)
# ============================================================================
HIGH_RISK_REPOS: List[str] = [
    "https://github.com/Azure/counterfit",
    "https://github.com/Trusted-AI/adversarial-robustness-toolbox",
    "https://github.com/BloodHoundAD/BloodHound",
    "https://github.com/nmap/nmap",
    "https://github.com/NationalSecurityAgency/ghidra",
]

# ============================================================================
# CVE-FLAGGED REPOS (Known CVEs but Actively Patched)
# ============================================================================
CVE_FLAGGED_REPOS: List[str] = [
    "https://github.com/tensorflow/tensorflow",
    "https://github.com/pytorch/pytorch",
    "https://github.com/kubernetes/kubernetes",
    "https://github.com/django/django",
    "https://github.com/FasterXML/jackson-databind",
]

# ============================================================================
# SECURITY SCANNING TOOL PATHS
# FIXED: npm install command now uses shell=True compatible format
# ============================================================================
SECURITY_TOOLS = {
    "pip_audit": {
        "check": ["pip", "show", "pip-audit"],
        "install": ["pip", "install", "pip-audit"],
        "required": True,
        "purpose": "Python dependency vulnerability scanning"
    },
    "gitleaks": {
        "check": ["gitleaks", "version"],
        "install": ["go", "install", "github.com/gitleaks/gitleaks@latest"],
        "required": True,
        "purpose": "Secret scanning in git repos"
    },
    "bandit": {
        "check": ["bandit", "--version"],
        "install": ["pip", "install", "bandit"],
        "required": False,
        "purpose": "Python SAST scanning"
    },
    "npm": {
        "check": ["npm", "--version"],
        "install": "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt install -y nodejs",
        "required": False,
        "purpose": "JavaScript dependency scanning"
    }
}

# ============================================================================
# LOGGING FUNCTION
# FIXED: All newline characters use proper \n escape sequences
# ============================================================================
def log_message(message: str, level: str = "INFO") -> None:
    """Log message to console and file"""
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
# SECURITY TOOL VERIFICATION
# ============================================================================
def verify_security_tools() -> Dict[str, bool]:
    """Verify that required security tools are installed"""
    log_message("Verifying security tools...", "INFO")
    tool_status = {}
    missing_required = []

    for tool_name, tool_info in SECURITY_TOOLS.items():
        try:
            result = subprocess.run(
                tool_info["check"],
                capture_output=True,
                text=True,
                check=False
            )
            if result.returncode == 0:
                tool_status[tool_name] = True
                log_message(f"  ✓ {tool_name} found", "SUCCESS")
            else:
                tool_status[tool_name] = False
                if tool_info["required"]:
                    missing_required.append(tool_name)
                log_message(f"  ✗ {tool_name} not found (optional)", "WARNING")
        except FileNotFoundError:
            tool_status[tool_name] = False
            if tool_info["required"]:
                missing_required.append(tool_name)
            log_message(f"  ✗ {tool_name} not found (optional)", "WARNING")

    if missing_required:
        log_message(f"\n❌ Missing required tools: {', '.join(missing_required)}", "ERROR")
        log_message("\nInstall missing tools:", "INFO")
        for tool in missing_required:
            install_cmd = " ".join(SECURITY_TOOLS[tool]["install"])
            log_message(f"  {tool}: {install_cmd}", "INFO")
        response = input("\nContinue without security scanning? (y/N): ")
        if response.lower() != 'y':
            sys.exit(1)
        log_message("Continuing WITHOUT security scanning - repositories will NOT be validated", "WARNING")
        return {k: False for k in tool_status}

    return tool_status

# ============================================================================
# INSTALL MISSING TOOLS
# FIXED: Function now properly called in main()
# FIXED: Uses shell=True for commands with pipes
# ============================================================================
def install_missing_tools(tool_status: Dict[str, bool]) -> None:
    """Attempt to install missing optional tools"""
    log_message("\nAttempting to install optional security tools...", "INFO")

    for tool_name, installed in tool_status.items():
        if not installed and SECURITY_TOOLS[tool_name]["required"] is False:
            log_message(f"  Installing {tool_name}...", "INFO")
            try:
                install_cmd = SECURITY_TOOLS[tool_name]["install"]
                if isinstance(install_cmd, str):
                    subprocess.run(install_cmd, shell=True, check=True, timeout=300)
                else:
                    subprocess.run(install_cmd, check=True, timeout=300)
                log_message(f"  ✓ {tool_name} installed", "SUCCESS")
            except Exception as e:
                log_message(f"  ✗ Failed to install {tool_name}: {e}", "WARNING")

# ============================================================================
# SECURITY SCANNING FUNCTIONS
# ============================================================================
def scan_python_vulnerabilities(repo_path: Path, tool_status: Dict[str, bool]) -> Dict[str, Any]:
    """Scan Python dependencies for known vulnerabilities using pip-audit"""
    if not tool_status.get("pip_audit", False):
        return {"status": "skipped", "reason": "pip-audit not installed"}

    req_files = list(repo_path.glob("requirements*.txt")) + \
                list(repo_path.glob("pyproject.toml")) + \
                list(repo_path.glob("Pipfile"))

    if not req_files:
        return {"status": "skipped", "reason": "No requirements files found"}

    results = {}
    total_count = 0
    for req_file in req_files:
        try:
            log_message(f"    Scanning Python deps: {req_file.name}", "INFO")
            result = subprocess.run(
                ["pip-audit", "--requirement", str(req_file), "--format", "json"],
                capture_output=True,
                text=True,
                timeout=600
            )
            if result.stdout:
                vulns = json.loads(result.stdout)
                file_count = sum(len(v.get('vulns', [])) for v in vulns) if isinstance(vulns, list) else len(vulns.get("vulnerabilities", []))
                results[req_file.name] = {
                    "vulnerabilities": vulns,
                    "count": file_count
                }
                total_count += file_count
            else:
                results[req_file.name] = {"vulnerabilities": [], "count": 0}
        except subprocess.TimeoutExpired:
            results[req_file.name] = {"error": "Timeout scanning dependencies"}
        except Exception as e:
            results[req_file.name] = {"error": str(e)}

    results["count"] = total_count
    return results

def scan_javascript_vulnerabilities(repo_path: Path, tool_status: Dict[str, bool]) -> Dict[str, Any]:
    """Scan JavaScript dependencies using npm audit"""
    if not tool_status.get("npm", False):
        return {"status": "skipped", "reason": "npm not installed"}

    package_files = list(repo_path.glob("package.json")) + \
                    list(repo_path.glob("package-lock.json"))

    if not package_files:
        return {"status": "skipped", "reason": "No package files found"}

    results = {}
    try:
        log_message(f"    Scanning JS deps", "INFO")
        result = subprocess.run(
            ["npm", "audit", "--json"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=1200
        )
        if result.stdout:
            audit = json.loads(result.stdout)
            results["npm_audit"] = {
                "vulnerabilities": audit.get("vulnerabilities", {}),
                "metadata": audit.get("metadata", {})
            }
    except Exception as e:
        results["error"] = str(e)

    return results

def scan_secrets(repo_path: Path, tool_status: Dict[str, bool]) -> Dict[str, Any]:
    """Scan repository for hardcoded secrets using gitleaks"""
    if not tool_status.get("gitleaks", False):
        return {"status": "skipped", "reason": "gitleaks not installed"}

    try:
        log_message(f"    Scanning for secrets", "INFO")
        # FIXED: Removed --no-git flag for better compatibility
        result = subprocess.run(
            ["gitleaks", "detect", "--source", str(repo_path), "--format", "json"],
            capture_output=True,
            text=True,
            timeout=1800
        )

        if result.returncode == 1:
            secrets = json.loads(result.stdout) if result.stdout else []
            return {
                "secrets_found": len(secrets),
                "secrets": secrets,
                "status": "vulnerable"
            }
        elif result.returncode == 0:
            return {"secrets_found": 0, "secrets": [], "status": "clean"}
        else:
            return {"error": result.stderr, "status": "error"}
    except subprocess.TimeoutExpired:
        return {"error": "Timeout scanning secrets", "status": "error"}
    except Exception as e:
        return {"error": str(e), "status": "error"}

def scan_python_sast(repo_path: Path, tool_status: Dict[str, bool]) -> Dict[str, Any]:
    """Run bandit SAST scan on Python code"""
    if not tool_status.get("bandit", False):
        return {"status": "skipped", "reason": "bandit not installed"}

    python_files = list(repo_path.rglob("*.py"))
    if not python_files:
        return {"status": "skipped", "reason": "No Python files found"}

    try:
        log_message(f"    Running SAST scan", "INFO")
        result = subprocess.run(
            ["bandit", "-r", str(repo_path), "-f", "json"],
            capture_output=True,
            text=True,
            timeout=1800
        )
        if result.stdout:
            sast_results = json.loads(result.stdout)
            return {
                "total_issues": len(sast_results.get("results", [])),
                "metrics": sast_results.get("metrics", {}),
                "results": sast_results.get("results", [])
            }
    except Exception as e:
        return {"error": str(e)}

    return {"status": "no_results"}

def analyze_git_history(repo_path: Path) -> Dict[str, Any]:
    """Analyze git history for security-relevant commits"""
    if not (repo_path / ".git").exists():
        return {"status": "skipped", "reason": "Not a git repository"}

    try:
        result = subprocess.run(
            ["git", "rev-list", "--count", "HEAD"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        total_commits = int(result.stdout.strip()) if result.stdout else 0

        result = subprocess.run(
            ["git", "log", "--grep", "security\\|vuln\\|cve\\|fix\\|patch", "--oneline"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=600
        )
        security_commits = result.stdout.strip().split('\n') if result.stdout else []
        if security_commits == ['']:
            security_commits = []

        result = subprocess.run(
            ["git", "log", "-1", "--format=%cd"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30
        )
        last_commit = result.stdout.strip()

        return {
            "total_commits": total_commits,
            "security_commits": len(security_commits),
            "security_commit_list": security_commits[:10],
            "last_commit": last_commit,
            "has_recent_activity": last_commit is not None
        }
    except Exception as e:
        return {"error": str(e)}

# ============================================================================
# CORE FUNCTIONS
# ============================================================================
def check_git_installed() -> bool:
    """Check if git is installed on the system."""
    try:
        subprocess.run(["git", "--version"], capture_output=True, check=True)
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False

def create_directory_structure() -> None:
    """Create all necessary Vault directories."""
    log_message("Creating directory structure...", "INFO")

    directories = [
        "03_Vault_Showroom/01_Secure_Code_C_CPP",
        "03_Vault_Showroom/02_Secure_Code_Java",
        "03_Vault_Showroom/03_Secure_Code_Python",
        "03_Vault_Showroom/04_Secure_Code_Web_Frontend",
        "03_Vault_Showroom/05_Secure_Code_Go_Rust",
        "03_Vault_Showroom/06_Secure_Code_Database",
        "03_Vault_Showroom/07_Secure_Code_DevOps_Cloud",
        "03_Vault_Showroom/08_Secure_Code_Machine_Learning_AI",
        "03_Vault_Showroom/09_Architecture_Decision_Records",
        "03_Vault_Showroom/10_Tool_Configs_Kali",
        "03_Vault_Showroom/11_Framework_Documentation",
    ]

    for dir_path in directories:
        full_path = BASE_VAULT_PATH / dir_path
        full_path.mkdir(parents=True, exist_ok=True)
        log_message(f"  ✓ Created: {full_path}", "SUCCESS")

def clone_repository(repo_url: str, destination: str, depth: int = 1) -> Tuple[bool, str, float]:
    """Clone a repository to the specified destination."""
    full_dest = BASE_VAULT_PATH / destination

    if full_dest.exists():
        return False, f"Already exists: {full_dest}", 0

    start_time = time.time()
    try:
        log_message(f"    Cloning: {repo_url}", "INFO")
        subprocess.run(
            ["git", "clone", "--depth", str(depth), repo_url, str(full_dest)],
            capture_output=True,
            check=True,
            timeout=2400
        )
        duration = time.time() - start_time
        return True, f"Success: {full_dest}", duration
    except subprocess.CalledProcessError as e:
        duration = time.time() - start_time
        return False, f"Failed: {e.stderr.decode()}", duration
    except subprocess.TimeoutExpired:
        duration = time.time() - start_time
        return False, f"Timeout: {repo_url}", duration

def validate_repository(repo_path: Path) -> Dict[str, bool]:
    """Validate repository for production readiness."""
    validation = {
        "has_license": False,
        "has_tests": False,
        "has_ci_cd": False,
        "has_readme": False,
        "has_config_files": False,
    }

    if not repo_path.exists():
        return validation

    license_files = ["LICENSE", "LICENSE.txt", "LICENSE.md", "COPYING"]
    for lic in license_files:
        if (repo_path / lic).exists():
            validation["has_license"] = True
            break

    test_dirs = ["tests", "test", "spec", "_test", "Testing"]
    for test_dir in test_dirs:
        if (repo_path / test_dir).exists():
            validation["has_tests"] = True
            break

    ci_files = [
        ".github/workflows",
        ".gitlab-ci.yml",
        ".travis.yml",
        ".circleci",
        "azure-pipelines.yml",
        ".jenkins"
    ]
    for ci in ci_files:
        if (repo_path / ci).exists():
            validation["has_ci_cd"] = True
            break

    readme_files = ["README.md", "README.txt", "README.rst"]
    for readme in readme_files:
        if (repo_path / readme).exists():
            validation["has_readme"] = True
            break

    config_files = [
        "pyproject.toml", "setup.py", "setup.cfg",
        "package.json", "Cargo.toml", "go.mod",
        "pom.xml", "build.gradle", "Makefile"
    ]
    for config in config_files:
        if (repo_path / config).exists():
            validation["has_config_files"] = True
            break

    return validation

def generate_metadata(repo_path: Path, repo_url: str, category: str,
                      tool_status: Dict[str, bool]) -> Dict:
    """Generate comprehensive metadata with security audit results."""
    validation = validate_repository(repo_path)

    is_python = (repo_path / "pyproject.toml").exists() or \
                (repo_path / "setup.py").exists() or \
                (repo_path / "requirements.txt").exists()

    is_javascript = (repo_path / "package.json").exists() or \
                    (repo_path / "package-lock.json").exists()

    has_src_layout = (repo_path / "src").exists() if is_python else False

    has_type_hints = False
    if is_python:
        py_files = list(repo_path.rglob("*.py"))
        for py_file in py_files[:10]:
            if py_file.is_file():
                try:
                    content = py_file.read_text(encoding='utf-8', errors='ignore')
                    if 'typing' in content or '->' in content:
                        has_type_hints = True
                        break
                except:
                    pass

    log_message(f"  🔍 Running security scans on {repo_path.name}...", "INFO")
    python_vulns = scan_python_vulnerabilities(repo_path, tool_status) if is_python else {"status": "skipped", "count": 0}
    js_vulns = scan_javascript_vulnerabilities(repo_path, tool_status) if is_javascript else {"status": "skipped"}
    secrets = scan_secrets(repo_path, tool_status)
    sast = scan_python_sast(repo_path, tool_status) if is_python else {"status": "skipped"}
    git_history = analyze_git_history(repo_path)

    risk_level = "LOW"
    warnings = []

    if python_vulns.get("count", 0) > 0:
        risk_level = "MEDIUM"
        warnings.append(f"Python vulnerabilities: {python_vulns.get('count')}")

    if js_vulns.get("vulnerabilities", {}):
        risk_level = "MEDIUM"
        warnings.append("JavaScript vulnerabilities found")

    if secrets.get("secrets_found", 0) > 0:
        risk_level = "HIGH"
        warnings.append(f"Secrets found: {secrets.get('secrets_found')}")

    if sast.get("total_issues", 0) > 5:
        risk_level = "MEDIUM"
        warnings.append(f"SAST issues: {sast.get('total_issues')}")

    if repo_url in HIGH_RISK_REPOS:
        risk_level = "CRITICAL"
        warnings.append("Pre-flagged as high-risk repository")

    if repo_url in CVE_FLAGGED_REPOS:
        if risk_level == "LOW":
            risk_level = "MEDIUM"
        warnings.append("Known CVEs (actively patched)")

    metadata = {
        "repository_url": repo_url,
        "category": category,
        "path": str(repo_path.relative_to(BASE_VAULT_PATH)),
        "cloned_at": datetime.now().isoformat(),
        "validation": validation,
        "is_production_ready": all(validation.values()) and risk_level not in ["HIGH", "CRITICAL"],
        "is_python": is_python,
        "is_javascript": is_javascript,
        "has_src_layout": has_src_layout if is_python else None,
        "has_type_hints": has_type_hints if is_python else None,
        "is_high_risk": repo_url in HIGH_RISK_REPOS,
        "educational_only": repo_url in HIGH_RISK_REPOS,
        "has_known_cves": repo_url in CVE_FLAGGED_REPOS,
        "security": {
            "risk_level": risk_level,
            "warnings": warnings,
            "python_vulnerabilities": python_vulns,
            "javascript_vulnerabilities": js_vulns,
            "secrets": secrets,
            "sast": sast,
            "git_history": git_history
        }
    }

    return metadata

def generate_reports(all_metadata: List[Dict]) -> None:
    """Generate comprehensive reports for all cloned repositories."""
    log_message("\n📊 Generating reports...", "INFO")

    json_path = BASE_VAULT_PATH / f"repository_metadata_{TIMESTAMP}.json"
    markdown_path = BASE_VAULT_PATH / f"repository_report_{TIMESTAMP}.md"

    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(all_metadata, f, indent=2, ensure_ascii=False)

    with open(markdown_path, 'w', encoding='utf-8') as f:
        f.write(f"# HackT Knowledge Base - Repository Validation Report\n")
        f.write(f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"**Total Repositories:** {len(all_metadata)}\n\n")

        production_ready = sum(1 for m in all_metadata if m.get("is_production_ready", False))
        high_risk = sum(1 for m in all_metadata if m.get("security", {}).get("risk_level") == "HIGH")
        critical_risk = sum(1 for m in all_metadata if m.get("security", {}).get("risk_level") == "CRITICAL")
        has_secrets = sum(1 for m in all_metadata if m.get("security", {}).get("secrets", {}).get("secrets_found", 0) > 0)
        has_cves = sum(1 for m in all_metadata if m.get("has_known_cves", False))

        f.write("## Summary Statistics\n")
        f.write("| Metric | Count |\n")
        f.write("| :--- | :---: |\n")
        f.write(f"| Total Repositories | {len(all_metadata)} |\n")
        f.write(f"| Production Ready | {production_ready} |\n")
        f.write(f"| High Risk | {high_risk} |\n")
        f.write(f"| Critical Risk | {critical_risk} |\n")
        f.write(f"| Contains Secrets | {has_secrets} |\n")
        f.write(f"| Known CVEs (Patched) | {has_cves} |\n\n")

        f.write("## Risk Summary\n")
        f.write("| Risk Level | Count | Action Required |\n")
        f.write("| :--- | :---: | :--- |\n")
        f.write(f"| 🔴 CRITICAL | {critical_risk} | Do not use - contains attack tools or critical secrets |\n")
        f.write(f"| 🟠 HIGH | {high_risk} | Security review required before use |\n")
        f.write(f"| 🟡 MEDIUM | {len([m for m in all_metadata if m.get('security', {}).get('risk_level') == 'MEDIUM'])} | Update vulnerable dependencies |\n")
        f.write(f"| 🟢 LOW | {len([m for m in all_metadata if m.get('security', {}).get('risk_level') == 'LOW'])} | Safe for ingestion |\n\n")

        f.write("## Repositories by Category\n")
        categories = {}
        for m in all_metadata:
            cat = m["category"]
            if cat not in categories:
                categories[cat] = []
            categories[cat].append(m)

        for cat, repos in sorted(categories.items()):
            f.write(f"### {cat}\n")
            f.write("| Repository | License | Tests | CI/CD | README | Risk Level | Secrets | CVEs |\n")
            f.write("| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")

            for repo in repos:
                v = repo["validation"]
                s = repo["security"]
                risk_emoji = {
                    "LOW": "🟢",
                    "MEDIUM": "🟡",
                    "HIGH": "🟠",
                    "CRITICAL": "🔴"
                }.get(s.get("risk_level", "UNKNOWN"), "⚪")

                secrets_found = s.get("secrets", {}).get("secrets_found", 0)
                secrets_indicator = f"🔑 {secrets_found}" if secrets_found > 0 else "✅"
                cve_indicator = "⚠️" if repo.get("has_known_cves", False) else "✅"

                f.write(f"| {repo['path'].split('/')[-1]} | ")
                f.write(f"{'✅' if v['has_license'] else '❌'} | ")
                f.write(f"{'✅' if v['has_tests'] else '❌'} | ")
                f.write(f"{'✅' if v['has_ci_cd'] else '❌'} | ")
                f.write(f"{'✅' if v['has_readme'] else '❌'} | ")
                f.write(f"{risk_emoji} {s.get('risk_level', 'UNKNOWN')} | ")
                f.write(f"{secrets_indicator} | ")
                f.write(f"{cve_indicator} |\n")

            f.write("\n")

    log_message(f"  ✓ JSON Report: {json_path}", "SUCCESS")
    log_message(f"  ✓ Markdown Report: {markdown_path}", "SUCCESS")

def generate_graphrag_config(all_metadata: List[Dict]) -> None:
    """Generate GraphRAG configuration file for AST parsing."""
    config_path = BASE_VAULT_PATH / "graphrag_config.json"

    config = {
        "version": "8.1",
        "generated_at": datetime.now().isoformat(),
        "vault_3_repositories": [],
        "tree_sitter_grammars": [
            "python", "javascript", "typescript", "java", "c", "cpp",
            "go", "rust", "html", "css", "sql", "yaml", "json"
        ],
        "ast_node_types": [
            "Function", "Class", "Module", "Import", "Variable",
            "Component", "Interface", "Trait", "Struct"
        ],
        "edge_types": [
            "calls", "imports", "inherits", "depends_on",
            "exposes_api", "tests_function", "implements"
        ]
    }

    for meta in all_metadata:
        repo_config = {
            "path": meta["path"],
            "category": meta["category"],
            "language": "python" if meta.get("is_python") else "javascript" if meta.get("is_javascript") else "mixed",
            "has_src_layout": meta.get("has_src_layout"),
            "has_type_hints": meta.get("has_type_hints"),
            "is_high_risk": meta["is_high_risk"],
            "educational_only": meta["educational_only"],
            "production_ready": meta["is_production_ready"],
            "risk_level": meta["security"]["risk_level"],
            "warnings": meta["security"]["warnings"],
            "has_known_cves": meta.get("has_known_cves", False)
        }
        config["vault_3_repositories"].append(repo_config)

    with open(config_path, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=2, ensure_ascii=False)

    log_message(f"  ✓ GraphRAG Config: {config_path}", "SUCCESS")

def print_summary(vault3_success: int, vault3_fail: int, vault1_success: int,
                  vault1_fail: int, all_metadata: List[Dict]) -> None:
    """Print final summary with risk assessment."""
    log_message("\n" + "="*80, "INFO")
    log_message("DOWNLOAD SUMMARY WITH SECURITY ASSESSMENT", "INFO")
    log_message("="*80, "INFO")
    log_message(f"Vault 3 Repositories: {vault3_success}/{len(VAULT_3_REPOS)} cloned", "INFO")
    log_message(f"Vault 1 Documentation: {vault1_success}/{len(VAULT_1_DOCS)} cloned", "INFO")
    log_message(f"Invalid Repos Skipped: {len(INVALID_REPOS)}", "INFO")

    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    secrets_count = 0
    vuln_count = 0
    cve_count = 0

    for meta in all_metadata:
        risk = meta["security"]["risk_level"]
        risk_counts[risk] = risk_counts.get(risk, 0) + 1
        if meta["security"]["secrets"].get("secrets_found", 0) > 0:
            secrets_count += 1
        python_vulns = meta["security"]["python_vulnerabilities"]
        if isinstance(python_vulns, dict) and "count" in python_vulns:
            vuln_count += python_vulns["count"]
        if meta.get("has_known_cves", False):
            cve_count += 1

    log_message("\n📊 SECURITY RISK ASSESSMENT:", "INFO")
    log_message(f"  🟢 LOW Risk: {risk_counts['LOW']} repos", "INFO")
    log_message(f"  🟡 MEDIUM Risk: {risk_counts['MEDIUM']} repos", "INFO")
    log_message(f"  🟠 HIGH Risk: {risk_counts['HIGH']} repos", "WARNING")
    log_message(f"  🔴 CRITICAL Risk: {risk_counts['CRITICAL']} repos", "ERROR")
    log_message(f"  🔑 Repos with Secrets: {secrets_count}", "WARNING" if secrets_count > 0 else "INFO")
    log_message(f"  🐛 Vulnerable Dependencies: {vuln_count}", "WARNING" if vuln_count > 0 else "INFO")
    log_message(f"  ⚠️  Known CVEs (Patched): {cve_count}", "INFO")

    high_risk_repos = [m for m in all_metadata if m["security"]["risk_level"] in ["HIGH", "CRITICAL"]]
    if high_risk_repos:
        log_message("\n⚠️  HIGH/CRITICAL RISK REPOSITORIES:", "WARNING")
        for repo in high_risk_repos:
            log_message(f"    - {repo['path']} ({repo['security']['risk_level']})", "WARNING")
            for warning in repo["security"]["warnings"][:3]:
                log_message(f"      • {warning}", "WARNING")

    log_message("\n📁 Reports generated:", "INFO")
    log_message(f"  • repository_metadata_{TIMESTAMP}.json", "INFO")
    log_message(f"  • repository_report_{TIMESTAMP}.md", "INFO")
    log_message(f"  • graphrag_config.json", "INFO")
    log_message(f"  • download_log_{TIMESTAMP}.txt", "INFO")
    log_message("\n" + "="*80, "INFO")


def check_repo(url):
    """Check if a GitHub repository URL is valid."""
    try:
        # Send a HEAD request to avoid downloading the whole page
        response = requests.head(url, allow_redirects=True, timeout=10)
        if response.status_code == 200:
            return url, True, "OK"
        else:
            # If HEAD fails, try a GET (some servers block HEAD)
            response = requests.get(url, timeout=10)
            if response.status_code == 200:
                return url, True, "OK (GET)"
            else:
                return url, False, f"HTTP {response.status_code}"
    except requests.exceptions.RequestException as e:
        return url, False, str(e)

# ============================================================================
# MAIN EXECUTION
# ============================================================================
def main():
    # Run checks in parallel for speed
    print("🔍 Verifying all repository URLs...\n")
    results = {}
    with ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {executor.submit(check_repo, url): url for url in VAULT_3_REPOS.keys()}
        for future in as_completed(future_to_url):
            url, is_ok, message = future.result()
            results[url] = (is_ok, message)
            status = "✅" if is_ok else "❌"
            print(f"{status} {url} -> {message}")

    # Summary
    print("\n" + "="*60)
    working = sum(1 for v in results.values() if v[0])
    failed = len(results) - working
    print(f"SUMMARY: {working} working, {failed} failed")
    print("="*60)
    """Main execution function."""
    print("\n" + "="*80)
    print("HackT Knowledge Base - Complete Repository Downloader")
    print("Version: 8.1 | Production-Ready with Security Scanning")
    print("Architecture: Hybrid RAG (Semantic + Sparse + GraphRAG + PageIndex)")
    print("="*80 + "\n")

    BASE_VAULT_PATH.mkdir(parents=True, exist_ok=True)
    log_message("Starting repository download process...", "INFO")

    log_message("[1/8] Checking git installation...", "INFO")
    if not check_git_installed():
        log_message("    ❌ Git is not installed. Please install git and try again.", "ERROR")
        return
    log_message("    ✓ Git is installed\n", "SUCCESS")

    log_message("[2/8] Verifying security tools...", "INFO")
    tool_status = verify_security_tools()
    if all(not v for v in tool_status.values()):
        log_message("    ⚠️  No security tools available - repos will not be scanned", "WARNING")
        response = input("Continue without security scanning? (y/N): ")
        if response.lower() != 'y':
            return
    log_message("")

    log_message("[2.5/8] Installing missing optional tools...", "INFO")
    install_missing_tools(tool_status)
    log_message("")

    log_message("[3/8] Creating directory structure...", "INFO")
    create_directory_structure()
    log_message("")

    log_message("[4/8] Cloning Vault 3 repositories...", "INFO")
    log_message(f"    Total repositories: {len(VAULT_3_REPOS)}\n", "INFO")

    vault3_success = 0
    vault3_fail = 0
    vault3_metadata = []

    for i, (repo_url, destination) in enumerate(VAULT_3_REPOS.items(), 1):
        log_message(f"  [{i}/{len(VAULT_3_REPOS)}] Processing...", "INFO")
        success, message, duration = clone_repository(repo_url, destination)
        if success:
            vault3_success += 1
            repo_path = BASE_VAULT_PATH / destination
            category = destination.split('/')[1]
            metadata = generate_metadata(repo_path, repo_url, category, tool_status)
            vault3_metadata.append(metadata)
            log_message(f"    ✓ {message} ({duration:.1f}s)", "SUCCESS")
        else:
            vault3_fail += 1
            log_message(f"    ⚠ {message}", "WARNING")

    log_message(f"\nVault 3: {vault3_success} successful, {vault3_fail} failed\n", "INFO")

    log_message("[5/8] Cloning Vault 1 documentation repositories...", "INFO")
    log_message(f"    Total documentation repos: {len(VAULT_1_DOCS)}\n", "INFO")

    vault1_success = 0
    vault1_fail = 0

    for repo_url, destination in VAULT_1_DOCS.items():
        success, message, duration = clone_repository(repo_url, destination, depth=1)
        if success:
            vault1_success += 1
            log_message(f"    ✓ {message} ({duration:.1f}s)", "SUCCESS")
        else:
            vault1_fail += 1
            log_message(f"    ⚠ {message}", "WARNING")

    log_message(f"\nVault 1 Docs: {vault1_success} successful, {vault1_fail} failed\n", "INFO")

    log_message("[6/8] Generating validation and metadata reports...", "INFO")
    generate_reports(vault3_metadata)
    log_message("")

    log_message("[7/8] Generating GraphRAG configuration...", "INFO")
    generate_graphrag_config(vault3_metadata)
    log_message("")

    print_summary(vault3_success, vault3_fail, vault1_success, vault1_fail, vault3_metadata)
    log_message("\n✅ Process complete! Review the reports before using in production.", "SUCCESS")

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