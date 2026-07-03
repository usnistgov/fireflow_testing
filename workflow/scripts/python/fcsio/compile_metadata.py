import re
import csv
from io import TextIOWrapper
import warnings
import pyreflow as pf
import pyreflow.typing as pft
from typing import Any, NamedTuple, assert_never, Literal, TypeAlias
from pathlib import Path
from datetime import date, time, datetime
from common.functional import key_maybe, fmap_maybe, maybe, esc
from common.config import (
    FCSConfig,
    RepoType,
    Machine,
    ALL_MACHINES,
    VendorId,
    MachineId,
    ParseConfig,
)

SaneDatatype: TypeAlias = Literal["uint", "float", "ascii"]


class FileMetadata(NamedTuple):
    filepath: Path
    repo: RepoType
    repo_id: str
    file_name: str
    conf: ParseConfig


class MatrixSchemaMetadata(NamedTuple):
    byteord: pft.ByteOrd
    datatype: SaneDatatype
    byte_width: int
    ranges: list[int | float]


class MeasMetadata(NamedTuple):
    shortname: str | None
    scale_gain: float | None
    scale_offset: float | None
    is_optical: bool
    wavelengths: list[float]
    bin: int | None
    size: int | None
    filter: str | None
    power: float | None
    detector_type: str | None
    percent_emitted: float | None
    detector_voltage: float | None
    longname: str | None
    calibration_slope: float | None
    calibration_intercept: float | None
    calibration_unit: str | None
    display_type: str | None
    display_n0: float | None
    display_n1: float | None
    analyte: str | None
    feature: str | None
    tag: str | None
    meas_type: str | None
    detector_name: str | None


class DatasetMetadata(NamedTuple):
    filepath: Path
    # the index of the dataset in the FCS file (almost always 0)
    dataset_index: int
    version: str
    # not keywords, but good to know if available
    vendor: str
    machine: Machine | None
    software: str | None
    # machine-specific keywords
    cyt: str | None
    cytsn: str | None
    # time and date keywords
    date: date | None
    btim: time | None
    etim: time | None
    begindatetime: datetime | None
    enddatetime: datetime | None
    # other keywords
    mode: str | None
    last_modifier: str | None
    last_modified: datetime | None
    originality: str | None
    plateid: str | None
    platename: str | None
    wellid: str | None
    vol: float | None
    carrierid: str | None
    carriertype: str | None
    locationid: str | None
    unstainedinfo: str | None
    flowrate: str | None
    abrt: int | None
    com: str | None
    cells: str | None
    exp: str | None
    fil: str | None
    inst: str | None
    lost: int | None
    op: str | None
    proj: str | None
    smno: str | None
    src: str | None
    sys: str | None
    gating: str | None
    timestep: float | None
    # data schema keywords
    schema: (
        pf.MixedDataSchema
        | pf.VariableUintDataSchema
        | pf.FixedAsciiDataSchema
        | pf.DelimAsciiDataSchema
        | MatrixSchemaMetadata
    )
    # this needs to be split into two components
    trigger_name: str | None
    trigger_value: float | None
    # non-scaler stuff
    unstainedcenters: dict[str, float]
    gated_meas: list[pf.GatedMeasurement]
    nonstd: dict[str, str]
    meas: list[MeasMetadata]
    spill_or_comp_present: bool


