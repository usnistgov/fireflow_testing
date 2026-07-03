import base64
import csv
from dataclasses import dataclass
from typing import Any, Self, Literal, Iterable, NamedTuple
from multiprocessing import Pool
from pathlib import Path
import logging
from pyreflow.pydantic import PyreflowReadStdDatasetConfig
import pyreflow.api as pfa
import pyreflow.typing as pt
from itertools import chain
from pyreflow.api import fcs_write_datasets
from common.config import FCSConfig
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
    def write_all(cls, p: Path, ds: Iterable[Self]) -> None:
        with open(p, "w") as f:
            w = csv.writer(f, delimiter="\t")
            h = cls.to_header()
            w.writerow(["fcs_path", "dataset", *h])
            for i, row in enumerate(ds):
                r = row.to_row()
                assert len(r) == len(h), f"{h} is not same length as {r}"
                w.writerow([row.path, row.dataset, *r])

    @classmethod
    def dataset_iter_top(
        cls,
        fcs_path: Path,
        ds: list[tuple[pt.AnyCoreDataset, pfa.StdDatasetOutput]],
    ) -> list[Self]:
        return [
            row
            for i, (c, u) in enumerate(ds)
            for row in cls.dataset_iter(fcs_path, i, c, u)
        ]

    @classmethod
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable[Self]:
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
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
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
            return cls._from_offset(p, i, n, (begin, end), False)

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
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable[Self]:
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
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable[Self]:
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
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable[Self]:
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
        ignored = (
            ("ignored_std", k, v) for k, v in u.dataset.repair_diagnostics.ignored
        )
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
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
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
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable[Self]:
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
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable[Self]:
        return (
            cls(p, i, si, n)
            for si, n in enumerate(u.dataset.std_diagnostics.dedup_names)
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
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable[Self]:
        return (
            cls(p, i, si, *x)
            for si, x in enumerate(u.dataset.dataset_diagnostics.overrange_columns)
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
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
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
class Padding(WritableDiagnostic):
    prev_segment: str
    next_segment: str
    start_index: int
    byte_char: int
    n: int

    @classmethod
    def to_header(self) -> list[str]:
        return [
            "prev_segment",
            "next_segment",
            "start_index",
            "byte_char",
            "n",
        ]

    def to_row(self) -> list[str]:
        return [
            self.prev_segment,
            self.next_segment,
            str(self.start_index),
            str(self.byte_char),
            str(self.n),
        ]

    @classmethod
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable["Padding"]:
        acc = []

        # TODO add method to compute this on the fly
        header_width = 58 + maybe(
            0,
            lambda x: len(x[0]) * 2 * x[1],
            u.flat_diagnostics.header_supp.header.final_offsets.others,
        )
        pre = u.flat_diagnostics.header_supp.header.dark_bytes
        if isinstance(pre, tuple):
            acc.append(cls(p, i, "HEADER", "FIRST", header_width, pre[0], pre[1]))

        for d in u.dataset.dataset_diagnostics.intra_segment_dark_bytes:
            db = d.bytes
            if isinstance(db, tuple):
                n0 = fmt_offset_name(d.prev)
                n1 = fmt_offset_name(d.next)
                acc.append(cls(p, i, n0, n1, d.start, db[0], db[1]))

        dataset_len = u.dataset.dataset_diagnostics.dataset_len
        post = u.dataset.dataset_diagnostics.post_dataset_dark_bytes
        if isinstance(post, tuple):
            acc.append(cls(p, i, "LAST", "END", dataset_len, post[0], post[1]))

        return acc


@dataclass(frozen=True)
class DarkBytes(WritableDiagnostic):
    prev_segment: str
    next_segment: str
    start_index: int
    content: str

    @classmethod
    def to_header(self) -> list[str]:
        return [
            "prev_segment",
            "next_segment",
            "start_index",
            "content",
        ]

    def to_row(self) -> list[str]:
        return [
            self.prev_segment,
            self.next_segment,
            str(self.start_index),
            self.content,
        ]

    @classmethod
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable["DarkBytes"]:
        acc = []

        header_width = 58 + maybe(
            0,
            lambda x: len(x[0]) * 2 * x[1],
            u.flat_diagnostics.header_supp.header.final_offsets.others,
        )
        pre = u.flat_diagnostics.header_supp.header.dark_bytes
        if isinstance(pre, str | bytes):
            acc.append(cls(p, i, "HEADER", "FIRST", header_width, encode_or_esc(pre)))

        for d in u.dataset.dataset_diagnostics.intra_segment_dark_bytes:
            db = d.bytes
            if isinstance(db, str | bytes):
                n0 = fmt_offset_name(d.prev)
                n1 = fmt_offset_name(d.next)
                acc.append(cls(p, i, n0, n1, d.start, encode_or_esc(db)))

        dataset_len = u.dataset.dataset_diagnostics.dataset_len
        post = u.dataset.dataset_diagnostics.post_dataset_dark_bytes
        if isinstance(post, str | bytes):
            acc.append(cls(p, i, "LAST", "END", dataset_len, encode_or_esc(post)))

        return acc


@dataclass(frozen=True)
class MiscDiagnostics(WritableDiagnostic):
    file_version: pt.FCSVersion
    real_version: pt.FCSVersion
    dataset_offset: int
    nextdata: int | None
    header_width: int
    prim_delimiter: int
    prim_escaped: bool
    prim_skipped_pairs: int
    prim_has_even_delims: bool
    prim_extra_leading_delim: int
    prim_last_odd_bytes: int
    supp_delimiter: int | None
    supp_escaped: bool | None
    supp_skipped_pairs: int | None
    supp_has_even_delims: int | None
    supp_extra_leading_delim: int | None
    supp_last_odd_bytes: int | None
    timestep_added: bool
    spillover_was_indexed: bool
    btim_pattern: bool
    etim_pattern: bool
    date_pattern: bool
    begindatetime_pattern: bool
    enddatetime_pattern: bool
    last_modified_pattern: bool
    original_int_width: int | None
    original_byteord: list[int] | None
    event_width: int | None
    event_data_remainder: int | None
    tot_event_mismatch: bool | None
    supp_origin_type: pt.SuppTEXTOffsetsOriginType
    data_origin_type: pt.TEXTOffsetsOriginType
    analysis_origin_type: pt.TEXTOffsetsOriginType
    file_crc: int | None
    computed_crc: int | None
    # put these last since they can sometimes be long and it is easier to see
    # things when they are at the end
    prim_last_odd_token: str | bytes
    supp_last_odd_token: str | bytes | None

    @classmethod
    def to_header(self) -> list[str]:
        return [
            "file_version",
            "real_version",
            "dataset_offset",
            "nextdata",
            "header_width",
            "prim_delimiter",
            "prim_escaped",
            "prim_skipped_pairs",
            "prim_has_even_delims",
            "prim_extra_leading_delim",
            "prim_last_odd_bytes",
            "supp_delimiter",
            "supp_escaped",
            "supp_skipped_pairs",
            "supp_has_even_delims",
            "supp_extra_leading_delim",
            "supp_last_odd_bytes",
            "timestep_added",
            "spillover_was_indexed",
            "btim_pattern",
            "etim_pattern",
            "date_pattern",
            "begindatetime_pattern",
            "enddatetime_pattern",
            "last_modified_pattern",
            "original_int_width",
            "original_byteord",
            "event_width",
            "event_data_remainder",
            "tot_event_mismatch",
            "supp_origin_type",
            "data_origin_type",
            "analysis_origin_type",
            "file_crc",
            "computed_crc",
            "supp_last_odd_token",
            "prim_last_odd_token",
        ]

    def to_row(self) -> list[str]:
        return [
            self.file_version,
            self.real_version,
            str(self.dataset_offset),
            str(self.nextdata),
            str(self.header_width),
            str(self.prim_delimiter),
            str(self.prim_escaped),
            str(self.prim_skipped_pairs),
            str(self.prim_has_even_delims),
            str(self.prim_extra_leading_delim),
            str(self.prim_last_odd_bytes),
            maybe("", str, self.supp_delimiter),
            maybe("", str, self.supp_escaped),
            maybe("", str, self.supp_skipped_pairs),
            maybe("", str, self.supp_has_even_delims),
            maybe("", str, self.supp_extra_leading_delim),
            maybe("", str, self.supp_last_odd_bytes),
            str(self.timestep_added),
            str(self.spillover_was_indexed),
            str(self.btim_pattern),
            str(self.etim_pattern),
            str(self.date_pattern),
            str(self.begindatetime_pattern),
            str(self.enddatetime_pattern),
            str(self.last_modified_pattern),
            maybe("", str, self.original_int_width),
            maybe("", lambda xs: ",".join(map(str, xs)), self.original_byteord),
            maybe("", str, self.event_width),
            maybe("", str, self.event_data_remainder),
            maybe("", str, self.tot_event_mismatch),
            self.supp_origin_type,
            self.data_origin_type,
            self.analysis_origin_type,
            maybe("", str, self.file_crc),
            maybe("", str, self.computed_crc),
            encode_or_esc(self.prim_last_odd_token),
            ""
            if self.supp_last_odd_token is None
            else encode_or_esc(self.supp_last_odd_token),
        ]

    @classmethod
    def dataset_iter(
        cls, p: Path, i: int, c: pt.AnyCoreDataset, u: pfa.StdDatasetOutput
    ) -> Iterable[Self]:
        flat = u.flat_diagnostics
        primary = flat.primary_split
        supp = flat.supp_split
        std = u.dataset.std_diagnostics
        schema = std.schema_diagnostics
        event = u.dataset.dataset_diagnostics
        header_width = 58 + maybe(
            0,
            lambda x: len(x[0]) * 2 * x[1],
            flat.header_supp.header.final_offsets.others,
        )
        crc = u.dataset.dataset_diagnostics.file_crc
        ret = cls(
            p,
            i,
            flat.header_supp.header.version,
            c.version,
            flat.header_supp.header.dataset_offset,
            flat.header_supp.nextdata,
            header_width,
            primary.delimiter,
            primary.escaped,
            primary.skipped_pairs,
            primary.has_even_delims,
            primary.extra_leading_delims,
            len(primary.last_odd_token),
            fmap_maybe(lambda x: x.delimiter, supp),
            fmap_maybe(lambda x: x.escaped, supp),
            fmap_maybe(lambda x: x.skipped_pairs, supp),
            fmap_maybe(lambda x: x.has_even_delims, supp),
            fmap_maybe(lambda x: x.extra_leading_delims, supp),
            fmap_maybe(lambda x: len(x.last_odd_token), supp),
            std.timestep_added,
            std.spillover_was_indexed is True,
            isinstance(std.btim_pattern, str),
            isinstance(std.etim_pattern, str),
            isinstance(std.date_pattern, str),
            isinstance(std.begindatetime_pattern, str),
            isinstance(std.enddatetime_pattern, str),
            isinstance(std.last_modified_pattern, str),
            schema.original_int_width,
            schema.original_byteord,
            event.event_width,
            event.event_data_remainder,
            event.tot_event_mismatch,
            flat.header_supp.supp_text.origin_type,
            u.dataset.dataset_offsets.data_origin.origin_type,
            u.dataset.dataset_offsets.analysis_origin.origin_type,
            crc if isinstance(crc, int) else None,
            u.dataset.dataset_diagnostics.computed_crc,
            encode_or_esc(primary.last_odd_token),
            fmap_maybe(lambda x: encode_or_esc(x.last_odd_token), supp),
        )
        return (ret,)


class RunConfig(NamedTuple):
    conf: PyreflowReadStdDatasetConfig
    input_path: Path
    output_path: Path


class RunOutput(NamedTuple):
    offsets: list[Offset]
    overflow: list[Overflow]
    overlap: list[Overlap]
    keyval: list[KeyValPair]
    token: list[Token]
    scale: list[FixedScale]
    oname: list[OriginalName]
    overrange: list[Overrange]
    scores: list[VersionScores]
    padding: list[Padding]
    dark: list[DarkBytes]
    misc: list[MiscDiagnostics]


def test_file(r: RunConfig) -> RunOutput:
    conf = r.conf

    # Time channel will sometimes be missing, flag these later. In some
    # cases this will be due to the time being not named TIME or Time, but
    # these are also easy to find later
    conf.allow_missing_time = "silent"

    # compute the CRC so it can be checked manually
    conf.compute_crc = "always"
    conf.allow_mismatch_crc = "silent"
    conf.read_intra_segment_dark_bytes = True
    conf.read_post_dataset_dark_bytes = True

    # read and write dataset (this will fail if pyreflow does not know how to
    # parse this particular brand of FCS file)
    try:
        datasets = conf.read_std_datasets(r.input_path, scan=True)
        cores = [d[0] for d in datasets]

        r.output_path.parent.mkdir(parents=True, exist_ok=True)
        fcs_write_datasets(r.output_path, cores)
    except Exception as e:
        msg = f"error for input '{r.input_path}' and output '{r.output_path}'"
        raise ExceptionGroup(msg, [e])

    # dump lots of diagnostic data into neat little tables that can be concatted
    # later
    out = RunOutput(
        Offset.dataset_iter_top(r.output_path, datasets),
        Overflow.dataset_iter_top(r.output_path, datasets),
        Overlap.dataset_iter_top(r.output_path, datasets),
        KeyValPair.dataset_iter_top(r.output_path, datasets),
        Token.dataset_iter_top(r.output_path, datasets),
        FixedScale.dataset_iter_top(r.output_path, datasets),
        OriginalName.dataset_iter_top(r.output_path, datasets),
        Overrange.dataset_iter_top(r.output_path, datasets),
        VersionScores.dataset_iter_top(r.output_path, datasets),
        Padding.dataset_iter_top(r.output_path, datasets),
        DarkBytes.dataset_iter_top(r.output_path, datasets),
        MiscDiagnostics.dataset_iter_top(r.output_path, datasets),
    )

    return out


def main(smk: Any) -> None:
    fcs_paths = Path(smk.input[0])
    fcs_out = Path(smk.output["fcs"])
    sconf: FCSConfig = smk.config

    fcs_out_base = fcs_out.parent

    with open(fcs_paths, "r") as f:
        runs = [
            RunConfig(
                (opts := sconf.find_file_options(fcs_path := Path(p.rstrip())))[
                    0
                ].merged_conf,
                fcs_path,
                fcs_out_base / opts[1].value / opts[2] / opts[3],
            )
            for p in f
        ]

    with Pool(smk.threads) as p:
        test_out = p.map(test_file, runs)

    # dump lots of diagnostic data into neat little tables that can be concatted
    # later
    Offset.write_all(
        Path(smk.output["offsets"]), (y for x in test_out for y in x.offsets)
    )

    Overflow.write_all(
        Path(smk.output["overflow"]), (y for x in test_out for y in x.overflow)
    )

    Overlap.write_all(
        Path(smk.output["overlap"]), (y for x in test_out for y in x.overlap)
    )

    KeyValPair.write_all(
        Path(smk.output["key_val_pairs"]), (y for x in test_out for y in x.keyval)
    )

    Token.write_all(Path(smk.output["tokens"]), (y for x in test_out for y in x.token))

    FixedScale.write_all(
        Path(smk.output["fixed_scales"]), (y for x in test_out for y in x.scale)
    )

    OriginalName.write_all(
        Path(smk.output["original_names"]), (y for x in test_out for y in x.oname)
    )

    Overrange.write_all(
        Path(smk.output["overrange"]), (y for x in test_out for y in x.overrange)
    )

    VersionScores.write_all(
        Path(smk.output["version_scores"]), (y for x in test_out for y in x.scores)
    )

    Padding.write_all(
        Path(smk.output["padding"]), (y for x in test_out for y in x.padding)
    )

    DarkBytes.write_all(
        Path(smk.output["dark_bytes"]), (y for x in test_out for y in x.dark)
    )

    MiscDiagnostics.write_all(
        Path(smk.output["misc"]), (y for x in test_out for y in x.misc)
    )

    # dump list of output files, which should all be "clean"
    with open(fcs_out, "w") as f:
        for r in runs:
            f.write(str(r.output_path) + "\n")


main(snakemake)  # type: ignore
