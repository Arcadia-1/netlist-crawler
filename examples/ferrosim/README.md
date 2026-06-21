# ferrosim netlist import

Source: https://github.com/Arcadia-1/ferrosim

Curated Spectre netlist examples imported from ferrosim test decks.

Included:

- Real test decks under `tests/`, including ported analog blocks, SAR ADC blocks, opamps, comparators, sampling switches, and small Verilog-A demos.
- One compact transistor-characterization set under `tests/decks/transistor_char/` (`gm/Id`, DIBL, and Ron sweeps).
- The SAR ADC `with_mos` variant; the duplicate `stripped` variant was omitted to avoid repeated shared blocks.

Excluded:

- `output/char_netlists/` characterization sweep decks; they are mostly one-template-per-corner/length/temperature expansions.

Total netlist files: 122

## Directory counts

| Directory | Files |
|---|---:|
| `tests/decks/amp5t` | 5 |
| `tests/decks/biquad` | 16 |
| `tests/decks/bsimbulk` | 3 |
| `tests/decks/cap_meas.scs` | 1 |
| `tests/decks/comparator` | 14 |
| `tests/decks/inbuf` | 7 |
| `tests/decks/ldo.scs` | 1 |
| `tests/decks/opamp` | 8 |
| `tests/decks/ported` | 17 |
| `tests/decks/refbuf` | 3 |
| `tests/decks/restrim` | 3 |
| `tests/decks/ring5.scs` | 1 |
| `tests/decks/sampling_bts` | 7 |
| `tests/decks/sar` | 18 |
| `tests/decks/sc_counter` | 3 |
| `tests/decks/sc_integrator.scs` | 1 |
| `tests/decks/sc_ring` | 2 |
| `tests/decks/transistor_char` | 3 |
| `tests/decks/va_decl_init.scs` | 1 |
| `tests/sc_sample/sc_sample.scs` | 1 |
| `tests/va_demo/tb_chain.scs` | 1 |
| `tests/va_demo/tb_cswitch_res.scs` | 1 |
| `tests/va_demo/tb_cswitch_short.scs` | 1 |
| `tests/va_demo/tb_degsh.scs` | 1 |
| `tests/va_demo/tb_diode.scs` | 1 |
| `tests/va_demo/tb_sqlaw.scs` | 1 |
| `tests/va_demo/tb_tee.scs` | 1 |

## Manifest

