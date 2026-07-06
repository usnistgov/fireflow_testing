import os
import tarfile
from urllib.parse import urljoin
from pathlib import Path
from typing import Any, assert_never
import requests as req
from shutil import rmtree, copyfileobj
import zipfile
from common.config import (
    FCSConfig,
    PlainUrl,
    DryadUrl,
    ArchiveSrc,
    MultiUrlSrc,
    SingleUrlSrc,
    ArchiveType,
)


# download something depending on what kind of url it is
def make_url_request(url: DryadUrl | PlainUrl) -> req.Response:
    if isinstance(url, PlainUrl):
        return req.get(url.plain, stream=True)
    elif isinstance(url, DryadUrl):
        token = os.getenv("DRYAD_TOKEN")
        assert token is not None, "Dryad token not provided"
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
        }
        dryad_id = url.dryad_file_id
        dryad_url = f"https://datadryad.org/api/v2/files/{dryad_id}/download"
        return req.get(dryad_url, headers=headers, stream=True)
    else:
        assert_never(url)


def download_single(smk: Any, src: SingleUrlSrc, downloaded_list: Path) -> None:
    target = downloaded_list.parent / src.output_path

    resp = make_url_request(src.url)
    if src.compression:
        # TODO this only supports *.tar.gz compression. It should also support
        # just plain *.gz and friends, but we have not encountered these yet
        with tarfile.open(fileobj=resp.raw, mode="r:*") as tar_f:
            # Iterate through archive until we find a file. There will be
            # multiple members if the file is in a subdirectory relative to the
            # tarball root
            found_file = False
            for member in tar_f:
                if not member.isfile():
                    continue
                else:
                    assert not found_file, "multiple FCS fils in this archive"
                    member_f = tar_f.extractfile(member)
                    assert member_f is not None
                    with open(target, "wb") as f:
                        copyfileobj(member_f, f)
                    found_file = True
    else:
        # just stream the url to a file (like curl url > blablabla)
        with resp as r:
            r.raise_for_status()
            with open(target, "wb") as f:
                for c in r.iter_content(chunk_size=8192):
                    if c:
                        f.write(c)

    # write target to list
    with open(downloaded_list, "w") as f:
        f.write(str(target) + "\n")


def download_multi(smk: Any, src: MultiUrlSrc, downloaded_list: Path) -> None:
    downloaded_dir = downloaded_list.parent

    # ensure the target is totally empty before doing anything
    rmtree(downloaded_dir)
    downloaded_dir.mkdir(parents=True, exist_ok=True)

    # pull all targets out of the archive
    target_pairs = [(target, downloaded_dir / target) for target in src.file_names]

    for target_src, target_dst in target_pairs:
        full_url = urljoin(src.root_url, target_src)
        with req.get(full_url, stream=True) as r:
            r.raise_for_status()
            with open(target_dst, "wb") as f:
                for c in r.iter_content(chunk_size=8192):
                    if c:
                        f.write(c)

    # write targets to list
    with open(downloaded_list, "w") as f:
        for _, target_dst in target_pairs:
            f.write(str(target_dst) + "\n")


def download_archive(smk: Any, src: ArchiveSrc, downloaded_list: Path) -> None:
    downloaded_dir = downloaded_list.parent

    # ensure the target is totally empty before doing anything
    rmtree(downloaded_dir)

    archive_dst = downloaded_list.parent / "downloaded.archive"
    archive_dst.parent.mkdir(parents=True)

    # download the archive using "curl"
    archive_resp = make_url_request(src.archive_url)
    with archive_resp as r:
        r.raise_for_status()
        with open(archive_dst, "wb") as f:
            for c in r.iter_content(chunk_size=8192):
                if c:
                    f.write(c)

    # pull all targets out of the archive
    target_pairs = [(target, downloaded_dir / target) for target in src.file_paths]

    if src.archive_type is ArchiveType.ZIP:
        with zipfile.ZipFile(archive_dst, "r") as archive_f:
            for target_src, target_dst in target_pairs:
                target_dst.parent.mkdir(parents=True, exist_ok=True)
                with (
                    archive_f.open(str(target_src), "r") as target_src_f,
                    open(target_dst, "wb") as target_dst_f,
                ):
                    copyfileobj(target_src_f, target_dst_f)
    elif src.archive_type is ArchiveType.TAR:
        with tarfile.open(archive_dst, "r:*") as archive_f:
            for target_src, target_dst in target_pairs:
                target_dst.parent.mkdir(parents=True, exist_ok=True)
                member_f = archive_f.extractfile(str(target_src))
                assert member_f is not None, f"could not find {target_src} in archive"
                with open(target_dst, "wb") as target_dst_f:
                    copyfileobj(member_f, target_dst_f)
    else:
        assert_never(src.archive_type)

    # write targets to list
    with open(downloaded_list, "w") as f:
        for _, target_dst in target_pairs:
            f.write(str(target_dst) + "\n")

    # remove the archive file since we extracted all we care about
    os.remove(archive_dst)


def main(smk: Any) -> None:
    conf: FCSConfig = smk.config

    src = conf.get_url_src(smk.wildcards["id"])

    downloaded_list = Path(smk.output[0])

    if isinstance(src, SingleUrlSrc):
        download_single(smk, src, downloaded_list)
    elif isinstance(src, MultiUrlSrc):
        download_multi(smk, src, downloaded_list)
    elif isinstance(src, ArchiveSrc):
        download_archive(smk, src, downloaded_list)
    else:
        assert_never(src)


main(snakemake)  # type: ignore
