suppressMessages(library(tidyverse))

DPI <- 125
HEIGHT <- 16
WIDTH <- 10

## import data

df_machines <- read_tsv(
  snakemake@input[["machine_table"]],
  col_types = cols(
    dataset = "i",
    .default = "c"
  )
)

df_root <- read_tsv(
  snakemake@input[["other_root_keywords"]],
  col_types = cols(
    dataset = "i",
    ABRT = "i",
    LOST = "i",
    CSTOT = "i",
    CSVBITS = "i",
    TIMESTEP = "d",
    TR_value = "d",
    spill_or_comp = "l",
    .default = "c",
  )
)

df_time <- read_tsv(
  snakemake@input[["time_keywords"]],
  col_types = "ciDttTT"
)

df_unstained <- read_tsv(
  snakemake@input[["unstained_centers"]],
  col_types = "cicc"
)

df_gated_meas <- read_tsv(
  snakemake@input[["gated_meas"]],
  col_types = cols(
    dataset = "i",
    .default = "c"
  )
)

df_meas <- read_tsv(
  snakemake@input[["meas_keywords"]],
  col_types = cols(
    dataset = "i",
    meas_index = "i",
    PnE_0 = "d",
    PnE_1 = "d",
    PnL = "d",
    PKn = "i",
    PKNn = "i",
    PnO = "d",
    PnE = "d",
    PnV = "d",
    PnCALIBRATION_slope = "d",
    PnCALIBRATION_intercept = "d",
    PnD_n0 = "d",
    PnD_n1 = "d",
    is_optical = "l",
    .default = "c"
  )
)

df_byteord <- read_tsv(
  snakemake@input[["byteord"]],
  col_types = "cic"
)

df_mixed_schema <- read_tsv(
  snakemake@input[["mixed_schema"]],
  col_types = "ciic"
)

df_var_uint_schema <- read_tsv(
  snakemake@input[["var_uint_schema"]],
  col_types = "ciic"
)

df_ascii_schema <- read_tsv(
  snakemake@input[["ascii_schema"]],
  col_types = "cil"
)

df_matrix_schema <- read_tsv(
  snakemake@input[["matrix_schema"]],
  col_types = "cici"
)

df_offsets <- read_tsv(
  snakemake@input[["offsets"]],
  col_types = "iciciil"
) %>%
  rename(filepath = fcs_path)

df_misc <- read_tsv(
  snakemake@input[["misc"]],
  col_types = cols(fcs_path = "c", dataset = "i", file_crc = "i", .default = "-")
) %>%
  rename(filepath = fcs_path)

df_dark <- read_tsv(
  snakemake@input[["dark_bytes"]],
  col_types = cols(fcs_path = "c", dataset = "i", .default = "-")
) %>%
  rename(filepath = fcs_path)

# make list of pretty machines and software

df_all <- df_root %>%
  select(filepath, dataset)

df_machines_pretty <- df_machines %>%
  mutate(ms = sprintf("%s_%s", machine_short, software_short)) %>%
  filter(dataset == 0) %>%
  select(filepath, vendor_short, machine_short, software_short, ms)

## show number of datasets per file

df_root %>%
  select(filepath) %>%
  group_by(filepath) %>%
  mutate(n = n()) %>%
  left_join(df_machines_pretty, by = c("filepath")) %>%
  ggplot(aes(x = n, y = fct_rev(ms))) +
  geom_point() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "log(N datasets)", y = NULL) +
  scale_x_log10() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_datasets"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show files that use supp text

df_has_supp <- df_offsets %>%
  filter(final) %>%
  filter(name == "supp_text") %>%
  filter(start > 0) %>%
  select(filepath, dataset) %>%
  add_column(has_supp = TRUE) %>%
  right_join(df_all, by = c("filepath", "dataset")) %>%
  replace_na(list(has_supp = FALSE))

df_has_supp %>%
  right_join(df_machines_pretty, by = "filepath") %>%
  ggplot(aes(y = fct_rev(ms), fill = has_supp)) +
  geom_bar() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "N datasets", y = NULL) +
  scale_x_continuous() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_supp_text"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show files that use ANALYSIS

df_has_analysis <- df_offsets %>%
  filter(final) %>%
  filter(name == "hdr_analysis" | name == "text_analysis") %>%
  filter(start > 0) %>%
  select(filepath, dataset) %>%
  add_column(has_analysis = TRUE) %>%
  right_join(df_all, by = c("filepath", "dataset")) %>%
  replace_na(list(has_analysis = FALSE))

df_has_analysis %>%
  right_join(df_machines_pretty, by = "filepath") %>%
  ggplot(aes(y = fct_rev(ms), fill = has_analysis)) +
  geom_bar() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "N datasets", y = NULL) +
  scale_x_continuous() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_analysis"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show how many OTHER segments files use

