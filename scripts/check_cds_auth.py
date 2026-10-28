"""Check the CDS API configuration without submitting a download request.

    python scripts/check_cds_auth.py

Prints what it finds, never the key itself. It makes a single authentication check, which is not a
data request, so it doesn't count toward the CDS rule on repeated invalid requests.
"""
import os

rc = os.environ.get("CDSAPI_RC", os.path.expanduser("~/.cdsapirc"))
print(f"Config file: {rc} -> {'found' if os.path.exists(rc) else 'NOT FOUND'}")
cfg = {}
if os.path.exists(rc):
    for line in open(rc):
        if ":" in line:
            k, v = line.split(":", 1)
            cfg[k.strip()] = v.strip()
    url, key = cfg.get("url", ""), cfg.get("key", "")
    print(f"  url: {url or 'MISSING'}")
    ok_url = url.rstrip("/") == "https://cds.climate.copernicus.eu/api"
    print(f"  url correct (https://cds.climate.copernicus.eu/api): {ok_url}")
    if key:
        legacy = ":" in key
        print(f"  key: present, {len(key)} characters, "
              f"{'OLD FORMAT (UID:key) - replace it with the API token from your CDS profile' if legacy else 'token format looks right'}")
    else:
        print("  key: MISSING")

overrides = [v for v in ("CDSAPI_URL", "CDSAPI_KEY", "CDSAPI_RC",
                         "ECMWF_DATASTORES_URL", "ECMWF_DATASTORES_KEY") if os.environ.get(v)]
print(f"Environment variables that override the file: {', '.join(overrides) if overrides else 'none'}")
if any(v in overrides for v in ("CDSAPI_KEY", "ECMWF_DATASTORES_KEY")):
    print("  -> a key set in the environment is used instead of ~/.cdsapirc; check or unset it")

try:
    from ecmwf.datastores import Client
    url = os.environ.get("CDSAPI_URL") or cfg.get("url")
    key = os.environ.get("CDSAPI_KEY") or cfg.get("key")
    c = Client(url=url, key=key, maximum_tries=1, retry_after=1, progress=False)
    c.check_authentication()
    print("Authentication check: OK")
except AttributeError:
    print("Authentication check: not available in this client version (the settings above are still valid to review)")
except Exception as e:
    print(f"Authentication check: FAILED -> {type(e).__name__}: {str(e).splitlines()[0][:200]}")
