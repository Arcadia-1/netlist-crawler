* Simple NMOS differential pair example for early CLI tests.
.subckt simple_diff_pair vinp vinn voutp voutn vdd vss vbias
M1 voutp vinp tail vss nch w=10u l=180n
M2 voutn vinn tail vss nch w=10u l=180n
M3 tail vbias vss vss nch w=20u l=180n
M4 voutp voutp vdd vdd pch w=20u l=180n
M5 voutn voutp vdd vdd pch w=20u l=180n
.ends simple_diff_pair