df_n_other <- df_offsets %>%
  filter(final) %>%
  filter(str_starts(name, "other-")) %>%
  filter(start > 0) %>%
  group_by(filepath, dataset) %>%
  tally() %>%
  right_join(df_all, by = c("filepath", "dataset")) %>%
  replace_na(list(n = 0))

df_n_other %>%
  right_join(df_machines_pretty, by = "filepath") %>%
  ggplot(aes(x = n, y = fct_rev(ms))) +
  geom_point() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "N other seg", y = NULL) +
  scale_x_continuous() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_other_seg"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show which files use CRC

df_misc %>%
  mutate(has_crc = !is.na(file_crc)) %>%
  right_join(df_machines_pretty, by = "filepath") %>%
  ggplot(aes(y = fct_rev(ms), fill = has_crc)) +
  geom_bar() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "N dataset", y = NULL) +
  scale_x_continuous() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_crc"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show which files use "dark bytes"

df_dark %>%
  unique() %>%
  add_column(has_dark = TRUE) %>%
  right_join(df_all, by = c("filepath", "dataset")) %>%
  replace_na(list(has_dark = FALSE)) %>%
  right_join(df_machines_pretty, by = "filepath") %>%
  ggplot(aes(y = fct_rev(ms), fill = has_dark)) +
  geom_bar() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "N dataset", y = NULL) +
  scale_x_continuous() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_dark"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show how many machines use linear scaling

df_scale <- df_meas %>%
  filter(is_optical) %>%
  mutate(is_log = !is.na(PnE_1)) %>%
  group_by(filepath, dataset) %>%
  summarize(
    is_log = mean(is_log),
    .groups = "drop"
  ) %>%
  mutate(
    scaling = case_when(
      is_log == 0 ~ "linear",
      is_log == 1 ~ "log",
      TRUE ~ "linear/log"
    )
  )

df_scale %>%
  right_join(df_machines_pretty, by = "filepath") %>%
  ggplot(aes(y = fct_rev(ms), fill = scaling)) +
  geom_bar() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "N datasets", y = NULL) +
  scale_x_continuous() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_scaling"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show which files use each byte order

df_byteord %>%
  right_join(df_machines_pretty, by = "filepath") %>%
  ggplot(aes(y = fct_rev(ms), fill = byteord)) +
  geom_bar() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "N datasets", y = NULL) +
  scale_x_continuous() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_byteord"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show which data layouts are used

df_is_ascii <- df_ascii_schema %>%
  mutate(schema_type = if_else(is_delim, "ascii-delim", "ascii-fixed")) %>%
  select(filepath, dataset, schema_type)

df_is_var <- df_var_uint_schema %>%
  select(filepath, dataset) %>%
  unique() %>%
  add_column(schema_type = "uint-var")

df_is_mixed <- df_mixed_schema %>%
  select(filepath, dataset) %>%
  unique() %>%
  add_column(schema_type = "mixed")

df_all_schema <- df_matrix_schema %>%
  mutate(schema_type = sprintf("%s-%s", datatype, byte_width * 8)) %>%
  bind_rows(df_is_ascii) %>%
  bind_rows(df_is_var) %>%
  bind_rows(df_is_mixed)

df_all_schema %>%
  write_tsv(snakemake@output[["schema"]])

df_all_schema %>%
  right_join(df_machines_pretty, by = "filepath") %>%
  ggplot(aes(y = fct_rev(ms), fill = schema_type)) +
  geom_bar() +
  facet_grid(
    "vendor_short",
    scales = "free",
    switch = "y",
    space = "free"
  ) +
  labs(x = "N datasets", y = NULL) +
  scale_x_continuous() +
  theme(
    strip.text.y.left = element_text(angle = 0),
    legend.position="bottom"
  )
ggsave(snakemake@output[["plot_schema"]], width = WIDTH, height = HEIGHT, dpi = DPI)

## show which keywords are in use

df_has_unstained_centers <- df_unstained %>%
  select(filepath, dataset) %>%
  add_column(UNSTAINEDCENTERS = TRUE) %>%
  right_join(df_all, by = c("filepath", "dataset")) %>%
  replace_na(list(UNSTAINEDCENTERS = FALSE))

df_has_gated_meas <- df_gated_meas %>%
  select(filepath, dataset) %>%
  add_column(has_gated_meas = TRUE) %>%
  right_join(df_all, by = c("filepath", "dataset")) %>%
  replace_na(list(has_gated_meas = FALSE))

df_meas_any <- df_meas %>%
  group_by(filepath, dataset) %>%
  summarize(
    PKn = any(!is.na(PKn)),
    PKNn = any(!is.na(PKNn)),
    PnS = any(!is.na(PnS)),
    PnD = any(!is.na(PnD_type)),
    PnTYPE = any(!is.na(PnTYPE)),
    .groups = "drop"
  )

