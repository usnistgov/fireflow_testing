from urllib.parse import urljoin
from enum import Enum
from pydantic import BaseModel as BaseModel_
from typing import TypeAlias
from pyreflow.pydantic import PyreflowReadStdDatasetConfig


class RepoType(Enum):
    PLAIN_URL = "plain_url"
    FR = "flow_repository"
    IMMPORT = "immport"


class BaseModel(BaseModel_):
    class Config:
        frozen = True
        extra = "forbid"


class PlainUrlSrc(BaseModel):
    url_root: str
    dataset_id: str
    filemap: dict[str, str]


class FlowRepoSrc(BaseModel):
    fr_id: str
    file_names: list[str]


class ImmportSrc(BaseModel):
    immport_id: str
    file_names: list[str]


AnySrc: TypeAlias = FlowRepoSrc | ImmportSrc | PlainUrlSrc


class FileConfig(BaseModel):
    src: AnySrc
    options: PyreflowReadStdDatasetConfig


class FCSConfig(BaseModel):
    test_files: list[FileConfig]

    def get_url(self, file_name: str, repo_id: str) -> str:
        ret = next(
            (
                urljoin(c.src.url_root, c.src.filemap[file_name])
                for c in self.test_files
                if isinstance(c.src, PlainUrlSrc)
                and repo_id == c.src.dataset_id
                and file_name in c.src.filemap
            ),
            None,
        )
        assert ret is not None, f"could not find URL for {file_name} and {repo_id}"
        return ret

    def find_file_options(
        self,
        repo_type: RepoType,
        file_name: str,
        repo_id: str,
    ) -> PyreflowReadStdDatasetConfig:
        def file_names_and_id(src: AnySrc) -> tuple[str, list[str]] | None:
            if repo_type is RepoType.PLAIN_URL and isinstance(src, PlainUrlSrc):
                return (src.dataset_id, list(src.filemap.keys()))
            elif repo_type is RepoType.IMMPORT and isinstance(src, ImmportSrc):
                return (src.immport_id, src.file_names)
            elif repo_type is RepoType.FR and isinstance(src, FlowRepoSrc):
                return (src.fr_id, src.file_names)
            else:
                return None

        ret = next(
            (
                c
                for c in self.test_files
                if (res := file_names_and_id(c.src)) is not None
                and repo_id == res[0]
                and file_name in res[1]
            ),
            None,
        )
        assert ret is not None, (
            f"could not find config for {file_name} and {repo_id} which is a {repo_type}"
        )
        return ret.options
