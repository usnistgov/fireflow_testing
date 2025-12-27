import requests
import os
import platform
import subprocess as sp
import tempfile
from itertools import groupby
from pathlib import Path
from typing import Any, Iterator, Generator, TypeAlias, Iterable

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


def filter_src_paths(ps: list[Path]) -> list[Path]:
    """Return three files for each study for cytof, controls, and other samples."""
    # ASSUME list is already sorted by study
    CTRL = "Flow_cytometry_compensation_or_control"
    CYTOF = "CyTOF_result"
    SAMPLE = "Flow_cytometry_result"

    def go(xs: Iterator[Path]) -> Generator[Path]:
        nsample = 0
        ncytof = 0
        nctrl = 0
        for x in xs:
            category = x.parts[2]
            if category == CTRL:
                if nctrl < 3:
                    nctrl = nctrl + 1
                    yield x
            elif category == CYTOF:
                if ncytof < 3:
                    ncytof = ncytof + 1
                    yield x
            elif category == SAMPLE:
                if nsample < 3:
                    nsample = nsample + 1
                    yield x
            elif nsample < 3:
                nsample = nsample + 1
                yield x

    return [x for _, g in groupby(ps, key=lambda p: p.parts[0]) for x in go(g)]


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

    We can do this with only a few aspera sessions which is likely the fastest
    way to do this, and we can tell aspera to check which files we already have
    (kinda like rsync). In case all files are already download, this session
    should only last 1-2 seconds. The only limitation is that we need to keep
    the file pair list under 24 KB

    """

    Pair: TypeAlias = tuple[Path, Path]
    pairs = [(src, Path(src.parts[0]) / src.name) for src in file_paths]

    def split_pairs(_pairs: list[Pair]) -> list[list[Pair]]:
        acc: list[list[Pair]] = []
        LIMIT = 24000
        k = LIMIT  # prime the loop
        for x, y in _pairs:
            z = len(str(x)) + len(str(y)) + 2
            if k + z < LIMIT:
                k = k + z
                acc[-1].append((x, y))
            else:
                k = z
                acc.append([(x, y)])
        return acc

    def run_ascp(_pairs: Iterable[Pair]) -> None:
        aspera_token = get_aspera_token(immport_token, [p[0] for p in _pairs])
        with tempfile.NamedTemporaryFile(mode="w", delete_on_close=False) as tf:
            for src, dest in _pairs:
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

    for xs in split_pairs(pairs):
        run_ascp(xs)

    return [out_dir / p[1] for p in pairs]


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

    src_paths = filter_src_paths(src_paths)

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
