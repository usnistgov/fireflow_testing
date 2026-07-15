from pathlib import Path
from itertools import dropwhile, groupby
from enum import Enum
from pydantic import BaseModel as BaseModel_, field_validator
from typing import TypeAlias, NewType, Literal, Any
from pyreflow.pydantic import PyreflowReadStdDatasetConfig

MachineName = NewType("MachineName", str)


class MachineType(Enum):
    CONVENTIONAL = "conventional"
    IMAGING = "imaging"
    SPECTRAL = "spectral"
    SPECTRAL_IMAGING = "spectral_imaging"
    CYTOF = "cytof"


class VendorId(Enum):
    APOGEE = "ApogeeFlow"
    AGILENT = "Agilent Technologies"
    BD = "BD Biosciences"
    COULTER = "Beckman Coulter"
    BIORAD = "Bio-Rad"
    CYTEK = "Cytek Biosciences"
    MILTENYI = "Miltenyi Biotec"
    SONY = "Sony Biotechnology"
    THERMO = "Thermo Fisher Scientific"
    SBT = "Standard Biotools"
    STRAT = "Stratedigm"
    SYSMEX = "Sysmex-Partec"
    VERITY = "Verity Software House"


class MachineId(Enum):
    APO_A60MICRO = "apo_a60micro"
    AGILENT_NOVOCYTE = "agilent_novocyte"
    BD_ACCURI_C6 = "bd_accuri_c6"
    BD_DISC_A8 = "bd_disc_a8"
    BD_DISC_S8 = "bd_disc_s8"
    BD_ARIA = "bd_aria"
    BD_ARIA2 = "bd_aria2"
    BD_ARIA3 = "bd_aria3"
    BD_FUSION = "bd_fusion"
    BD_CANTO = "bd_canto"
    BD_CANTO2 = "bd_canto2"
    BD_CELESTA = "bd_celesta"
    BD_FACSCALIBUR = "bd_facscalibur"
    BD_FACSCAN = "bd_facscan"
    BD_FACSVERSE = "bd_facsverse"
    BD_FORTESSA = "bd_fortessa"
    BD_FORTESSA_X20 = "bd_fortessa_x20"
    BD_INFLUX = "bd_influx"
    BD_LSR2 = "bd_lsr2"
    BD_LYRIC = "bd_lyric"
    BD_SYMPH_A5 = "bd_symph_a5"
    BC_ASTRIOS = "bc_astrios"
    BC_CYAN = "bc_cyan"
    BC_CYTOFLEX = "bc_cytoflex"
    BC_FC500 = "bc_fc500"
    BC_GALLIOS = "bc_gallios"
    BC_NAVIOS = "bc_navios"
    BC_SYSTEM2 = "bc_system2"
    BC_XDP = "bc_xdp"
    BR_ZE5 = "br_ze5"
    CYTEK_AURORA = "cytek_aurora"
    CYTEK_EASYCYTE = "cytek_easycyte"
    CYTEK_IMGSTR = "cytek_imgstr"
    SBT_CYTOF = "sbt_cytof"
    SBT_CYTOF2 = "sbt_cytof2"
    SBT_HELIOS = "sbt_helios"
    MILTENYI_MQA = "miltenyi_mqa"
    SONY_ECLIPSE = "sony_eclipse"
    SONY_ID7000 = "sony_id7000"
    SONY_SA3800 = "sony_sa3800"
    PARTEC_PAS = "partec_pas"
    STRAT_S1400 = "strat_s1400"
    STRAT_S1400EX = "strat_s1400ex"
    THERMO_ATTUNE = "thermo_attune"
    THERMO_ATTUNE_NXT_B = "thermo_attune_nxt_b"
    THERMO_ATTUNE_NXT_BV = "thermo_attune_nxt_bv"
    THERMO_ATTUNE_NXT_BVY = "thermo_attune_nxt_bvy"
    THERMO_ATTUNE_NXT_BRVY = "thermo_attune_nxt_brvy"
    VERITY_GEMSTONE = "verity_gemstone"


class RepoType(Enum):
    MISC = "misc_repo"
    FR = "flow_repository"
    IMMPORT = "immport"


class ArchiveType(Enum):
    ZIP = "zip"
    TAR = "tar"


class BaseModel(BaseModel_):
    class Config:
        frozen = True
        extra = "forbid"


