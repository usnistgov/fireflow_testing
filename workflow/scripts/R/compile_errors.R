suppressMessages(library(tidyverse))

# TODO
# - how to assess overrange columns? this should be done for ints above their bitmask
# - get missing nextdata
# - report files with corrected offsets (right this only accounts for auto-corrected offsets)

df_misc <- read_tsv(
  snakemake@input[["misc"]],
  col_types = cols(
    fcs_path = "c",
    file_version = "c",
    real_version = "c",
    prim_escaped = "l",
    prim_has_even_delims = "l",
    prim_extra_leading_delim = "l",
    prim_multibyte = "l",
    supp_escaped = "l",
    supp_has_even_delims = "l",
    supp_extra_leading_delim = "l",
    supp_multibyte = "l",
    timestep_added = "l",
    spillover_was_indexed = "l",
    btim_pattern = "l",
    etim_pattern = "l",
    date_pattern = "l",
    begindatetime_pattern = "l",
    enddatetime_pattern = "l",
    last_modified_pattern = "l",
    original_byteord = "c",
    tot_event_mismatch = "l",
    supp_origin_type = "c",
    data_origin_type = "c",
    analysis_origin_type = "c",
    supp_last_odd_token = "c",
    prim_last_odd_token = "c",
    .default = "i",
  )
)

df_scale <- read_tsv(snakemake@input[["fixed_scales"]], col_types = "iciilcc")
df_key_val <- read_tsv(snakemake@input[["key_val_pairs"]], col_types = "icicc")
df_orig_names <- read_tsv(snakemake@input[["original_names"]], col_types = "iciic")
df_overflow <- read_tsv(snakemake@input[["overflow"]], col_types = "iciciiiil")
df_tokens <- read_tsv(snakemake@input[["tokens"]], col_types = "icicc")
df_offsets <- read_tsv(snakemake@input[["offsets"]], col_types = "iciciil")
df_overrange <- read_tsv(snakemake@input[["overrange"]], col_types = "iciiil")

df_machines <- read_tsv(
  snakemake@input[["machines"]],
  col_types = "ci-ccccc---"
) %>%
  filter(dataset == 0) %>%
  rename(fcs_path = filepath) %>%
  select(-dataset) %>%
  unique()

df_all <- df_misc %>%
  select(fcs_path, dataset)

df_misc_errors <- df_misc %>%
  mutate(
    # version in HEADER should match what the version really is
    nc_version = file_version != real_version,
    # delimiter should be a byte numbered 1-126
    nc_text_delimiter = !(0 < prim_delimiter & prim_delimiter <= 126) |
      replace_na(!(0 < supp_delimiter & supp_delimiter <= 126), FALSE),
    # escaping the delimiter is non-compliant behavior, so both TEXT segments
    # should not have it
    nc_text_non_escape = prim_escaped | replace_na(supp_escaped, FALSE),
    # both TEXT segments should have odd number of delimiters
    nc_text_delim_number = prim_has_even_delims |
      replace_na(supp_has_even_delims, FALSE),
    # both TEXT segments should have even number of tokens
    nc_text_token_number = prim_last_odd_bytes > 0 |
      replace_na(supp_last_odd_bytes > 0, FALSE),
    # both TEXT segments should be multibyte encoded (UTF-8)
    nc_text_utf8 = !prim_multibyte | replace_na(!supp_multibyte, FALSE),
    # timestep should not be missing
    nc_key_val_timestep_missing = timestep_added,
    # DATA should not have a remainder (usually an off-by-one error)
    nc_offsets_data_len = replace_na(event_data_remainder > 0, FALSE),
    # $TOT should match the number of events in DATA
    nc_tot = tot_event_mismatch,
    # CRC should be present in 3.0+ file
    nc_crc_word = (real_version != "FCS2.0") & is.na(file_crc),
    # if CRC is present, it should match what is computed.
    nc_crc_validity = replace_na(file_crc != computed_crc, FALSE),
    # supp offsets are non-compliant if they overlap with ANALYSIS or TEXT or
    # cannot be parsed
    nc_offsets_supp = supp_origin_type %in%
      c("unparsed", "malformed", "dup_ptext", "dup_analysis"),
    # TEXT DATA/ANALYSIS offsets are non-compliant if they cannot be parsed or
    # mismatch the HEADER
    nc_offsets_data = data_origin_type %in%
      c("unparsed", "malformed", "mismatch_header", "mismatch_text"),
    nc_offsets_analysis = data_origin_type %in%
      c("unparsed", "malformed", "mismatch_header", "mismatch_text"),
    # $SPILLOVER should have names but not indices
    nc_parse_spillover_names = spillover_was_indexed,
    # timestamps should all have proper formats
    nc_parse_btim_fmt = btim_pattern,
    nc_parse_etim_fmt = etim_pattern,
    nc_parse_date_fmt = date_pattern,
    nc_parse_begindatetime_fmt = begindatetime_pattern,
    nc_parse_enddatetime_fmt = enddatetime_pattern,
    nc_parse_last_modified_fmt = last_modified_pattern,
    # $BYTEORD should reflect the actual data, so flag files that needed it fixed
    nc_byteord = !is.na(original_byteord),
    # ditto $PnB, this likely will only happen for files with non-octet widths
    nc_int_width = !is.na(original_int_width)
  ) %>%
  group_by(fcs_path) %>%
  mutate(
    # $NEXTDATA should match where the next dataset actually is
    .expected_nextdata = replace_na(lead(dataset_offset) - dataset_offset, 0),
    nc_offsets_nextdata = .expected_nextdata != nextdata
  ) %>%
  ungroup() %>%
  select(fcs_path, dataset, starts_with("nc_"))

