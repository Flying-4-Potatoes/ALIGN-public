************************************************************************
* auCdl Netlist:
* 
* Library Name:  OTA_class
* Top Cell Name: single_ended_cascode_current_mirror
* View Name:     schematic
* Netlisted on:  Sep 11 21:41:11 2019
************************************************************************

*.BIPOLAR
*.RESI = 2000 
*.RESVAL
*.CAPVAL
*.DIOPERI
*.DIOAREA
*.EQUATION
*.SCALE METER
*.MEGA
.PARAM

*.GLOBAL vdd!
+        gnd!

*.PIN vdd!
*+    gnd!

************************************************************************
* Library Name: OTA_class
* Cell Name:    single_ended_cascode_current_mirror
* View Name:    schematic
************************************************************************

.SUBCKT single_ended_cascode_current_mirror Vbiasn Vbiasn2 Vbiasp2 Vinn Vinp 
+ Voutn
*.PININFO Vbiasn:I Vbiasn2:I Vbiasp2:I Vinn:I Vinp:I Voutn:O
MM12 net12 Vbiasp2 net37 vdd! pmos w=WA l=LA nfin=nA
MM11 net23 Vbiasp2 net36 vdd! pmos w=WA l=LA nfin=nA
MM10 net10 Vbiasp2 net35 vdd! pmos w=WA l=LA nfin=nA
MM9 Voutn Vbiasp2 net34 vdd! pmos w=WA l=LA nfin=nA
MM2 net37 net12 vdd! vdd! pmos w=WA l=LA nfin=nA
MM1 net36 net23 vdd! vdd! pmos w=WA l=LA nfin=nA
MM6 net35 net12 vdd! vdd! pmos w=WA l=LA nfin=nA
MM5 net34 net23 vdd! vdd! pmos w=WA l=LA nfin=nA
MM14 net10 Vbiasn2 net33 gnd! nmos w=WA l=LA nfin=nA
MM13 Voutn Vbiasn2 net31 gnd! nmos w=WA l=LA nfin=nA
MM3 net23 Vinp net17 gnd! nmos w=WA l=LA nfin=nA
MM0 net12 Vinn net17 gnd! nmos w=WA l=LA nfin=nA
MM4 net17 Vbiasn gnd! gnd! nmos w=WA l=LA nfin=nA
MM8 net33 net10 gnd! gnd! nmos w=WA l=LA nfin=nA
MM7 net31 net10 gnd! gnd! nmos w=WA l=LA nfin=nA
.ENDS


.SUBCKT LG_load_biasn_LV Vbiasn2 Biasp
*.PININFO Biasp:I Vbiasn2:O
MM13 net9 Vbiasn2 gnd! gnd! nmos w=WA l=LA nfin=nA
MM15 Vbiasn2 Vbiasn2 net9 gnd! nmos w=WA l=LA nfin=nA
MM14 Vbiasn2 Biasp vdd! vdd! pmos w=WA l=LA nfin=nA
.ENDS

.SUBCKT CR6_3 Vbiasn1 Vbiasn2 Vbiasp
*.PININFO Vbiasn1:O Vbiasn2:O Vbiasp:O
MM2 Vbiasp Vbiasn2 Vbiasn1 gnd! nmos w=WA l=LA nfin=nA
MM0 Vbiasn2 Vbiasn1 gnd! gnd! nmos w=WA l=LA nfin=nA
MM4 Vbiasn1 net15 gnd! gnd! nmos w=WA l=LA nfin=nA
MM5 net15 net15 gnd! gnd! nmos w=WA l=LA nfin=nA
MM3 Vbiasp Vbiasp vdd! vdd! pmos w=WA l=LA nfin=nA
MM1 Vbiasn2 Vbiasp vdd! vdd! pmos w=WA l=LA nfin=nA
MM6 net15 Vbiasp vdd! vdd! pmos w=WA l=LA nfin=nA
.ENDS


xiota LG_Vbiasn LG_Vbiasn2 LG_Vbiasp2 Vinn Vinp single_ended_cascode_current_mirror
xiLG_load_biasn_LV Biasp LG_Vbiasn2 LG_load_biasn_LV
xibCR6_3 Biasn1 Biasn2 Biasp CR6_3
.END