from urllib.parse import urljoin
from enum import Enum
from pydantic import BaseModel as BaseModel_, model_validator
from typing import TypeAlias, NewType, Self
from pyreflow.pydantic import PyreflowReadStdDatasetConfig

MachineId = NewType("MachineId", str)
VendorId = NewType("VendorId", str)

MachineName = NewType("MachineName", str)
VendorName = NewType("VendorName", str)


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


class ParseConfig(BaseModel):
    machine: MachineId | None = None
    options: PyreflowReadStdDatasetConfig


class FileConfig(BaseModel):
    src: AnySrc
    parse: ParseConfig


class Machine(BaseModel):
    name: MachineName
    vendor: VendorId
    cyt_values: list[str] = []
    sorting: bool = False
    imaging: bool = False
    spectral: bool = False


class FCSConfig(BaseModel):
    machines: dict[MachineId, Machine]
    vendors: dict[VendorId, VendorName]
    test_files: list[FileConfig]

    # TODO test that all CYT values are unique across machines

    @model_validator(mode="after")
    def vendors_match(self) -> Self:
        vs = set([x.vendor for x in self.machines.values()])
        assert vs.issubset(set(self.vendors)), "some vendor IDs are not configured"
        return self

    @model_validator(mode="after")
    def machines_match(self) -> Self:
        ms = set(
            [x.parse.machine for x in self.test_files if x.parse.machine is not None]
        )
        assert ms.issubset(set(self.machines)), "some machine IDs are not configured"
        return self

    def get_machine(self, cyt: str | None, i: MachineId | None) -> Machine | None:
        if i is not None:
            return self.machines[i]
        elif cyt is not None:
            return next(
                (m for m in self.machines.values() if cyt in m.cyt_values), None
            )
        else:
            return None

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
        self, repo_type: RepoType, file_name: str, repo_id: str
    ) -> ParseConfig:
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
        return ret.parse