df_scale_errors <- df_scale %>%
  group_by(fcs_path, dataset) %>%
  summarize(
    # $PnE was something like "1,0" which is illegal.
    nc_key_val_scale_log = ("log" %in% scale_fix) | ("trimmed_log" %in% scale_fix),
    # $PnE was forced to be linear when is was originally log
    nc_key_val_scale_forced = "forced" %in% scale_fix,
    # $PnE had whitespace which needed to be trimmed
    nc_key_val_scale_trimmed = ("trimmed" %in% scale_fix) | ("trimmed_log" %in% scale_fix),
    .groups = "drop"
  ) %>%
  right_join(df_all, by = c("fcs_path", "dataset")) %>%
  replace_na(
    list(
      nc_key_val_scale_log = FALSE,
      nc_key_val_scale_forced = FALSE,
      nc_key_val_scale_trimmed = FALSE
    )
  ) %>%
  select(fcs_path, dataset, starts_with("nc_"))

STR_KWS <- c("$PROJ", "$LAST_MODIFIER", "$PLATEID", "$PLATENAME", "$WELLID",
             "$UNSTAINEDINFO", "$CARRIERID", "$CARRIERTYPE", "$LOCATIONID",
             "$CYT", "$CELLS", "$COM", "$EXP", "$FIL", "$INST", "$OP",
             "$PROJ", "$SMNO", "$SRC", "$SYS", "$CYTSN", "$FLOWRATE")