class PlainUrl(BaseModel):
    plain: str


class DryadUrl(BaseModel):
    dryad_file_id: int


class SingleUrlSrc(BaseModel):
    url: PlainUrl | DryadUrl
    dataset_id: str
    output_path: Path
    compression: bool = False


class MultiUrlSrc(BaseModel):
    root_url: str
    dataset_id: str
    file_names: list[str]


class ArchiveSrc(BaseModel):
    archive_url: PlainUrl | DryadUrl
    dataset_id: str
    file_paths: list[Path]
    archive_type: ArchiveType = ArchiveType.ZIP


class FlowRepoSrc(BaseModel):
    fr_id: str
    file_names: list[str]


class ImmportSrc(BaseModel):
    immport_id: str
    file_names: list[str]


AnySrc: TypeAlias = FlowRepoSrc | ImmportSrc | SingleUrlSrc | MultiUrlSrc | ArchiveSrc

Strategy: TypeAlias = Literal["none", "scalpal", "sledgehammer"]


class ParseConfig(BaseModel):
    machine: MachineId | None = None
    strategy: Strategy = "scalpal"
    options: PyreflowReadStdDatasetConfig = PyreflowReadStdDatasetConfig()

    @property
    def merged_conf(self) -> PyreflowReadStdDatasetConfig:
        conf = self.strat_conf
        # only use options that were set explicitly in the config
        for k, v in self.options.model_dump(exclude_unset=True).items():
            setattr(conf, k, v)
        # TODO fix these, not clear why these will screw with the non-standard
        # keywords dicts
        setattr(conf, "promote_to_standard", [])
        setattr(conf, "rename_standard_keys", {})
        # override these to "drop" since this will make it easier to diagnose
        # which keywords were bad
        setattr(conf, "process_time_optical_keys", "drop_silent")
        setattr(conf, "process_pseudostandard", "drop_silent")
        setattr(conf, "process_hyper_par", "drop_silent")
        setattr(conf, "process_other_version", "drop_silent")
        setattr(conf, "process_extra_timestep", "drop_silent")
        setattr(conf, "process_optional_failure", "drop_silent")
        return conf

    @property
    def strat_conf(self) -> PyreflowReadStdDatasetConfig:
        if self.strategy == "scalpal":
            return PyreflowReadStdDatasetConfig().new_scalpal()
        elif self.strategy == "sledgehammer":
            return PyreflowReadStdDatasetConfig().new_sledgehammer()
        elif self.strategy == "none":
            return PyreflowReadStdDatasetConfig()
        else:
            assert False, f"invalid strategy: {self.strategy}"


class FileConfig(BaseModel):
    src: AnySrc
    parse: ParseConfig = ParseConfig()


class Machine(BaseModel):
    name: MachineName
    vendor: VendorId
    cyt_values: list[str] = []
    machine_type: MachineType = MachineType.CONVENTIONAL
    sorting: bool = False