| Path | Bytes | SHA256 |
|---|---:|---|
| `tests/decks/amp5t/netlist/dut/amp_5t_d2s.scs` | 461 | `5ca6e86bce133ac92d93520f0a240e733bd3b4cd7ace2ba36407551db3cb20df` |
| `tests/decks/amp5t/netlist/runs/common_setup.scs` | 2477 | `c8a441ba688e2157788df9173cf4093da876748054e3e15d0f6eeeb42b2f12f7` |
| `tests/decks/amp5t/netlist/runs/vdd_0p9.scs` | 74 | `4e3f70f41af98c38ec3e4bd3577dc94553541ecb56aa61b983cce2a5424ec038` |
| `tests/decks/amp5t/netlist/runs/vdd_1p0.scs` | 74 | `54d43f9a41c6f796a59b0a08f1fffc212a6605ecb7072f0715b9ec2803746c3f` |
| `tests/decks/amp5t/netlist/tb/tb_amp_5t_d2s_dc_ac.scs` | 438 | `8f1d0bb2df59b70fecd3d86ae033b95103885154be32d2e585446cd30273412f` |
| `tests/decks/biquad/netlist/dut/hs_biquad_ota.scs` | 13857 | `df6f6b108539a6df0a92ef197639d73e9e836d5aba4b36704d911934ee1c8b6b` |
| `tests/decks/biquad/netlist/dut/hs_biquad_ota_geometry.scs` | 100660 | `adbaf0dc56479284cb31e1f52cad3c8b2777d7e4fd3966a3f402c9a1a70c6f96` |
| `tests/decks/biquad/netlist/runs/common_ac_noise.scs` | 1339 | `b833b46d79b4ccd1bf6067e94097ef19ecdc68c65d53b6b76bdcbcc6fb6e4784` |
| `tests/decks/biquad/netlist/runs/common_ac_noise_geometry.scs` | 1357 | `7fae76bad2ff2cd1ee4048d8c963b1aa1951851d39bef94434248be198b0aeea` |
| `tests/decks/biquad/netlist/runs/common_setup.scs` | 1636 | `50256e01bc7ecab41ca0f5ae8f72ec46a45eac452370d0578fe144730a7ebaaa` |
| `tests/decks/biquad/netlist/runs/common_setup_geometry.scs` | 1654 | `3557537c8b57a636139fcfb7ac1cc5ab8c5f674a5d34f1e487150a78b760c938` |
| `tests/decks/biquad/netlist/runs/vdd_1p1.scs` | 74 | `42415cfd1bb8e2edb8e7b27d9d76766f5596ae5a7926b2fdd03371c4b0d260f9` |
| `tests/decks/biquad/netlist/runs/vdd_1p1_geometry.scs` | 83 | `df1264c4edbdb2e41a7249621f010d516cd54c1a78ed827b02ad494ffa0110a3` |
| `tests/decks/biquad/netlist/runs/vdd_1p2.scs` | 74 | `dd5fa2f29211542eac15614342c8b7aa4a8887a4ff8b8adb54daee7d12c3ddd0` |
| `tests/decks/biquad/netlist/runs/vdd_1p2_ac_noise.scs` | 77 | `bd94e42870445625b065c19bd6ef13160e49f31487c39357c0da2bab799f009f` |
| `tests/decks/biquad/netlist/runs/vdd_1p2_ac_noise_geometry.scs` | 86 | `04a1b2e201bda8919fd93a197a94ee82765a574cc94d712bbfeb00d76c1c2d61` |
| `tests/decks/biquad/netlist/runs/vdd_1p2_geometry.scs` | 83 | `670fca9417e6f8246cc2422c3c166b917c78120e62c77b99eedaf44ccbf977e6` |
| `tests/decks/biquad/netlist/runs/vdd_1p3.scs` | 74 | `d42cdbf8ae2cd29df8fce2661e449126da0fed42423ab2f14261a3e6ef675601` |
| `tests/decks/biquad/netlist/runs/vdd_1p3_geometry.scs` | 83 | `b7e83d671d0046cf3f89cb75b2a85bcb9284add2146e46e5dcdf63a38e1bf695` |
| `tests/decks/biquad/netlist/tb/tb_biquad_exp.scs` | 1135 | `bf03866eb36a9c3110b0c61dd8f25a0693fa3cc5a0eba4c1e70478881fefe8ff` |
| `tests/decks/biquad/netlist/tb/tb_biquad_exp_geometry.scs` | 2038 | `4a59a3d031866119493371857ef298a67eb9aebea0b73096b66bc0865afa7a91` |
| `tests/decks/bsimbulk/bench_nmos.scs` | 518 | `51bc01b6e66793a6cc5737c478c7c58cee12618b856b1a7aaae62b7c6161e12a` |
| `tests/decks/bsimbulk/nmos_iv.scs` | 573 | `714fedec43125ec29ecc404078ead10b1c5949fd32f9957954b00b08c7ab21f8` |
| `tests/decks/bsimbulk/pmos_iv.scs` | 527 | `ba02ad7fb33904637adb8302f38de57f7cafde1a25ea3bd96da4cf0e1a2f5c32` |
| `tests/decks/cap_meas.scs` | 1118 | `cec6650d0663506db5f0ad18e1841638d5f2a7cb21b546696d6374286c1e6e43` |
| `tests/decks/comparator/netlist/dut/cmp_strongarm.scs` | 1281 | `bf70e886fe8be2d565b7c4a8f20bc03710c7a4d7e03fc94fd4e9e61ec40b8b6c` |
| `tests/decks/comparator/netlist/dut/cmp_strongarm_offset_trim.scs` | 3583 | `c5770a8d11823688fb63603281d273ce9f0cfa0867537464f88a1642fce6e226` |
| `tests/decks/comparator/netlist/dut/cmp_under_test_offset_trim.scs` | 316 | `c6d2b3a87fd6491da6dbf4381fd1edd8800f88b1bed2344fa6b2f2c54e28908a` |
| `tests/decks/comparator/netlist/dut/cmp_under_test_plain.scs` | 236 | `c022555c306dc9f473baf67d0087df30bed63d3be3bf130708b0c07cf3cd684c` |
| `tests/decks/comparator/netlist/runs/mc_offset_offset_trim.scs` | 1422 | `9fc379d5ee1e16123d8a4219d6e6e5dfb872c1fa55f7b64e2c6c6fbd1ca39883` |
| `tests/decks/comparator/netlist/runs/mc_offset_plain.scs` | 1403 | `1ccc1bf981f0a274950d0f6c16c60b92599b5223459c00334d97e36f71f40776` |
| `tests/decks/comparator/netlist/runs/offset_offset_trim.scs` | 1142 | `3b62e5162848b8607eaabcb0d4db52339ee3d1d8264d422fabe1c584aeda479c` |
| `tests/decks/comparator/netlist/runs/offset_plain.scs` | 1123 | `016930c059fef21442ae182f66a8c8e9b63a6442a712f76be4eb6298121240db` |
| `tests/decks/comparator/netlist/runs/pss_pnoise_offset_trim.scs` | 1291 | `0caf944b211c5168752dd4d53fa0a032c942cc63e4fd7385a33fb19507b55251` |
| `tests/decks/comparator/netlist/runs/pss_pnoise_plain.scs` | 1272 | `2436c61cffb64c2fe6a4210497184f6afeb9dd8984f04f719d420b61982750ae` |
| `tests/decks/comparator/netlist/runs/pvt_pss_pnoise_offset_trim.scs` | 1993 | `d4b447b2aa0c307b82a6f9f4e93a76fb2b28fa34f702aae7a0cb38ccdef83d2f` |
| `tests/decks/comparator/netlist/runs/pvt_pss_pnoise_plain.scs` | 1992 | `df5ddc7e559903f11c4a7532ec3380f8e0a69c3257be0b072df145ffb007b6b8` |
| `tests/decks/comparator/netlist/tb/tb_cmp_offset_search.scs` | 530 | `9ef03c60d0c9e860bfeb463caba38f12f6010299659b10421f5b3a2b5441979e` |
| `tests/decks/comparator/netlist/tb/tb_cmp_pss_pnoise.scs` | 537 | `fc03fc73184e4956bff4539353b6e4bed879e962ca4914a6d5b478e45dbbf012` |
| `tests/decks/inbuf/netlist/dut/l1_input_buffer_cascode.scs` | 15981 | `3b223abfd9f402e68061338ffb5e1d67afdb4fd12d110be5b4b65b7832a6cfe4` |
| `tests/decks/inbuf/netlist/runs/pss_100M.scs` | 814 | `997be7a10615f0086a855132f02bfd3af5770d26c8c803863159ac64944127d1` |
| `tests/decks/inbuf/netlist/runs/pss_1G.scs` | 812 | `6e700552dc8ee641b536c6da92945f24ba11b108e33df599a1a978297d398403` |
| `tests/decks/inbuf/netlist/runs/pss_2G.scs` | 812 | `b0163f435abf864ac73d355669fc61e71b91edda6c65d2adc5c469c729bddbf5` |
| `tests/decks/inbuf/netlist/runs/pss_4G.scs` | 812 | `2d09b3491bb232150b2250fffe315b47c3c4672be7d1bd51dd361ee12d4234a0` |
| `tests/decks/inbuf/netlist/runs/pss_8G.scs` | 812 | `aee98bb34387b44ff636b3cfda344d3f1007b205bca46cea6058717232296fe3` |
| `tests/decks/inbuf/netlist/tb/tb_input_buffer_cascode_pss.scs` | 564 | `d1d0126176e4f6f5e0da00a87667cb038a0b28e2c110c1ef844b167438c6f3a5` |
| `tests/decks/ldo.scs` | 1849 | `64818c200c0e257ac9a6a5c6f283968feee52346f2ae21a34e0080c0a6b6e1dc` |
| `tests/decks/opamp/netlist/dut/ota_fd2s.scs` | 4306 | `4a4558925b8bf72a1e40e0dfa5b989244f5a7dcd3ab24eca6c8a34dc65be1c34` |
| `tests/decks/opamp/netlist/runs/cl_tran.scs` | 821 | `4f05a9ab54e2696249d3645d31f11380add62935df28e01aae94780fec464bd1` |
| `tests/decks/opamp/netlist/runs/mc_offset.scs` | 777 | `993992cea1152248a5216047fea4ef33a6e9b7699128fd89cca0e558181d365c` |
| `tests/decks/opamp/netlist/runs/ol_cmrr.scs` | 765 | `64d8b9ec30cfcaf24b296ca88f38d0ef0e1a7d42925d9701cdd30ea1e2863c83` |
| `tests/decks/opamp/netlist/runs/ol_main.scs` | 1225 | `f61f718a01707f9f03c1f94145ed1068cc259cf33990e08080b31683795e8182` |
| `tests/decks/opamp/netlist/runs/ol_psrr.scs` | 794 | `29bf280b6fc39176ff3768c70393fb68bd1428a63b259975272203ab6456203a` |
| `tests/decks/opamp/netlist/tb/tb_closedloop.scs` | 1397 | `b7923e2241b1acf624878335b05f3ba425b9e104c8667f6d13c0accd8462bf70` |
| `tests/decks/opamp/netlist/tb/tb_openloop.scs` | 976 | `e6203272e77ac6cf38d5a89392ab6a538f1578d2430bd5b9ff5aa47677b4d298` |
| `tests/decks/ported/bandgap_core_28.scs` | 1348 | `6df671f491632b5f4e3963a0dc714e617f2147c055e46430c182645b498e591f` |
| `tests/decks/ported/bandgap_core_65.scs` | 1323 | `d04e6c8aa87346517a9280ed3ea24765c4e5062181e144a82e0b3a1768ee8a69` |
| `tests/decks/ported/bjt_cal_28.scs` | 412 | `e871ecb0ce9941b12129a4aa1cc6a9db11b38b2c88fbdd0ba28453d750c1ce18` |
| `tests/decks/ported/common_source_28.scs` | 1036 | `21bca650cb49d43c34c9c294ea58e42ff6deafb885e2aaff503a096c8da44e07` |
| `tests/decks/ported/common_source_65.scs` | 1033 | `2fba08455078e75733e6665ddce0ed2e7b7d1eda89ffba7ea4d4f13ec1c8f46d` |
| `tests/decks/ported/differential_pair_28.scs` | 696 | `a19bf5af1be7cc8e01918ebda88229245f6c4197f8b849605fc5c97c6da99981` |
| `tests/decks/ported/differential_pair_65.scs` | 725 | `74aa9bf2e4be8a6fbda9d060f852103fc14ecb33c0e7394b9956046f3ec74cbb` |
| `tests/decks/ported/hyst_comparator_28.scs` | 1109 | `0b25fc36d54d12239c761ee9ee2ec794a4cb0a8f84ab3ae1cf612b1b247ba8fa` |
| `tests/decks/ported/hyst_comparator_65.scs` | 1094 | `30dc88feaf31d6c5635187b93e316f3c4de9cc510045ad43b8940cdb0503670c` |
| `tests/decks/ported/ldo_28.scs` | 1076 | `1c1bee7c89a1a6f2a73e9996a336b0dfe87702d66c0d6d5b6bc638351f683431` |
| `tests/decks/ported/ldo_65.scs` | 1081 | `81b7478620eb9a1c222c516dcb6e6355681ac780ab5965f1892dd1a89f3819a7` |
| `tests/decks/ported/lfsr8_28.scs` | 1836 | `4d45bc396e41fb896bc561ba1325e5b62be5fad4c16897dfe7008b48b85c5850` |
| `tests/decks/ported/pga_16step_28.scs` | 2304 | `d7340934b2cab9ba5153a4508f4a44a09f36ea99b9dcd168e265ec8099f15e43` |
| `tests/decks/ported/source_follower_28.scs` | 776 | `0bc5635db5573a8033e03f63b23880da99244b8a5c6e77b9287e4c4c6037ac34` |
| `tests/decks/ported/source_follower_65.scs` | 786 | `c6bb31dd0131d0a83c31b7024f1ff14ab3070786bcf681640266431ca285cb87` |
| `tests/decks/ported/two_stage_opamp_28.scs` | 948 | `dd5b696fad0e1f7a45ff534f2d850c60d6398c70bea2933db3667391bf8df2e0` |
| `tests/decks/ported/two_stage_opamp_65.scs` | 949 | `36b5ca458ba79642667746ba5ec27b217f2865a291a0eaf3396ff8f258e29ee4` |
| `tests/decks/refbuf/netlist/dut/ref_buffer_blocks.scs` | 2895 | `9f07578fca987c9a6169330f74e36a4a0931066455ce388426608a77f57ac9a2` |
| `tests/decks/refbuf/netlist/runs/dc_ac_tran_noise.scs` | 2691 | `75e8e890789eb88fabe036d72ea0446c95b8ab3e5b5b607e9eea7e9e42152c8c` |
| `tests/decks/refbuf/netlist/tb/tb_ref_buffer_characterization.scs` | 1103 | `4ceb30c44256c258a3842021cc61a37fe006a80ca2571ebcd5c8fea4e4456bce` |
| `tests/decks/restrim/netlist/dut/res_trim_thermo_16.scs` | 2578 | `087324f5d9b90a6d33862dbb7219e6a618faef83503bfd717adf4a2653ed4504` |
| `tests/decks/restrim/netlist/runs/dc_trim_resistance.scs` | 1788 | `cdd4b1640b2c381ecdc7be8296e39ed0c546a08e9c7b6b64ef05d3966c0ece38` |
| `tests/decks/restrim/netlist/tb/tb_resistance_dc.scs` | 856 | `11c7b2e68d5b2c55a8967acf8aa383fca32c6b2cdda3c87d62eca7580d164fc2` |
| `tests/decks/ring5.scs` | 1144 | `a6fa1708cd2bdacf70a72c4e96aca2b972458c5ad4e2dd8dad022d40bff42b68` |
| `tests/decks/sampling_bts/netlists/bootstrap.scs` | 8367 | `77cde6f2ed79e6da2306f7491382b987576a12643793f33fe53e5d2325d72d64` |
| `tests/decks/sampling_bts/netlists/bottom_plate_dut.scs` | 2921 | `5407fbef2e0d8c18865aecf508c7a89ab62615b7a4f68b7c9aac6b8d89f82238` |
| `tests/decks/sampling_bts/netlists/bottom_plate_ideal_bts.scs` | 2638 | `1b123f30b9b967e467a37ee7f166061bfbe7361d8b4be3bb390f4f6d8baa5ac4` |
| `tests/decks/sampling_bts/netlists/bottom_plate_real_bts.scs` | 2615 | `dd04515d55809849a136933e4c2e833277773c9db25fc383abe30d66befec5d8` |
| `tests/decks/sampling_bts/netlists/top_plate_dut.scs` | 1336 | `20b7f7818d73bfa8ba4f46e68d9c4e468ec807512944c6264bba2946ddf06df6` |
| `tests/decks/sampling_bts/netlists/top_plate_ideal_bts.scs` | 1676 | `10c46d517a419f5bb85f05fa050ab1f024048a74bd47d1daadbe5e4d0132eeca` |
| `tests/decks/sampling_bts/netlists/top_plate_real_bts.scs` | 1691 | `0bd16f9cb30350f530426a5efa9502f53151555e004e89358bff0e08ece18859` |
| `tests/decks/sar/netlists/sampling_bootstrap_l4_bts_x2.scs` | 396 | `d188efcb1353ca3e13890da9cd785942299061f3579fc3fb87c2d1b01f5978f6` |
| `tests/decks/sar/netlists/sar_adc_11b_sampling_bts_with_mos.scs` | 923 | `0e28dc1a92f8d1e72f75846f8299076847a1b53ff563f471020482fe6359891e` |
| `tests/decks/sar/netlists/sar_adc_11b_with_mos.scs` | 929 | `389d571300e4bcbc778f53d5bc3735ec88c5fb6dc05bf5c506d4aa922bc66a31` |
| `tests/decks/sar/netlists/variants/with_mos/00_corner_and_models.scs` | 1940 | `7fd76f7a198483c5b028ef36e649a23e96d0d54c61acf90c77994944d75ebfe1` |
| `tests/decks/sar/netlists/variants/with_mos/10_refgen_ideal.scs` | 394 | `837d32f814d2acc4dc923fb69398087504df5da847aa5db888e2075cbd49b51b` |
| `tests/decks/sar/netlists/variants/with_mos/20_comparator_dynamic_l4.scs` | 19380 | `b34e6dfe544c33a46595ec4ec610b107dd8b06f6add3ff8c06611ee5a3e0a8e0` |
| `tests/decks/sar/netlists/variants/with_mos/30_bottom_plate_switch_l5.scs` | 11641 | `1b211d9c9b7eb579587946d9763dccda6a7dc8fc87be99df6e30112eeafdbf6c` |
| `tests/decks/sar/netlists/variants/with_mos/40_sar_latch_cell_l5.scs` | 7413 | `e4b37ff0fa74de483a9e56bdc7d70cfaa48870db0ddce72425035d6ecfe19497` |
| `tests/decks/sar/netlists/variants/with_mos/41_sar_latch_lsb_l5.scs` | 7350 | `4114a76bf3534b24400ef17d086cea2de3446c00db736f4c32c50f64c8ef4346` |
| `tests/decks/sar/netlists/variants/with_mos/42_sar_logic_switch_l4.scs` | 7193 | `514950cc7c12bbaa54709dc3132be5bcd0cd3db50a74bc9ead243dbdb0bd86f1` |
| `tests/decks/sar/netlists/variants/with_mos/50_cap_unit_x1.scs` | 282 | `3ffcf0c349332eae2752e8808fe49b069116f227462b735c4ac735552621bf56` |
| `tests/decks/sar/netlists/variants/with_mos/51_cap_unit_x3.scs` | 354 | `818bc1493f4a42a090bcaaf78931cf6e9d4944de8998a5c0359c191f876a44c6` |
| `tests/decks/sar/netlists/variants/with_mos/52_cap_array_l5.scs` | 16508 | `54cd1a338e90d1b8ea0caf16638cd70e0c5659d4c24dbe5f644282f0270e27cd` |
| `tests/decks/sar/netlists/variants/with_mos/53_cdac_sampler_l4.scs` | 2565 | `e2aa6f2136241bf48373efc3bcfcac6a0fce791a511e23637c7c48ad9e0e1316` |
| `tests/decks/sar/netlists/variants/with_mos/60_bootstrap_core_lb.scs` | 6337 | `1ef6323ea0b16d13f3ad961fbfa2e5bb880c84e8e98bdb1e65a1af1deeeaee1c` |
| `tests/decks/sar/netlists/variants/with_mos/61_bootstrap_diff_l4.scs` | 351 | `0890636ea0aa2eabe18dee6008490d704c090e2d1f6d8e4f2eddc70364d91900` |
| `tests/decks/sar/netlists/variants/with_mos/90_sar_adc_11b_l3.scs` | 1924 | `fc155a9f59886385fafa807e305416095674055b79dff279abfd31e9c9719c00` |
| `tests/decks/sar/netlists/variants/with_mos/99_tb_sar_adc_11b_interactive13.scs` | 2346 | `2da8acde8972c390f18f9eb778e2a2265387009ac224f63f9c870d8b83c2d766` |
| `tests/decks/sc_counter/netlist/dut/counter_prog_4b.scs` | 1990 | `42a973b738f8d4af4355c657df4d12e4a30121c292340ad989f97f5bf9e36b08` |
| `tests/decks/sc_counter/netlist/runs/tran_counter_prog_4b.scs` | 2076 | `ba31e064daff9c40ef45ec0f882fec187dc002382f049e73e68127c2a3b44baf` |
| `tests/decks/sc_counter/netlist/tb/tb_counter_prog_4b.scs` | 597 | `8570a20237fbc4f610cb46c2a992dae6a863ad47941a9232121f409af715a53d` |
| `tests/decks/sc_integrator.scs` | 1910 | `67857807eb388f5a3f5fd47350e65b97e835d03fe5d05fb6b273a671a962e6ec` |
| `tests/decks/sc_ring/netlists/ring_osc_lvt.scs` | 938 | `9c8f4b0bdea795679439e6603f2a0ae49d3790f828823a914a20e7514cf07316` |
| `tests/decks/sc_ring/netlists/ring_osc_svt.scs` | 926 | `6f8b2bcb91f97bcd9737398ddad4725d99b0f047c03a7f09d4deb7c0d2b808bb` |
| `tests/decks/transistor_char/dc_vds_dibl_ulvt.scs` | 1007 | `7e12364843312f8162761ad1fdaba0eb7ee99bc0e1506bfdd8110dfa6085e0cb` |
| `tests/decks/transistor_char/dc_vds_ron_ulvt.scs` | 1067 | `633346b1d7b9dc64cc74c394627034c77fbce090121b3bef53f8ae4741846a76` |
| `tests/decks/transistor_char/dc_vgs_gmid_ulvt.scs` | 1039 | `ea3b85b0b51659b044eacbea23cfffcec6bdcabd5f516de805bef6cf2dcba37e` |
| `tests/decks/va_decl_init.scs` | 1110 | `47b9ef3536d93ff8d9faf5141c6f47f4449f24b06cd6b71586023339daa3943a` |
| `tests/sc_sample/sc_sample.scs` | 939 | `ea075347dd6b9ca93909b4049309c87fac67d75b525fb93ed92f7b18360c4869` |
| `tests/va_demo/tb_chain.scs` | 231 | `49b89a4296c78ec6b2aed4fd51fcb17927cec5ae2f91d5e87aa3e1b6e939d82e` |
| `tests/va_demo/tb_cswitch_res.scs` | 245 | `7653ff5e9306111a3f09c45ebb28ebc73a80ce7ef7c3b9d62f8f34e44673ace8` |
| `tests/va_demo/tb_cswitch_short.scs` | 246 | `d34fefef35d2e4d54a8d99de67550191ad1f3a66f45b65c2171bf0dc467f56a0` |
| `tests/va_demo/tb_degsh.scs` | 235 | `9b3a36b5590ad8ea570d9bf2fde86f82bd22a72157c76b54a2b5528fcd9f5b32` |
| `tests/va_demo/tb_diode.scs` | 496 | `883997c6ea9e6270bfcc2414a1991c7f4981c37bf2d9882c7c4edeb6bbda9f7a` |
| `tests/va_demo/tb_sqlaw.scs` | 239 | `098e50f28ad8870fdb59e748bdfe7c566145a60b02aea5538f3e72c0276cffba` |
| `tests/va_demo/tb_tee.scs` | 216 | `11ff0b334f55a209a03c4e7b56ff90dff4d0d07800e01f90e7a550f05000256e` |