df_key_val_errors <- df_key_val %>%
  # remove lines that are trimmed but won't cause an error
  filter(
    pair_type != "edge" |
      (pair_type == "edge" &
         !str_detect(key, "^(P|G)[0-9](N|T|S|F)$") &
         !str_detect(key, "^P[0-9](DET|TAG|ANALYTE)$") &
         !(key %in% STR_KWS))
  ) %>%
  group_by(fcs_path, dataset) %>%
  summarize(
    # optional keyword could not be parsed
    nc_key_val_optional = "optional" %in% pair_type,
    # keyword(s) has a $ in front but is not a real keyword
    nc_extra_pseudostd = "pseudostandard" %in% pair_type,
    # keyword(s) is a $Pn* keyword but the "n" exceeds $PAR
    nc_extra_hyper_par = "hyper_par" %in% pair_type,
    # keyword(s) is a $Gn* keyword but the "n" exceeds $GATE
    nc_extra_hyper_gate = "hyper_gate" %in% pair_type,
    # keyword(s) is standard but for another version
    nc_extra_other_verison = "other_version" %in% pair_type,
    # keyword(s) is an optical keyword but found for a temporal measurement
    nc_extra_temporal_optical = "temporal_optical" %in% pair_type,
    # keyword(s) is $TIMESTEP which could not be parsed
    nc_key_val_timestep_invalid = "timestep" %in% pair_type,
    # keyword(s) had whitespace on beginning/end which needed to be trimmed
    nc_key_val_ws_edge = ("edge" %in% pair_type),
    # keyword(s) had whitespace in b/t comma-sep values which needed to be trimmed
    nc_key_val_ws_inner = "inner" %in% pair_type,
    # keyword(s) had key or value which had invalid bytes
    nc_text_byte_pair = "byte_pair" %in% pair_type,
    # keyword(s) was standard and non-unique
    nc_text_std_nonunique = "non_unique_std" %in% pair_type,
    # keyword(s) was non-standard and non-unique
    nc_text_nonstd_nonunique = "non_unique_nonstd" %in% pair_type,
    .groups = "drop"
  ) %>%
  right_join(df_all, by = c("fcs_path", "dataset")) %>%
  replace_na(
    list(
      nc_key_val_optional = FALSE,
      nc_extra_pseudostd = FALSE,
      nc_extra_hyper_par = FALSE,
      nc_extra_hyper_gate = FALSE,
      nc_extra_other_verison = FALSE,
      nc_extra_temporal_optical = FALSE,
      nc_key_val_timestep_invalid = FALSE,
      nc_key_val_ws_edge = FALSE,
      nc_key_val_ws_inner = FALSE,
      nc_text_byte_pair = FALSE,
      nc_text_std_nonunique = FALSE,
      nc_text_nonstd_nonunique = FALSE
    )
  ) %>%
  select(fcs_path, dataset, starts_with("nc_"))

df_orig_names_errors <- df_orig_names %>%
  group_by(fcs_path, dataset) %>%
  summarize(
    # $PnN was non-unique and renamed
    nc_key_val_pnn_non_unique = TRUE,
    .groups = "drop"
  ) %>%
  right_join(df_all, by = c("fcs_path", "dataset")) %>%
  replace_na(
    list(
      nc_key_val_pnn_non_unique = FALSE
    )
  ) %>%
  select(fcs_path, dataset, starts_with("nc_"))

df_overflow_errors <- df_overflow %>%
  add_column(
    # last segment exceeded end of dataset
    nc_offsets_overflow_last = TRUE,
  ) %>%
  right_join(df_all, by = c("fcs_path", "dataset")) %>%
  replace_na(
    list(
      nc_offsets_overflow_last = FALSE
    )
  ) %>%
  select(fcs_path, dataset, starts_with("nc_"))

df_token_errors <- df_tokens %>%
  group_by(fcs_path, dataset) %>%
  summarize(
    # pair is a key with a blank value (escaped mode only)
    nc_text_token_blank_value = "prim_blank_value" %in% token_type |
      "supp_blank_value" %in% token_type,
    # value was entirely whitespace and was trimmed to nothing (unescaped mode only)
    nc_text_token_trimmed = "empty_trimmed" %in% token_type,
    # pair is a value with a blank key
    nc_text_token_blank_key = "prim_blank_keys" %in% token_type |
      "supp_blank_keys" %in% token_type,
    # token had an escaped delimiter at the boundary which need to be removed
    nc_text_token_boundary = "prim_boundary" %in% token_type |
      "supp_boundary" %in% token_type,
    .groups = "drop"
  ) %>%
  right_join(df_all, by = c("fcs_path", "dataset")) %>%
  replace_na(
    list(
      nc_text_token_blank_value = FALSE,
      nc_text_token_blank_key = FALSE,
      nc_text_token_boundary = FALSE,
      nc_text_token_trimmed = FALSE
    )
  ) %>%
  select(fcs_path, dataset, starts_with("nc_"))

df_pseudoempty <- df_offsets %>%
  filter(!final) %>%
  filter(start == end + 1) %>%
  select(fcs_path, dataset) %>%
  unique() %>%
  add_column(nc_offsets_pseudoempty = TRUE) %>%
  right_join(df_all, by = c("fcs_path", "dataset")) %>%
  replace_na(
    list(
      nc_offsets_pseudoempty = FALSE
    )
  ) %>%
  select(fcs_path, dataset, starts_with("nc_"))