BD_MACHINES = {
    MachineId.BD_ACCURI_C6: Machine(
        name=MachineName("Accuri C6"),
        vendor=VendorId.BD,
        cyt_values=["Accuri C6", "BD Accuri C6"],
    ),
    MachineId.BD_DISC_A8: Machine(
        name=MachineName("FACSDiscover A8"),
        vendor=VendorId.BD,
        machine_type=MachineType.SPECTRAL_IMAGING,
        cyt_values=["FACSDiscover A8"],
    ),
    MachineId.BD_DISC_S8: Machine(
        name=MachineName("FACSDiscover S8"),
        vendor=VendorId.BD,
        machine_type=MachineType.SPECTRAL_IMAGING,
        sorting=True,
        cyt_values=["FACSDiscover S8"],
    ),
    MachineId.BD_ARIA: Machine(
        name=MachineName("FACSAria"),
        vendor=VendorId.BD,
        sorting=True,
        cyt_values=["FACSAria"],
    ),
    MachineId.BD_ARIA2: Machine(
        name=MachineName("FACSAriaII"),
        vendor=VendorId.BD,
        sorting=True,
        cyt_values=["FACSAriaII"],
    ),
    MachineId.BD_ARIA3: Machine(
        name=MachineName("FACSAriaIII"),
        vendor=VendorId.BD,
        sorting=True,
        cyt_values=["FACSAriaIII"],
    ),
    MachineId.BD_FUSION: Machine(
        name=MachineName("FACSAria Fusion"),
        vendor=VendorId.BD,
        sorting=True,
        cyt_values=["FACSAriaIII Fusion (FACSAriaIII)"],
    ),
    MachineId.BD_CANTO: Machine(
        name=MachineName("FACSCanto"),
        vendor=VendorId.BD,
        cyt_values=["FACSCanto"],
    ),
    MachineId.BD_CANTO2: Machine(
        name=MachineName("FACSCantoII"),
        vendor=VendorId.BD,
        cyt_values=["FACSCantoII"],
    ),
    MachineId.BD_CELESTA: Machine(
        name=MachineName("FACSCelesta"),
        vendor=VendorId.BD,
        cyt_values=["FACSCelesta"],
    ),
    MachineId.BD_FACSCALIBUR: Machine(
        name=MachineName("FACSCalibur"),
        vendor=VendorId.BD,
        sorting=True,
        # many of these are also "Cytek DxP*" but we can't match on this because
        # FACScan and FACSort can also have these upgrades
        cyt_values=["FACSCalibur"],
    ),
    MachineId.BD_FACSCAN: Machine(
        name=MachineName("FACScan"),
        vendor=VendorId.BD,
        cyt_values=["FACScan"],
    ),
    MachineId.BD_FACSVERSE: Machine(
        name=MachineName("FACSVerse"),
        vendor=VendorId.BD,
        cyt_values=["BD FACSVerse"],
    ),
    MachineId.BD_FORTESSA: Machine(
        name=MachineName("LSRFortessa"),
        vendor=VendorId.BD,
        cyt_values=["LSRFortessa", "SORP LSRFortessa (LSRFortessa)"],
    ),
    MachineId.BD_FORTESSA_X20: Machine(
        name=MachineName("LSRFortessa X20"),
        vendor=VendorId.BD,
        cyt_values=["LSRFortessa X20 (LSRFortessa)"],
    ),
    MachineId.BD_INFLUX: Machine(
        name=MachineName("Influx"),
        vendor=VendorId.BD,
        sorting=True,
        cyt_values=["inFlux v7 Sorter", "BD Influx System (USB)"],
    ),
    MachineId.BD_LSR2: Machine(
        name=MachineName("LSRII"),
        vendor=VendorId.BD,
        cyt_values=["LSRII", "Guinevere (LSRII)"],
    ),
    MachineId.BD_LYRIC: Machine(
        name=MachineName("FACSLyric"),
        vendor=VendorId.BD,
        cyt_values=["BD FACSLyric"],
    ),
    MachineId.BD_SYMPH_A5: Machine(
        name=MachineName("FACSymphony A5"),
        vendor=VendorId.BD,
    ),
}

BC_MACHINES = {
    MachineId.BC_ASTRIOS: Machine(
        name=MachineName("MoFlo Astrios"),
        vendor=VendorId.COULTER,
        sorting=True,
        cyt_values=["MoFlo Astrios"],
    ),
    MachineId.BC_CYAN: Machine(
        name=MachineName("CyAn"),
        vendor=VendorId.COULTER,
    ),
    MachineId.BC_CYTOFLEX: Machine(
        name=MachineName("CytoFLEX"),
        vendor=VendorId.COULTER,
        cyt_values=["CytoFLEX"],
    ),
    MachineId.BC_FC500: Machine(
        name=MachineName("Cytomics FC 500"),
        vendor=VendorId.COULTER,
        cyt_values=["Cytomics FC 500"],
    ),
    MachineId.BC_GALLIOS: Machine(
        name=MachineName("Gallios"),
        vendor=VendorId.COULTER,
        cyt_values=["Gallios", "Gallios (Kaluza)"],
    ),
    MachineId.BC_NAVIOS: Machine(
        name=MachineName("Navios"),
        vendor=VendorId.COULTER,
        cyt_values=["Navios"],
    ),
    MachineId.BC_SYSTEM2: Machine(
        name=MachineName("System II"),
        vendor=VendorId.COULTER,
    ),
    MachineId.BC_XDP: Machine(
        name=MachineName("MoFlo XDP"),
        vendor=VendorId.COULTER,
        sorting=True,
        cyt_values=["MoFlo XDP"],
    ),
}

