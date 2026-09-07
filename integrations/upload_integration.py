# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Upload/Import Integration to Google Security Operations (SOAR).

Creates a ZIP archive from a local integration directory (default: SecOpsToolkit)
and uploads it using the Google SecOps Integrations Import API:
https://docs.cloud.google.com/chronicle/docs/reference/rest/v1alpha/projects.locations.instances.integrations/import
"""

import argparse
import io
import json
import os
import sys
import time
import zipfile
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import google.auth
    import google.auth.transport.requests
    import google.oauth2.service_account
    import requests

    HAS_DEPS = True
except ImportError:
    HAS_DEPS = False

BASE_DIR = Path(__file__).resolve().parent
SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/chronicle",
]

# Load environment variables from .env in the integration script directory or current working directory
env_path = BASE_DIR / ".env"
if load_dotenv:
    if env_path.is_file():
        load_dotenv(dotenv_path=env_path, override=False)
    else:
        load_dotenv(override=False)
elif env_path.is_file():
    # Fallback parser if python-dotenv is not installed
    with open(env_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, val = line.split("=", 1)
                key = key.strip()
                val = val.strip().strip("'\"")
                if key and key not in os.environ:
                    os.environ[key] = val


def list_available_integrations(base_dir: Path) -> list[str]:
    """
    Scans the integrations base directory for folders containing an 'Integration-*.def' file.
    """
    integrations = []
    if not base_dir.is_dir():
        return integrations

    for entry in base_dir.iterdir():
        if (
            entry.is_dir()
            and not entry.name.startswith((".", "_", "venv"))
            and any(
                f.name.startswith("Integration-") and f.name.endswith(".def")
                for f in entry.iterdir()
                if f.is_file()
            )
        ):
            integrations.append(entry.name)
    return sorted(integrations)


def resolve_integration_dir(integration_name_or_path: str, base_dir: Path) -> Path:
    """
    Resolves the integration directory from either a name or a file system path.
    """
    candidate = Path(integration_name_or_path)
    if candidate.is_dir():
        return candidate.resolve()

    candidate_in_base = base_dir / integration_name_or_path
    if candidate_in_base.is_dir():
        return candidate_in_base.resolve()

    available = list_available_integrations(base_dir)
    available_msg = (
        f"\nAvailable integrations in {base_dir}:\n  - " + "\n  - ".join(available)
        if available
        else ""
    )
    raise FileNotFoundError(
        f"Integration directory '{integration_name_or_path}' not found.{available_msg}"
    )


def create_integration_zip(
    source_dir: Path, output_zip_path: str | None = None
) -> bytes:
    """
    Creates a ZIP archive in-memory (and optionally saves to disk) from the integration directory.
    Excludes unwanted temporary and metadata files (__pycache__, .git, .DS_Store, *.pyc).
    """
    if not source_dir.is_dir():
        raise FileNotFoundError(
            f"Integration source directory '{source_dir}' does not exist."
        )

    print(f"📦 Packaging integration files from: {source_dir}")
    zip_buffer = io.BytesIO()
    total_files = 0

    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for root, dirs, files in os.walk(source_dir):
            # Exclude unwanted directories
            dirs[:] = [
                d
                for d in dirs
                if d not in ("__pycache__", ".git", ".idea", ".pytest_cache", "venv")
            ]
            for file in sorted(files):
                if file == ".DS_Store" or file.endswith((".pyc", "~")):
                    continue
                full_path = Path(root) / file
                rel_path = full_path.relative_to(source_dir)
                zip_file.write(full_path, str(rel_path))
                total_files += 1

    zip_bytes = zip_buffer.getvalue()
    size_mb = len(zip_bytes) / (1024 * 1024)
    print(f"✅ Packaged {total_files} files into ZIP ({size_mb:.2f} MB)")

    if output_zip_path:
        with open(output_zip_path, "wb") as f:
            f.write(zip_bytes)
        print(f"💾 Saved ZIP archive to: {output_zip_path}")

    return zip_bytes


def get_auth_token(service_account_path: str | None = None) -> str:
    """
    Retrieves a valid OAuth2 Bearer token using Service Account or Application Default Credentials (ADC).
    """
    if service_account_path:
        if os.path.isfile(service_account_path):
            creds = google.oauth2.service_account.Credentials.from_service_account_file(
                service_account_path, scopes=SCOPES
            )
        else:
            try:
                info = json.loads(service_account_path)
                creds = (
                    google.oauth2.service_account.Credentials.from_service_account_info(
                        info, scopes=SCOPES
                    )
                )
            except Exception as e:
                raise ValueError(
                    f"Invalid service account file path or JSON string: {e}"
                ) from e
    else:
        creds, _ = google.auth.default(scopes=SCOPES)

    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    return creds.token


def resolve_endpoint(location: str, custom_endpoint: str | None = None) -> str:
    """
    Resolves the regional or custom API endpoint host.
    """
    if custom_endpoint:
        return (
            custom_endpoint.replace("https://", "").replace("http://", "").rstrip("/")
        )
    if location and location.lower() not in ("global", "us"):
        loc = location.lower()
        return f"{loc}-chronicle.googleapis.com"
    return "chronicle.googleapis.com"


def import_integration(
    zip_bytes: bytes,
    project_id: str,
    location: str,
    instance_id: str,
    token: str,
    staging: bool = False,
    endpoint: str | None = None,
    verify_ssl: bool = True,
) -> dict:
    """
    Uploads the integration ZIP file to Google SecOps API.
    """
    host = resolve_endpoint(location, endpoint)
    parent = f"projects/{project_id}/locations/{location}/instances/{instance_id}"
    staging_str = "true" if staging else "false"
    upload_url = f"https://{host}/upload/v1alpha/{parent}/integrations:import?uploadType=media&staging={staging_str}"

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/zip",
    }

    print("🚀 Uploading integration to Google SecOps:")
    print(f"   • Endpoint: {upload_url}")
    print(f"   • Staging Mode: {staging}")

    max_retries = 3
    retry_delay = 3
    response = None

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                upload_url, headers=headers, data=zip_bytes, verify=verify_ssl
            )
            if (
                response.status_code in (429, 500, 502, 503, 504)
                and attempt < max_retries
            ):
                print(
                    f"⚠️ Upload attempt {attempt} returned {response.status_code}. Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            response.raise_for_status()
            break
        except requests.HTTPError as err:
            if (
                attempt < max_retries
                and response is not None
                and response.status_code in (429, 500, 502, 503, 504)
            ):
                print(
                    f"⚠️ Upload attempt {attempt} failed ({err}). Retrying in {retry_delay}s..."
                )
                time.sleep(retry_delay)
                retry_delay *= 2
                continue
            print(
                f"\n❌ Import failed with status code {response.status_code if response else 'Unknown'}:",
                file=sys.stderr,
            )
            try:
                error_data = response.json()
                print(json.dumps(error_data, indent=2), file=sys.stderr)
            except Exception:  # noqa: BLE001
                if response is not None:
                    print(response.text, file=sys.stderr)
            raise

    result = response.json() if response else {}
    return result


def main():
    default_integration = os.getenv("SECOPS_INTEGRATION_NAME", "SecOpsToolkit")
    default_project = os.getenv("SECOPS_PROJECT_ID")
    default_location = os.getenv("SECOPS_LOCATION", "europe")
    default_instance = os.getenv("SECOPS_INSTANCE_ID")
    default_sa = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    default_staging = os.getenv("SECOPS_STAGING", "false").lower() in ("true", "1")

    parser = argparse.ArgumentParser(
        description="Package and import a Google SecOps SOAR integration from a local directory.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--integration",
        "-i",
        dest="integration",
        default=default_integration,
        help="Integration name or folder path (e.g. SecOpsToolkit)",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List available integrations in this repository and exit",
    )
    parser.add_argument(
        "--project",
        "-p",
        default=default_project,
        help="Google Cloud Project ID (env: SECOPS_PROJECT_ID)",
    )
    parser.add_argument(
        "--location",
        "-l",
        default=default_location,
        help="SecOps Instance Location (env: SECOPS_LOCATION)",
    )
    parser.add_argument(
        "--instance",
        "-inst",
        default=default_instance,
        help="SecOps Instance ID (env: SECOPS_INSTANCE_ID)",
    )
    parser.add_argument(
        "--endpoint",
        "-e",
        default=None,
        help="Custom SecOps API Host (default: auto-resolved based on location)",
    )
    parser.add_argument(
        "--staging",
        action="store_true",
        default=default_staging,
        help="Upload integration in staging mode (env: SECOPS_STAGING)",
    )
    parser.add_argument(
        "--service-account",
        "-s",
        default=default_sa,
        help="Path to Service Account JSON key file (env: GOOGLE_APPLICATION_CREDENTIALS, uses ADC if not set)",
    )
    parser.add_argument(
        "--save-zip",
        "-z",
        default=None,
        help="Optional path to save the generated ZIP file locally",
    )
    parser.add_argument(
        "--no-verify-ssl",
        action="store_true",
        default=False,
        help="Disable SSL verification for API requests",
    )

    args = parser.parse_args()

    if args.list:
        integrations = list_available_integrations(BASE_DIR)
        print("Available integrations in this directory:")
        for name in integrations:
            print(f"  • {name}")
        sys.exit(0)

    # Validate required parameters
    missing = []
    if not args.project:
        missing.append("--project / SECOPS_PROJECT_ID")
    if not args.location:
        missing.append("--location / SECOPS_LOCATION")
    if not args.instance:
        missing.append("--instance / SECOPS_INSTANCE_ID")

    if missing:
        parser.error(
            f"Missing required parameters: {', '.join(missing)}.\n"
            "Please provide them via command-line arguments or define them in your .env file."
        )

    # 1. Resolve integration path
    integration_dir = resolve_integration_dir(args.integration, BASE_DIR)

    # 2. Package ZIP
    zip_bytes = create_integration_zip(
        source_dir=integration_dir, output_zip_path=args.save_zip
    )

    # 3. Authenticate & Upload
    if not HAS_DEPS:
        sys.exit(
            "Missing required dependencies for upload. Please install:\n"
            "  pip install -r requirements.txt\n"
            "or:\n"
            "  pip install google-auth requests python-dotenv"
        )

    print("🔑 Authenticating with Google Cloud...")
    token = get_auth_token(args.service_account)

    # 4. Upload / Import
    result = import_integration(
        zip_bytes=zip_bytes,
        project_id=args.project,
        location=args.location,
        instance_id=args.instance,
        token=token,
        staging=args.staging,
        endpoint=args.endpoint,
        verify_ssl=not args.no_verify_ssl,
    )

    print("\n🎉 Integration imported successfully!")
    print(f"   • Integration Name:    {result.get('integration')}")
    print(f"   • Integration Version: {result.get('integrationVersion')}")
    if result.get("mediaInfo", {}).get("resourceName"):
        print(
            f"   • Resource:            {result.get('mediaInfo', {}).get('resourceName')}"
        )

    failed_deps = result.get("failedDependencies", [])
    if failed_deps:
        print("\n⚠️ Warning: Failed dependencies reported:")
        for dep in failed_deps:
            print(f"   - {dep.get('dependencyId')}: {dep.get('dependencyMessage')}")


if __name__ == "__main__":
    main()
