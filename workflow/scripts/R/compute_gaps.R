library(tidyverse)

df_files <- read_tsv(snakemake@input[["file_paths"]])
df_offsets <- read_tsv(snakemake@input[["offsets"]])
df_misc_diag <- read_tsv(snakemake@input[["misc"]])

# compute dead space in files that was not used by any segments

df_header_widths <- df_misc_diag %>%
  select(fcs_path, dataset, header_width, dataset_offset) %>%
  add_column(name = "HEADER") %>%
  rename(start = dataset_offset) %>%
  mutate(end = start + header_width) %>%
  select(-header_width)

df_crc <- df_misc_diag %>%
  select(fcs_path, dataset, file_crc_offset) %>%
  filter(!is.na(file_crc_offset)) %>%
  add_column(name = "CRC") %>%
  rename(start = file_crc_offset) %>%
  mutate(end = start + 8)

df_dataset_ends <- df_misc_diag %>%
  left_join(df_files, by = c("fcs_path" = "filepath")) %>%
  group_by(fcs_path) %>%
  mutate(
    dataset_end = lead(dataset_offset, default = max(file_size))
  ) %>%
  ungroup() %>%
  mutate(
    start = dataset_end,
    end = dataset_end
  ) %>%
  add_column(name = "DATASET_END") %>%
  select(fcs_path, dataset, start, end, name)

df_final_offsets <- df_offsets %>%
  left_join(
    df_misc_diag %>% select(fcs_path, dataset, dataset_offset),
    by = c("fcs_path", "dataset")
  ) %>%
  filter(final) %>%
  mutate(
    start = start + dataset_offset,
    end = end + dataset_offset
  ) %>%
  select(-final, -dataset_offset) %>%
  bind_rows(df_header_widths) %>%
  bind_rows(df_dataset_ends) %>%
  bind_rows(df_crc) %>%
  mutate(
    used_bytes = end - start,
    segtype = case_when(
      name %in% c("hdr_data", "text_data") ~ "data",
      name %in% c("hdr_analysis", "text_analysis") ~ "analysis",
      TRUE ~ name
    )
  ) %>%
  arrange(fcs_path, dataset, start)

df_gaps <- df_final_offsets %>%
  group_by(fcs_path, dataset) %>%
  mutate(
    next_start = lead(start),
    next_segtype = lead(segtype),
    next_gap = next_start - end
  ) %>%
  filter(name != "DATASET_END")

df_final_offsets %>%
  write_tsv(snakemake@output[["final_offsets"]])

df_gaps %>%
  write_tsv(snakemake@output[["gaps"]])