CYTEK_MACHINES = {
    MachineId.CYTEK_AURORA: Machine(
        name=MachineName("Aurora"),
        vendor=VendorId.CYTEK,
        machine_type=MachineType.SPECTRAL,
        cyt_values=["Aurora"],
    ),
    MachineId.CYTEK_EASYCYTE: Machine(
        name=MachineName("Guava easyCyte"),
        vendor=VendorId.CYTEK,
    ),
    MachineId.CYTEK_IMGSTR: Machine(
        name=MachineName("Image Stream"),
        vendor=VendorId.CYTEK,
        machine_type=MachineType.IMAGING,
        cyt_values=["Image Stream"],
    ),
}

# $CYT is misleading for this since it appears to be the software and version
SBT_MACHINES = {
    MachineId.SBT_CYTOF: Machine(
        name=MachineName("CyTOF"),
        vendor=VendorId.SBT,
        machine_type=MachineType.CYTOF,
    ),
    MachineId.SBT_CYTOF2: Machine(
        name=MachineName("CyTOF 2"),
        vendor=VendorId.SBT,
        machine_type=MachineType.CYTOF,
        cyt_values=["cytof2"],
    ),
    MachineId.SBT_HELIOS: Machine(
        name=MachineName("Helios"),
        vendor=VendorId.SBT,
        machine_type=MachineType.CYTOF,
    ),
}

SONY_MACHINES = {
    MachineId.SONY_ECLIPSE: Machine(
        name=MachineName("Eclipse Analyzer"),
        vendor=VendorId.SONY,
        cyt_values=["Eclipse Analyzer"],
    ),
    MachineId.SONY_ID7000: Machine(
        name=MachineName("ID7000"),
        vendor=VendorId.SONY,
        cyt_values=["ID7000"],
    ),
    MachineId.SONY_SA3800: Machine(
        name=MachineName("SA3800"),
        vendor=VendorId.SONY,
        cyt_values=["SA3800"],
    ),
}

THERMO_MACHINES = {
    # $CYT is misleading since it seems to reflect software and version
    MachineId.THERMO_ATTUNE: Machine(
        name=MachineName("Attune"),
        vendor=VendorId.THERMO,
    ),
    # The NxT machines can be further broken down by different laser configs,
    # which are technically different model numbers
    MachineId.THERMO_ATTUNE_NXT_B: Machine(
        name=MachineName("Attune NxT (B)"),
        vendor=VendorId.THERMO,
        cyt_values=[
            "4486515 Attune NxT Acoustic Focusing Cytometer (Lasers: BXXX)",
        ],
    ),
    MachineId.THERMO_ATTUNE_NXT_BV: Machine(
        name=MachineName("Attune NxT (BV)"),
        vendor=VendorId.THERMO,
        cyt_values=[
            "4486518 Attune NxT Acoustic Focusing Cytometer (Lasers: BYXX)",
        ],
    ),
    MachineId.THERMO_ATTUNE_NXT_BVY: Machine(
        name=MachineName("Attune NxT (BVY)"),
        vendor=VendorId.THERMO,
        cyt_values=[
            "4486520 Attune NxT Acoustic Focusing Cytometer (Lasers: BVYX)",
        ],
    ),
    MachineId.THERMO_ATTUNE_NXT_BRVY: Machine(
        name=MachineName("Attune NxT (BRVY)"),
        vendor=VendorId.THERMO,
        cyt_values=[
            "0A29009 Attune NxT Acoustic Focusing Cytometer (Lasers: BRV6Y)",
            "4486521 Attune NxT Acoustic Focusing Cytometer (Lasers: BRVY)",
        ],
    ),
}

MISC_MACHINES = {
    MachineId.APO_A60MICRO: Machine(
        name=MachineName("A60-Micro"),
        vendor=VendorId.APOGEE,
    ),
    MachineId.AGILENT_NOVOCYTE: Machine(
        name=MachineName("Novocyte"),
        vendor=VendorId.AGILENT,
        cyt_values=["NovoCyte"],
    ),
    MachineId.BR_ZE5: Machine(
        name=MachineName("ZE5"),
        vendor=VendorId.BIORAD,
        cyt_values=["YETI"],
    ),
    MachineId.MILTENYI_MQA: Machine(
        name=MachineName("MACSQuant Analyzer"),
        vendor=VendorId.MILTENYI,
    ),
    MachineId.PARTEC_PAS: Machine(
        name=MachineName("PAS"),
        vendor=VendorId.SYSMEX,
        cyt_values=["partec PAS"],
    ),
    MachineId.STRAT_S1400: Machine(
        name=MachineName("S1400"),
        vendor=VendorId.STRAT,
    ),
    MachineId.STRAT_S1400EX: Machine(
        name=MachineName("S1400EX"),
        vendor=VendorId.STRAT,
        cyt_values=["S1400EX"],
    ),
    MachineId.VERITY_GEMSTONE: Machine(
        name=MachineName("GemStone (software only)"),
        vendor=VendorId.VERITY,
    ),
}

