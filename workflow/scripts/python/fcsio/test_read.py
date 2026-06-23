import base64
import csv
from dataclasses import dataclass
from typing import Any, Self, Literal, Iterable
from pathlib import Path
import logging
import pyreflow.api as pfa
import pyreflow.typing as pt
from itertools import chain
from pyreflow.api import fcs_write_datasets
from common.config import RepoType, FCSConfig
from common.functional import maybe, esc, fmap_maybe

logging.basicConfig(filename=snakemake.log[0], level=logging.DEBUG)  # type: ignore
logging.captureWarnings(True)


def fmt_offset_name(n: str | int) -> str:
    return f"other-{n}" if isinstance(n, int) else str(n)


def encode_bytes(obj: Any) -> str:
    if isinstance(obj, bytes):
        return "base64:" + base64.b64encode(obj).decode("ascii")
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")


def encode_or_esc(xs: str | bytes) -> str:
    return esc(xs) if isinstance(xs, str) else encode_bytes(xs)


@dataclass(frozen=True)
class WritableDiagnostic:
    path: Path
    dataset: int

    @classmethod
    def write_datasets(
        cls, p: Path, fcs_path: Path, ds: list[pfa.StdDatasetOutput]
    ) -> None:
        with open(p, "w") as f:
            w = csv.writer(f, delimiter="\t")
            h = cls.to_header()
            w.writerow(["fcs_path", "dataset", *h])
            for i, u in enumerate(ds):
                for row in cls.dataset_iter(fcs_path, i, u):
                    r = row.to_row()
                    assert len(r) == len(h), f"{h} is not same length as {r}"
                    w.writerow([row.path, row.dataset, *r])

    @classmethod
    def dataset_iter(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        raise NotImplementedError

    @classmethod
    def to_header(cls) -> list[str]:
        raise NotImplementedError

    def to_row(self) -> list[str]:
        raise NotImplementedError


@dataclass(frozen=True)
class Offset(WritableDiagnostic):
    name: str
    start: int
    end: int
    final: bool

    @classmethod
    def dataset_iter(
        cls, p: Path, i: int, u: pfa.StdDatasetOutput
    ) -> Iterable["Offset"]:
        return chain(cls._uncorrected(p, i, u), cls._final(p, i, u))

    @classmethod
    def to_header(self) -> list[str]:
        return ["name", "start", "end", "final"]

    def to_row(self) -> list[str]:
        return [
            self.name,
            str(self.start),
            str(self.end),
            str(self.final),
        ]

    @classmethod
    def _uncorrected(
        cls, p: Path, i: int, u: pfa.StdDatasetOutput
    ) -> Iterable["Offset"]:
        def go(n: str, o: tuple[int, int]) -> Offset:
            begin, end = o
            # Make second offset mean the same thing as final offsets. Original
            # offsets will be the final byte of the segment rather than the next
            # byte, which is what the final offsets use (the sane choice).
            new_end = end + 1 if begin > 0 and end > 0 else 0
            return cls._from_offset(p, i, n, (begin, new_end), False)

        h_orig = u.flat_diagnostics.header_supp.header.original_offsets
        hdr_text = go("primary_text", h_orig.text)
        hdr_analysis = go("hdr_analysis", h_orig.analysis)
        hdr_data = go("hdr_data", h_orig.data)
        hdr_other = [go(f"other-{oi}", u) for oi, u in enumerate(h_orig.others)]
        empty: list[Offset] = []
        supp_text = maybe(
            empty,
            lambda o: [go("supp_text", o)],
            u.flat_diagnostics.header_supp.supp_text.original_offsets,
        )
        ds = u.dataset.dataset_offsets
        text_data = maybe(
            empty,
            lambda o: [go("text_data", o)],
            ds.data_origin.original_offsets,
        )
        text_analysis = maybe(
            empty,
            lambda o: [go("text_analysis", o)],
            ds.analysis_origin.original_offsets,
        )
        return chain(
            [hdr_text, hdr_analysis, hdr_data],
            hdr_other,
            supp_text,
            text_data,
            text_analysis,
        )

    @classmethod
    def _final(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable["Offset"]:
        def go(n: str, o: tuple[int, int]) -> Offset:
            return Offset._from_offset(p, i, n, o, True)

        h_final = u.flat_diagnostics.header_supp.header.final_offsets
        hdr_text = go("primary_text", h_final.text)
        hdr_analysis = go("hdr_analysis", h_final.analysis)
        hdr_data = go("hdr_data", h_final.data)
        empty: list[Offset] = []
        hdr_other = maybe(
            empty,
            lambda o: [go(f"other-{u[0]}", u[1]) for u in o[0]],
            h_final.others,
        )
        supp_text = maybe(
            empty,
            lambda o: [go("supp_text", o)],
            u.flat_diagnostics.header_supp.supp_text.final_offsets,
        )
        ds = u.dataset.dataset_offsets
        text_data = (
            [go("text_data", ds.final_data_offsets)]
            if ds.data_origin.origin_type in ["mismatch_text", "empty_header"]
            else empty
        )
        text_analysis = (
            [go("text_analysis", ds.final_analysis_offsets)]
            if ds.analysis_origin.origin_type in ["mismatch_text", "empty_header"]
            else empty
        )
        return chain(
            [hdr_text, hdr_analysis, hdr_data],
            hdr_other,
            supp_text,
            text_data,
            text_analysis,
        )

    @classmethod
    def _from_offset(
        cls, path: Path, dataset: int, name: str, offset: tuple[int, int], final: bool
    ) -> Self:
        return cls(path, dataset, name, offset[0], offset[1], final)


@dataclass(frozen=True)
class Overflow(WritableDiagnostic):
    name: str
    start: int
    end: int
    overflow: int
    dataset_len: int
    is_nextdata: bool

    @classmethod
    def to_header(self) -> list[str]:
        return ["name", "start", "end", "overflow", "dataset_len", "is_nextdata"]

    def to_row(self) -> list[str]:
        return [
            self.name,
            str(self.start),
            str(self.end),
            str(self.overflow),
            str(self.dataset_len),
            str(self.is_nextdata),
        ]

    @classmethod
    def dataset_iter(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        header_overflows = (
            cls._from_overflow(p, i, o) for o in u.flat_diagnostics.header_overflows
        )
        empty: list[Self] = []
        supp_overflows = maybe(
            empty,
            lambda o: [cls._from_overflow(p, i, o)],
            u.flat_diagnostics.header_supp.supp_text.overflow,
        )
        ds = u.dataset.dataset_offsets
        data_overflows = maybe(
            empty,
            lambda o: [cls._from_overflow(p, i, o)],
            ds.data_origin.overflow,
        )
        analysis_overflows = maybe(
            empty,
            lambda o: [cls._from_overflow(p, i, o)],
            ds.analysis_origin.overflow,
        )
        return chain(
            header_overflows, supp_overflows, data_overflows, analysis_overflows
        )

    @classmethod
    def _from_overflow(
        cls,
        path: Path,
        dataset: int,
        overflow: pfa.TextOffsetsOverflow
        | pfa.SuppOffsetsOverflow
        | pfa.HeaderOffsetsOverflow,
    ) -> Self:
        n, s, e = overflow.offsets
        return cls(
            path,
            dataset,
            fmt_offset_name(n),
            s,
            e,
            overflow.overflow,
            overflow.dataset_len,
            overflow.bound_is_nextdata,
        )


@dataclass(frozen=True)
class Overlap(WritableDiagnostic):
    name0: str
    start0: int
    end0: int
    name1: str
    start1: int
    end1: int
    overlap: int

    @classmethod
    def to_header(self) -> list[str]:
        return [
            "name0",
            "start0",
            "end0",
            "name1",
            "start1",
            "end1",
            "overlap",
        ]

    def to_row(self) -> list[str]:
        return [
            self.name0,
            str(self.start0),
            str(self.end0),
            self.name1,
            str(self.start1),
            str(self.end1),
            str(self.overlap),
        ]

    @classmethod
    def from_overlap(
        cls,
        path: Path,
        dataset: int,
        overlap: pfa.TextToHeaderOrSuppOffsetsOverlap
        | pfa.TextToHeaderOffsetsOverlap
        | pfa.HeaderToHeaderOffsetsOverlap
        | pfa.SuppToHeaderOffsetsOverlap,
    ) -> Self:
        n0, s0, e0 = overlap.offsets0
        n1, s1, e1 = overlap.offsets1
        return cls(
            path,
            dataset,
            fmt_offset_name(n0),
            s0,
            e0,
            fmt_offset_name(n1),
            s1,
            e1,
            overlap.overlap,
        )

    @classmethod
    def dataset_iter(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        hsupp = u.flat_diagnostics.header_supp
        header_overlaps = (cls.from_overlap(p, i, o) for o in hsupp.header.overlaps)
        supp_overlaps = (cls.from_overlap(p, i, o) for o in hsupp.supp_text.overlaps)
        ds = u.dataset.dataset_offsets
        data_overlaps = (cls.from_overlap(p, i, o) for o in ds.data_origin.overlaps)
        analysis_overlaps = (
            cls.from_overlap(p, i, o) for o in ds.analysis_origin.overlaps
        )
        # TODO add data/analysis overlap
        return chain(header_overlaps, supp_overlaps, data_overlaps, analysis_overlaps)


@dataclass(frozen=True)
class KeyValPair(WritableDiagnostic):
    pair_type: str
    key: str | bytes
    value: str | bytes

    @classmethod
    def to_header(self) -> list[str]:
        return ["pair_type", "key", "value"]

    def to_row(self) -> list[str]:
        return [
            self.pair_type,
            encode_or_esc(self.key),
            encode_or_esc(self.value),
        ]

    @classmethod
    def dataset_iter(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        return chain(
            cls._bad_pairs(p, i, u),
            cls._trimmed(p, i, u),
            cls._dropped(p, i, u),
        )

    @classmethod
    def _bad_pairs(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        fd = u.flat_diagnostics
        byte_pairs = (("byte_pair", k, v) for k, v in fd.byte_pairs)
        non_unq_std = (("non_unique_std", k, v) for k, v in fd.non_unique_std_keywords)
        non_unq_nonstd = (
            ("non_unique_nonstd", k, v) for k, v in fd.non_unique_std_keywords
        )
        ignored = (("ignored_std", k, v) for k, v in fd.ignored_standard_keywords)
        return (
            cls(p, i, t, k, v)
            for t, k, v in chain(byte_pairs, non_unq_std, non_unq_nonstd, ignored)
        )

    @classmethod
    def _trimmed(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        edge = (("edge", k, v) for k, v in u.flat_diagnostics.keys_with_trimmed_values)
        inner = (("inner", k, v) for k, v in u.dataset.std_diagnostics.trimmed)
        return (cls(p, i, t, k, v) for t, k, v in chain(edge, inner))

    @classmethod
    def _dropped(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        diag = u.dataset.std_diagnostics
        opt = (("optional", k, v) for k, v in diag.optional.items())
        pseudo = (("pseudostandard", k, v) for k, v in diag.pseudostandard.items())
        hyper_par = (("hyper_par", k, v) for k, v in diag.hyper_par.items())
        hyper_gate = (("hyper_gate", k, v) for k, v in diag.hyper_gate.items())
        other = (("other_version", k, v) for k, v in diag.other_version.items())
        tmp_opt = (("temporal_optical", k, v) for k, v in diag.temporal_optical_pairs)
        ts: list[tuple[str, str, str]] = maybe(
            [], lambda t: [("timestep", "$TIMESTEP", t)], diag.timestep
        )

        return (
            cls(p, i, t, k, v)
            for t, k, v in chain(opt, pseudo, hyper_gate, hyper_par, other, tmp_opt, ts)
        )


@dataclass(frozen=True)
class Token(WritableDiagnostic):
    token_type: str
    token: str | bytes

    @classmethod
    def to_header(self) -> list[str]:
        return ["token_type", "token"]

    def to_row(self) -> list[str]:
        return [
            self.token_type,
            encode_or_esc(self.token),
        ]

    @classmethod
    def dataset_iter(
        cls, p: Path, i: int, u: pfa.StdDatasetOutput
    ) -> Iterable["Token"]:
        def go(src: pfa.SplitTEXTDiagnostics, which: str) -> Iterable["Token"]:
            blank_values = (
                (f"{which}_blank_value", k) for k in src.keys_with_blank_values
            )
            blank_keys = (
                (f"{which}_blank_keys", k) for k in src.values_with_blank_keys
            )
            boundary = (
                (f"{which}_boundary", k) for k in src.tokens_with_boundary_delims
            )
            return (
                cls(p, i, t, k) for t, k in chain(blank_values, blank_keys, boundary)
            )

        primary = go(u.flat_diagnostics.primary_split, "primary")
        supp = u.flat_diagnostics.primary_split
        if supp is None:
            return primary
        else:
            return chain(primary, go(supp, "supp"))


@dataclass(frozen=True)
class FixedScale(WritableDiagnostic):
    meas_index: int
    is_meas: bool
    scale_value: str
    scale_fix: Literal["forced", "log", "trimmed", "trimmed_log"]

    @classmethod
    def to_header(self) -> list[str]:
        return ["meas_index", "is_meas", "scale_value", "scale_fix"]

    def to_row(self) -> list[str]:
        return [
            str(self.meas_index),
            str(self.is_meas),
            self.scale_value,
            self.scale_fix,
        ]

    @classmethod
    def dataset_iter(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        diag = u.dataset.std_diagnostics
        meas = (
            cls(p, i, si, True, s[0], s[1])
            for si, s in enumerate(diag.scale)
            if s is not None
        )
        gate = (
            cls(p, i, si, False, s[0], s[1])
            for si, s in enumerate(diag.gate_scale)
            if s is not None
        )
        return chain(meas, gate)


@dataclass(frozen=True)
class OriginalName(WritableDiagnostic):
    meas_index: int
    original_name: str

    @classmethod
    def to_header(self) -> list[str]:
        return ["meas_index", "original_name"]

    def to_row(self) -> list[str]:
        return [
            str(self.meas_index),
            self.original_name,
        ]

    @classmethod
    def dataset_iter(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        return (
            cls(p, i, si, n)
            for si, n in enumerate(u.dataset.std_diagnostics.original_names)
            if n is not None
        )


@dataclass(frozen=True)
class Overrange(WritableDiagnostic):
    meas_index: int
    first_row: int
    truncate: bool

    @classmethod
    def to_header(self) -> list[str]:
        return ["meas_index", "first_row", "truncate"]

    def to_row(self) -> list[str]:
        return [
            str(self.meas_index),
            str(self.first_row),
            str(self.truncate),
        ]

    @classmethod
    def dataset_iter(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        return (
            cls(p, i, si, *x)
            for si, x in enumerate(u.dataset.events_diagnostics.overrange_columns)
            if x is not None
        )


@dataclass(frozen=True)
class VersionScores(WritableDiagnostic):
    version: pt.FCSVersion
    good_req: int
    good_opt: int
    drop: int
    missing_opt: int
    missing_req: int
    missing_absent: int

    @classmethod
    def to_header(self) -> list[str]:
        return [
            "version",
            "good_req",
            "good_opt",
            "drop",
            "missing_opt",
            "missing_req",
            "missing_absent",
        ]

    def to_row(self) -> list[str]:
        return [
            self.version,
            str(self.good_req),
            str(self.good_opt),
            str(self.drop),
            str(self.missing_opt),
            str(self.missing_req),
            str(self.missing_absent),
        ]

    @classmethod
    def dataset_iter(
        cls, p: Path, i: int, u: pfa.StdDatasetOutput
    ) -> Iterable["VersionScores"]:
        def go(v: pt.FCSVersion, src: pfa.KeywordVersionScore) -> VersionScores:
            return cls(
                p,
                i,
                v,
                src.good_req,
                src.good_opt,
                src.drop,
                src.missing_opt,
                src.missing_req,
                src.missing_absent,
            )

        scores = u.version_scores
        if scores is not None:
            (v20, v30, v31, v32) = scores
            return [
                go("FCS2.0", v20),
                go("FCS3.0", v30),
                go("FCS3.1", v31),
                go("FCS3.2", v32),
            ]
        else:
            return []


@dataclass(frozen=True)
class MiscDiagnostics(WritableDiagnostic):
    version: pt.FCSVersion
    dataset_offset: int
    nextdata: int | None
    header_width: int
    prim_delimiter: int
    prim_escaped: bool
    prim_skipped_pairs: int
    prim_last_odd_token: str | bytes
    prim_has_even_delims: bool
    prim_extra_leading_delim: int
    supp_delimiter: int | None
    supp_escaped: bool | None
    supp_skipped_pairs: int | None
    supp_last_odd_token: str | bytes | None
    supp_has_even_delims: int | None
    supp_extra_leading_delim: int | None
    timestep_added: bool
    event_width: int | None
    event_data_remainder: int | None
    tot_event_mismatch: bool | None
    supp_origin_type: pt.SuppTEXTOffsetsOriginType
    data_origin_type: pt.TEXTOffsetsOriginType
    analysis_origin_type: pt.TEXTOffsetsOriginType
    file_crc_value: int | None
    file_crc_offset: int | None

    @classmethod
    def to_header(self) -> list[str]:
        return [
            "version",
            "dataset_offset",
            "nextdata",
            "header_width",
            "prim_delimiter",
            "prim_escaped",
            "prim_skipped_pairs",
            "prim_last_odd_token",
            "prim_has_even_delims",
            "prim_extra_leading_delim",
            "supp_delimiter",
            "supp_escaped",
            "supp_skipped_pairs",
            "supp_last_odd_token",
            "supp_has_even_delims",
            "supp_extra_leading_delim",
            "timestep_added",
            "event_width",
            "event_data_remainder",
            "tot_event_mismatch",
            "supp_origin_type",
            "data_origin_type",
            "analysis_origin_type",
            "file_crc_value",
            "file_crc_offset",
        ]

    def to_row(self) -> list[str]:
        return [
            self.version,
            str(self.nextdata),
            str(self.dataset_offset),
            str(self.header_width),
            str(self.prim_delimiter),
            str(self.prim_escaped),
            str(self.prim_skipped_pairs),
            encode_or_esc(self.prim_last_odd_token),
            str(self.prim_has_even_delims),
            str(self.prim_extra_leading_delim),
            maybe("", str, self.supp_delimiter),
            maybe("", str, self.supp_escaped),
            maybe("", str, self.supp_skipped_pairs),
            ""
            if self.supp_last_odd_token is None
            else encode_or_esc(self.supp_last_odd_token),
            maybe("", str, self.supp_has_even_delims),
            maybe("", str, self.supp_extra_leading_delim),
            str(self.timestep_added),
            maybe("", str, self.event_width),
            maybe("", str, self.event_data_remainder),
            maybe("", str, self.tot_event_mismatch),
            self.supp_origin_type,
            self.data_origin_type,
            self.analysis_origin_type,
            str(self.file_crc_value),
            str(self.file_crc_offset),
        ]

    @classmethod
    def dataset_iter(cls, p: Path, i: int, u: pfa.StdDatasetOutput) -> Iterable[Self]:
        flat = u.flat_diagnostics
        primary = flat.primary_split
        supp = flat.supp_split
        event = u.dataset.events_diagnostics
        header_width = 58 + maybe(
            0,
            lambda x: len(x[0]) * 2 * x[1],
            flat.header_supp.header.final_offsets.others,
        )
        crc = u.dataset.file_crc
        ret = cls(
            p,
            i,
            flat.header_supp.header.version,
            flat.header_supp.header.dataset_offset,
            flat.header_supp.nextdata,
            header_width,
            primary.delimiter,
            primary.escaped,
            primary.skipped_pairs,
            encode_or_esc(primary.last_odd_token),
            primary.has_even_delims,
            primary.extra_leading_delims,
            fmap_maybe(lambda x: x.delimiter, supp),
            fmap_maybe(lambda x: x.escaped, supp),
            fmap_maybe(lambda x: x.skipped_pairs, supp),
            fmap_maybe(lambda x: x.last_odd_token, supp),
            fmap_maybe(lambda x: x.has_even_delims, supp),
            fmap_maybe(lambda x: x.extra_leading_delims, supp),
            u.dataset.std_diagnostics.timestep_added,
            event.event_width,
            event.event_data_remainder,
            event.tot_event_mismatch,
            flat.header_supp.supp_text.origin_type,
            u.dataset.dataset_offsets.data_origin.origin_type,
            u.dataset.dataset_offsets.analysis_origin.origin_type,
            crc[0] if isinstance(crc, tuple) else None,
            crc[1] if isinstance(crc, tuple) else None,
        )
        return (ret,)


def main(smk: Any) -> None:
    fcs_path = Path(smk.input[0])
    flag_out = Path(smk.output["flag"])
    repo = RepoType(smk.wildcards.repo)
    id = smk.wildcards.id
    testname = smk.wildcards.testname
    sconf: FCSConfig = smk.config
    conf = sconf.find_file_options(repo, testname, id).merged_conf

    # read and write dataset (this will fail if pyreflow does not know how to
    # parse this particular brand of FCS file)
    datasets = conf.read_std_datasets(fcs_path)
    cores = [d[0] for d in datasets]
    uncores = [d[1] for d in datasets]
    fcs_write_datasets(smk.output["fcs"], cores)

    # dump lots of diagnostic data into neat little tables that can be concatted
    # later
    Offset.write_datasets(Path(smk.output["offsets"]), fcs_path, uncores)
    Overflow.write_datasets(Path(smk.output["overflow"]), fcs_path, uncores)
    Overlap.write_datasets(Path(smk.output["overlap"]), fcs_path, uncores)
    KeyValPair.write_datasets(Path(smk.output["key_val_pairs"]), fcs_path, uncores)
    Token.write_datasets(Path(smk.output["tokens"]), fcs_path, uncores)
    FixedScale.write_datasets(Path(smk.output["fixed_scales"]), fcs_path, uncores)
    OriginalName.write_datasets(Path(smk.output["original_names"]), fcs_path, uncores)
    Overrange.write_datasets(Path(smk.output["overrange"]), fcs_path, uncores)
    VersionScores.write_datasets(Path(smk.output["version_scores"]), fcs_path, uncores)
    MiscDiagnostics.write_datasets(Path(smk.output["misc"]), fcs_path, uncores)

    # make sentinel to indicate that everything worked
    flag_out.touch()


main(snakemake)  # type: ignore