# Get the "software version" using some messy heuristics
def get_software_string(
    core: pft.AnyCoreTEXT,
    vendorid: VendorId | None,
    machineid: MachineId | None,
) -> str | None:
    # BD and Cytek store their software in the "CREATOR" keyword
    if vendorid in [VendorId.BD, VendorId.CYTEK]:
        return key_maybe(core.nonstandard_keywords, "CREATOR")
    # Agilent stores their software in the "#NCCreator" keyword
    elif vendorid in [VendorId.AGILENT]:
        return key_maybe(core.nonstandard_keywords, "#NCCreator")
    # Thermo stores the software string in $CYT (and the cytometer name is
    # supposedly implied)
    elif machineid is MachineId.THERMO_ATTUNE:
        return core.cyt
    # A few random machines store software in $SYS as "X" in an "X / Y" pattern
    elif machineid in [MachineId.BC_CYAN, MachineId.BC_XDP, MachineId.BC_ASTRIOS]:
        return fmap_maybe(lambda sys: sys.split(" / ")[0], core.sys)
    # The FC500 stores software in $SYS
    elif machineid is MachineId.BC_FC500:
        return core.sys
    # Beckman (with the exception of other machines above) generally stores
    # their software in "SWVER"
    elif vendorid in [VendorId.COULTER]:
        return key_maybe(core.nonstandard_keywords, "SWVER")
    # Stratedigm stores software in $SOFTWARE (makes sense)
    elif vendorid is VendorId.STRAT:
        return key_maybe(core.nonstandard_keywords, "SOFTWARE")
    # Cytof machines store their software in $CYT...sometimes
    elif vendorid in [VendorId.SBT]:
        if (
            core.cyt is not None
            and re.search("[0-9]+\\.[0-9]+\\.[0-9]+", core.cyt) is not None
        ):
            return core.cyt
        else:
            return None
    else:
        return None


