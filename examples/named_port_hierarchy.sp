* Named-port hierarchy example for expansion tests.
.subckt inv in out vdd vss
M1 out in vss vss nch w=1u l=180n
M2 out in vdd vdd pch w=2u l=180n
.ends inv

.subckt top a y vdd vss
XINV out=y in=a vss=vss vdd=vdd inv
.ends top
