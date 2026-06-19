* Simple NMOS cascode stage.
.subckt cascode_stage vin vout vss vbias_tail vbias_cas
M1 ncas vin tail vss nch w=10u l=180n
M2 vout vbias_cas ncas vss nch w=10u l=180n
M3 tail vbias_tail vss vss nch w=20u l=180n
.ends cascode_stage
