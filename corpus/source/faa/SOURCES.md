# Where the FAA documents come from

Every file in this folder is a US government work, published by the FAA, the Federal Register, or NACA, and free
to reuse. They were downloaded between 23 and 30 October 2026 and are committed unchanged, except three
excerpts made with `scripts/excerpt_pdf.py`: `ac/ac-43.13-1b-chapter-7.pdf` (pages 313 to 380 of the
full advisory circular) and the two chapters in `handbook/` (pages 55 to 102 and 633 to 642 of the
full handbook).

- Each airworthiness directive is the Federal Register's printed PDF of the final rule. A printed page holds
  more than one rule, so a PDF often starts with the end of the previous rule and ends with the start of the
  next one, for other aircraft. Three of the files are corrections to a rule published earlier.
- The type certificate data sheet was downloaded through the viewer of the FAA's Dynamic Regulatory System;
  its download link does not accept scripted requests.
- The four regulations are the eCFR's XML for 14 CFR as of 15 October 2026.

| File | Document | Source |
| --- | --- | --- |
| `ac/ac-39-7d.pdf` | AC 39-7D, Airworthiness Directives | [link](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC%2039-7D.pdf) |
| `ac/ac-43-9c.pdf` | AC 43-9C, Maintenance Records (cancelled 22 September 2025) | [link](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC43-9C.pdf) |
| `ac/ac-43-9d.pdf` | AC 43-9D, Maintenance Records | [link](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_43-9D.pdf) |
| `ac/ac-43.13-1b-chapter-7.pdf` | AC 43.13-1B, Acceptable Methods, Techniques, and Practices: Aircraft Inspection and Repair, chapter 7 (aircraft hardware, control cables, and turnbuckles) | [link](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC_43.13-1B_w-chg1.pdf) |
| `ac/ac-43.13-2b.pdf` | AC 43.13-2B, Acceptable Methods, Techniques, and Practices: Aircraft Alterations | [link](https://www.faa.gov/documentLibrary/media/Advisory_Circular/AC%2043.13-2B.pdf) |
| `ad/ad-2000-04-01.pdf` | AD 2000-04-01: Cessna Aircraft Company Models 172R, 172S, 182S, 206H, and T206H Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2000-02-22/pdf/00-3794.pdf) |
| `ad/ad-2001-06-17-correction.pdf` | AD 2001-06-17 (correction): Cessna Aircraft Company Models 172R and 172S Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2001-04-10/pdf/01-8746.pdf) |
| `ad/ad-2001-06-17.pdf` | AD 2001-06-17: Cessna Aircraft Company Models 172R and 172S Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2001-03-30/pdf/01-7831.pdf) |
| `ad/ad-2003-24-13-correction.pdf` | AD 2003-24-13 (correction): Cessna Aircraft Company Models 172R, 172S, 182S, 182T, T182T, 206H, and T206H Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2003-12-30/pdf/03-31667.pdf) |
| `ad/ad-2003-24-13.pdf` | AD 2003-24-13: Cessna Aircraft Company Models 172R, 172S, 182S, 182T, T182T, 206H, and T206H Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2003-12-04/pdf/03-30075.pdf) |
| `ad/ad-2004-10-15.pdf` | AD 2004-10-15: GARMIN International Inc. GTX 330 Mode S Transponders and GTX 330D Diversity Mode S Transponders | [link](https://www.govinfo.gov/content/pkg/FR-2004-05-21/pdf/04-11438.pdf) |
| `ad/ad-2004-15-18.pdf` | AD 2004-15-18: Cessna Aircraft Company Models 172R, 172S, 182S, 182T, T182T, 206H, and T206H Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2004-07-30/pdf/04-17217.pdf) |
| `ad/ad-2005-01-19.pdf` | AD 2005-01-19: GARMIN International Inc. GTX 33, GTX 33D, GTX 330, and GTX 330D Mode S Transponders | [link](https://www.govinfo.gov/content/pkg/FR-2005-01-19/pdf/05-832.pdf) |
| `ad/ad-2005-05-53-r1.pdf` | AD 2005-05-53 R1: The Cessna Aircraft Company Models 172R, 172S, 182T, and T182T Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2005-03-21/pdf/05-5385.pdf) |
| `ad/ad-2005-13-10.pdf` | AD 2005-13-10: Cessna Aircraft Company Models 172R, 172S, 182T, T182T, 206H, and T206H Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2005-06-22/pdf/05-12175.pdf) |
| `ad/ad-2006-17-04.pdf` | AD 2006-17-04: The Cessna Aircraft Company Models 172R, 172S, 182T, T182T, 206H, and T206H Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2006-08-18/pdf/E6-13442.pdf) |
| `ad/ad-2007-05-10.pdf` | AD 2007-05-10: Cessna Aircraft Company Models 172R, 172S, 182S, 182T, T182T, 206H, and T206H Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2007-03-07/pdf/E7-3834.pdf) |
| `ad/ad-2007-08-03.pdf` | AD 2007-08-03: Cessna Aircraft Company Models 172R, 172S, 182T, T182T, 206H, and T206H Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2007-04-12/pdf/E7-6826.pdf) |
| `ad/ad-2008-02-18.pdf` | AD 2008-02-18: Cessna Aircraft Company 172 and 182 Series Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2008-01-24/pdf/E8-1130.pdf) |
| `ad/ad-2008-03-02.pdf` | AD 2008-03-02: Cessna Aircraft Company Models 172R and 172S Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2008-01-31/pdf/E8-1460.pdf) |
| `ad/ad-2008-05-09.pdf` | AD 2008-05-09: Cessna Aircraft Company 172, 182, and 206 Series Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2008-03-04/pdf/E8-3771.pdf) |
| `ad/ad-2008-10-02.pdf` | AD 2008-10-02: Cessna Aircraft Company 172, 175, 180, 182, 185, 206, 207, 208, 210, and 303 Series Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2008-05-02/pdf/E8-9719.pdf) |
| `ad/ad-2008-26-10.pdf` | AD 2008-26-10: Cessna Aircraft Company 172, 175, 177, 180, 182, 185, 188, 206, 207, 208, 210, 303, 336, and 337 Series Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2008-12-24/pdf/E8-30465.pdf) |
| `ad/ad-2009-24-10.pdf` | AD 2009-24-10: Thielert Aircraft Engines GmbH (TAE) Model TAE 125-01 Reciprocating Engines | [link](https://www.govinfo.gov/content/pkg/FR-2009-11-27/pdf/E9-28166.pdf) |
| `ad/ad-2010-04-06.pdf` | AD 2010-04-06: Thielert Aircraft Engines GmbH (TAE) Model TAE 125-01 Reciprocating Engines | [link](https://www.govinfo.gov/content/pkg/FR-2010-02-23/pdf/2010-3117.pdf) |
| `ad/ad-2011-06-02.pdf` | AD 2011-06-02: Cessna Aircraft Company (Cessna) Model 172 Airplanes Modified by Supplemental Type Certificate (STC) SA01303WI | [link](https://www.govinfo.gov/content/pkg/FR-2011-04-21/pdf/2011-8564.pdf) |
| `ad/ad-2012-02-02.pdf` | AD 2012-02-02: Cessna Aircraft Company Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2012-02-07/pdf/2012-1451.pdf) |
| `ad/ad-2012-22-01.pdf` | AD 2012-22-01: Cessna Aircraft Company Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2012-11-23/pdf/2012-26500.pdf) |
| `ad/ad-2013-03-15.pdf` | AD 2013-03-15: Cessna Aircraft Company Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2013-02-12/pdf/2013-02897.pdf) |
| `ad/ad-2013-11-11.pdf` | AD 2013-11-11: Cessna Aircraft Company Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-2013-06-27/pdf/2013-14995.pdf) |
| `ad/ad-2018-02-04.pdf` | AD 2018-02-04: Aerospace Welding Minneapolis, Inc., Mufflers | [link](https://www.govinfo.gov/content/pkg/FR-2018-01-17/pdf/2018-00479.pdf) |
| `ad/ad-2019-01-02.pdf` | AD 2019-01-02: Aspen Avionics, Inc., Evolution Flight Display Units | [link](https://www.govinfo.gov/content/pkg/FR-2019-01-23/pdf/2019-00104.pdf) |
| `ad/ad-2020-16-08-correction.pdf` | AD 2020-16-08 (correction): Aspen Avionics, Inc. | [link](https://www.govinfo.gov/content/pkg/FR-2020-08-17/pdf/2020-17902.pdf) |
| `ad/ad-2020-16-08.pdf` | AD 2020-16-08: Aspen Avionics, Inc. | [link](https://www.govinfo.gov/content/pkg/FR-2020-07-31/pdf/2020-16592.pdf) |
| `ad/ad-97-12-06.pdf` | AD 97-12-06: Cessna Aircraft Company Model 172R Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-1997-07-09/pdf/97-17729.pdf) |
| `ad/ad-98-01-01.pdf` | AD 98-01-01: Cessna Aircraft Company Models 172R and 182S Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-1998-01-23/pdf/98-1297.pdf) |
| `ad/ad-98-02-05.pdf` | AD 98-02-05: Cessna Aircraft Company Model 172R Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-1998-02-05/pdf/98-2774.pdf) |
| `ad/ad-98-13-41.pdf` | AD 98-13-41: Cessna Aircraft Company Model 172R Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-1998-06-26/pdf/98-17020.pdf) |
| `ad/ad-98-14-07.pdf` | AD 98-14-07: Cessna Aircraft Company Model 172R Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-1998-07-01/pdf/98-17414.pdf) |
| `ad/ad-98-25-03.pdf` | AD 98-25-03: Cessna Aircraft Company Model 172R Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-1998-12-03/pdf/98-32044.pdf) |
| `ad/ad-99-18-14.pdf` | AD 99-18-14: Cessna Aircraft Company Model 172R Airplanes | [link](https://www.govinfo.gov/content/pkg/FR-1999-09-01/pdf/99-22536.pdf) |
| `cfr/14-cfr-part-145.xml` | 14 CFR Part 145: Repair Stations | [link](https://www.ecfr.gov/api/versioner/v1/full/2026-10-15/title-14.xml?part=145) |
| `cfr/14-cfr-part-39.xml` | 14 CFR Part 39: Airworthiness Directives | [link](https://www.ecfr.gov/api/versioner/v1/full/2026-10-15/title-14.xml?part=39) |
| `cfr/14-cfr-part-43.xml` | 14 CFR Part 43: Maintenance, Preventive Maintenance, Rebuilding, and Alteration | [link](https://www.ecfr.gov/api/versioner/v1/full/2026-10-15/title-14.xml?part=43) |
| `cfr/14-cfr-part-91-subpart-e.xml` | 14 CFR Part 91, subpart E: Maintenance, Preventive Maintenance, and Alterations | [link](https://www.ecfr.gov/api/versioner/v1/full/2026-10-15/title-14.xml?part=91&subpart=E) |
| `handbook/faa-h-8083-30a-chapter-13.pdf` | FAA-H-8083-30A, Aviation Maintenance Technician Handbook: General, chapter 13 (mechanic privileges and limitations) | [link](https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/amt_general_handbook.pdf) |
| `handbook/faa-h-8083-30a-chapter-2.pdf` | FAA-H-8083-30A, Aviation Maintenance Technician Handbook: General, chapter 2 (regulations, maintenance forms, records, and publications) | [link](https://www.faa.gov/sites/faa.gov/files/regulations_policies/handbooks_manuals/aviation/amt_general_handbook.pdf) |
| `naca/naca-tm-579.pdf` | NACA Technical Memorandum 579, Structural Details of German Light Airplanes (1930, scanned) | [link](https://ntrs.nasa.gov/api/citations/19930094837/downloads/19930094837.pdf) |
| `tcds/tcds-3a12-rev89.pdf` | Type Certificate Data Sheet 3A12, revision 89 (Textron Aviation 172 series) | [link](https://drs.faa.gov (Type Certificate Data Sheets, 3A12, revision 89)) |
