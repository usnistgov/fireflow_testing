import os
from pathlib import Path
from typing import Any, assert_never
import requests
from shutil import rmtree, copyfileobj
import zipfile
from common.config import FCSConfig, PlainUrl, DryadUrl


def main(smk: Any) -> None:
    conf: FCSConfig = smk.config

    id = smk.wildcards["id"]

    downloaded_list = Path(smk.output[0])
    downloaded_dir = downloaded_list.parent

    # ensure the target is totally empty before doing anything
    rmtree(downloaded_dir)

    archive_src = conf.get_archive_url(id)
    archive_dst = downloaded_list.parent / "downloaded.archive"
    archive_dst.parent.mkdir(parents=True)

    # create request depending on where the archive is
    if isinstance(archive_src, PlainUrl):
        archive_req = requests.get(archive_src.plain, stream=True)
    elif isinstance(archive_src, DryadUrl):
        token = os.getenv("DRYAD_TOKEN")
        assert token is not None, "Dryad token not provided"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        dryad_id = archive_src.dryad_file_id
        dryad_url = f"https://datadryad.org/api/v2/files/{dryad_id}/download"
        archive_req = requests.get(dryad_url, headers=headers, stream=True)
    else:
        assert_never(archive_src)

    # download the archive using "curl"
    with archive_req as r:
        r.raise_for_status()
        with open(archive_dst, "wb") as f:
            for c in r.iter_content(chunk_size=8192):
                if c:
                    f.write(c)

    # pull all targets out of the archive
    target_pairs = [
        (target, downloaded_dir / target) for target in conf.get_zip_paths(id)
    ]

    with zipfile.ZipFile(archive_dst, "r") as archive_f:
        for target_src, target_dst in target_pairs:
            target_dst.parent.mkdir(parents=True, exist_ok=True)
            with (
                archive_f.open(str(target_src), "r") as target_src_f,
                open(target_dst, "wb") as target_dst_f,
            ):
                copyfileobj(target_src_f, target_dst_f)

    # write targets to list
    with open(downloaded_list, "w") as f:
        for _, target_dst in target_pairs:
            f.write(str(target_dst) + "\n")

    # remove the archive file since we extracted all we care about
    os.remove(archive_dst)


main(snakemake)  # type: ignore
