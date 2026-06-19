* Top cell that depends on an included subckt file.
.include "include_blocks/diff_core.inc"

.subckt include_top vinp vinn voutp voutn vss vbias
XCORE vinp vinn voutp voutn vss vbias inc_diff
.ends include_top
