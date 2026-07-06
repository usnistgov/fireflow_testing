import os
from pathlib import Path
from typing import Any
import requests
from shutil import rmtree, copyfileobj
import zipfile
from common.config import FCSConfig


def main(smk: Any) -> None:
    conf: FCSConfig = smk.config

    id = smk.wildcards["id"]

    downloaded_list = Path(smk.output[0])
    downloaded_dir = downloaded_list.parent

    # ensure the target is totally empty before doing anything
    rmtree(downloaded_dir)

    # download the archive using "curl"
    archive_src = conf.get_zip_url(id)
    archive_dst = downloaded_list.parent / "downloaded.archive"
    archive_dst.parent.mkdir(parents=True)

    with requests.get(archive_src) as r:
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
