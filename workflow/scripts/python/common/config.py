from pydantic import BaseModel as BaseModel_
from typing import TypeAlias
from pyreflow.pydantic import PyreflowReadStdDatasetConfig


class BaseModel(BaseModel_):
    class Config:
        frozen = True
        extra = "forbid"


class FlowRepoSrc(BaseModel):
    fr_id: str
    file_names: list[str]


class ImmportSrc(BaseModel):
    immport_id: str
    file_names: list[str]


AnySrc: TypeAlias = FlowRepoSrc | ImmportSrc


class FileConfig(BaseModel):
    src: AnySrc
    options: PyreflowReadStdDatasetConfig


class FCSConfig(BaseModel):
    test_files: list[FileConfig]
