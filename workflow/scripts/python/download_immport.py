import requests
import os
import platform
import subprocess as sp
import tempfile
from pathlib import Path
from typing import Any

IMMPORT_URL = "https://www.immport.org"
IMMPORT_TOKEN_URL = f"{IMMPORT_URL}/auth/token"
IMMPORT_DATA_URL = f"{IMMPORT_URL}/data"

ASPERA_USERNAME = "databrowser"
ASPERA_SERVER = "aspera-immport.niaid.nih.gov"


def get_ostype() -> str:
    os_name = platform.system()
    if os_name == "Linux":
        hardware_name = platform.machine()
        if hardware_name == "x86_64":
            return "linux"
        else:
            return "linux32"
    elif os_name == "Darwin":
        return "osx"
    else:
        assert False, "Only Linux (32/64 bit) or OS-X are supported"


def get_aspera_token(immport_token: str, paths: list[Path]) -> str:
    headers = {
        "Authorization": f"bearer {immport_token}",
        "Content-Type": "application/json",
    }
    u = f"{IMMPORT_DATA_URL}/download/token"
    data = {"paths": [str(p) for p in paths]}
    results = requests.post(u, headers=headers, json=data)
    assert results is not None, "Error getting POST results for Aspera token"
    assert results.status_code == 200, f"API Status Code: {results.status_code}"
    res = results.json()
    return str(res["token"])


def download_file(
    bin_path: Path,
    pkey: Path,
    immport_token: str,
    out_dir: Path,
    file_paths: list[Path],
) -> list[Path]:
    """Download metric boatload of files using ascp and return dest paths.

    Take the list of sources and split them apart by study so we are less likely
    to have name clashes and so that we can access them individually more easily
    later. This requires the --file-pair-list option so we can manually specify
    the destination for each source.

    We can do this with one aspera session which is likely the fastest way to do
    this, and we can tell aspera to check which files we already have (kinda
    like rsync). In case all files are already download, this session should
    only last 1-2 seconds.
    """
    out_paths: list[Path] = []
    aspera_token = get_aspera_token(immport_token, file_paths)

    with tempfile.NamedTemporaryFile(mode="w", delete_on_close=False) as tf:
        for src in file_paths:
            dest = Path(src.parts[0]) / src.name
            out_paths.append(out_dir / dest)
            # weirdly, src and dest are on separate lines
            tf.write(f"{src}\n")
            tf.write(f"{dest}\n")

        tf.close()

        args: list[str] = [str(bin_path)]
        args += ["--user", ASPERA_USERNAME]
        args += ["--host", ASPERA_SERVER]
        args += ["--mode", "recv"]
        # these are ports apparently
        args += ["-O33001", "-P33001"]
        # specify private key and token
        args += ["-i", str(pkey)]
        args += ["-W", aspera_token]
        # use checksum to test if we need to redownload file
        args += ["-k", "2"]
        # preserve timestamps, don't print stuff
        args += ["-p", "-q"]
        # specify sources and destination paths
        args += [f"--file-pair-list={tf.name}"]
        # specify destination (must be last)
        args += [str(out_dir)]
        sp.run(args)

    return out_paths


def main(smk: Any) -> None:
    ostype = get_ostype()

    # this is actually the license path, so adjust to point to ascp binary
    aspera_path = Path(smk.input["aspera"])
    manifest_path = Path(smk.input["manifest"])
    fcs_list_path = Path(smk.output[0])

    aspera_cli = aspera_path.parent.parent / "bin" / ostype / "ascp"
    aspera_pkey = aspera_path.parent / "asperaweb_id_dsa.openssh"

    fcs_list_dir = fcs_list_path.parent
    immport_token = os.environ["IMMPORT_TOKEN"]

    assert len(immport_token) > 0, "IMMPORT_TOKEN is not specified"

    src_paths: list[Path] = []

    with open(manifest_path, "r") as f:
        for x in f:
            s = x.rstrip()
            if s.endswith(".fcs") and not s.startswith("#"):
                src_paths.append(Path(s))

    fcs_list_dir.mkdir(exist_ok=True, parents=True)

    dest_paths = download_file(
        aspera_cli,
        aspera_pkey,
        immport_token,
        fcs_list_dir,
        src_paths,
    )

    with open(fcs_list_path, "w") as f:
        for p in dest_paths:
            f.write(f"{p}\n")


main(snakemake)  # type: ignore
