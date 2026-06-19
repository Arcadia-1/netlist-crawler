* Hierarchical example for expansion tests.
.subckt diff_core vinp vinn voutp voutn vss vbias
M1 voutp vinp tail vss nch w=10u l=180n
M2 voutn vinn tail vss nch w=10u l=180n
M3 tail vbias vss vss nch w=20u l=180n
.ends diff_core

.subckt load_core voutp voutn vdd
M4 voutp voutp vdd vdd pch w=20u l=180n
M5 voutn voutp vdd vdd pch w=20u l=180n
.ends load_core

.subckt ota_top vinp vinn voutp voutn vdd vss vbias
XCORE vinp vinn voutp voutn vss vbias diff_core
XLOAD voutp voutn vdd load_core
.ends ota_top