ALL_MACHINES = {
    **BD_MACHINES,
    **BC_MACHINES,
    **CYTEK_MACHINES,
    **SBT_MACHINES,
    **SONY_MACHINES,
    **THERMO_MACHINES,
    **MISC_MACHINES,
}

all_cyt_values = [c for m in ALL_MACHINES.values() for c in m.cyt_values]
assert len(all_cyt_values) == len(set(all_cyt_values)), "not all $CYT values are unique"


class FCSConfig(BaseModel):
    test_files: list[FileConfig]

    @field_validator("test_files", mode="after")
    @classmethod
    def unique_dataset_ids(cls, value: list[FileConfig]) -> list[FileConfig]:
        ds = [
            c.src.dataset_id
            for c in value
            if isinstance(c.src, ArchiveSrc | SingleUrlSrc | MultiUrlSrc)
        ]
        ds.sort()
        dupped = [k for k, g in groupby(ds) if len(list(g)) > 1]
        assert len(dupped) == 0, f"all dataset ids must be unique, got {dupped}"
        return value

    def get_machine(self, cyt: str | None, i: MachineId | None) -> MachineId | None:
        if i is not None:
            return i
        elif cyt is not None:
            if cyt == "":
                return i
            else:
                return next(
                    (mi for mi, m in ALL_MACHINES.items() if cyt in m.cyt_values),
                    None,
                )
        else:
            return None

    def get_immport_src(self, repo_id: str) -> ImmportSrc:
        ret = next(
            (
                c.src
                for c in self.test_files
                if isinstance(c.src, ImmportSrc) and repo_id == c.src.immport_id
            ),
            None,
        )
        assert ret is not None, f"could not find immport src for {repo_id}"
        return ret

    def get_url_src(self, repo_id: str) -> SingleUrlSrc | MultiUrlSrc | ArchiveSrc:
        ret = next(
            (
                c.src
                for c in self.test_files
                if isinstance(c.src, ArchiveSrc | SingleUrlSrc | MultiUrlSrc)
                and repo_id == c.src.dataset_id
            ),
            None,
        )
        assert ret is not None, f"could not find URL src for {repo_id}"
        return ret

    def get_misc_dataset_ids(self) -> list[str]:
        return [
            c.src.dataset_id
            for c in self.test_files
            if isinstance(c.src, ArchiveSrc | SingleUrlSrc | MultiUrlSrc)
        ]

    def find_file_options(self, path: Path) -> tuple[ParseConfig, RepoType, str, str]:
        ps = dropwhile(lambda n: n != "resources", path.parts)
        next(ps)
        repo_type = RepoType(next(ps))
        repo_id = next(ps)
        file_name = "/".join(ps)
        return (
            self.find_options(repo_type, repo_id, file_name),
            repo_type,
            repo_id,
            file_name,
        )

    def find_options(
        self,
        repo_type: RepoType,
        repo_id: str,
        file_name: str,
    ) -> ParseConfig:
        def file_names_and_id(src: AnySrc) -> tuple[str, list[str]] | None:
            if repo_type is RepoType.MISC and isinstance(src, ArchiveSrc):
                return (src.dataset_id, list(map(str, src.file_paths)))
            elif repo_type is RepoType.MISC and isinstance(src, MultiUrlSrc):
                return (src.dataset_id, list(src.file_names))
            elif repo_type is RepoType.MISC and isinstance(src, SingleUrlSrc):
                return (src.dataset_id, [str(src.output_path)])
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
                and any(map(lambda x: x.endswith(file_name), res[1]))
            ),
            None,
        )
        assert ret is not None, (
            f"could not find config for {file_name} and {repo_id} which is a {repo_type}"
        )
        return ret.parse

    # hack to make rmd scripts work with this (note this will totally kill
    # the config as it passes into an rmd script)
    def items(self) -> Any:
        return {}.items()