def read_file(m: FileMetadata, fcs_conf: FCSConfig) -> list[DatasetMetadata]:
    parse = m.conf
    conf = parse.merged_conf

    conf.allow_missing_time = "silent"

    ret = []

    try:
        out = conf.to_std_text_config().read_std_texts(m.filepath)
    except Exception as e:
        msg = f"error for input '{m.filepath}'"
        raise ExceptionGroup(msg, [e])

    for i, (core, _) in enumerate(out):
        version = core.version
        machineid: MachineId | None = fcs_conf.get_machine(core.cyt, parse.machine)
        vendorid = fmap_maybe(lambda i: ALL_MACHINES[i].vendor, machineid)
        software = get_software_string(core, vendorid, machineid)

        cytsn = None if isinstance(core, pf.CoreTEXT2_0) else core.cytsn

        last_modifier, last_modified, originality, plateid, platename, wellid, vol = (
            (
                core.last_modifier,
                core.last_modified,
                core.originality,
                core.plateid,
                core.platename,
                core.wellid,
                core.vol,
            )
            if isinstance(core, pf.CoreTEXT3_1 | pf.CoreTEXT3_2)
            else (None,) * 7
        )

        (
            begindatetime,
            enddatetime,
            carrierid,
            carriertype,
            locationid,
            unstainedinfo,
            unstainedcenters,
            flowrate,
        ) = (
            (
                core.begindatetime,
                core.enddatetime,
                core.carrierid,
                core.carriertype,
                core.locationid,
                core.unstainedinfo,
                core.unstainedcenters,
                core.flowrate,
            )
            if isinstance(core, pf.CoreTEXT3_2)
            else (None,) * 8
        )

        # TODO dump region data, do this once we find files that actually
        # use $GATING
        if isinstance(core, pf.CoreTEXT2_0):
            gated_meas, rs20, gating = core.applied_gates
        elif isinstance(core, pf.CoreTEXT3_0 | pf.CoreTEXT3_1):
            gated_meas, rs30, gating = core.applied_gates
        elif isinstance(core, pf.CoreTEXT3_2):
            rs32, gating = core.applied_gates
            gated_meas = []
        else:
            assert_never(core)

        if isinstance(core, pf.CoreTEXT2_0):
            timestep = None
        elif isinstance(core, pf.CoreTEXT3_0):
            timestep = fmap_maybe(lambda x: x[2].timestep, core.temporal)
        elif isinstance(core, pf.CoreTEXT3_1):
            timestep = fmap_maybe(lambda x: x[2].timestep, core.temporal)
        elif isinstance(core, pf.CoreTEXT3_2):
            timestep = fmap_maybe(lambda x: x[2].timestep, core.temporal)
        else:
            assert_never(core)

        schema = core.data_schema

        schema_meta: (
            pf.MixedDataSchema
            | pf.VariableUintDataSchema
            | pf.DelimAsciiDataSchema
            | pf.FixedAsciiDataSchema
            | MatrixSchemaMetadata
        )

        if isinstance(
            schema,
            pf.MixedDataSchema
            | pf.VariableUintDataSchema
            | pf.DelimAsciiDataSchema
            | pf.FixedAsciiDataSchema,
        ):
            schema_meta = schema
        elif isinstance(schema, pf.BigLittleF32DataSchema | pf.BigLittleF64DataSchema):
            schema_meta = MatrixSchemaMetadata(
                byteord=schema.endian,
                datatype="float",
                ranges=[r for r in schema.ranges],
                byte_width=schema.byte_width,
            )
        elif isinstance(schema, pf.SingleUintDataSchema):
            schema_meta = MatrixSchemaMetadata(
                byteord=schema.endian,
                datatype="uint",
                ranges=[r for r in schema.ranges],
                byte_width=schema.byte_width,
            )
        elif isinstance(schema, pf.OrderedF32DataSchema | pf.OrderedF64DataSchema):
            schema_meta = MatrixSchemaMetadata(
                byteord=schema.byteord,
                datatype="float",
                ranges=[r for r in schema.ranges],
                byte_width=schema.byte_width,
            )
        elif isinstance(schema, pf.OrderedUintDataSchema):
            schema_meta = MatrixSchemaMetadata(
                byteord=schema.byteord,
                datatype="uint",
                ranges=[r for r in schema.ranges],
                byte_width=schema.byte_width,
            )
        else:
            assert_never(schema)

        if isinstance(core, pf.CoreTEXT2_0 | pf.CoreTEXT3_0):
            shortnames = core.all_shortnames_maybe
        elif isinstance(core, pf.CoreTEXT3_1 | pf.CoreTEXT3_2):
            shortnames = [n for n in core.all_shortnames]
        else:
            assert_never(core)

        scales: list[tuple[float | None, float | None]]
        if isinstance(core, pf.CoreTEXT2_0):
            scales = [
                (None, None)
                if s is None
                else ((1.0, None) if len(s) == 0 else (s[0], s[1]))
                for s in core.all_scales
            ]
        elif isinstance(core, pf.CoreTEXT3_0 | pf.CoreTEXT3_1 | pf.CoreTEXT3_2):
            scales = [
                (None, None)
                if s is None
                else ((s[0], s[1]) if isinstance(s, tuple) else (1.0, None))
                for s in core.all_scales
            ]
        else:
            assert_never(core)

        def make_meas_meta(
            shortname: str | None,
            scale_gain: float | None,
            scale_offset: float | None,
            rest: pft.AnyOptical | pft.AnyTemporal,
        ) -> MeasMetadata:
            is_optical = isinstance(
                rest, pf.Optical2_0 | pf.Optical3_0 | pf.Optical3_1 | pf.Optical3_2
            )

            if isinstance(rest, pf.Optical2_0 | pf.Optical3_0):
                wavelengths = [] if rest.wavelength is None else [rest.wavelength]
            elif isinstance(rest, pf.Optical3_1 | pf.Optical3_2):
                wavelengths = rest.wavelengths
            else:
                wavelengths = []

            bin, size = (
                (rest.bin, rest.size)
                if isinstance(
                    rest,
                    pf.Optical2_0
                    | pf.Optical3_0
                    | pf.Optical3_1
                    | pf.Temporal2_0
                    | pf.Temporal3_0
                    | pf.Temporal3_1,
                )
                else (None, None)
            )

            filter, power, detector_type, percent_emitted, detector_voltage = (
                (
                    rest.filter,
                    rest.power,
                    rest.detector_type,
                    rest.percent_emitted,
                    rest.detector_voltage,
                )
                if isinstance(
                    rest, pf.Optical2_0 | pf.Optical3_0 | pf.Optical3_1 | pf.Optical3_2
                )
                else (None, None, None, None, None)
            )

            cal0, cal1, cal2 = (None, None, None)
            if isinstance(rest, pf.Optical3_1) and rest.calibration is not None:
                cal0, cal2 = rest.calibration
            elif isinstance(rest, pf.Optical3_2) and rest.calibration is not None:
                cal0, cal1, cal2 = rest.calibration

            disp0, disp1, disp2 = (
                rest.display
                if (
                    isinstance(
                        rest,
                        pf.Optical3_1 | pf.Optical3_2 | pf.Temporal3_1 | pf.Temporal3_2,
                    )
                    and rest.display is not None
                )
                else (None, None, None)
            )

            analyte, feature, tag, det_name = (
                (rest.analyte, rest.feature, rest.tag, rest.detector_name)
                if isinstance(rest, pf.Optical3_2)
                else (None, None, None, None)
            )

            meas_type = (
                rest.measurement_type
                if isinstance(rest, pf.Optical3_2)
                else ("Time" if isinstance(rest, pf.Temporal3_2) else None)
            )

            return MeasMetadata(
                shortname=shortname,
                scale_gain=scale_gain,
                scale_offset=scale_offset,
                is_optical=is_optical,
                wavelengths=wavelengths,
                bin=bin,
                size=size,
                longname=rest.longname,
                filter=filter,
                power=power,
                detector_type=detector_type,
                detector_voltage=detector_voltage,
                percent_emitted=percent_emitted,
                calibration_slope=cal0,
                calibration_intercept=cal1,
                calibration_unit=cal2,
                display_type=fmap_maybe(lambda x: "lin" if x else "log", disp0),
                display_n0=disp1,
                display_n1=disp2,
                analyte=analyte,
                feature=feature,
                meas_type=meas_type,
                tag=tag,
                detector_name=det_name,
            )

        if isinstance(core, pf.CoreTEXT2_0 | pf.CoreTEXT3_0):
            spill_or_comp_present = core.comp is not None
        elif isinstance(core, pf.CoreTEXT3_1 | pf.CoreTEXT3_2):
            spill_or_comp_present = core.spillover is not None
        else:
            assert_never(core)

        meas = [
            make_meas_meta(n, s0, s1, m)
            for n, (s0, s1), m in zip(shortnames, scales, core.measurements)
        ]

        dm = DatasetMetadata(
            filepath=m.filepath,
            dataset_index=i,
            version=version,
            cyt=core.cyt,
            cytsn=cytsn,
            sys=core.sys,
            vendor=maybe("unknown", lambda i: i.value, vendorid),
            machine=fmap_maybe(lambda i: ALL_MACHINES[i], machineid),
            software=software,
            date=core.date,
            btim=core.btim,
            etim=core.etim,
            mode=core.mode,
            begindatetime=begindatetime,
            enddatetime=enddatetime,
            last_modifier=last_modifier,
            last_modified=last_modified,
            originality=originality,
            plateid=plateid,
            platename=platename,
            wellid=wellid,
            carrierid=carrierid,
            carriertype=carriertype,
            locationid=locationid,
            vol=vol,
            unstainedinfo=unstainedinfo,
            flowrate=flowrate,
            abrt=core.abrt,
            com=core.com,
            cells=core.cells,
            exp=core.exp,
            fil=core.fil,
            inst=core.inst,
            lost=core.lost,
            op=core.op,
            proj=core.proj,
            smno=core.smno,
            src=core.src,
            gating=gating,
            timestep=timestep,
            schema=schema_meta,
            trigger_name=fmap_maybe(lambda t: t[0], core.tr),
            trigger_value=fmap_maybe(lambda t: t[1], core.tr),
            unstainedcenters=maybe({}, lambda x: x, unstainedcenters),
            gated_meas=gated_meas,
            nonstd=core.nonstandard_keywords,
            spill_or_comp_present=spill_or_comp_present,
            meas=meas,
        )
        ret.append(dm)

    return ret


