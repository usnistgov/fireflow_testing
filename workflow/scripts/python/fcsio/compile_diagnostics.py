from itertools import chain
import csv
import json
from typing import Any, TypeAlias
from pathlib import Path
from common.functional import maybe, esc


Diags: TypeAlias = list[tuple[Path, int, dict[str, Any]]]


# dump all non-OTHER segments
def compile_offsets(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(
            [
                "path",
                "dataset",
                # TEXT segments
                "text0",
                "text1",
                "u_text0",
                "u_text1",
                # supp TEXT segements
                "supp0",
                "supp1",
                "u_supp0",
                "u_supp1",
                # DATA segments
                "data0",
                "data1",
                "text_data0",
                "text_data1",
                "u_data0",
                "u_data1",
                "u_text_data0",
                "u_text_data1",
                # ANALYSIS segments
                "analysis0",
                "analysis1",
                "text_analysis0",
                "text_analysis1",
                "u_analysis0",
                "u_analysis1",
                "u_text_analysis0",
                "u_text_analysis1",
            ]
        )

        for p, di, d in diags:
            header_supp = d["flat_diagnostics"]["header_supp"]
            header_segs = header_supp["header"]["segments"]
            header_u_segs = header_supp["header"]["uncorrected_segments"]

            supp0 = ""
            supp1 = ""
            u_supp0 = ""
            u_supp1 = ""

            supp_text = header_supp["supp_text"]
            if supp_text is not None:
                (supp, u_supp) = supp_text
                supp0 = maybe("", lambda x: x[0], supp)
                supp1 = maybe("", lambda x: x[1], supp)
                u_supp0 = u_supp[0]
                u_supp1 = u_supp[1]

            dataset_segs = d["dataset"]["dataset_segs"]

            w.writerow(
                [
                    str(p),
                    di,
                    # TEXT
                    header_segs["text_seg"][0],
                    header_segs["text_seg"][1],
                    header_u_segs["text_seg"][0],
                    header_u_segs["text_seg"][1],
                    # supp TEXT
                    supp0,
                    supp1,
                    u_supp0,
                    u_supp1,
                    # DATA
                    header_segs["data_seg"][0],
                    header_segs["data_seg"][1],
                    dataset_segs["data_seg"][0],
                    dataset_segs["data_seg"][1],
                    header_u_segs["data_seg"][0],
                    header_u_segs["data_seg"][1],
                    maybe("", lambda x: x[0], dataset_segs["data_seg_uncorrected"]),
                    maybe("", lambda x: x[1], dataset_segs["data_seg_uncorrected"]),
                    # ANALYSIS
                    header_segs["analysis_seg"][0],
                    header_segs["analysis_seg"][1],
                    dataset_segs["analysis_seg"][0],
                    dataset_segs["analysis_seg"][1],
                    header_u_segs["analysis_seg"][0],
                    header_u_segs["analysis_seg"][1],
                    maybe(
                        "",
                        lambda x: x[0],
                        dataset_segs["analysis_seg_uncorrected"],
                    ),
                    maybe(
                        "",
                        lambda x: x[1],
                        dataset_segs["analysis_seg_uncorrected"],
                    ),
                ]
            )


# dump OTHER segments
#
# Print uncorrected and corrected in the same list. Note that the lengths
# may not match because we sometimes take out OTHER segments if they
# exactly match something else.
def compile_other_offsets(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        # no width -> uncorrected
        w.writerow(["path", "dataset", "width", "other0", "other1"])

        for p, di, d in diags:
            header_supp = d["flat_diagnostics"]["header_supp"]
            corr = header_supp["header"]["segments"]["other_segs"]
            uncorr = header_supp["header"]["uncorrected_segments"]["other_segs"]

            if corr is not None:
                (corr_segs, width) = corr
                for s0, s1 in corr_segs:
                    w.writerow([p, di, width, s0, s1])

            for u0, u1 in uncorr:
                w.writerow([p, "", u0, u1])


# dump keywords that failed standardization
def compile_bad_pairs(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(["path", "dataset", "type", "key", "value"])

        for p, di, d in diags:
            flat = d["flat_diagnostics"]

            byte_pairs = [("byte_pair", esc(k), esc(v)) for k, v in flat["byte_pairs"]]

            non_unq_std = [
                ("non_unique_std", k, esc(v))
                for k, v in flat["non_unique_std_keywords"]
            ]

            non_unq_nonstd = [
                ("non_unique_nonstd", esc(k), esc(v))
                for k, v in flat["non_unique_std_keywords"]
            ]

            ignored = [
                ("ignored_std", esc(k), esc(v))
                for k, v in flat["ignored_standard_keywords"]
            ]

            for t, k, v in byte_pairs + non_unq_nonstd + non_unq_std + ignored:
                w.writerow([p, di, t, k, v])


# dump keywords that had excess whitespace trimmed off/out
def compile_trimmed(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(["path", "dataset", "trim_type", "key", "value"])

        for p, di, d in diags:
            for k, v in d["flat_diagnostics"]["keys_with_trimmed_values"]:
                w.writerow([p, "edge", di, esc(k), esc(v)])

            for k, v in d["dataset"]["std_diagnostics"]["trimmed"]:
                w.writerow([p, "inner", di, esc(k), esc(v)])


# dump tokens found at boundaries
def compile_bad_tokens(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(["path", "dataset", "type", "value"])

        for p, di, d in diags:
            flat = d["flat_diagnostics"]
            supp = flat["supp_split"]

            for k in flat["keys_with_empty_trimmed_values"]:
                w.writerow([p, "empty_trimmed", k])

            def write_split(src: dict[str, Any], which: str) -> None:
                for k in src["keys_with_blank_values"]:
                    w.writerow([p, di, f"{which}_blank_value", esc(k)])

                for v in src["values_with_blank_keys"]:
                    w.writerow([p, di, f"{which}_blank_key", "", esc(v)])

                for k in src["tokens_with_boundary_delims"]:
                    w.writerow([p, di, f"{which}_boundary", k])

            write_split(flat["primary_split"], "prim")

            if supp is not None:
                write_split(supp, "supp")


# dump parse diagnostics
def compile_parse(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(
            [
                "path",
                "dataset",
                "version",
                "nextdata",
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
            ]
        )

        for p, di, d in diags:
            flat = d["flat_diagnostics"]
            version = flat["header_supp"]["header"]["version"]
            nextdata = flat["header_supp"]["nextdata"]
            primary = flat["primary_split"]
            supp = flat["supp_split"]
            event = d["dataset"]["events_diagnostics"]

            w.writerow(
                [
                    p,
                    di,
                    version,
                    nextdata,
                    primary["delimiter"],
                    primary["escaped"],
                    primary["skipped_pairs"],
                    esc(primary["last_odd_token"]),
                    primary["has_even_delims"],
                    primary["extra_leading_delims"],
                    maybe("", lambda x: x["delimiter"], supp),
                    maybe("", lambda x: x["escaped"], supp),
                    maybe("", lambda x: x["skipped_pairs"], supp),
                    maybe("", lambda x: esc(x["last_odd_token"]), supp),
                    maybe("", lambda x: x["has_even_delims"], supp),
                    maybe("", lambda x: x["extra_leading_delims"], supp),
                    d["dataset"]["std_diagnostics"]["timestep_added"],
                    event["event_width"],
                    event["event_data_remainder"],
                    event["tot_event_mismatch"],
                ]
            )


# dump dropped keywords
def compile_dropped(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(["path", "dataset", "type", "key", "value"])

        for p, di, d in diags:
            diag = d["dataset"]["std_diagnostics"]

            opt = (("optional", k, v) for k, v in diag["optional"].items())
            pseudo = (
                ("pseudostandard", k, v) for k, v in diag["pseudostandard"].items()
            )
            hyper_par = (("hyper_par", k, v) for k, v in diag["hyper_par"].items())
            hyper_gate = (("hyper_gate", k, v) for k, v in diag["hyper_gate"].items())
            other = (("other_version", k, v) for k, v in diag["other_version"].items())
            tmp_opt = (
                ("temporal_optical", k, v) for k, v in diag["temporal_optical_pairs"]
            )
            ts: list[tuple[str, str, str]] = maybe(
                [], lambda t: [("timestep", "$TIMESTEP", t)], diag["timestep"]
            )

            for t, k, v in chain(
                opt, pseudo, hyper_gate, hyper_par, other, tmp_opt, ts
            ):
                w.writerow([p, di, t, k, esc(v)])


# dump version scores
def compile_version_scores(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(
            [
                "path",
                "dataset",
                "version",
                "good_req",
                "good_opt",
                "drop",
                "missing_opt",
                "missing_req",
                "missing_absent",
            ]
        )

        for p, di, d in diags:

            def write_version(v: str, src: dict[str, int]) -> None:
                w.writerow(
                    [
                        p,
                        di,
                        v,
                        src["good_req"],
                        src["good_opt"],
                        src["drop"],
                        src["missing_opt"],
                        src["missing_req"],
                        src["missing_absent"],
                    ]
                )

            scores = d["version_scores"]
            if scores is not None:
                (v20, v30, v31, v32) = scores
                write_version("FCS2.0", v20)
                write_version("FCS3.0", v30)
                write_version("FCS3.1", v31)
                write_version("FCS3.2", v32)


# dump scales which were forced
def compile_scales(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(["path", "dataset", "type", "index", "scale_value", "scale_fix"])
        for p, di, d in diags:
            std = d["dataset"]["std_diagnostics"]

            def write_scale(key: str) -> None:
                for i, s in enumerate(std[key]):
                    if s is not None:
                        w.writerow([p, di, key, i, s[0], s[1]])

            write_scale("scale")
            write_scale("gate_scale")


# dump indices that were renamed
def compile_original_names(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(["path", "dataset", "index", "old_name"])
        for p, di, d in diags:
            for i, n in enumerate(d["dataset"]["std_diagnostics"]["original_names"]):
                if n is not None:
                    w.writerow([p, di, i, n])


# dump indices that were renamed
def compile_overrange(out: Path, diags: Diags) -> None:
    with open(out, "w") as f:
        w = csv.writer(f, delimiter="\t", lineterminator="\n")

        w.writerow(["path", "dataset", "index", "first_row", "truncated"])
        for p, di, d in diags:
            for i, n in enumerate(
                d["dataset"]["events_diagnostics"]["overrange_columns"]
            ):
                if n is not None:
                    w.writerow([p, di, i, n[0], n[1]])


def main(smk: Any) -> None:
    def read_json(p: Path) -> Any:
        with open(p, "r") as f:
            return json.load(f)

    diags = [
        (dataset["path"], int(di), dataset["diag"])
        for fcs_path in smk.input
        for di, dataset in enumerate(read_json(fcs_path))
    ]

    compile_offsets(smk.output["segments"], diags)
    compile_other_offsets(smk.output["other_segments"], diags)
    compile_bad_pairs(smk.output["bad_pairs"], diags)
    compile_trimmed(smk.output["trimmed"], diags)
    compile_bad_tokens(smk.output["bad_tokens"], diags)
    compile_parse(smk.output["parse"], diags)
    compile_dropped(smk.output["dropped"], diags)
    compile_version_scores(smk.output["scores"], diags)
    compile_scales(smk.output["scales"], diags)
    compile_original_names(smk.output["original_names"], diags)
    compile_overrange(smk.output["overrange"], diags)


main(snakemake)  # type: ignore
