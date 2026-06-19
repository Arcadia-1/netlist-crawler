* Parameter metadata example.
.param WBIAS=20u LMIN=180n

.subckt param_amp vin vout vss vbias WN=10u LN=LMIN
M1 vout vin tail vss nch w=WN l=LN
M2 tail vbias vss vss nch w=WBIAS l=LMIN
.ends param_amp