df_bitmask_overrange <- df_overrange %>%
  # ASSUME truncation will only happen for values which exceed their bitmask due
  # to the config we chose, which is what we want here.
  filter(truncate) %>%
  select(fcs_path, dataset) %>%
  add_column(nc_bitmask = TRUE) %>%
  right_join(df_all, by = c("fcs_path", "dataset")) %>%
  replace_na(
    list(
      nc_bitmask = FALSE
    )
  ) %>%
  select(fcs_path, dataset, starts_with("nc_"))
  

df_all_errors <- df_misc_errors %>%
  left_join(df_scale_errors, by = c("fcs_path", "dataset")) %>%
  left_join(df_key_val_errors, by = c("fcs_path", "dataset")) %>%
  left_join(df_orig_names_errors, by = c("fcs_path", "dataset")) %>%
  left_join(df_overflow_errors, by = c("fcs_path", "dataset")) %>%
  left_join(df_token_errors, by = c("fcs_path", "dataset")) %>%
  left_join(df_pseudoempty, by = c("fcs_path", "dataset")) %>%
  left_join(df_bitmask_overrange, by = c("fcs_path", "dataset")) %>%
  left_join(df_machines, by = "fcs_path") %>%
  # combine these since they are basically the same thing with different keywords
  mutate(nc_key_val_ws_inner = nc_key_val_scale_trimmed | nc_key_val_ws_inner) %>%
  select(-nc_key_val_scale_trimmed)

df_all_errors %>%
  mutate(
    vendor = case_when(
      str_detect(vendor, "BD") ~ "BD",
      str_detect(vendor, "Agilent") ~ "Agilent",
      str_detect(vendor, "Beckman") ~ "BC",
      str_detect(vendor, "Thermo") ~ "TFS",
      str_detect(vendor, "Biotools") ~ "SBT",
      str_detect(vendor, "Cytek") ~ "Cytek",
      str_detect(vendor, "Sony") ~ "Sony",
      str_detect(vendor, "Verity") ~ "Verity",
      TRUE ~ vendor
    ),
    software = case_when(
      str_detect(software, "FACSDiva") ~
        str_replace(software, "BD FACSDiva Software Version", "FACSDiva"),
      str_detect(software, "DVSSCIENCES") ~
        str_replace(software, "DVSSCIENCES-?", ""),
      TRUE ~ software %>% str_replace("Development-only Version", ""),
    )
  ) %>%
  replace_na(list(software = "UNK")) %>%
  mutate(machine = sprintf("%s_%s", machine, software)) %>%
  group_by(vendor, machine) %>%
  summarize(
    across(starts_with("nc_"), mean),
    .groups = "drop",
  ) %>%
  pivot_longer(cols = starts_with("nc_")) %>%
  mutate(
    value = case_when(
      value == 1.0 ~ "all",
      value == 0.0 ~ "none",
      value < 0.1 ~ "<10%",
      value < 0.9 ~ "10-90%",
      TRUE ~ ">90%"
    )
  ) %>%
  mutate(
    category = case_when(
      str_detect(name, "nc_offsets") ~ "offsets",
      str_detect(name, "nc_parse") ~ "keyword value",
      str_detect(name, "nc_key_val") ~ "keyword value",
      str_detect(name, "nc_extra") ~ "extra",
      str_detect(name, "nc_text") ~ "TEXT layout",
      TRUE ~ "misc"
    )
  ) %>%
  mutate(
    category = fct_relevel(category, "offsets", "TEXT layout", "keyword value",
                           "extra", "misc")) %>%
  ggplot(
    aes(
      name,
      fct_rev(machine),
      color = fct_relevel(value, "all", ">90%", "10-90%", "<10%", "none")
    )
  ) +
  geom_point() +
  facet_grid(
    vendor ~ category,
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  scale_color_manual(
    values = c(
      "none" = "white",
      "<10%" = "#ffbbbb",
      "10-90%" = "#ff8888",
      ">90%" = "#ff5555",
      "all" = "#ff0000"
    )
  )  +
  labs(x = NULL, y = NULL, color = "Fraction\nwith errors") +
  theme(
    axis.text.x = element_text(angle = 90, hjust = 1.0, vjust = 0.5),
    strip.text.y.left = element_text(angle = 0),
  )
ggsave(snakemake@output[["plot"]], width = 12, height = 12, dpi = 125)

df_all_errors %>%
  write_tsv(snakemake@output[["table"]])
