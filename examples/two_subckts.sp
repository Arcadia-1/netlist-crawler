* Two independent subcircuits for topcell selection tests.
.subckt gain_stage vin vout vdd vss vbias
M1 vout vin tail vss nch w=10u l=180n
M2 tail vbias vss vss nch w=20u l=180n
.ends gain_stage

.subckt bias_block vbias vdd vss
M3 vbias vbias vdd vdd pch w=5u l=180n
R1 vbias vss 100k
.ends bias_block
