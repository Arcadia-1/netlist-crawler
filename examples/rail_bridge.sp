* Structural path exists only through a common rail.
.subckt rail_bridge a b vdd vss
M1 a en vdd vdd pch w=1u l=180n
M2 b enb vdd vdd pch w=1u l=180n
.ends rail_bridge