df_meas_optical <- df_meas %>%
  filter(is_optical) %>%
  group_by(filepath, dataset) %>%
  summarize(
    PnL = any(!is.na(PnL)),
    PnF = any(!is.na(PnF)),
    PnO = any(!is.na(PnO)),
    PnV = any(!is.na(PnV)),
    PnCALIBRATION = any(!is.na(PnCALIBRATION_unit)),
    PnANALYTE = any(!is.na(PnANALYTE)),
    PnFEATURE = any(!is.na(PnFEATURE)),
    PnTAG = any(!is.na(PnTAG)),
    PnDET = any(!is.na(PnDET)),
    .groups = "drop"
  )

df_time_has_kw <- df_time %>%
  mutate(
    across(
      c(DATE, BTIM, ETIM, BEGINDATETIME, ENDDATETIME),
      ~ !is.na(.x)
    )
  )

df_root_has_kw <- df_root %>%
  mutate(
    across(
      c(
        LAST_MODIFIER,
        LAST_MODIFIED,
        ORIGINALITY,
        PLATEID,
        PLATENAME,
        WELLID,
        VOL,
        CARRIERID,
        CARRIERTYPE,
        LOCATIONID,
        UNSTAINEDINFO,
        FLOWRATE,
        ABRT,
        COM,
        CELLS,
        EXP,
        FIL,
        INST,
        LOST,
        OP,
        PROJ,
        SMNO,
        SRC,
        GATING,
        CSTOT,
        CSVBITS,
        CSVFLAGS
      ),
      ~ !is.na(.x)
    ),
  ) %>%
  mutate(TR = !is.na(TR_name)) %>%
  select(-TR_name, -TR_value, -MODE, -TIMESTEP)
  
df_all_kw <- df_root_has_kw %>%
  left_join(df_time_has_kw, by = c("filepath", "dataset")) %>%
  left_join(df_meas_any, by = c("filepath", "dataset")) %>%
  left_join(df_meas_optical, by = c("filepath", "dataset")) %>%
  left_join(df_has_unstained_centers, by = c("filepath", "dataset")) %>%
  left_join(df_has_gated_meas, by = c("filepath", "dataset")) %>%
  pivot_longer(cols = c(-filepath, -dataset), names_to = "key", values_to = "used") %>%
  mutate(used = as.logical(used)) %>%
  mutate(
    key = case_when(
      key == "has_gated_meas" ~ "Gn*",
      key == "spill_or_comp" ~ "SPILLOVER/COMP",
      TRUE ~ key
    )
  )

df_all_kw %>%
  write_tsv(snakemake@output[["kw_usage"]])

df_all_kw %>%
  left_join(df_machines_pretty, by = c("filepath")) %>%
  group_by(vendor_short, ms, key) %>%
  mutate(tot = n()) %>%
  group_by(vendor_short, ms, software_short, key) %>%
  summarize(
    used = mean(used),
    .groups = "drop"
    ) %>%
  mutate(
    category = case_when(
      str_starts(key, "Pn") ~ "meas",
      key %in% c("Gn*", "GATING") ~ "gate",
      key %in% c("PKNn", "PKn") ~ "peak",
      key %in% c("LAST_MODIFIER", "LAST_MODIFIED", "ORIGINALITY") ~ "mod",
      key %in% c("UNSTAINEDCENTERS", "UNSTAINEDINFO") ~ "spillref",
      key %in% c("PLATEID", "PLATENAME", "WELLID") ~ "plate",
      key %in% c("CARRIERID", "CARRIERTYPE", "LOCATIONID") ~ "carrier",
      key %in% c("CSTOT", "CSVFLAGS", "CSVBITS") ~ "subset",
      key %in% c("DATE", "ETIM", "BTIM", "BEGINDATETIME", "ENDDATETIME") ~ "time",
      TRUE ~ "misc"
    )
  ) %>%
  mutate(
    used = case_when(
      used == 1.0 ~ "all",
      used == 0.0 ~ "none",
      used < 0.1 ~ "<10%",
      used < 0.9 ~ "10-90%",
      TRUE ~ ">90%"
    )
  ) %>%
  ggplot(
    aes(
      key,
      fct_rev(ms),
      color = fct_relevel(used, "all", ">90%", "10-90%", "<10%", "none")
    )
  )+
  geom_point() +
  facet_grid(
    vendor_short~ category,
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
      "all" = "#000000"
    )
  )  +
  labs(x = NULL, y = NULL, color = "Fraction\nkey usage") +
  theme(
    axis.text.x = element_text(angle = 90, hjust = 1.0, vjust = 0.5),
    strip.text.y.left = element_text(angle = 0),
    strip.text.x.top = element_text(angle = 90),
    legend.position="bottom"
  ) 
ggsave(snakemake@output[["plot_kw_usage"]], width = WIDTH, height = HEIGHT, dpi = DPI)
