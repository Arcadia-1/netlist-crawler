* Included differential core.
.subckt inc_diff vinp vinn voutp voutn vss vbias
M1 voutp vinp tail vss nch w=10u l=180n
M2 voutn vinn tail vss nch w=10u l=180n
M3 tail vbias vss vss nch w=20u l=180n
.ends inc_diff