def dump_file_meta(f: TextIOWrapper, fs: FileMetadata | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if fs is None:
        header = ["filepath", "repo_type", "repo_id", "file_name", "file_size"]
        w.writerow(header)
    else:
        w.writerow(
            [
                fs.filepath,
                fs.repo.value,
                fs.repo_id,
                fs.file_name,
                fs.filepath.stat().st_size,
            ]
        )


def dump_machine_table(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = [
            "filepath",
            "dataset",
            "version",
            "vendor",
            "machine",
            "software",
            "machine_type",
            "sorting",
            "CYT",
            "CYTSN",
            "SYS",
        ]
        w.writerow(header)
    else:
        for d in ds:
            w.writerow(
                [
                    d.filepath,
                    d.dataset_index,
                    d.version,
                    d.vendor,
                    maybe("unknown", lambda x: x.name, d.machine),
                    d.software,
                    maybe("unknown", lambda x: x.machine_type.value, d.machine),
                    maybe("unknown", lambda x: str(x.sorting), d.machine),
                    d.cyt,
                    d.cytsn,
                    d.sys,
                ]
            )


def dump_time_keywords(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = [
            "filepath",
            "dataset",
            "DATE",
            "BTIM",
            "ETIM",
            "BEGINDATETIME",
            "ENDDATETIME",
        ]
        w.writerow(header)
    else:
        for d in ds:
            w.writerow(
                [
                    d.filepath,
                    d.dataset_index,
                    d.date,
                    d.btim,
                    d.etim,
                    d.begindatetime,
                    d.enddatetime,
                ]
            )


def dump_other_root_keywords(
    f: TextIOWrapper, ds: list[DatasetMetadata] | None
) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = [
            "filepath",
            "dataset",
            "MODE",
            "LAST_MODIFIER",
            "LAST_MODIFIED",
            "ORIGINALITY",
            "PLATEID",
            "PLATENAME",
            "WELLID",
            "VOL",
            "CARRIERID",
            "CARRIERTYPE",
            "LOCATIONID",
            "UNSTAINEDINFO",
            "FLOWRATE",
            "ABRT",
            "COM",
            "CELLS",
            "EXP",
            "FIL",
            "INST",
            "LOST",
            "OP",
            "PROJ",
            "SMNO",
            "SRC",
            "GATING",
            "TIMESTEP",
            "TR_name",
            "TR_value",
            "spill_or_comp",
        ]
        w.writerow(header)
    else:
        for d in ds:
            w.writerow(
                [
                    d.filepath,
                    d.dataset_index,
                    d.mode,
                    d.last_modifier,
                    d.last_modified,
                    d.originality,
                    d.plateid,
                    d.platename,
                    d.wellid,
                    d.vol,
                    d.carrierid,
                    d.carriertype,
                    d.locationid,
                    d.unstainedinfo,
                    d.flowrate,
                    d.abrt,
                    d.com,
                    d.cells,
                    d.exp,
                    d.fil,
                    d.inst,
                    d.lost,
                    d.op,
                    d.proj,
                    d.smno,
                    d.src,
                    d.gating,
                    d.timestep,
                    d.trigger_name,
                    d.trigger_value,
                    d.spill_or_comp_present,
                ]
            )


def dump_unstained_centers(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = ["filepath", "dataset", "key", "value"]
        w.writerow(header)
    else:
        for d in ds:
            for k, v in d.unstainedcenters.items():
                w.writerow([d.filepath, d.dataset_index, k, v])


def dump_gated_meas(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = [
            "filepath",
            "dataset",
            "index",
            "GnE",
            "GnF",
            "GnS",
            "GnP",
            "GnR",
            "GnN",
            "GnT",
            "GnV",
        ]
        w.writerow(header)
    else:
        for d in ds:
            for i, m in enumerate(d.gated_meas):
                w.writerow(
                    [
                        d.filepath,
                        d.dataset_index,
                        m.scale,
                        m.filter,
                        m.longname,
                        m.percent_emitted,
                        m.range,
                        m.shortname,
                        m.detector_type,
                        m.detector_voltage,
                    ]
                )


def dump_nonstd(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = ["filepath", "dataset", "key", "value"]
        w.writerow(header)
    else:
        for d in ds:
            for k, v in d.nonstd.items():
                w.writerow([d.filepath, d.dataset_index, esc(k), esc(v)])


def dump_mixed_schema(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = ["filepath", "dataset", "meas_index", "datatype"]
        w.writerow(header)
    else:
        for d in ds:
            if isinstance(d.schema, pf.MixedDataSchema):
                for i, (t, _) in enumerate(d.schema.typed_ranges):
                    w.writerow([d.filepath, d.dataset_index, i, t])


def dump_var_uint_schema(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = ["filepath", "dataset", "meas_index", "datatype"]
        w.writerow(header)
    else:
        for d in ds:
            if isinstance(d.schema, pf.VariableUintDataSchema):
                for i, (t, _) in enumerate(d.schema.ranges):
                    w.writerow([d.filepath, d.dataset_index, i, t])


def dump_ascii_schema(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = ["filepath", "dataset", "is_delim"]
        w.writerow(header)
    else:
        for d in ds:
            s = d.schema
            if isinstance(s, pf.FixedAsciiDataSchema):
                w.writerow([d.filepath, d.dataset_index, False])
            elif isinstance(s, pf.DelimAsciiDataSchema):
                w.writerow([d.filepath, d.dataset_index, True])


def dump_matrix_schema(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = ["filepath", "dataset", "datatype", "byte_width"]
        w.writerow(header)
    else:
        for d in ds:
            s = d.schema
            if isinstance(s, MatrixSchemaMetadata):
                w.writerow([d.filepath, d.dataset_index, s.datatype, s.byte_width])


def dump_ranges(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = ["filepath", "dataset", "meas_index", "range"]
        w.writerow(header)
    else:
        for d in ds:
            s = d.schema
            if isinstance(s, pf.MixedDataSchema):
                for i, (_, r) in enumerate(s.typed_ranges):
                    w.writerow([d.filepath, d.dataset_index, i, r])
            elif isinstance(s, pf.VariableUintDataSchema):
                for i, (_, r) in enumerate(s.ranges):
                    w.writerow([d.filepath, d.dataset_index, i, r])
            elif isinstance(
                s,
                pf.DelimAsciiDataSchema
                | pf.FixedAsciiDataSchema
                | MatrixSchemaMetadata,
            ):
                for i, r in enumerate(s.ranges):
                    w.writerow([d.filepath, d.dataset_index, i, r])
            else:
                assert_never(s)


def dump_byteord(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = ["filepath", "dataset", "byteord"]
        w.writerow(header)
    else:
        for d in ds:
            s = d.schema
            if isinstance(s, pf.MixedDataSchema):
                w.writerow([d.filepath, d.dataset_index, s.endian])
            elif isinstance(s, pf.VariableUintDataSchema):
                w.writerow([d.filepath, d.dataset_index, s.endian])
            elif isinstance(s, pf.DelimAsciiDataSchema | pf.FixedAsciiDataSchema):
                w.writerow([d.filepath, d.dataset_index, "none"])
            elif isinstance(
                s,
                MatrixSchemaMetadata,
            ):
                b = (
                    ",".join(map(str, s.byteord))
                    if isinstance(s.byteord, list)
                    else s.byteord
                )
                w.writerow([d.filepath, d.dataset_index, b])
            else:
                assert_never(s)


def dump_meas_keywords(f: TextIOWrapper, ds: list[DatasetMetadata] | None) -> None:
    w = csv.writer(f, delimiter="\t")
    if ds is None:
        header = [
            "filepath",
            "dataset",
            "meas_index",
            "is_optical",
            "PnN",
            "PnE_0",
            "PnE_1",
            "PnL",
            "PKn",
            "PKNn",
            "PnF",
            "PnO",
            "PnT",
            "PnE",
            "PnV",
            "PnS",
            "PnCALIBRATION_slope",
            "PnCALIBRATION_intercept",
            "PnCALIBRATION_unit",
            "PnD_type",
            "PnD_n0",
            "PnD_n1",
            "PnANALYTE",
            "PnFEATURE",
            "PnTAG",
            "PnTYPE",
            "PnDET",
        ]
        w.writerow(header)
    else:
        for d in ds:
            for i, m in enumerate(d.meas):
                w.writerow(
                    [
                        d.filepath,
                        d.dataset_index,
                        i,
                        m.is_optical,
                        m.shortname,
                        m.scale_gain,
                        m.scale_offset,
                        ",".join(map(str, m.wavelengths)),
                        m.bin,
                        m.size,
                        m.filter,
                        m.power,
                        m.detector_type,
                        m.percent_emitted,
                        m.detector_voltage,
                        m.longname,
                        m.calibration_slope,
                        m.calibration_intercept,
                        m.calibration_unit,
                        m.display_type,
                        m.display_n0,
                        m.display_n1,
                        m.analyte,
                        m.feature,
                        m.tag,
                        m.meas_type,
                        m.detector_name,
                    ]
                )


def main(smk: Any) -> None:
    warnings.simplefilter("ignore")
    fcs_conf: FCSConfig = smk.config

    with open(smk.input[0], "r") as f:
        src_paths = [
            FileMetadata(
                filepath=(p := Path(fcs_path.rstrip())),
                repo=(out := fcs_conf.find_file_options(p))[1],
                repo_id=out[2],
                file_name=out[3],
                conf=out[0],
            )
            for fcs_path in f
        ]

    with (
        open(smk.output["file_paths"], "w") as file_paths,
        open(smk.output["machine_table"], "w") as machine_table,
        open(smk.output["time_keywords"], "w") as time_keywords,
        open(smk.output["other_root_keywords"], "w") as other_root_keywords,
        open(smk.output["unstained_centers"], "w") as unstained_centers,
        open(smk.output["gated_meas"], "w") as gated_meas,
        open(smk.output["nonstd"], "w") as nonstd,
        open(smk.output["mixed_schema"], "w") as mixed_schema,
        open(smk.output["var_uint_schema"], "w") as var_uint_schema,
        open(smk.output["ascii_schema"], "w") as ascii_schema,
        open(smk.output["matrix_schema"], "w") as matrix_schema,
        open(smk.output["ranges"], "w") as ranges,
        open(smk.output["byteord"], "w") as byteord,
        open(smk.output["meas_keywords"], "w") as meas_keywords,
    ):
        # write header first
        dump_file_meta(file_paths, None)
        dump_machine_table(machine_table, None)
        dump_time_keywords(time_keywords, None)
        dump_other_root_keywords(other_root_keywords, None)
        dump_unstained_centers(unstained_centers, None)
        dump_gated_meas(gated_meas, None)
        dump_nonstd(nonstd, None)
        dump_mixed_schema(mixed_schema, None)
        dump_var_uint_schema(var_uint_schema, None)
        dump_ascii_schema(ascii_schema, None)
        dump_matrix_schema(matrix_schema, None)
        dump_ranges(ranges, None)
        dump_byteord(byteord, None)
        dump_meas_keywords(meas_keywords, None)

        for file_meta in src_paths:
            dataset_meta = read_file(file_meta, smk.config)
            dump_file_meta(file_paths, file_meta)
            dump_machine_table(machine_table, dataset_meta)
            dump_time_keywords(time_keywords, dataset_meta)
            dump_other_root_keywords(other_root_keywords, dataset_meta)
            dump_unstained_centers(unstained_centers, dataset_meta)
            dump_gated_meas(gated_meas, dataset_meta)
            dump_nonstd(nonstd, dataset_meta)
            dump_mixed_schema(mixed_schema, dataset_meta)
            dump_var_uint_schema(var_uint_schema, dataset_meta)
            dump_ascii_schema(ascii_schema, dataset_meta)
            dump_matrix_schema(matrix_schema, dataset_meta)
            dump_ranges(ranges, dataset_meta)
            dump_byteord(byteord, dataset_meta)
            dump_meas_keywords(meas_keywords, dataset_meta)


main(snakemake)  # type: ignore
